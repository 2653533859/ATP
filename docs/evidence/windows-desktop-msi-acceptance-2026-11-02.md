# D7 Windows 桌面端 MSI 构建与本机安装/卸载验收（2026-11-02）

## 结论

D7 MSI 安装包已完成构建，并在本机完成静默安装、启动冒烟、静默卸载与残留清零验收；安装与卸载退出码均为 0，卸载后零残留。MSI 未做代码签名；升级安装与全新电脑验收未在本轮执行，仍为外部阻塞，暂不能称为可用于分发的正式安装包。

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

## 未覆盖边界

- 升级安装（旧版本 → 1.0.0）未执行；本轮为全新安装 → 卸载。
- 全新电脑验收未执行：本轮在同机（Windows 11、自带 Edge WebView2、具备构建环境）完成；Tauri 未显式配置 `webviewInstallMode`，采用默认 WebView2 安装模式，缺失 WebView2 机器的获取行为待验。
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

本轮构建/安装/卸载原始日志留存于本会话作业临时目录（非仓库）：`msi_build4.log`、`msi_install.log`、`msi_uninstall.log`。
