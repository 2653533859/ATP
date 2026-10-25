# A1 接口规格到场景影响预览

日期：2026-10-25。状态：代码与定向验证完成；真实环境验收待补。

## 实现

- 契约资产页调用已有 `/projects/{id}/api-contracts/sync-cases`，传入当前规格及可选旧版规格，展示用例差异与受影响场景步骤，提供用例详情和 API 工作台步骤跳转。
- 后端复用规格与用例同步逻辑，补充仅由旧版规格发现的端点变化，读取项目场景快照并按来源用例 ID 或请求方法和路径关联。预览只读，不应用补丁，也不修改历史运行。
- 保存过的场景步骤继续保留 `sourceCaseId`；工作台支持从影响预览定位到指定场景步骤。

## 验证

- `backend/.venv/bin/pytest -q backend/tests/services/test_spec_sync.py backend/tests/api/test_api_contracts_routes.py`：8 passed。
- `npx vitest run src/views/system/ApiContractAssetsView.spec.ts src/views/workbench/ApiWorkbenchView.spec.ts`：17 passed。
- `npm run type-check`：通过。`npm ci --ignore-scripts --no-audit --no-fund` 恢复锁文件指定的前端依赖后执行，未升级依赖。

## 已知限制与后续验收

- 当前场景步骤未保存来源用例版本及局部覆盖差异，因此预览明确提示人工逐项确认，不能精确判定版本冲突或覆盖状态。
- 关联采用来源用例 ID 优先、方法和规范化路径回退；动态路径参数、环境变量 URL 及同一路径多种语义需要实际项目样例复核。
- 需在真实部署环境使用同一项目的两份规格、用例和场景完整走通预览与跳转；未将定向测试视为线上验收。
