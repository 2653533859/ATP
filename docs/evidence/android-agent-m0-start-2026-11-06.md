# Android Agent M0 首批实现与环境预检

日期：2026-11-06。基于 `eb1eddc4` 开始开发；本记录对应工作区新增代码，未部署到 Windows 安装包或 Linux。

后续进展：用户提供模型并连接汽水音乐测试设备后的结果见[首次实测记录](android-agent-m0-qishui-model-20261106.md)。下文“无设备/无模型”保留为首轮环境快照，不代表后续未曾连接或调用模型。

## 已完成的首批工作

- `backend/app/services/android_agent/contracts.py`：七类候选动作的严格协议，拒绝未知字段、重复 JSON 键、空预期、越界等待预算、非法变量引用；检查观察 ID、App 包名、控制代次和目标/变量白名单。没有执行设备命令，也没有把 finish 当作成功结论。
- `backend/app/services/android_agent/observation.py`：完整 UIAutomator XML 的有界解析，保留节点层级；拒绝 DTD/实体、畸形树和超限结构；无效坐标不可作为有效目标；清除 password 节点及其子节点的文本和描述。
- `scripts/android-agent-preflight.py`：只运行 `adb devices -l` 和只读 SQLite 配置计数，输出脱敏 JSON。不读取模型密钥，不采集截图，不操作 App，不调用模型；报告仅保存设备数量，不保存序列号或地址。

这些是 M0 验证原型，不是已接入工作台的 Agent。上下文校验不代替身份鉴权、设备租约和执行端串行门禁。密码节点清除不是通用隐私脱敏，尤其不覆盖截图；未经确认不能据此向外部模型发送观察。

## 现场预检结果

使用当前 Windows ADB 和已有 `E:\ATP_resources\atp.sqlite3` 只读检查：

- ADB 在线、离线、未授权设备数量均为 0。
- 本地启用且标记支持视觉的模型配置数量为 0；模型调用未验证。
- 测试 App、账号/重置方法以及图片外发范围尚未确定。
- 报告 `m0_accepted=false`，现场原始脱敏报告位于 `.local-run/android-agent-m0-preflight-20261106.json`。

数据库“配置存在”只能标记 configured，不能标记 model verified。预检脚本遇到缺失依赖返回非零；即便返回 0，也只说明没有检测到已知配置阻断，不表示 M0 验收通过。

复跑命令（输出文件必须是新文件，防止覆盖历史证据）：

```powershell
backend\.venv\Scripts\python.exe scripts\android-agent-preflight.py `
  --database E:\ATP_resources\atp.sqlite3 `
  --output .local-run\android-agent-m0-preflight-next.json
```

## 代码验证

以下两个文件分别独立执行，正常退出：

| 文件 | 结果 | 范围 |
| --- | --- | --- |
| `backend/tests/services/test_android_agent_m0.py` | 43 passed | 动作校验、迟到/过期决策拒绝、变量白名单、XML 解析与资源边界 |
| `backend/tests/scripts/test_android_agent_preflight.py` | 5 passed | ADB 异常、只读数据库、密钥/设备标识不输出、配置不冒充模型实测 |

Ruff 检查通过；新增服务模块 mypy 检查通过（3 个文件）。早期测试把大段 XML 用作自动参数 ID，触发测试初始化问题；已改为短 ID，修正后的单文件测试通过。没有执行全量项目回归。

## 仍未完成的 M0 项

- A00：两个测试 App、真机/模拟器、固定任务和重置夹具。
- A01：真实截图与 UI 树一致性、目标唯一性、中文/特殊字符输入、SQLite 租约争抢和设备断线。
- A02：真实视觉模型 JSON 响应、用量/时延与图片外发边界验证；当前只测试协议，不是模型效果。
- A03：持久协调器接入、执行前控制屏障、实际低代码独立回放路径及 v1 契约冻结。

上述依赖未齐，因此不关闭 M0，不进入生产设备自动写操作，也不宣称自然语言端到端可用。下一步先连接用户指定的测试设备、明确 App/模型与图片范围，再通过同一套预检工具继续记录证据。
