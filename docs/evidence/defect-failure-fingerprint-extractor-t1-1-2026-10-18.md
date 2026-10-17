# T1.1 失败堆栈与异常语义指纹提取器服务验收 (2026-10-18)

## 概述与交付物

T1.1（失败堆栈与异常语义指纹提取器服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v6.0.0（重大版本：智能缺陷聚类去重、根因归因与跨平台全生命周期中台）的第一阶段研发**：
1. **动态变量归一化清洗引擎 (`sanitize_dynamic_tokens`)**：
   - 内存十六进制地址脱敏（`0x*` ➔ `<HEX_ADDR>`）；
   - 标准 UUID/GUID 规整（`xxxxxxxx-xxxx-...` ➔ `<UUID>`）；
   - ISO 时间戳与日期时间脱敏（`2026-10-18 14:30:00` ➔ `<TIMESTAMP>`）；
   - 动态主机与 IP/端口规整（`192.168.1.100:8080` ➔ `<HOST:PORT>`）；
   - 动态业务前缀 ID 规整（`user_112233` ➔ `user_<ID>`）。
2. **业务代码调用帧提炼与框架杂质过滤 (`_is_business_path`)**：
   - 智能排除 `site-packages`、`pytest`、`unittest`、`asyncio` 等底层调度杂质帧；
   - 提取最深业务源文件、函数名与代码行作为 `root_cause_frame`。
3. **确定性 64 位 SHA-256 故障语义指纹生成 (`FailureFingerprintResult`)**：
   - 将异常类型、归一化报错消息、底层业务根因代码帧与端点上下文组装为确定性规范序列，计算 64 字符十六进制哈希指纹；
   - 保证同源故障无论在何时、何地、哪个用例发生，计算出的指纹完全一致，为后续海量失败去重提供坚实基础。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_defect_failure_fingerprint_extractor.py`：3 passed（动态变量归一化清洗有效性、同源不同时刻及临时地址生成完全一致的指纹、不同异常类型生成不同指纹及字典序列化）；
   - **通过率**：**3 passed in 0.30s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：1/1 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 1 source file.**。
