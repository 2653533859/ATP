# scripts/archive

这里存放**已完成验收的一次性脚本**：它们为某一次现场验收或问题定位而写，对应结论已经
落在 `docs/evidence/` 的证据文档里，保留只为让那些文档中的复现命令仍然可查。

- 不在 `make lint` / `make format-check`、CI ruff 步骤和 pre-commit 钩子的受检范围内
  （受检清单是 Makefile 的 `LINT_SCRIPTS`），也不被任何测试、Makefile 目标或其它脚本调用。
- 不保证随主线代码演进继续可运行；需要重新验收时请以当前代码为准重写，而不是直接复用。
- 运行方式与归档前一致：在仓库根目录执行 `python scripts/archive/<脚本名>`。

| 脚本 | 对应证据文档 |
| --- | --- |
| `android-agent-model-probe.py` | `docs/evidence/android-agent-m0-qishui-model-20261106.md` |
| `android_agent_m2_live_setup.py`、`android_agent_m2_probe_model.py`、`android_agent_m2_keycheck.py`、`android_agent_m2_action_matrix.py`、`android_agent_m2_live_e2e.py`、`android_agent_m2_live_safety.py` | `docs/evidence/android-agent-m2-real-device-20261111.md` |
| `android_agent_m3_smoke.py` | `docs/evidence/android-agent-m3-draft-replay-20261111.md` |
| `verify_d0_physical_data_dir.py` | `docs/evidence/d5-node-grant-field-acceptance-2026-11-03.md` |
