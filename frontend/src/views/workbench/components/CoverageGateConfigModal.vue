<template>
  <a-modal
    :open="open"
    title="增量代码覆盖率发布门禁配置与高危分支补测中枢"
    width="860px"
    :destroy-on-close="true"
    class="coverage-gate-config-modal"
    @cancel="handleCancel"
  >
    <div class="modal-container">
      <!-- 1. 顶部门禁指标概览横幅 -->
      <div class="gate-metrics-banner">
        <div class="banner-stat">
          <div class="stat-num text-primary font-bold font-mono">
            {{ formState.min_diff_line_coverage_pct }}%
          </div>
          <div class="stat-label">增量行覆盖率门槛</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-warning font-bold font-mono">
            {{ formState.min_diff_branch_coverage_pct }}%
          </div>
          <div class="stat-label">增量分支覆盖率门槛</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num font-mono">
            <a-tag :color="!formState.allow_p0_uncovered ? 'red' : 'orange'">
              {{ !formState.allow_p0_uncovered ? 'P0 零容忍强阻断' : '允许豁免放行' }}
            </a-tag>
          </div>
          <div class="stat-label">高危分支准入策略</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-secondary font-mono">
            ≤ {{ formState.max_allowed_uncovered_lines }} <span class="text-xs">行</span>
          </div>
          <div class="stat-label">容许未覆盖行上限</div>
        </div>
      </div>

      <!-- 2. 双 Tab 切换：门禁红线配置 + 缺失用例场景导出 -->
      <a-tabs v-model:activeKey="activeTab" class="gate-tabs">
        <!-- Tab 1: 门禁策略配置 -->
        <a-tab-pane key="policy" tab="发布门禁准入红线配置 (Gate Rules)">
          <a-form layout="vertical" class="gate-form">
            <a-form-item label="增量代码行覆盖率准入基准线 (Diff Line Coverage %)">
              <div class="slider-input-group">
                <a-slider
                  v-model:value="formState.min_diff_line_coverage_pct"
                  :min="60"
                  :max="100"
                  :step="1"
                  class="flex-1"
                />
                <a-input-number
                  v-model:value="formState.min_diff_line_coverage_pct"
                  :min="60"
                  :max="100"
                  style="width: 80px;"
                />
              </div>
              <div class="form-help-text">
                CI/CD 发布流水线卡点：PR 变更可执行代码行测试覆盖率必须达到该指标，推荐 85.0%。
              </div>
            </a-form-item>

            <a-form-item label="增量条件分支覆盖率准入门槛 (Diff Branch Coverage %)">
              <div class="slider-input-group">
                <a-slider
                  v-model:value="formState.min_diff_branch_coverage_pct"
                  :min="50"
                  :max="100"
                  :step="1"
                  class="flex-1"
                />
                <a-input-number
                  v-model:value="formState.min_diff_branch_coverage_pct"
                  :min="50"
                  :max="100"
                  style="width: 80px;"
                />
              </div>
              <div class="form-help-text">
                确保 if/else、switch、三元运算等分支路径被正反双向测试覆盖，推荐 70.0%。
              </div>
            </a-form-item>

            <a-row :gutter="16">
              <a-col :span="14">
                <a-form-item label="P0 阻塞级高危分支未覆盖强制阻断 (Zero-Tolerance)">
                  <div class="switch-row">
                    <a-switch v-model:checked="p0BlockEnabled" />
                    <span class="switch-desc">
                      {{ p0BlockEnabled ? '严禁资金支付或安全鉴权未测分支上线（触发即强阻断）' : '放宽限制（仅提示警告）' }}
                    </span>
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="10">
                <a-form-item label="最大容许未覆盖变更行数">
                  <a-input-number
                    v-model:value="formState.max_allowed_uncovered_lines"
                    :min="0"
                    :max="100"
                    style="width: 100%;"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="准入核算豁免文件匹配白名单 (Exempt File Patterns)">
              <a-select
                v-model:value="formState.exempt_file_patterns"
                mode="tags"
                placeholder="输入需豁免的文件模式，如 tests/*, *.spec.ts"
                class="font-mono"
                style="width: 100%;"
              />
              <div class="form-help-text">
                白名单路径内的测试用例脚本、数据库迁移、文档等，不纳入发布覆盖率分子分母核算。
              </div>
            </a-form-item>
          </a-form>
        </a-tab-pane>

        <!-- Tab 2: 缺失用例场景反向合成与导出 -->
        <a-tab-pane key="cases" tab="缺失高危分支补测用例 (Synthesized Cases)">
          <div class="cases-pane-header">
            <span class="text-xs text-secondary">
              系统反向推导共生成 <strong>{{ displayCases.length }}</strong> 组补测用例建议，补齐后预估提升增量覆盖率 <strong>+18.0%</strong>
            </span>
            <a-button type="primary" size="small" @click="handleExportCases">
              <template #icon><ExportOutlined /></template>
              导出补测脚本草稿
            </a-button>
          </div>

          <div class="synthesized-cases-list">
            <div
              v-for="c in displayCases"
              :key="c.draft_id"
              class="case-item-card"
            >
              <div class="case-card-header">
                <span class="case-title font-bold">{{ c.case_title }}</span>
                <a-tag :color="c.severity === 'P0_BLOCKING' ? 'red' : 'orange'">
                  {{ c.severity }}
                </a-tag>
              </div>
              <div class="case-meta font-mono text-xs">
                <span>文件: {{ c.file_path }} (L: {{ c.target_lines }})</span>
                <span class="text-primary">分类: {{ c.category }}</span>
              </div>
              <div class="case-inputs font-mono text-xs">
                <strong>推荐输入参数: </strong>
                <code>{{ JSON.stringify(c.recommended_inputs) }}</code>
              </div>
              <div class="case-code-box">
                <pre class="code-pre font-mono text-xs">{{ c.suggested_test_code }}</pre>
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>

    <template #footer>
      <div class="modal-footer">
        <a-button @click="resetToDefaults">恢复推荐门禁值</a-button>
        <a-space>
          <a-button @click="handleCancel">取消</a-button>
          <a-button type="primary" :loading="saving" @click="handleSave">
            <template #icon><CheckOutlined /></template>
            保存并生效门禁策略
          </a-button>
        </a-space>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ExportOutlined, CheckOutlined } from '@ant-design/icons-vue'

export interface IncrementalCoverageGatePolicy {
  policy_id: string
  min_diff_line_coverage_pct: number
  min_diff_branch_coverage_pct: number
  allow_p0_uncovered: boolean
  max_allowed_uncovered_lines: number
  exempt_file_patterns: string[]
}

export interface SuggestedTestCaseItem {
  draft_id: string
  target_branch_id: string
  file_path: string
  target_lines: string
  case_title: string
  test_type: string
  severity: string
  category: string
  recommended_inputs: Record<string, any>
  expected_assertion: string
  mock_prerequisites: string[]
  suggested_test_code: string
}

const props = withDefaults(
  defineProps<{
    open: boolean
    initialPolicy?: Partial<IncrementalCoverageGatePolicy> | null
    synthesizedCases?: SuggestedTestCaseItem[]
  }>(),
  {
    open: false,
    initialPolicy: null,
    synthesizedCases: () => [],
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'cancel'): void
  (e: 'save', policy: IncrementalCoverageGatePolicy): void
  (e: 'exportCases', cases: SuggestedTestCaseItem[]): void
}>()

const activeTab = ref('policy')
const saving = ref(false)

const formState = reactive<IncrementalCoverageGatePolicy>({
  policy_id: 'policy_atp_standard',
  min_diff_line_coverage_pct: 85.0,
  min_diff_branch_coverage_pct: 70.0,
  allow_p0_uncovered: false,
  max_allowed_uncovered_lines: 15,
  exempt_file_patterns: ['tests/*', 'test/*', '*.spec.ts', '*.test.ts', 'alembic/*'],
})

const p0BlockEnabled = computed({
  get: () => !formState.allow_p0_uncovered,
  set: (val: boolean) => {
    formState.allow_p0_uncovered = !val
  },
})

const defaultSynthesizedCases: SuggestedTestCaseItem[] = [
  {
    draft_id: 'draft_01',
    target_branch_id: 'br_pay_01',
    file_path: 'backend/app/services/payment.py',
    target_lines: '14-15',
    case_title: '【补测】覆盖 payment.py:14 VIP 充值折扣分支',
    test_type: 'api',
    severity: 'P0_BLOCKING',
    category: 'PAYMENT_FINANCIAL',
    recommended_inputs: { user_id: 'vip_tester_01', amount: 500.0 },
    expected_assertion: 'assert response.status_code == 200',
    mock_prerequisites: ['Mock: payment_gateway_service'],
    suggested_test_code: 'def test_cover_vip_discount(client):\n    resp = client.post("/api/v1/payment", json={"user_id": "vip_01", "amount": 500.0})\n    assert resp.status_code == 200',
  },
]

const displayCases = computed(() =>
  props.synthesizedCases && props.synthesizedCases.length > 0
    ? props.synthesizedCases
    : defaultSynthesizedCases
)

watch(
  () => props.initialPolicy,
  (newVal) => {
    if (newVal) {
      if (newVal.policy_id) formState.policy_id = newVal.policy_id
      if (newVal.min_diff_line_coverage_pct !== undefined) formState.min_diff_line_coverage_pct = newVal.min_diff_line_coverage_pct
      if (newVal.min_diff_branch_coverage_pct !== undefined) formState.min_diff_branch_coverage_pct = newVal.min_diff_branch_coverage_pct
      if (newVal.allow_p0_uncovered !== undefined) formState.allow_p0_uncovered = newVal.allow_p0_uncovered
      if (newVal.max_allowed_uncovered_lines !== undefined) formState.max_allowed_uncovered_lines = newVal.max_allowed_uncovered_lines
      if (newVal.exempt_file_patterns) formState.exempt_file_patterns = [...newVal.exempt_file_patterns]
    }
  },
  { immediate: true }
)

function resetToDefaults() {
  formState.min_diff_line_coverage_pct = 85.0
  formState.min_diff_branch_coverage_pct = 70.0
  formState.allow_p0_uncovered = false
  formState.max_allowed_uncovered_lines = 15
  formState.exempt_file_patterns = ['tests/*', 'test/*', '*.spec.ts', '*.test.ts', 'alembic/*']
}

function handleCancel() {
  emit('update:open', false)
  emit('cancel')
}

function handleSave() {
  saving.value = true
  emit('save', { ...formState, exempt_file_patterns: [...formState.exempt_file_patterns] })
  setTimeout(() => {
    saving.value = false
    emit('update:open', false)
  }, 300)
}

function handleExportCases() {
  emit('exportCases', displayCases.value)
}
</script>

<style scoped>
.modal-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.gate-metrics-banner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-subtle, #fafafa);
  border: 1px solid var(--c-border, #f0f0f0);
  border-radius: 8px;
  text-align: center;
}

.banner-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.stat-num {
  font-size: 18px;
}

.stat-label {
  font-size: 11px;
  color: var(--c-text-secondary, #666);
  margin-top: 2px;
}

.slider-input-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.flex-1 {
  flex: 1;
}

.form-help-text {
  font-size: 11px;
  color: var(--c-text-secondary, #888);
  margin-top: 4px;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.switch-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #666);
}

.cases-pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.synthesized-cases-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 460px;
  overflow-y: auto;
}

.case-item-card {
  padding: 12px 14px;
  border: 1px solid var(--c-border-subtle, #e8e8e8);
  border-radius: 6px;
  background: var(--c-bg-surface, #ffffff);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.case-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.case-title {
  font-size: 13px;
}

.case-meta {
  display: flex;
  gap: 16px;
  color: var(--c-text-secondary, #666);
}

.case-code-box {
  background: #fcfcfc;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  padding: 8px;
}

.code-pre {
  margin: 0;
  white-space: pre-wrap;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.text-danger {
  color: #ff4d4f;
}

.text-warning {
  color: #faad14;
}

.text-primary {
  color: #1677ff;
}

.text-secondary {
  color: var(--c-text-secondary, #666);
}
</style>
