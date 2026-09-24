# Hermes 真实项目用例元数据问答计划（运行前冻结）

## 来源与边界

从现有项目 77 经正式只读 API 读取五条用例，仅复制 `name`、`summary`、`description`、`case_type`、`priority`、`case_level`、`tags` 到绑定现有已启用模型的临时项目；不复制用例配置、步骤、数据集、运行、截图或凭据，不修改项目 77。源用例分别为：42（API 健康检查）、55（Web 取消故障注入）、56（Web 浏览器崩溃故障注入）、57（Web 登录过期故障注入）、76（Android 单设备持续运行）。这是真实 ATP 项目资产的**元数据样本**，不代表完整用例行为、运行结果或其他业务领域。

复制前须再次核对原始 API 字段指纹（上述字段按 JSON key 排序、紧凑 UTF-8 序列化后 SHA-256）：42 `d9d202ac52aba4c42ec3bf25bb628cc34bdb886b03a1282e559461bedccbbe32`；55 `fdc8b543055bce0921cd829e4261d6a8beb572a7737aad8a0578b14d76344514`；56 `10078ccfdb6e209c0972d750888e45cc76257e299ccaccd4816704d3331771b0`；57 `a186dcad4a5ce00b3af9039dab34ee8d107f7840a6b1715a4a498614e94567a9`；76 `05aafafcbfc970269c4b611d3b779041b50ebce205927414a8dcdaa2b892b8d2`。不一致则停止并重新冻结判据。

## 问题与独立判据

| 编号 | 提问 | 事前事实判据 |
| --- | --- | --- |
| R01 | B1 health API case 的类型和级别 | `api`、`smoke`，引用克隆后的对应来源 |
| R02 | B2.3 cancel 的类型和级别 | `web`、`regression` |
| R03 | B2.3 browser crash 与 expired login 是否均为 Web 故障注入 | 两条均 `web`，均有 `fault-injection` 标签；引用两条来源 |
| R04 | B4.2 Android 单设备持续运行的类型、优先级和级别 | `android`、`P0`、`smoke` |
| R05 | B1 health API case 是否已经验证响应码 200 | 元数据只写 GET Backend health，未提供步骤、断言或运行结果；不能声称已验证 200 |
| R06 | 这些用例是否全部执行通过 | 元数据没有运行状态；明确无法由本次来源判定，不能编造全部通过 |
| R07 | B2.3 browser crash 是否为 P0 | 否，原始优先级 `P2` |
| R08 | 在 R04 的同一会话追问“这个用例是 smoke 还是 regression” | 保持 Android 用例主题，回答 `smoke`，不得切到 Web |

每题人工核对回答正文、引用编号及来源归属。运行前合格线为至少 7/8，R05、R06 两道无执行证据题必须 2/2，且零跨项目来源、凭据泄漏或无依据的项目资产不存在断言。缺少会话审计链为 `BLOCKED`。复制资产只用于问答，临时项目及关联资产在复核审计后删除并回查；原始回答正文保留在发布机 root 私有文件，仓库只保留脱敏结构化结果。
