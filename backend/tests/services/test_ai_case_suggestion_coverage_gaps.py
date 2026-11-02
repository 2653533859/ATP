"""AI 用例建议服务（app.services.ai_case.suggestion）覆盖率补测。

覆盖范围：
- 纯函数：_sanitize_json / _response_path / _suggestion_matches_response /
  _extraction_matches_response / heuristic_suggestions / _filter_existing_rules
- 主流程：suggest_assertions_and_extractions 的启发式、每日配额、LLM 成功/失败/降级分支

约定：LLM 客户端与每日配额一律 monkeypatch，不依赖真实 PG/Redis/MinIO/LLM。
"""

import asyncio
import json
from types import SimpleNamespace

from app.models.bootstrap import load_all_models
from app.schemas.ai_case import (
    AIAssertionSuggestIn,
    AIAssertionSuggestion,
    AIExtractionSuggestion,
)
from app.services.ai_case import suggestion
from app.services.ai_case.suggestion import (
    _extraction_matches_response,
    _filter_existing_rules,
    _response_path,
    _sanitize_json,
    _suggestion_matches_response,
    heuristic_suggestions,
    suggest_assertions_and_extractions,
)

load_all_models()


# ──────────── 辅助构造 ────────────


def _assertion(**overrides) -> AIAssertionSuggestion:
    fields = {"target": "body", "operator": "eq", "expected": "1", "expression": "$.value"}
    fields.update(overrides)
    return AIAssertionSuggestion(**fields)


def _extraction(**overrides) -> AIExtractionSuggestion:
    fields = {"variable": "var1", "type": "jsonpath", "expression": "$.var1"}
    fields.update(overrides)
    return AIExtractionSuggestion(**fields)


def _suggest_body(**overrides) -> AIAssertionSuggestIn:
    fields = {"method": "GET", "url": "/api/ping", "status_code": 200}
    fields.update(overrides)
    return AIAssertionSuggestIn(**fields)


def _llm_config(**overrides) -> SimpleNamespace:
    fields = {
        "enabled": True,
        "provider": "openai",
        "model_name": "gpt-test",
        "endpoint": "http://llm.local/v1",
        "default_params": {},
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


async def _allowed_quota(**_kwargs) -> bool:
    return True


# ──────────── _sanitize_json ────────────


def test_sanitize_json_passthrough_and_string_parsing():
    assert _sanitize_json(None) is None
    assert _sanitize_json(3) == 3
    assert _sanitize_json(True) is True
    assert _sanitize_json([1, 2]) == [1, 2]
    assert _sanitize_json({"a": 1}) == {"a": 1}
    # 既非基础类型也非字符串（如 tuple）直接原样返回
    assert _sanitize_json((1, 2)) == (1, 2)
    # JSON 字符串：对象与数组均解析成功
    assert _sanitize_json(' {"a": 1} ') == {"a": 1}
    assert _sanitize_json(" [1, 2] ") == [1, 2]
    # 括号包裹但非法 JSON：解析失败后原样返回
    assert _sanitize_json("{bad-json}") == "{bad-json}"
    # 仅一侧括号或普通字符串：不做解析，去空白后返回
    assert _sanitize_json("{no-close") == "{no-close"
    assert _sanitize_json("  plain  ") == "plain"


# ──────────── _response_path ────────────


def test_response_path_supported_and_rejected_expressions():
    body = {"a": {"b": 2}, "list": [{"name": "first"}]}
    assert _response_path(body, "$") == (True, body)
    # 不支持的前缀 / "$." 之后无有效片段
    assert _response_path(body, "a.b") == (False, None)
    assert _response_path(body, "$.") == (False, None)
    # 常规嵌套与数组下标
    assert _response_path(body, "$.a.b") == (True, 2)
    assert _response_path(body, "$.list[0].name") == (True, "first")
    # 下标越界 / 对非列表取下标 / 键不存在
    assert _response_path(body, "$.list[5]") == (False, None)
    assert _response_path(body, "$.a[0]") == (False, None)
    assert _response_path({"a": 1}, "$[0]") == (False, None)
    assert _response_path(body, "$.missing") == (False, None)


# ──────────── _suggestion_matches_response ────────────


def test_suggestion_matches_target_and_operator_fallbacks():
    empty = _suggest_body(status_code=None, response_body=None, response_headers=None)
    # status_code 缺失：found 为 False 直接返回
    assert _suggestion_matches_response(_assertion(target="status_code"), empty) is False
    # 不支持的目标（duration）直接返回 False
    assert _suggestion_matches_response(_assertion(target="duration", operator="lt", expected="500"), empty) is False
    # 非法 operator（绕开 pydantic 校验模拟脏数据）走末尾兜底 False
    dirty = AIAssertionSuggestion.model_construct(
        target="body", operator="xor", expected="", expression="$.a", description="dirty"
    )
    assert _suggestion_matches_response(dirty, _suggest_body(response_body={"a": 1})) is False


def test_suggestion_matches_status_code_and_header_targets():
    body = _suggest_body(
        status_code=200,
        response_headers={"X-Token": "abc", "X-Empty": ""},
    )
    assert _suggestion_matches_response(_assertion(target="status_code", expected="200", expression=""), body) is True
    assert (
        _suggestion_matches_response(
            _assertion(target="status_code", operator="ne", expected="404", expression=""), body
        )
        is True
    )
    assert _suggestion_matches_response(_assertion(target="status_code", expected="500", expression=""), body) is False
    # header：大小写不敏感；空值 exists 判定为 False
    assert (
        _suggestion_matches_response(_assertion(target="header", operator="exists", expression="x-token"), body) is True
    )
    assert _suggestion_matches_response(_assertion(target="header", expected="abc", expression="X-Token"), body) is True
    assert (
        _suggestion_matches_response(_assertion(target="header", operator="exists", expression="x-empty"), body)
        is False
    )
    assert _suggestion_matches_response(_assertion(target="header", expected="abc", expression="x-none"), body) is False


def test_suggestion_matches_scalar_operators():
    body = _suggest_body(
        response_body={"code": 0, "flag": True, "name": "alpha", "items": [1, 2], "num": 5},
    )
    # body 带表达式：eq / ne / contains
    assert _suggestion_matches_response(_assertion(expected="0", expression="$.code"), body) is True
    assert _suggestion_matches_response(_assertion(operator="ne", expected="1", expression="$.code"), body) is True
    assert _suggestion_matches_response(_assertion(operator="ne", expected="0", expression="$.code"), body) is False
    assert (
        _suggestion_matches_response(_assertion(operator="contains", expected="ph", expression="$.name"), body) is True
    )
    assert (
        _suggestion_matches_response(_assertion(operator="contains", expected="zzz", expression="$.name"), body)
        is False
    )
    # contains 的 expected 为空字符串时恒不匹配
    assert (
        _suggestion_matches_response(_assertion(operator="contains", expected="", expression="$.name"), body) is False
    )
    # 布尔值比较前转小写
    assert _suggestion_matches_response(_assertion(expected="true", expression="$.flag"), body) is True
    # 复合类型（dict/list）不参与标量比较
    assert _suggestion_matches_response(_assertion(expected="1", expression="$.items"), body) is False
    # gt / lt 数值比较及转换失败
    assert _suggestion_matches_response(_assertion(operator="gt", expected="3", expression="$.num"), body) is True
    assert _suggestion_matches_response(_assertion(operator="gt", expected="9", expression="$.num"), body) is False
    assert _suggestion_matches_response(_assertion(operator="lt", expected="9", expression="$.num"), body) is True
    assert _suggestion_matches_response(_assertion(operator="gt", expected="abc", expression="$.num"), body) is False


def test_suggestion_matches_body_without_expression_and_json_string_body():
    # 无表达式时直接比较整体响应体
    assert _suggestion_matches_response(_assertion(expected="0", expression=""), _suggest_body(response_body=0)) is True
    assert (
        _suggestion_matches_response(_assertion(expected="x", expression=""), _suggest_body(response_body=0)) is False
    )
    # 整体响应体为复合类型时不参与标量比较
    assert (
        _suggestion_matches_response(_assertion(expected="[]", expression=""), _suggest_body(response_body=[1]))
        is False
    )
    # JSON 字符串响应体走 _sanitize_json 解析
    assert (
        _suggestion_matches_response(
            _assertion(expected="1", expression="$.id"), _suggest_body(response_body='{"id": 1}')
        )
        is True
    )
    # "$" + None 响应体：found=True 但 exists 要求非空
    assert (
        _suggestion_matches_response(_assertion(operator="exists", expression="$"), _suggest_body(response_body=None))
        is False
    )


# ──────────── _extraction_matches_response ────────────


def test_extraction_matches_jsonpath_header_and_regex():
    body = _suggest_body(
        response_headers={"X-Trace": "tid-1"},
        response_body={"data": {"user_id": 42, "empty": None}},
    )
    # jsonpath：存在且非 None
    assert _extraction_matches_response(_extraction(expression="$.data.user_id"), body) is True
    # jsonpath：字段存在但值为 None / 路径不存在
    assert _extraction_matches_response(_extraction(expression="$.data.empty"), body) is False
    assert _extraction_matches_response(_extraction(expression="$.data.missing"), body) is False
    # header 提取（大小写不敏感）
    assert _extraction_matches_response(_extraction(type="header", expression="x-trace"), body) is True
    assert _extraction_matches_response(_extraction(type="header", expression="x-none"), body) is False
    # regex：命中 / 未命中 / 非法表达式 / 空响应体
    text_body = _suggest_body(response_body="order id=42 done")
    assert _extraction_matches_response(_extraction(type="regex", expression=r"id=\d+"), text_body) is True
    assert _extraction_matches_response(_extraction(type="regex", expression=r"id=\d{3}"), text_body) is False
    assert _extraction_matches_response(_extraction(type="regex", expression="[unclosed"), text_body) is False
    assert (
        _extraction_matches_response(_extraction(type="regex", expression="x"), _suggest_body(response_body=None))
        is False
    )
    # 非法 type（绕开 pydantic 校验模拟脏数据）走末尾兜底
    dirty = AIExtractionSuggestion.model_construct(variable="v", type="xml", expression="$.v", description="dirty")
    assert _extraction_matches_response(dirty, body) is False


# ──────────── heuristic_suggestions ────────────


def test_heuristic_defaults_and_status_code_normalization():
    assertions, extractions = heuristic_suggestions(None, None, None, None)
    assert extractions == []
    assert len(assertions) == 1
    assert assertions[0].target == "status_code" and assertions[0].expected == "200"
    # 越界或缺失状态码回退 200；合法状态码原样保留
    for bad in (0, 99, 700):
        assert heuristic_suggestions("GET", "/x", bad, None)[0][0].expected == "200"
    assert heuristic_suggestions("post", "/x", 201, None)[0][0].expected == "201"


def test_heuristic_business_status_and_message_fields():
    long_message = "操作成功" * 10
    body = {
        "code": True,
        "status": {"nested": 1},
        "success": False,
        "errorCode": "E500",
        "errcode": 7,
        "message": long_message,
        "msg": "   ",
        "detail": 123,
        "description": "说明文本",
    }
    assertions, extractions = heuristic_suggestions("PUT", "/api/orders", 200, body)
    by_expr = {(a.expression, a.operator): a for a in assertions}
    assert by_expr[("$.code", "eq")].expected == "true"
    assert by_expr[("$.success", "eq")].expected == "false"
    assert by_expr[("$.errorCode", "eq")].expected == "E500"
    assert by_expr[("$.errcode", "eq")].expected == "7"
    # 复合类型业务字段（status）不生成断言
    assert "$.status" not in {a.expression for a in assertions}
    # message 截取前 30 字符；空白 msg / 非字符串 detail 不生成断言
    assert by_expr[("$.message", "contains")].expected == long_message.strip()[:30]
    assert by_expr[("$.description", "contains")].expected == "说明文本"
    assert "$.msg" not in {a.expression for a in assertions}
    assert "$.detail" not in {a.expression for a in assertions}
    assert extractions == []


def test_heuristic_walk_covers_tokens_ids_lists_and_depth_limit():
    body = {
        "outer": {"token": "t-1"},
        "jwt": "",
        "ticket": None,
        "uuid": "u-1",
        "order_id": 12,
        "trade_no": None,
        "data": [{"user_id": 100}],
        "list": [],
        "records": [1, 2],
        "rows": [{"tradeNo": "TN-1"}],
        "other": [1],
        "a": {"b": {"c": {"d": {"token": "too-deep"}}}},
    }
    assertions, extractions = heuristic_suggestions("GET", "/x", 200, body)
    expressions = {a.expression for a in assertions}
    # token / id 类字段产生提取与存在断言
    assert "$.outer.token" in expressions
    assert "$.uuid" in expressions
    assert "$.order_id" in expressions
    # 空串 / None 值不产生规则
    assert "$.jwt" not in expressions and "$.ticket" not in expressions and "$.trade_no" not in expressions
    # 列表字段断言与首元素递归
    assert "$.data" in expressions
    assert "$.data[0].user_id" in expressions
    assert "$.rows[0].tradeNo" in expressions
    # 空列表 / 首元素非 dict 的列表仍生成存在断言但不递归
    assert "$.list" in expressions and "$.records" in expressions
    # 非白名单列表键不生成断言
    assert "$.other" not in expressions
    # 超过递归深度（depth > 4）后不再深入
    assert "$.a.b.c.d.token" not in expressions
    assert all("too-deep" not in e.expression for e in extractions)
    assert [e.variable for e in extractions] == ["token", "uuid", "order_id", "user_id", "tradeNo"]


def test_heuristic_deduplicates_assertions_with_aliased_paths():
    # 嵌套 a.b 与字面键 "a.b" 生成相同的存在断言表达式：按 (target, expression, operator) 去重
    body = {"a": {"b": {"token": "x"}}, "a.b": {"token": "y"}}
    assertions, extractions = heuristic_suggestions("GET", "/x", 200, body)
    aliased = [a for a in assertions if a.expression == "$.a.b.token"]
    assert len(aliased) == 1
    # 同名变量同样只保留首个提取
    assert len(extractions) == 1 and extractions[0].variable == "token"


def test_heuristic_deduplicates_extraction_variables():
    body = {"token": "top", "data": {"token": "nested", "list": [{"token": "deep"}]}}
    assertions, extractions = heuristic_suggestions("GET", "/x", 200, body)
    # 同名变量只保留首个提取
    assert [e.variable for e in extractions] == ["token"]
    assert [e.expression for e in extractions] == ["$.token"]
    # 不同路径的存在断言仍各自保留
    assert any(a.expression == "$.data.token" for a in assertions)
    assert any(a.expression == "$.data.list[0].token" for a in assertions)


def test_heuristic_list_body_and_json_string_body():
    assertions, _ = heuristic_suggestions("GET", "/x", 200, [{"id": 1}])
    assert any(a.expression == "$[0]" and a.operator == "exists" for a in assertions)
    # 空列表 / 首元素非 dict / 非 dict 列表体均不产生 $[0]
    for body in ([], [1, 2], "plain text", 42):
        out, _ = heuristic_suggestions("GET", "/x", 200, body)
        assert all(a.expression != "$[0]" for a in out)
    # JSON 字符串响应体解析后复用 dict 规则
    out, _ = heuristic_suggestions("GET", "/x", 200, '{"code": 0, "token": "abc"}')
    assert any(a.expression == "$.code" for a in out)


# ──────────── _filter_existing_rules ────────────


def test_filter_existing_rules_early_return_when_no_existing():
    a = _assertion()
    e = _extraction()
    out_a, out_e = _filter_existing_rules([a], [e], None, None)
    assert out_a == [a] and out_e == [e]
    out_a, out_e = _filter_existing_rules([a], [e], [], [])
    assert out_a == [a] and out_e == [e]


def test_filter_existing_rules_assertion_dedup_variants():
    sc = _assertion(target="status_code", expected="200", expression="")
    body_eq = _assertion(expected="1", expression="$.code")
    # 命中去重：非 dict 条目跳过；status_code 期望一致；property/value 回退键
    existing = [
        "skip-me",
        {"target": "status_code", "expected": "200"},
        {"target": "body", "property": "$.code", "value": "1"},
    ]
    kept, _ = _filter_existing_rules([sc, body_eq], [], existing, None)
    assert kept == []
    # raw_expected 为 None（缺 expected/value 键）时同样视为重复
    kept, _ = _filter_existing_rules([sc], [], [{"target": "status_code"}], None)
    assert kept == []
    kept, _ = _filter_existing_rules([body_eq], [], [{"target": "body", "expression": "$.code"}], None)
    assert kept == []
    # 期望值不同 / 表达式不同 / target 缺省为 body 时不做去重
    kept, _ = _filter_existing_rules(
        [sc, body_eq],
        [],
        [
            {"target": "status_code", "expected": "404"},
            {"expression": "$.code", "expected": "2"},
            {"expected": True, "expression": "$.other"},
        ],
        None,
    )
    assert kept == [sc, body_eq]


def test_filter_existing_rules_extraction_dedup_variants():
    keep = _extraction(variable="keep", expression="$.keep")
    token = _extraction(variable="token", expression="$.data.token")
    # 非 dict 条目跳过；variable 缺失时回退 name；两者皆缺视为空变量名
    existing = ["skip-me", {"variable": "token"}, {"name": "other"}, {}]
    kept_a, kept_e = _filter_existing_rules([], [keep, token], None, existing)
    assert kept_a == []
    assert [e.variable for e in kept_e] == ["keep"]


# ──────────── suggest_assertions_and_extractions ────────────


def test_suggest_without_config_or_disabled_stays_heuristic(monkeypatch):
    async def fail_llm(_request):
        raise AssertionError("config 未启用时不应调用 LLM")

    monkeypatch.setattr(suggestion, "call_llm", fail_llm)
    body = _suggest_body(response_body={"code": 0})
    out_none = asyncio.run(suggest_assertions_and_extractions(body, None, ""))
    out_disabled = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(enabled=False), ""))
    for out in (out_none, out_disabled):
        assert out.source == "heuristic"
        assert any(a.target == "status_code" for a in out.assertions)


def test_suggest_falls_back_when_daily_limit_exceeded(monkeypatch):
    async def denied(**_kwargs):
        return False

    async def fail_llm(_request):
        raise AssertionError("配额耗尽时不应调用 LLM")

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", denied)
    monkeypatch.setattr(suggestion, "call_llm", fail_llm)
    body = _suggest_body(response_body={"code": 0})
    out = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(), "k"))
    assert out.source == "heuristic"


def test_suggest_llm_happy_path_filters_and_redacts_prompt(monkeypatch):
    captured = {}

    async def fake_llm(request):
        captured["request"] = request
        return SimpleNamespace(
            text=json.dumps(
                {
                    "assertions": [
                        {"target": "status_code", "operator": "eq", "expected": "200", "expression": ""},
                        {"target": "body", "operator": "eq", "expression": "$.code", "expected": "0"},
                        # 响应中不存在：应被过滤
                        {"target": "body", "operator": "eq", "expression": "$.nope", "expected": "1"},
                        # 缺 operator：应被跳过
                        {"target": "body", "description": "invalid"},
                    ],
                    "extractions": [
                        {"variable": "token", "type": "jsonpath", "expression": "$.token"},
                        "not-a-dict",
                        # 缺 variable：应被跳过
                        {"type": "jsonpath", "expression": "$.x"},
                    ],
                },
                ensure_ascii=False,
            )
        )

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", _allowed_quota)
    monkeypatch.setattr(suggestion, "call_llm", fake_llm)
    config = _llm_config(default_params={"temperature": 0.7, "daily_limit": 0})
    body = _suggest_body(
        url="/api/orders?token=mysecret",
        response_body={"code": 0, "token": "s3cr3t", "phone": "13800138000"},
    )
    out = asyncio.run(suggest_assertions_and_extractions(body, config, "secret-key"))

    assert out.source == "llm"
    assert [(a.target, a.expression) for a in out.assertions] == [("status_code", ""), ("body", "$.code")]
    assert [(e.variable, e.expression) for e in out.extractions] == [("token", "$.token")]
    request = captured["request"]
    assert request.provider == "openai" and request.model_name == "gpt-test"
    assert request.endpoint == "http://llm.local/v1" and request.api_key == "secret-key"
    assert request.timeout_seconds == 30.0 and request.system_prompt
    # provider 额外参数经 llm_extra_params 过滤后透传
    assert request.extra_params == {"temperature": 0.7}
    # prompt 中 URL / 响应体敏感信息已脱敏
    assert "mysecret" not in request.prompt
    assert "s3cr3t" not in request.prompt
    assert "13800138000" not in request.prompt


def test_suggest_llm_markdown_fence_and_status_code_retention(monkeypatch):
    async def fake_llm(_request):
        fenced = (
            "```json\n"
            '{"assertions": [{"target": "body", "operator": "eq", "expression": "$.code", "expected": "0"}], '
            '"extractions": []}\n'
            "```"
        )
        return SimpleNamespace(text=fenced)

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", _allowed_quota)
    monkeypatch.setattr(suggestion, "call_llm", fake_llm)
    body = _suggest_body(response_body={"code": 0, "token": "t-1"})
    out = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(), ""))

    assert out.source == "llm"
    # LLM 未给 status_code 断言时保留启发式状态码断言
    assert out.assertions[0].target == "status_code" and out.assertions[0].expected == "200"
    assert any(a.expression == "$.code" for a in out.assertions)
    # LLM extractions 为空时回退启发式提取
    assert [e.variable for e in out.extractions] == ["token"]


def test_suggest_llm_empty_payload_falls_back_to_final_return(monkeypatch):
    async def fake_llm(_request):
        return SimpleNamespace(text='{"assertions": [], "extractions": []}')

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", _allowed_quota)
    monkeypatch.setattr(suggestion, "call_llm", fake_llm)
    body = _suggest_body(response_body={"code": 0})
    out = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(), ""))
    assert out.source == "heuristic"
    assert any(a.target == "status_code" for a in out.assertions)


def test_suggest_llm_non_dict_json_falls_back(monkeypatch):
    async def fake_llm(_request):
        return SimpleNamespace(text="[1, 2, 3]")

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", _allowed_quota)
    monkeypatch.setattr(suggestion, "call_llm", fake_llm)
    body = _suggest_body(response_body={"code": 0})
    out = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(), ""))
    assert out.source == "heuristic"


def test_suggest_llm_invalid_json_falls_back(monkeypatch):
    async def fake_llm(_request):
        return SimpleNamespace(text="这不是 JSON")

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", _allowed_quota)
    monkeypatch.setattr(suggestion, "call_llm", fake_llm)
    body = _suggest_body(response_body={"code": 0})
    out = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(), ""))
    assert out.source == "heuristic"


def test_suggest_llm_exception_falls_back(monkeypatch):
    async def boom(_request):
        raise RuntimeError("LLM 不可用")

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", _allowed_quota)
    monkeypatch.setattr(suggestion, "call_llm", boom)
    body = _suggest_body(response_body={"code": 0})
    out = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(), ""))
    assert out.source == "heuristic"


def test_suggest_llm_with_none_body_uses_placeholder(monkeypatch):
    captured = {}

    async def fake_llm(request):
        captured["request"] = request
        return SimpleNamespace(
            text='{"assertions": [{"target": "status_code", "operator": "eq", "expected": "200"}], "extractions": []}'
        )

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", _allowed_quota)
    monkeypatch.setattr(suggestion, "call_llm", fake_llm)
    body = _suggest_body(status_code=200, response_body=None)
    out = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(), ""))
    assert out.source == "llm"
    assert "（无响应体）" in captured["request"].prompt


def test_suggest_llm_with_text_body_masks_prompt(monkeypatch):
    captured = {}

    async def fake_llm(request):
        captured["request"] = request
        return SimpleNamespace(text='{"assertions": [], "extractions": []}')

    monkeypatch.setattr(suggestion, "check_and_incr_daily_limit", _allowed_quota)
    monkeypatch.setattr(suggestion, "call_llm", fake_llm)
    body = _suggest_body(response_body="plain body 13800138000")
    out = asyncio.run(suggest_assertions_and_extractions(body, _llm_config(), ""))
    assert out.source == "heuristic"
    assert "plain body" in captured["request"].prompt
    assert "13800138000" not in captured["request"].prompt
