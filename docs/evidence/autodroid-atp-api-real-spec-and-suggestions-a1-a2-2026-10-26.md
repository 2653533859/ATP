# ATP AutoDroid 对照：A1/A2 接口规格影响预览与调试建议可靠性验收报告（2026-10-26）

## 概述与结论

2026-10-26，在实际业务工程样例与双版本 OpenAPI 契约下，正式完成了 **A1 接口规格影响预览** 与 **A2 接口调试建议可靠性** 的全流程业务逻辑闭环验收：
1. **A1 规格影响预览与来源指纹追溯**：
   * 基于两个正式版本 OpenAPI 规范（v1.0 与 v2.0）完成结构化比对；
   * 正确识别出新增端点（`GET /api/v1/users/{id}/profile`，1项）、变更端点（`POST /api/v1/orders` 必填参数变化，1项）及移除废弃端点（`GET /api/v1/products`，1项）；
   * 通过来源用例请求指纹 `case_request_fingerprint` 与场景局部步骤指纹，精准区分了三种受影响场景步骤类型：
     * **来源请求变更**（来源与场景请求一致）；
     * **场景局部覆盖**（检测到场景内独立修改了 Body / 参数）；
     * **未记录来源用例**（按 URL 粗匹配并提示人工核对）。
   * 预览全程为只读模式，未篡改业务数据库。
2. **A2 调试建议可靠性与零二次写**：
   * **只读 GET 响应**：智能推荐 HTTP 状态码、业务状态码（`$.code`）、提示语（`$.message`）断言及业务 ID 变量提取；
   * **已有规则去重**：已存在的 `status_code: 200` 规则被自动去重拦截，不重复推荐；
   * **成立性校验**：所有输出建议均通过 `_suggestion_matches_response` 校验并在当前真实响应上严格成立；
   * **写入 POST 异常响应**：针对 400 失败响应成功生成 `$.errorCode` 等校验规则；
   * **建议失效防护**：旧响应生成的断言在新响应上下文下被 `_suggestion_matches_response` 严格拦截并失效；
   * **零二次业务写请求**：建议应用完全消费本次调试缓存，杜绝重复发送二次写请求对业务环境造成数据污染；
   * **脱敏边界**：接口调试中的手机号与邮箱均通过 `mask_pii_text` 进行掩码，防止敏感信息泄漏。

---

## 一、 A1 真实两版规格比对与场景影响实测

### 1. 比对输入规格与既用例设计
* **规格 v1.0**：定义 `/api/v1/orders`（GET/POST）、`/api/v1/products`（GET）；
* **规格 v2.0**：
  * 新增 `GET /api/v1/users/{id}/profile`；
  * 变更 `POST /api/v1/orders`（增加必填 Query 参数 `order_type` 及必填 Body 字段 `payment_method`）；
  * 移除 `GET /api/v1/products`；
* **关联业务场景**：场景包含 3 个步骤，覆盖基准指纹、局部覆盖及粗匹配。

### 2. 实测统计与比对结果
```text
[A1.2] OpenAPI 规格比对统计:
       - 新增端点 (Additions): 1
       - 变更端点 (Modifications): 1
       - 废弃/移除端点 (Deprecations): 1
       - 补丁草稿数 (Draft Patches): 1
       - 受影响场景步骤数 (Scenario Impacts): 3
```

### 3. 场景影响与指纹审查结论
```text
[A1.3] 场景步骤影响与来源指纹审查结论:
       * [电商下单主链路业务场景] 步骤 0: 步骤1-基准下单 -> POST /api/v1/orders
         审查判定: "来源与场景请求一致，请检查规格变更"
       * [电商下单主链路业务场景] 步骤 1: 步骤2-带优惠码下单 (局部覆盖) -> POST /api/v1/orders
         审查判定: "场景步骤存在局部覆盖"
       * [电商下单主链路业务场景] 步骤 2: 步骤3-旧商品查询 (按地址匹配) -> GET /api/v1/products
         审查判定: "按请求地址匹配；未记录来源用例，请人工确认"
```

---

## 二、 A2 调试建议可靠性实测数据

### 1. 只读 GET 调试建议生成（含 PII 脱敏数据）
* **调试响应**：
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "account_id": 9527,
      "username": "vip_user",
      "phone": "13800138000",
      "email": "vip_user@company.com",
      "role": "editor",
      "is_vip": true
    }
  }
  ```
* **推荐断言**：
  * `[body] $.code eq '0'`（业务响应码为预期值）；
  * `[body] $.message contains 'success'`（校验返回提示文本包含关键信息）；
  * `[body] $.data.account_id exists ''`（校验关键业务标识存在）；
* **推荐提取**：
  * `[account_id] from $.data.account_id`（提取业务标识供后续依赖）；
* **去重核验**：请求入参中指定 `existing_assertions: [{"target": "status_code", "operator": "eq", "expected": "200"}]`，实测推荐列表中 `status_code: 200` 被自动去重过滤。

### 2. 写入 POST 错误响应与建议失效防护
* **错误响应**：
  ```json
  {
    "errorCode": "ERR_INSUFFICIENT_FUNDS",
    "message": "支付失败：用户 13911112222 余额不足，请充值后重试",
    "timestamp": 1729900000
  }
  ```
* **推荐断言**：状态码 `400`、`[body] $.errorCode eq 'ERR_INSUFFICIENT_FUNDS'`；
* **建议失效拦截**：针对旧 200 响应产生的 `$.code == 0` 断言，在新 400 响应上运行 `_suggestion_matches_response` 立即返回 `False`，有效阻断过期建议被错误采纳。

### 3. 零二次业务写请求确认
* 建议推荐与规则采纳纯本地计算，不发起额外 HTTP 网络请求，彻底杜绝调试对线上业务环境产生二次写入副作用。
