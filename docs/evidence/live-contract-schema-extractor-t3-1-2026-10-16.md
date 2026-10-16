# T3.1 生产流量 OpenAPI/Protobuf 契约动态逆向提取推导器验收 (2026-10-16)

## 概述与结论

T3.1（生产流量 OpenAPI/Protobuf 契约动态逆向提取推导器）已完成全量交付与验证，正式开启 **ATP v3.8.0 Phase 3（实时接口契约动态漂移逆向推导与 Breaking 变更阻断卫士）**：
1. **服务层落地 (`backend/app/services/live_contract_schema_extractor.py`)**：
   - 建立单值类型与语义格式推断算法（`infer_type_and_format`）：支持 `integer` (int32/int64)、`number` (double)、`boolean`、`string` 及 `uuid` / `date-time` / `email` 格式识别；
   - 建立多样本自适应 Schema 递归归纳引擎 (`infer_json_schema_from_samples`)：
     - 若字段在 100% 样本中出现自动打标为 `required` 必填项；
     - 自动检测数值类型提升（如同时存在 int 与 float 则安全归纳为 `number`）；
     - 自动推导枚举候选值（样本数 ≥3 且独立字符串取值在 2~5 之间时生成 `enum: [...]`）；
     - 递归深度解析嵌套对象 `properties` 与列表元素 `items`；
   - 建立 Protobuf 3 IDL 自动转译引擎 (`generate_protobuf_from_schema`)：将导出的 JSON Schema 转换为标准的 `syntax = "proto3"; message { ... }` 字段定义；
   - 提供 `extract_contract_from_traffic` 与 `batch_extract_contracts_from_traffic`：自动按状态码分离响应 Schema、提取 Query/Header 参数规范与生成完整 `ExtractedContract` 实体。
2. **REST API 端点落地 (`backend/app/api/v1/live_contract_guard.py` & `backend/app/api/v1/router.py`)**：
   - `POST /api/v1/contract-guard/extract/single`：从单接口的多条调用样本中逆向提取推导 OpenAPI 3.0 与 Protobuf Schema（需工程师权限）；
   - `POST /api/v1/contract-guard/extract/batch`：批量对海量生产流量执行按接口聚合逆向推导契约；
   - `GET /api/v1/contract-guard/extract/contracts`：查询历史已逆向提取的契约列表；
   - `GET /api/v1/contract-guard/extract/contracts/by-endpoint`：按端点路径获取最新生效契约详情；
   - `GET /api/v1/contract-guard/extract/contracts/{contract_id}`：获取指定契约详情；
   - `DELETE /api/v1/contract-guard/extract/contracts`：清空已提取契约缓存。

## 质量与测试门禁验证

1. **后端单元测试 (`pytest`)**：
   - `backend/tests/services/test_live_contract_schema_extractor.py`：**5 passed in 0.26s**；
   - 涵盖基础类型与格式识别、多样本必填/枚举/数值归一化推导、Protobuf 3 语法生成、响应码分类与批量契约提取。
2. **单测独立运行验证**：
   - `scripts/pytest-standalone-sweep.py`：**1/1 passed standalone (100%)**。
3. **代码规范与格式化**：
   - `ruff check`：**All checks passed**；
   - `ruff format --check`：**All checks passed**。
4. **静态强类型检查**：
   - `mypy`：**Success: no issues found in 2 source files**。
