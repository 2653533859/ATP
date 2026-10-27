# ATP AutoDroid 对照：M3 Android 真机闭环验收报告（2026-10-26）

## 概述与结论

2026-10-26，使用本地 Windows 宿主机连接的真实授权 Android 物理设备（华为平板 `5CQBB26605200808`），正式跑通并验证了 **M3 Android 真机端到端全流程闭环**：
涵盖 **设备扫描与资产注册 → M2 结构化执行前预检 → M1 低代码用例执行（成功路径） → 异常中断与租约自愈（故障路径） → D2 脱敏摘要原子入队 → D4 跨网络同步到云端服务器（`192.168.3.196:8000`）** 的全链条闭环。

---

## 1. 真实受测设备环境

| 参数项 | 取值 |
| :--- | :--- |
| **设备序列号** | `5CQBB26605200808` |
| **品牌与型号** | HUAWEI `BZH5-W00` |
| **系统版本** | Android 10 (SDK API 29) |
| **屏幕物理分辨率** | `1200x1920` |
| **连接方式** | USB ADB 本地授权直连 |

---

## 2. M2 设备级执行前预检诊断

对已注册的华为真机与用例配置发起结构化预检：
```text
[3/7] M2 执行前预检完成: ok=True, total_steps=8, items_count=0
```
* **设备与平台**：已在 Central Device 表中注册，状态为 `online`，不存在租约占用冲突，排除了 iOS 混淆防呆。
* **环境与应用**：ADB 握手连通，包名 `com.android.settings` 存在于物理设备 `pm list packages` 清单中。
* **定位与变量**：步骤动作定位合法，无未声明变量，预检判定无阻塞问题（`has_blocking_issue=False`）。

---

## 3. M3 真机低代码用例执行实测（成功路径）

* **用例信息**：`TC_M3_REAL_001`（M3 华为真机设置启停与按键流程）
* **运行 ID**：`Run 1`
* **终态**：`passed`
* **总耗时**：`16265ms`
* **租约占用与释放**：执行开始时获取 `device_leases` 独占行锁，执行结束在 `finally` 块中原子释放（活动租约数即刻归零）。
* **步骤逐项执行与本地截图产物**：

| 步骤序号 | 步骤名称 | 动作与参数 | 状态 | 耗时 | 本地对象存储截图 |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **0** | 启动系统设置 | `start_app` (`com.android.settings`) | `passed` | 2375ms | `/api/v1/local-files/screenshots/runs/1/step_0.png` |
| **1** | 等待页面渲染 | `wait` (`ms: 1500`) | `passed` | 2750ms | `/api/v1/local-files/screenshots/runs/1/step_1.png` |
| **2** | 捕获设置页屏幕 | `screenshot` | `passed` | 750ms | `/api/v1/local-files/screenshots/runs/1/step_2.png` |
| **3** | 点击返回键 | `press_key` (`key: BACK`) | `passed` | 2000ms | `/api/v1/local-files/screenshots/runs/1/step_3.png` |
| **4** | 等待页面返回 | `wait` (`ms: 800`) | `passed` | 1765ms | `/api/v1/local-files/screenshots/runs/1/step_4.png` |
| **5** | 返回主屏幕 | `press_key` (`key: HOME`) | `passed` | 1657ms | `/api/v1/local-files/screenshots/runs/1/step_5.png` |
| **6** | 等待主屏幕稳定 | `wait` (`ms: 1000`) | `passed` | 2063ms | `/api/v1/local-files/screenshots/runs/1/step_6.png` |
| **7** | 停止设置进程 | `stop_app` (`com.android.settings`) | `passed` | 1421ms | `/api/v1/local-files/screenshots/runs/1/step_7.png` |

---

## 4. 故障路径与租约自愈实测

* **用例信息**：`TC_M3_FAULT_002`（M3 故障路径-不存在应用异常阻断）
* **运行 ID**：`Run 2`
* **异常触发**：请求启动不存在的应用包名 `com.invalid.nonexistent.app`。
* **执行结果**：
  * 用例执行被安全捕获，终态收敛为 `failed`；
  * **租约自愈**：当前活动租约数在执行后立即收敛为 0，防止设备因异常用例被永久锁死。

---

## 5. D2/D4 跨网络脱敏同步至云端服务器

* **本地持久化 Outbox 队列入队**：
  * 成功用例唯一键：`win-3498f96ead4149ef94a4a084:case:1`
  * 故障用例唯一键：`win-3498f96ead4149ef94a4a084:case:2`
  * 自动脱敏剥离原始图片字节与敏感请求体，生成 `CloudRunSummary`。
* **跨局域网推送至云端中心**：
  * 目标服务器：`http://192.168.3.196:8000/api/v1/cloud-sync/runs`
  * 同步结果：`{'status': 'ok', 'synced': 2, 'failed': 0, 'processed': 2}`
  * 本地两项 Outbox 记录状态原子翻转为 `synced`（时间戳 `2026-10-26 06:33:31`）。
* **云端中心实测查询回显（`192.168.3.196:8000`）**：
  * `GET /api/v1/cloud-sync/runs/win-3498f96ead4149ef94a4a084:case:1` 成功返回包含 8 个步骤的轻量摘要，耗时 `16265ms`，状态 `passed`；
  * `GET /api/v1/cloud-sync/stats` 统计显示连接客户端机器 ID `win-3498f96ead4149ef94a4a084` 已上报 3 条运行（含此前联调 1 条 API 与本次 2 条真机用例）。
