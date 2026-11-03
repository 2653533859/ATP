# Windows 后端 PyInstaller 打包

`backend/frozen_entry.py` 是 Windows 本地模式专用入口，只允许绑定回环地址，并要求 `ATP_LOCAL_MODE=true`。`scripts/build-windows-backend.ps1` 使用 PyInstaller one-folder 模式将 FastAPI 后端与 Python 依赖打到 `.local-run/pyinstaller/dist/atp-backend/`。`scripts/windows-standalone.ps1` 在安装目录的 `backend/atp-backend.exe` 存在时优先运行它；开发环境继续使用 `backend/.venv/Scripts/python.exe`。直接双击 `atp-backend.exe` 不是启动桌面界面的方式；新版会弹出“完整解压 ZIP 并运行根目录 `start-atp.bat`”的提示。

构建机需有 Python 3.12、后端依赖和 `frontend/node_modules`。先运行：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-build.txt
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build-windows-backend.ps1
py scripts\verify_windows_bundled_backend.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\package-windows-standalone-bundle.ps1 -FrozenBackend -SkipFrozenBackendBuild -OutputPath .local-run\atp-windows-bundled-backend.zip
```

打包脚本默认重新构建本地模式前端；只有在当前 `frontend/dist` 已由 `VITE_ATP_LOCAL_MODE=true` 构建时，才可加 `-SkipFrontendBuild`。ZIP 中 `backend/atp-backend.exe` 必须与 `backend/_internal/` 保持同级，`frontend/dist/`、`scripts/` 位于安装目录根部。首次启动生成私有 profile 并选择非 C 盘数据目录；ZIP 不包含本机 profile、数据库、签名密钥或云端 API Key。源码便携 ZIP 模式仍可使用，但需要用户自行安装 Python。

2026-10-27 实测：从 95.27 MiB 的 ZIP 解压后，独立数据目录中的 exe 返回 `health=200`、`runtime=local`、本地页面 200、管理员登录 200；解压包的 `windows-standalone.ps1 -Action up -Frontend static` 确认启动的进程为 `atp-backend.exe`，页面和健康接口均返回 200。直接打开 exe 的闪退已改为启动提示。用户尝试便携包时，原开发版仍占用 `8001`；停止原开发版后，用户解压目录中的便携版已真实启动并通过登录验证，数据目录为新建的 `E:\ATP_resources`，未自动接管 `D:\ATP_resources` 或原 `.local-data`。`atp-windows-bundled-backend-20261027-v3.zip` 修复了启动 BAT 乱码并在启动成功后打开浏览器；1982 个文件通过清单哈希校验，未包含本机私有 profile。

此阶段完成的是自带 Python 运行时和依赖的便携后端；原生桌面窗口、MSI 安装程序、升级和全新电脑验收仍属于 D7 后续工作。设备执行、ADB 与大文件场景尚未用该 ZIP 在新电脑上验证。

2026-11-03 重建（本地迁移修复）：D5 现场验收发现既有用户升级后本机后端拒启，缺失表有两处——`remote_node_grants`（D5 新增模型未同步本地迁移），以及 `api_schema_assets` / `api_contract_assets`（只随 Alembic 建到云端，`load_all_models()` 漏导入这两个模型模块，因此脚本建的本地库只有 73 张表）。`backend/app/core/local_schema.py` 版本推进到 17 并新增 17 号显式迁移，`load_all_models()` 补齐导入。重建产物 `atp-windows-bundled-backend-20261103-v5.zip`（110,539,032 字节，SHA-256 `a0bcec3302162be82469d240f3c4de12c9aff5b71ee5ed30f5ef9d3eeb6d40f9`，2657 个文件），包内 `backend/atp-backend.exe` 28,580,469 字节（SHA-256 `a4b6695f26204b84244702b0c3f874e43a53c99d9a5e61317621d948cf542923`），构建步骤与上文相同；同日的 v4 包（`3a8bc421…`）因该缺陷未交付，由 v5 取代。验收：空库首启为 v17 / 76 张表；现场库副本（v15、73 张表、6 个项目 / 148 次运行）就地升级到 v17 / 76 张表且数据零改动；被修复前构建卡在 v16 的库同样恢复到 v17 / 76 张表；三阶段的 `/health`、本地页面与 `/login` 均为 200，停止后 8001 无监听。修复前该现场库副本报 `RuntimeError: local SQLite schema is missing table api_schema_assets`。桌面 MSI 的 File 表只有 `atp-desktop.exe`、不含 Python 后端，本次未重打。
