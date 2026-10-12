# N3.1 / N3.2 / N3.3 SQLite 升级、单机备份校验与便携包交付证据（2026-10-12）

## 概述与结论

N3.1、N3.2、N3.3 已完成机制建设与定向自动化回归验证：
1. **N3.1 SQLite 新旧库升级与版本 12 迁移**：
   - 当前版本定格为 `CURRENT_LOCAL_SCHEMA_VERSION = 12`；
   - 补齐从版本 11 升级至版本 12 清理废弃 `local_group_cancellations` 表的迁移逻辑；
   - 覆盖全新空库、历史原型库、版本 1 至版本 12 连续升级及重复启动幂等性保护，超前版本与破损库明确拒绝。
2. **N3.2 完整备份清单、校验与异目录恢复**：
   - 备份包含配置（`local-lite.env`）、数据文件（`atp.sqlite3`）与对象存储文件（`objects/`、`object-metadata/`）；
   - 生成格式规范的 `manifest.json` 与逐文件 SHA-256 哈希列表；
   - 严格篡改防护：任何校验和不匹配（`Backup checksum mismatch`）、文件缺失（`Backup file missing`）、未登记文件（`Unlisted backup file`）及路径穿越（`invalid path`）全部明确拒绝；
   - 异目录/异机恢复：解包后能够完整回读配置，恢复后的 SQLite 数据库正常执行 `ensure_local_schema` 并通过全表结构校验。
3. **N3.3 Windows 绿色单机便携包打包与分发验证**：
   - 运维脚本 `scripts/package-windows-standalone-bundle.ps1` 能够自动组装独立的 Windows 运行包；
   - 打包产物包含一键启动与停止脚本（`start-atp.bat`、`stop-atp.bat`、`status-atp.bat`）、使用文档、预构建前端静态资源、后端核心与配置；
   - 自动生成 ZIP 归档及同名 `.sha256` 侧车校验和，经 `zipfile` 验证 617 个关键文件完整无损。

## 测试与代码清单

- `backend/app/core/local_schema.py`：版本 12 迁移定义。
- `backend/tests/services/test_local_schema.py`：8 项 SQLite 版本升级与迁移回归通过（8 passed in 13.48s）。
- `backend/tests/services/test_n3_backup_restore.py`：6 项备份清单结构、篡改拒绝、文件缺失拒绝、未登记文件拒绝、路径穿越拦截及异目录恢复数据库重连验证通过（6 passed in 12.85s）。
- `scripts/package-windows-standalone-bundle.ps1`：单机便携打包测试通过。

## 质量门禁

1. **定向测试**：14 项（8 + 6）全部通过。
2. **静态质量**：`ruff check`、`ruff format`、`mypy` 188 个源文件全部通过。
