import logging
import re
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_MAX_HEALS_PER_RUN = 2
EXPLORATORY_TIMEOUT_MS = 2500

# 常见元素定位器失效特征特征词
_LOCATOR_FAILURE_PATTERNS = [
    re.compile(r"waiting for locator", re.IGNORECASE),
    re.compile(r"waiting for element", re.IGNORECASE),
    re.compile(r"元素不可见"),
    re.compile(r"页面中未找到文本"),
    re.compile(r"not visible", re.IGNORECASE),
    re.compile(r"Timeout \d+ms exceeded", re.IGNORECASE),
    re.compile(r"strict mode violation", re.IGNORECASE),
]


def is_locator_failure(error_message: str | None) -> bool:
    """判定异常信息是否属于元素定位器失效/漂移导致的失败。"""
    if not error_message:
        return False
    return any(pattern.search(error_message) for pattern in _LOCATOR_FAILURE_PATTERNS)


def generate_candidate_selectors(action: str, params: dict[str, Any]) -> list[str]:
    """基于启发式规则生成候选备选选择器列表。

    处理常见的前端 DOM 漂移：
    1. 动态生成后缀的 ID (如 #submit-btn_v2 -> [id^='submit-btn'])
    2. 文本按钮定位：button:has-text('...') / [role='button']:has-text('...')
    3. 表单占位符与名称：input[placeholder*='...'] / [name='...']
    4. 无障碍标识符：[aria-label*='...'] / [data-testid='...']
    """
    candidates: list[str] = []
    original_selector = str(params.get("selector", "")).strip()

    # 1. 从原选择器中提取 ID 动态特征并模糊化
    id_match = re.search(r"#([a-zA-Z0-9_\-]+)", original_selector)
    if id_match:
        raw_id = id_match.group(1)
        # 剥离随机数字/版本后缀 (如 btn_submit_123 -> btn_submit)
        stem = re.sub(r"[_\-][0-9a-fA-F]+$", "", raw_id)
        if stem and stem != raw_id:
            candidates.append(f"[id*='{stem}']")
            candidates.append(f"button[id*='{stem}']")
            candidates.append(f"input[id*='{stem}']")

    # 2. 基于文本信息的推断
    text_hint = str(params.get("text") or params.get("value") or "").strip()
    if not text_hint and "has-text" in original_selector:
        m = re.search(r"has-text\(['\"](.+?)['\"]\)", original_selector)
        if m:
            text_hint = m.group(1)

    if text_hint and len(text_hint) <= 30:
        if action in {"click", "hover"}:
            candidates.append(f"button:has-text('{text_hint}')")
            candidates.append(f"[role='button']:has-text('{text_hint}')")
            candidates.append(f"a:has-text('{text_hint}')")
            candidates.append(f"text={text_hint}")
        elif action in {"fill", "select"}:
            candidates.append(f"input[placeholder*='{text_hint}']")
            candidates.append(f"textarea[placeholder*='{text_hint}']")

    # 3. 基于 data-testid / aria-label / name / placeholder
    for attr in ("data-testid", "aria-label", "name", "placeholder"):
        val = str(params.get(attr, "")).strip()
        if val:
            candidates.append(f"[{attr}='{val}']")
            candidates.append(f"[{attr}*='{val}']")

    # 4. 去重并排除与原选择器完全一致的项
    seen: set[str] = set()
    filtered: list[str] = []
    for cand in candidates:
        if cand and cand != original_selector and cand not in seen:
            seen.add(cand)
            filtered.append(cand)

    return filtered


class RuntimeLocatorHealer:
    """运行时元素定位器自愈沙箱。

    在用例执行遭遇定位超时/找不到元素时，利用启发式规则与相似度机制生成备选 Locator，
    在配额控制（默认单用例限 2 次）内自动沙箱重试。重试成功则救活用例，标记自愈证据；
    重试失败或配额超限则安全回退原始异常。
    """

    def __init__(self, max_heals_per_run: int = DEFAULT_MAX_HEALS_PER_RUN) -> None:
        self.max_heals_per_run = max(1, max_heals_per_run)
        self._heals_count_by_run: dict[int, int] = {}

    def get_heals_count(self, run_id: int) -> int:
        return self._heals_count_by_run.get(run_id, 0)

    def reset_run(self, run_id: int) -> None:
        self._heals_count_by_run.pop(run_id, None)

    async def attempt_heal_and_retry(
        self,
        page: Any,
        action: str,
        params: dict[str, Any],
        timeout_ms: int,
        *,
        run_id: int,
        step_index: int,
        execute_step_fn: Callable[..., Any],
    ) -> dict[str, Any] | None:
        """尝试对失效步骤进行动态自愈重试。

        若成功自愈，返回附带 `healed_info` 的 step 结果；若自愈失败或配额超限返回 None。
        """
        current_heals = self.get_heals_count(run_id)
        if current_heals >= self.max_heals_per_run:
            logger.info("Run %s exceeded max runtime healing quota (%s)", run_id, self.max_heals_per_run)
            return None

        candidates = generate_candidate_selectors(action, params)
        if not candidates:
            return None

        original_selector = str(params.get("selector", ""))
        logger.info(
            "Attempting runtime self-healing for run %s step %s (original='%s', %s candidates)",
            run_id,
            step_index,
            original_selector,
            len(candidates),
        )

        retry_timeout = min(timeout_ms, EXPLORATORY_TIMEOUT_MS)

        for candidate_idx, candidate in enumerate(candidates, start=1):
            retry_params = {**params, "selector": candidate}
            try:
                result = await execute_step_fn(page, action, retry_params, retry_timeout)
            except Exception as exc:
                result = {"success": False, "error": str(exc)}

            if result and result.get("success"):
                self._heals_count_by_run[run_id] = current_heals + 1
                healed_info = {
                    "healed": True,
                    "original_selector": original_selector,
                    "healed_selector": candidate,
                    "candidate_index": candidate_idx,
                    "step_index": step_index,
                }
                existing_data = result.get("data") or {}
                result["data"] = {**existing_data, "healed_info": healed_info}
                logger.info(
                    "Runtime self-healing SUCCEEDED for run %s step %s: '%s' -> '%s'",
                    run_id,
                    step_index,
                    original_selector,
                    candidate,
                )
                return result

        logger.info("Runtime self-healing exhausted all candidates for run %s step %s", run_id, step_index)
        return None


# 全局自愈器单例
runtime_locator_healer = RuntimeLocatorHealer()
