# D7 Windows 桌面端 MSI 构建与本机安装/卸载验收（2026-11-02）

## 结论

D7 MSI 安装包已完成构建，并在本机完成静默安装、启动冒烟、静默卸载与残留清零验收；安装与卸载退出码均为 0，卸载后零残留。2026-11-03 补充完成升级安装验收：0.9.0 → 1.0.0 静默升级返回 0，旧版本产品代码被移除、卸载表仅保留一条 1.0.0 条目、安装目录内可执行文件被替换为 1.0.0 包内负载，升级后启动冒烟通过，随后卸载零残留。MSI 未做代码签名；全新电脑验收未执行，仍为外部阻塞，暂不能称为可用于分发的正式安装包。

## 构建

- 构建方式：`build_msi.bat` 加载 VS 2022 Build Tools 的 `VsDevCmd.bat -arch=amd64 -host_arch=amd64`，在 `frontend/` 执行 `npx --yes "@tauri-apps/cli@^2" build --bundles msi`。
- 构建修复：Tauri v2 的 WiX 配置键位于 `bundle.windows.wix`（直接置于 `bundle.wix` 会被 schema 拒绝：`Additional properties are not allowed ('wix' was unexpected)`）；中文 `productName` 必须配置 `"windows": { "wix": { "language": "zh-CN" } }`（代码页 936），否则 `light.exe` 报 `LGHT0311`（代码页 1252 无法容纳中文字符）。
- 链路与耗时：npm 前端构建 2.23s → `cargo build --release` 24.02s（产出 `atp-desktop.exe`）→ candle 编译 `main.wxs` → light 产出 MSI。
- 产物：`frontend/src-tauri/target/release/bundle/msi/ATP 自动化测试平台_1.0.0_x64_zh-CN.msi`，5,124,096 字节（4.89 MiB）。
- SHA-256（2026-11-02 复核）：`5A4C55F6639CE54FFC3DE1B0E4EA4282F9C14073C26A7BC32BBEA7180DA15DA7`。
- 产物位于 gitignored 的 `frontend/src-tauri/target/`，不入库；可按下方命令重建。
- 签名：`tauri.conf.json` 无签名证书/命令配置，构建日志无 `signtool` 调用，MSI 未做 Authenticode 签名；本机 PowerShell 环境的 `Get-AuthenticodeSignature` 模块不可用，未能独立复核签名状态。未签名安装包在用户机器上会触发 SmartScreen/未知发布者提示。

## 静默安装验收（19:26 构建，19:27 安装）

- 命令：`msiexec /i "<MSI>" /qn /norestart /l*v msi_install.log`；退出码 0；verbose 日志以 `MainEngineThread is returning 0` 结束（service 与 client 两侧）。
- MSI 属性：`ALLUSERS=1`（每机器安装）、`ProductCode={1B20E50F-79EB-4B7F-8DBD-BA86FCB467CC}`、`ProductVersion=1.0.0`。
- 注册表登记显示名称 `ATP 自动化测试平台`，安装位置 `C:\Program Files\ATP 自动化测试平台\`（包含 `atp-desktop.exe`）。
- 冒烟：启动已安装的 `atp-desktop.exe`，进程存活 4 秒后确认运行正常，随后结束进程。

## 静默卸载验收（19:28）

- 命令：`msiexec /x {1B20E50F-79EB-4B7F-8DBD-BA86FCB467CC} /qn /norestart /l*v msi_uninstall.log`；退出码 0；日志以 `MainEngineThread is returning 0` 结束。
- 残留核验（2026-11-02 当日复测）：HKLM/HKCU 三处 Uninstall 注册表位置中 `ATP` 相关键 0 个；`C:\Program Files` 下 ATP 相关目录 0 个；`atp-desktop` 进程 0 个。

## 升级安装验收（2026-11-03）

- 产物与身份（用 Windows Installer COM 读取 MSI 的 Property 表）：旧版 `ATP 自动化测试平台_0.9.0_x64_zh-CN.msi`，5,124,096 字节，SHA-256 `208EE233BD835B45153BC5F88E42DECCEFB939970659BC1B63A445AC43E07FF3`，ProductVersion 0.9.0，ProductCode `{E567CBD4-D5DA-4411-8F06-7D4821E48CC6}`；新版 `ATP 自动化测试平台_1.0.0_x64_zh-CN.msi`，5,124,096 字节，SHA-256 `5A4C55F6639CE54FFC3DE1B0E4EA4282F9C14073C26A7BC32BBEA7180DA15DA7`，ProductVersion 1.0.0，ProductCode `{1B20E50F-79EB-4B7F-8DBD-BA86FCB467CC}`。两者 UpgradeCode 相同 `{DC72F384-C6C7-54AB-AC13-23DCF5CFFD51}`，`ALLUSERS=1`、ProductLanguage 2052（zh-CN）、Manufacturer `atp`，即 MajorUpgrade 依赖的稳定 UpgradeCode 与随版本派生的 ProductCode。
- 步骤 1 安装旧版：`msiexec /i <0.9.0 MSI> /qn /norestart /l*v`，verbose 日志以 `MainEngineThread is returning 0` 结束；卸载表 ATP 条目 1 条、版本 0.9.0、键为旧 ProductCode；`C:\Program Files\ATP 自动化测试平台` 存在且含 `atp-desktop.exe`。
- 步骤 2 升级到 1.0.0：同一包名同目录下执行 `msiexec /i <1.0.0 MSI> /qn /norestart /l*v`。verbose 日志先出现旧产品的移除会话（`REMOVE=ALL` 且 `UPGRADINGPRODUCTCODE={1B20E50F-79EB-4B7F-8DBD-BA86FCB467CC}`，旧 ProductCode 的组件被逐个注销），随后以新 ProductCode 写入安装数据库，日志同样以 `MainEngineThread is returning 0` 结束。
- 步骤 2 结果：卸载表仍为 1 条、版本 1.0.0、键为新 ProductCode，旧 ProductCode 键已不存在（未出现新旧版本共存）；安装目录中 `atp-desktop.exe` 的时间戳由 2026-11-03 08:54:24（0.9.0 包内负载）变为 2026-11-02 19:26:24（1.0.0 包内负载），证明文件被替换而非并存。
- 步骤 3 升级后冒烟：启动已安装的 `atp-desktop.exe`，进程存活 5 秒未退出，结束进程后无残留进程。
- 步骤 4 卸载 1.0.0：按新 ProductCode 执行 `msiexec /x {1B20E50F-79EB-4B7F-8DBD-BA86FCB467CC} /qn /norestart /l*v`，返回 0；卸载后 ATP 相关卸载表条目 0 条、新旧 ProductCode 键均不存在、`C:\Program Files` 下 ATP 目录 0 个、`atp-desktop` 进程 0 个。
- 采集方法：注册表与文件系统状态在 `msiexec` 返回后才落定，直接快照会得到中间态；本轮每步都在轮询到目标卸载表状态后才采集证据，退出码以 verbose 日志的 `MainEngineThread is returning 0` 为准（该调用形态下 `$LASTEXITCODE` 为空，不可用）。
- 旧版产物来源：与 1.0.0 使用同一构建命令（`build_msi.bat` 加载 VS 2022 Build Tools 后 `tauri build --bundles msi`），只是构建时版本号临时置为 0.9.0；验收后仓库 `frontend/src-tauri/tauri.conf.json` 与 `frontend/src-tauri/Cargo.toml` 版本均为 1.0.0，`git status` 无版本相关改动。

## 未覆盖边界

- 升级安装已于 2026-11-03 补充验收（见上一节）；但仍只覆盖同一台机器、同一 Windows 版本的升级，未覆盖跨机器迁移或跨 Windows 版本升级。
- 全新电脑验收未执行：本轮在同机（Windows 11、自带 Edge WebView2、具备构建环境）完成。生成产物中的证据显示采用 WebView2 下载引导模式：`frontend/src-tauri/target/release/wix/x64/main.wxs`（2026-11-03 构建）自定义动作 `DownloadAndInvokeBootstrapper` 在条件 `NOT(REMOVE OR INSTALLED_WEBVIEW2_VERSION)` 下从 `https://go.microsoft.com/fwlink/p/?LinkId=2124703` 下载 `MicrosoftEdgeWebview2Setup.exe` 并静默安装。即缺失 WebView2 运行时的机器需要能访问该地址；离线环境的全新机器无法获得运行时，这一点是明确的交付限制。
- MSI 未签名；未做 SmartScreen 信誉或企业分发验证。
- 本轮只验证安装包链路与宿主窗口启动；D7 桌面端与本地后端/便携包的联合业务流此前见 D0–D6 证据，本轮未重复执行。

## 复现命令

```bat
:: 构建（需 VS Build Tools + Node）
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=amd64 -host_arch=amd64
cd /d E:\csh\MyProject\ATP\frontend
npx --yes "@tauri-apps/cli@^2" build --bundles msi

:: 安装 / 卸载（管理员）
msiexec /i "E:\csh\MyProject\ATP\frontend\src-tauri\target\release\bundle\msi\ATP 自动化测试平台_1.0.0_x64_zh-CN.msi" /qn /norestart /l*v msi_install.log
msiexec /x {1B20E50F-79EB-4B7F-8DBD-BA86FCB467CC} /qn /norestart /l*v msi_uninstall.log
```

升级验收命令（2026-11-03）：

```bat
msiexec /i "<0.9.0 MSI>" /qn /norestart /l*v msi_install_090.log
msiexec /i "<1.0.0 MSI>" /qn /norestart /l*v msi_upgrade_100.log
msiexec /x {1B20E50F-79EB-4B7F-8DBD-BA86FCB467CC} /qn /norestart /l*v msi_uninstall_100.log
```

原始日志留存于本会话作业临时目录（非仓库）：1.0.0 全新安装 `msi_build4.log`/`msi_install.log`/`msi_uninstall.log`；升级验收 `msi_build_090.log`/`msi_install_090.log`/`msi_upgrade_100.log`/`msi_uninstall_100.log`，2026-11-03 复跑为 `v2_*.log` 与 `v3_*.log`。
