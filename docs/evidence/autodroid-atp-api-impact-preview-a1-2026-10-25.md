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

- 2026-10-26 补充：新保存的场景步骤会记录来源用例请求指纹。影响预览比较保存时的来源请求、当前来源请求和当前场景步骤，可分别提示来源请求变化与局部覆盖；更新场景时保留原指纹，避免把已有变化误认为新基线。旧场景没有指纹时继续提示人工确认。
- 指纹覆盖请求方法、URL、请求头、查询参数、Cookie、请求体类型和请求体；来源用例的断言、提取规则或描述变化不属于这项“请求版本”判断。
- 关联采用来源用例 ID 优先、方法和规范化路径回退；动态路径参数、环境变量 URL 及同一路径多种语义需要实际项目样例复核。
- 需在真实部署环境使用同一项目的两份规格、用例和场景完整走通预览与跳转；未将定向测试视为线上验收。

## 2026-10-26 非真机补充验证

- `backend/.venv/bin/pytest -q backend/tests/services/test_spec_sync.py backend/tests/services/test_api_scenario.py backend/tests/api/test_api_contracts_routes.py`：20 passed，覆盖来源变化、局部覆盖、空请求头、首次绑定和更新时保留基线。
- `npm test -- src/views/workbench/ApiWorkbenchView.spec.ts src/views/system/ApiContractAssetsView.spec.ts`：21 passed；`npm run type-check` 通过。
- OMP CLI 审查指出空对象回退问题，已修复；对最终后端 diff 的复审未发现严重问题。
