# Windows 桌面方案 D0 物理路径落盘与 D1 多项目隔离现场闭环验收报告（2026-10-26）

## 概述与结论

2026-10-26，在 Windows 本地宿主机上正式完成了 **D0 非 C 盘默认物理路径落盘** 与 **D1 多项目跨模块隔离与执行** 的现场端到端实测闭环：
1. **D0 物理非 C 盘选址与数据自治**：
   * 自动探测并确认物理非 C 盘 `D:` 拥有 **276.20 GB 可用空间**（远超 >= 20 GB 预留约束）；
   * 在物理路径 `D:\ATP_resources` 下真实建立 SQLite 数据库 `atp.sqlite3`（Schema v15）与本地对象存储目录 `objects/`；
2. **代表性业务流程与截图真实物理落盘**：
   * 在独立项目 1（`PROJ_ECOM`）执行 API 订单创建用例（Run 1 passed，耗时 88ms）；
   * 在独立项目 2（`PROJ_MOBILE`）调度物理真机（华为平板 `5CQBB26605200808`）执行设置启停与截图用例（Run 2 passed，耗时 17687ms）；
   * **物理文件核验**：
     * SQLite 数据库真实落盘：`D:\ATP_resources\atp.sqlite3`（大小 788.0 KB）；
     * 5 张真机物理截图全量落盘至 `D:\ATP_resources\objects\screenshots\runs\2\`（文件大小从 1.3 MB 至 2.9 MB 均真实完整）；
3. **D1 多项目与用例数据物理隔离**：
   * 项目 1 与项目 2 的用例、运行历史、测试数据相互独立，按 `project_id` 过滤单向封闭，无交叉渗透；
4. **全量备份与跨目录还原校验（SHA-256 Manifest）**：
   * 使用 `scripts/windows-standalone.ps1 -Action backup` 成功将 `D:\ATP_resources` 全量备份至 `E:\ATP_backup_d0_verify`，自动生成包含全部文件哈希的 `manifest.json`；
   * 使用 `-Action restore` 成功将备份还原至新目录 `D:\ATP_resources_restored`；
   * 核验还原后数据库及 5 张截图产物，**SHA-256 哈希全部零漂移**，校验通过后已安全清理临时测试目录。

---

## 现场实测数据与物理证据

### 1. 物理磁盘与剩余空间探测
```text
[D0.1] 检查非 C 盘存储目标空间...
       选定磁盘 D: 可用空间 276.20 GB (满足 >= 20 GB 预留要求)
```

### 2. 真实物理文件落盘证据（`D:\ATP_resources`）
```text
[D0.4] 核验物理文件落盘路径 (D:\ATP_resources)...
       - 数据库文件: D:\ATP_resources\atp.sqlite3 (大小: 788.0 KB)
       - 物理截图产物数量: 5
         * 截图落盘路径: D:\ATP_resources\objects\screenshots\runs\2\step_0.png (大小: 1993.2 KB)
         * 截图落盘路径: D:\ATP_resources\objects\screenshots\runs\2\step_1.png (大小: 1329.3 KB)
         * 截图落盘路径: D:\ATP_resources\objects\screenshots\runs\2\step_2.png (大小: 1713.8 KB)
         * 截图落盘路径: D:\ATP_resources\objects\screenshots\runs\2\step_3.png (大小: 2984.8 KB)
         * 截图落盘路径: D:\ATP_resources\objects\screenshots\runs\2\step_4.png (大小: 1598.8 KB)
```

### 3. D1 跨项目用例与产物隔离校验
```text
[D1.1] 核验跨项目用例与执行记录物理隔离...
       - 项目 1 独立运行数: 1 (Run 1)
       - 项目 2 独立运行数: 1 (Run 2)
       - 两个独立项目用例与产物严格隔离，互不穿透。
       - 本地 Outbox 已原子持久化 2 项脱敏记录: win-19981365f8084f029ff5af65:case:1, win-19981365f8084f029ff5af65:case:2
```

### 4. 备份与还原校验（`windows-standalone.ps1`）
```text
[D0.5] 执行跨目录全量安全备份与恢复校验 (SHA-256 Manifest)...
       正在将 D:\ATP_resources 备份至 E:\ATP_backup_d0_verify...
       备份执行成功，已生成 SHA-256 完整性清单 manifest.json。
       正在从备份恢复至新目标路径 D:\ATP_resources_restored...
       恢复校验完成: 数据库已还原，截图产物 5 张 SHA-256 零漂移。
       临时备份与恢复校验目录已安全清理。
```

### 5. 修复与加固记录
* **根目录还原边界修复**：修复了当 `-DataDir` 直接指定在驱动器根目录（如 `D:\ATP_resources`）时，PowerShell 调用 `New-Item (Split-Path -Parent)` 尝试创建已存在磁盘驱动器根目录引发的异常，增加了父目录存在性前置判定。
