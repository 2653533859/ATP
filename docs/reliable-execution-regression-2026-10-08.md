# N1.6 可靠执行回归与迁移证据（2026-10-08）

## 当前结论

N1.6 进行中。本批完成事务回归、历史 SQLite 升级夹具修复、完整 PostgreSQL 16 迁移链，以及 Windows/服务器两种隔离栈的真实 API 与执行链路。服务器过期租约核对、双模式浏览器恢复面板、Windows 浏览器取消、真实并发确认和两侧项目权限拒绝已完成；跨浏览器/多副本及独立代码审查仍待验收。

分支为 `codex/windows-local-dual-mode`，基于 HEAD `2ba16f88becaa182ac87c1b348c0972c373feb92` 的工作区；首批源码快照为 `.local-run/development-baselines/20261008-n1-6-regression/`，追加 Alembic 修复及首批实测后的快照为 `.local-run/development-baselines/20261008-n1-6-live/`，Windows 浏览器取消/并发/权限快照为 `.local-run/development-baselines/20261008-n1-6-browser/`，当前服务器浏览器与子运行边界修复快照为 `.local-run/development-baselines/20261008-n1-6-server-browser/`。未提交、推送、合并或发布生产版本。

## 修复与审查

1. **子套件租约身份误报**：计划的子套件状态查询原先只按数字 ID 检索异常租约。同编号旧运行的过期租约会把新运行的已完成结果误报为 `child_execution_uncertain`。已改为同时匹配子套件 ID 与归属记录中的 UUID。
2. **正反两侧回归**：不同 UUID 的旧租约不影响新运行；同一 UUID 的过期租约仍提示核对，避免通过过滤隐藏实际异常。
3. **旧夹具适配**：本地队列夹具加入 `run_identity`、`dispatch_id` 与实际运行时间；套件配置测试补充身份；API 测试验证同事务记录意图，替代旧的直接 Celery 发布假设。旧无身份组租约的预期改为不猜测当前运行归属，新身份租约另有真实数据库覆盖。
4. **历史升级结构**：旧 SQLite 测试此前把最新 `Base.metadata` 标记为版本 1/2，造成新表重复建立。夹具现在移除版本 7–11 新增表/列，再运行连续升级。此为历史结构重建回归，不等同于所有用户历史备份的升级验收。
5. **单角色 Alembic 升级失败**：隔离 PostgreSQL 16 从空库升到 0079 时，迁移尾部权限同步收到空的 `POSTGRES_MIGRATION_USER` 并报错。`backend/alembic/env.py` 现将未配置的迁移角色解析为现有运行角色，保留单角色部署契约；同一隔离库重新执行完整迁移并成功升至 0079。
6. **子运行展示上限误报安全终态**：状态接口只返回前 200 条子运行；父运行已有终态时，第 201 条可能仍在运行或身份失效。原逻辑会返回 `reason=terminal`、`requires_reconciliation=false`。现在当子运行被截断且没有更具体的异常原因时，返回 `children_truncated` 并要求人工核对；中英文面板增加说明。新增 201 条子运行的回归，PostgreSQL 16 隔离栈上复现并验证页面黄色提示。

用例测试代码位于 `backend/tests/services/test_group_execution_recovery.py`。审查为本轮代码检查及回归定位，尚未替代 N6 的独立审查。

## 自动化回归范围

最初 24 项定向事务回归加本轮 1 项子运行展示上限回归，当前单文件共 25 项；使用独立文件 SQLite、真实 SQLAlchemy 同步/异步事务，服务器配置分支中的 Broker 为模拟传输。覆盖：

- 提交后未唤醒投递器，扫描仍发现意图且只入队一次。
- 回滚不留下新运行或投递意图；本地队列插入后、提交前退出，插入与领取一起回滚。
- 八份消息、四线程并发接受，仅一个接受成功。
- 本地/服务器配置下接受消息后未开始执行，接受记录仍阻止第二次启动。
- 错误消息 UUID、任务 ID、参数和缺失头不消耗合法消息。
- Broker 超时与过期发布保持未知状态，扫描不自动重发。
- 套件/计划的排队与运行中取消持久化；重复取消保留首次时间；运行中取消不虚报已停止。
- 套件/计划过期租约仅恢复匹配身份的非终态，保留替代资源与既有终态。
- 子套件租约 UUID 的正反两侧状态查询。
- 终态父计划超过 200 条子运行时，未显示的第 201 条仍在运行必须标记为需核对。

第一轮既有回归另受默认 pytest 临时目录权限错误影响，后续显式使用 `.local-run/pytest-n16-*` 隔离目录；没有修改用户临时目录权限。

证据文件：

| 检查 | 证据 | 边界 |
| --- | --- | --- |
| 初版事务回归，24 项通过 | `.local-run/n16-final-service.log` | SQLite 实际事务；传输模拟；没有 UI/真实 Worker |
| 当前单文件，25 项通过 | 本轮 `pytest -q backend/tests/services/test_group_execution_recovery.py` 输出 | 增加 201 条子运行边界；PostgreSQL 另有真实 API 与页面验证 |
| 合并定向回归，110 项通过 | `.local-run/n16-combined.log` | 包含新增测试早一轮的 22 项；子租约修复最终版本由上述 24 项重新覆盖 |
| 七个既有文件分别运行，88 项通过 | `.local-run/n16-standalone.json`、`n16-standalone-0.log` 至 `-6.log` | 每个文件独立进程，避免依赖合并收集副作用；该证据早于第 25 项新增测试 |
| Ruff 与格式 | 本批工具输出 | 变更的服务和测试文件 |
| mypy | 本批工具输出，181 源文件通过 | 仓库既定渐进检查范围 |

运行时服务查询、Alembic 权限调用和中英文恢复提示均已修改；当前定向 25 项、Ruff、mypy 181 文件、`vue-tsc --noEmit` 与 Windows 本地模式 `npm run build` 通过。Windows 无 `make` 命令，本轮直接运行其 `mypy` 等价命令。确认用户库仅有 12 条 finished 本地任务后，通过既有启动脚本重启静态模式服务加载最终后端修复，`http://127.0.0.1:8001/health` 返回 200；本地静态前端也已重建，包含新增提示。没有在用户数据库创建测试业务记录。Linux 生产服务器未更新，仅隔离栈验证最终候选。

## 独立服务实测

**Windows 本地栈**：在 `.local-run/n16-live-local-20261008-c/` 新建独立数据目录、随机凭据及 8108 API，目标仅为本机只读 HTTP 测试服务。记录见 `events.jsonl` 与 `api.log`。真实登录、创建两个 API 用例和套件后：

- 同一个 `command_id` 连续确认两次，只返回同一个运行 ID 1；该运行通过，投递已提交且存在接受时间，子运行数为 1。
- 第二条运行的慢请求期间发出协作取消；运行以 `error` 结束，状态原因显示 `cancelled`。
- 第三条运行的子任务开始后强制结束 API 进程，再以同一 SQLite 重启；恢复结果为 `error`，原因 `execution_interrupted`，子运行数为 1。队列最后有 2 条 finished、1 条 interrupted；总套件运行数仍为 3，没有自动重放。
- 全程使用独立 SQLite，未读写用户 `.local-data/atp.sqlite3`。启动过程第一次试图创建第二项目遭 409 拒绝，按单项目约束改为使用隔离栈自动创建的项目。第二次验收脚本条件表达式报错，修复脚本后第三次完整流程通过；这两次属于验收脚本问题。

**服务器隔离栈**：Linux MCP 上新建专用 Docker 网络、PostgreSQL 16、Redis 7、MinIO、API、默认队列 Worker、维护 Worker 和 Beat，所有数据与现有容器隔离；API 仅绑定服务器的 `127.0.0.1:8109`，所有凭据只保存在该隔离目录的私有环境文件中。当前候选源代码以只读挂载提供，未修改生产容器、业务库或发布镜像。

- PostgreSQL 16 从空库完整运行 Alembic 到 `20261008_0079`；API 启动日志确认版本匹配，MinIO bucket 创建，默认 Worker 连接独立 Redis。
- 真实登录、项目/用例/套件创建后，重复命令确认返回同一运行 ID 1；该运行 `passed`，投递状态 `submitted`、执行已接受、子运行数为 1。
- 运行 ID 2 的慢请求期间取消，最终 `error`，状态原因 `cancelled`。
- 运行 ID 3 的子运行已记录后，强制终止并重启默认 Worker。终止后、租约 90 秒窗口内仍显示 `running`，这反映尚未过期的租约，不能据此认定 Worker 仍在执行。维护 Worker 与 Beat 在租约到期后将父运行标为 `error`、租约标为 `expired`，状态原因 `children_unfinished` 且 `requires_reconciliation=true`。已核实子运行仍为 `running`，需要人工检查实际外部副作用和子任务；没有记录第二次套件启动。

服务器迁移、业务事件及最终恢复状态分别保存于 `.local-run/n16-server-migrate.log`、`.local-run/n16-server-events.jsonl`、`.local-run/n16-server-recovery-result.json`；API、默认 Worker、维护 Worker 和 Beat 日志保存于 `.local-run/n16-server-{api,worker,maintenance,beat}.log`。隔离容器和专用网络已按名称删除，私有环境文件也已删除。此处的 API、队列、数据库和对象存储都是真实进程；目标 HTTP 服务是隔离栈内的只读测试目标，未验证外部业务服务。

**Windows 浏览器首轮查看**：隔离 SQLite 服务配合独立 Vite 入口 `127.0.0.1:5178`、无头 Chromium，真实登录后打开套件列表与运行记录，展开通过运行及取消运行的“执行状态与恢复”面板，能看到投递状态、接受时间、取消时间和子运行；无页面异常。证据为 `.local-run/n16-browser-20261008-f/browser.log` 与 `suite-page.png`、`fast-run.png`、`slow-run.png`。前两次浏览器脚本误把登录页 URL 中的 `redirect=/suites` 当作已跳转，以及把标题“执行状态与恢复”误写成“执行与恢复”；修正脚本后通过，未发现对应页面缺陷。首轮只覆盖本地模式的查看入口，取消与权限由下述追加检查覆盖。

**Windows 浏览器取消与权限/并发追加**：将此前隔离数据库复制到新的 `.local-run/n16-next-20261008-e/data/`，不访问用户数据库。Chromium 登录后发起慢套件运行，从“记录”展开恢复面板，点击取消并确认；页面显示取消请求时间和“已请求取消”，运行随后以 `error` 结束。8 个线程在同一屏障后同时向真实本地 API 提交相同命令 ID，8 个 HTTP 响应均为 202 且运行 ID 均为 9；只新增 1 条对应运行。将隔离账号的全局角色及项目角色降为 viewer 后，状态读取 200、取消 403；移除其项目成员关系后，两入口均返回 403。证据为 `.local-run/n16-next-20261008-e/events.jsonl`、`browser.log`、`cancel-confirm.png` 和 `cancel-result.png`。首次脚本等待文案错误、第二次并发预先登录触发本地登录限流、第三次只降全局角色但保留项目 owner 且发送无效版本字段；修正夹具后完整通过。此轮没有发现需要改动的产品源码缺陷。

**Linux 服务器模式浏览器及权限**：在同一 Linux 主机新建第二套专用 Docker 网络及 PostgreSQL 16/Redis/MinIO/API/Worker，API 仅绑定主机私有地址 `172.31.27.133:8109`；Windows Vite 5179 以服务器模式代理该 API。当前候选完整迁移至 0079，真实套件运行 `passed`、投递 `submitted`、子运行 1 条；Chromium 登录并展开“执行状态与恢复”面板，无页面异常。通过服务器 API 创建 viewer 项目成员和非成员账号：成员读状态 200、取消 403；非成员读/取消均 403；匿名读 401。随后在隔离 PostgreSQL 构造父计划已 `passed`、201 条子运行中最后一条仍 `running` 的边界：最终候选 API 返回 `children_truncated`、`requires_reconciliation=true`、`child_count=201`、展示 200 条；Chromium 的计划运行面板显示黄色人工核对提示。直接 SQL 夹具最初未填计划/运行列表必需字段导致页面 500；补齐夹具字段后业务页面通过，并非正常 API 创建的记录。证据在 `.local-run/n16-linux-browser-20261008/` 的 `events.jsonl`、`browser.log`、`server-run.png`、`server-hidden-child.png`、`browser-schema.txt`。这只验证 Chromium 与单 API/Worker 的隔离栈，不代表生产、多浏览器或多副本验收。

隔离服务器容器及网络已按名称删除，私有环境文件和本地临时登录凭据已删除；私有地址端口已关闭。普通本地服务未被该隔离栈修改。

**同库双 API 副本与三浏览器追加**：重新建立专用 PostgreSQL 16/Redis/MinIO/API/Worker 隔离栈，再加第二 API 副本；两个 API 分别仅绑定服务器私有地址的 8109、8112 端口，共享同一隔离数据库和队列。8 个真实并发 HTTP 确认交错送往两个副本，同一命令仅产生 1 条套件运行；两侧均读到 `passed`、同一状态版本、投递 `submitted` 和 1 条子运行。viewer 成员在两个副本均读 200/取消 403，非成员均读 403/取消 403。Windows Vite 5179 以服务器模式代理第一个副本，Chromium、Firefox、WebKit 均通过登录后套件记录展开，恢复面板显示 `submitted`，浏览器页面错误为 0；WebKit 截图另经人工查看，布局和状态正常。证据为 `.local-run/n16-replicas-20261008/events.jsonl`、`browser.log` 和三张 `*-recovery.png`。首次浏览器脚本误按计划弹窗定位套件抽屉，第二次未等待异步状态加载，第三次复用登录态却停在登录路由；修正验收脚本后矩阵全部通过，未定位到产品源码问题。

本轮只覆盖一个数据库、一个 Worker、两个 API 副本的最终状态和只读权限；未覆盖双 Worker、浏览器跨副本会话路由或生产多节点网络。临时登录材料和环境文件在验收后清除，生产栈未变更。

**双 Worker/浏览器跨副本后续尝试（2026-10-08）**：已准备同一浏览器会话在 Vite 代理从副本 A 切至副本 B 后读取状态、展开恢复面板的临时验收脚本，并重新运行定向事务回归，`25 passed in 55.71s`。开始重建隔离 Linux 栈时，Linux MCP 的 SSH 连接在读取协议 banner 前中断；随后多次只读重试仍如此，Windows 直连 SSH 显示远端关闭连接，8109/8112 健康请求超时。因此未取得双 Worker 或浏览器跨副本通过证据，也未确认首次启动命令是否已创建部分临时容器。待 SSH 恢复后，须先按 `atp-n16-browser-*` 和 `atp-n16-browser-net` 核对并清理可能残留的隔离资源及 `/tmp/atp-n16-server-20261008/browser.env`、`browser-login.txt`，再重新验收。未操作生产容器或数据库。

复查时 Windows 普通本地服务的旧进程状态文件仍在但进程已停止；通过既有脚本先 `down` 清理失效状态、再以静态前端模式 `up` 启动，最终 `127.0.0.1:8001/health` 返回 200。没有修改用户业务数据库。

**指定 Linux 主机上的双 Worker 与浏览器跨副本验收**：用户提供 `192.168.3.196:222` 后，检查发现端口 222 在 SSH banner 前断开，而本机保存的 SSH 配置使用 2222；Linux MCP 经 2222 连接到 `CHINAMI-762P0P5`。这台主机与上一轮 `172.31.27.133` 地址不同，核对时没有 `atp-n16-browser-*` 容器或旧候选目录，不能用它证明另一地址上首次启动命令的结果。当前候选源码通过私有 SFTP 上传，SHA-256 两侧一致；在本机新建 `atp-n16-dual-*` 专用网络、PostgreSQL 16、Redis、MinIO、双 API 和双默认队列 Worker，完整 Alembic 到 `20261008_0079`。API 只绑定该主机私有地址 8109、8112，使用随机临时凭据，未操作既有生产栈。

- 两台 Worker 暂停时，8 个并发确认交错发送给两个 API，仅建立同一条待执行运行。投递提交后向隔离 Redis 注入同身份、同参数的第二份真实 Celery 消息，再启动两台 Worker；第一条运行通过，第二份消息因 `RUN_NOT_PENDING` 被拒绝。
- 两台 Worker 均就绪后再次发起运行。隔离目标开始处理、运行 Worker 尚未结束时注入精确重复消息；Worker 2 完成执行，Worker 1 跳过重复消息。两条运行均 `passed`，数据库中有 2 条套件运行、2 条用例运行、2 条接受记录；隔离目标恰有 2 次请求，即每条运行一次。两个 API 均读取相同终态和状态版本。首轮重复消息被同一 Worker 串行取走，因此单独补做第二轮跨 Worker 重复消息检查。
- Chromium 在 Windows Vite 5179 登录一次后，保持同一页面 origin 和浏览器上下文，重启 Vite 代理从 API A 切到 API B；登录态有效，恢复状态版本一致，页面仍可展开套件恢复面板，页面错误 0。第二次验收脚本在代理重启瞬间遇到导航取消，改为等待新代理健康并对该导航重试后通过；这是脚本时序问题，未定位到产品源码缺陷。

证据位于 `.local-run/n16-dual-worker-20261008/`：`events.jsonl`、`acceptance-summary.txt`、`browser.log`、`cross-replica-session.png`。本轮仅证明隔离栈中两台 Worker 对相同消息的接受防重及 Windows 同源浏览器的 API 切换，不代表生产多节点网络或外部副作用的全域验收。验收后按精确名称删除新建容器、网络、私有环境和临时账号文件；Windows 临时登录文件也已删除。

Windows 为传输候选源码曾建立 `.local-run/n16-transfer/`，其临时 HTTP 进程已停止。自动审批拒绝删除该忽略目录，目录仅余候选源码压缩包和 HTTP 日志；没有凭据。该本地临时目录留待允许的清理方式处理。

## PostgreSQL 隔离迁移

Linux MCP 已连接并确认服务器容器可用。使用新建 `atp-n16-pg-20261008` 临时 PostgreSQL 18.4 容器：无宿主端口、`--network none`、数据放 tmpfs；检查容器共享其网络命名空间。没有使用已有 PostgreSQL 的业务库。验收完成后临时 PostgreSQL 容器已删除。

实际运行当前候选 `0076 → 0077 → 0078 → 0079` 的 Alembic `upgrade()`，再按相反顺序运行 `downgrade()`。证据为 `.local-run/n16-postgres-migrations.log`，包含逐版本升级/回退事件和 `N1_POSTGRES_MIGRATION_HARNESS_OK`：

- 六条历史套件/套件运行/计划运行得到非空、各表不重复的 32 字符身份。
- 三条不显式提供身份的新记录由数据库默认值赋予身份。
- 投递表 18 列、子归属表 9 列。
- 两条旧命令回执保持身份为空，不通过数字 ID 推断身份。
- 回退后新增投递/归属表移除。

**限制**：数据库是最小迁移前置表夹具，使用 PostgreSQL 18.4；没有执行从空库到全部历史 Alembic 的完整链，也没有验证仓库 PostgreSQL 16 基线。本检查不能代表生产业务数据升级、服务器 API/Celery/Redis/MinIO 联动或混合版本 Worker 验收。

## 后续仍须完成

1. 已完成三浏览器恢复面板、双 API 并发命令/权限矩阵、隔离双 Worker 重复消息及同源浏览器跨副本会话检查。生产多节点网络与外部副作用仍未验收；此前不可达的 `172.31.27.133` 地址上首次启动命令的副作用尚不能核对。服务器子运行在 Worker 被强杀后仍可能显示 `running`，必须结合外部副作用人工核对，不自动重放。
2. 对当前候选做独立代码审查；本轮自查发现并修复了 200 条展示上限问题，但不将同一执行者的自查称为独立审查。Linux 生产发布仍按 N5 门禁单独进行。

完成以上标准前 N1.2–N1.6 保持开放；下一批继续 N1.6，再进入 N2 日常业务验收。
