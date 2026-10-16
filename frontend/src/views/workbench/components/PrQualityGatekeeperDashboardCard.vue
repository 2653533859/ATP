<template>
  <div class="pr-quality-gatekeeper-card">
    <div class="card-header">
      <div class="header-left">
        <SafetyCertificateOutlined class="card-icon" />
        <span class="card-title">CI/CD PR 全要素质量门禁合并准入仲裁卡片</span>
        <a-tag v-if="currentReport" :color="getVerdictTagColor(currentReport.verdict)" class="verdict-pill">
          <component :is="getVerdictIcon(currentReport.verdict)" />
          <span>{{ getVerdictLabel(currentReport.verdict) }}</span>
        </a-tag>
      </div>

      <div class="header-right">
        <a-space size="small">
          <a-button size="small" :loading="evaluating" @click="loadInitialReport">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" @click="applyPreset('approved')">
            预设: 准入放行
          </a-button>
          <a-button size="small" @click="applyPreset('blocked')">
            预设: 变异分不足阻断
          </a-button>
          <a-button size="small" @click="applyPreset('conditional')">
            预设: 高危双人签批
          </a-button>
          <a-button type="primary" size="small" @click="showCustomModal = true">
            <SlidersOutlined /> 自定义裁决评估
          </a-button>
        </a-space>
      </div>
    </div>

    <a-spin :spinning="evaluating">
      <div v-if="currentReport" class="card-body">
        <!-- 核心裁决结果大横幅 -->
        <div class="verdict-banner" :class="`banner-verdict-${currentReport.verdict.toLowerCase()}`">
          <div class="verdict-left">
            <div class="verdict-badge-box">
              <span class="verdict-tag-big">{{ getVerdictLabel(currentReport.verdict) }}</span>
              <span class="mergeable-text" :class="currentReport.is_mergeable ? 'text-mergeable' : 'text-unmergeable'">
                {{ currentReport.is_mergeable ? '✓ 允许合并入目标分支' : '✗ 阻断合流 / 禁止 Merge' }}
              </span>
            </div>
          </div>

          <div class="verdict-center">
            <div class="meta-row">
              <span class="meta-item">PR 编号: <strong>{{ currentReport.pr_id }}</strong></span>
              <span class="meta-item">Commit: <code>{{ currentReport.commit_sha.slice(0, 7) }}</code></span>
              <span class="meta-item">作者: {{ currentReport.author }}</span>
              <span class="meta-item">目标分支: <code>{{ currentReport.target_branch }}</code></span>
            </div>
            <div class="reasons-summary">
              <div v-if="currentReport.blocking_reasons.length > 0" class="reason-block">
                <span class="reason-label text-danger">阻断项 ({{ currentReport.blocking_reasons.length }}):</span>
                <span class="reason-val">{{ currentReport.blocking_reasons.join('；') }}</span>
              </div>
              <div v-if="currentReport.warning_reasons.length > 0" class="reason-block">
                <span class="reason-label text-warning">告警项 ({{ currentReport.warning_reasons.length }}):</span>
                <span class="reason-val">{{ currentReport.warning_reasons.join('；') }}</span>
              </div>
              <div v-if="currentReport.blocking_reasons.length === 0 && currentReport.warning_reasons.length === 0" class="reason-block">
                <span class="reason-label text-success">合规状态:</span>
                <span class="reason-val text-success">所有硬性单测、代码变异充分度及安全审批规则全部通过！</span>
              </div>
            </div>
          </div>

          <div class="verdict-right">
            <div class="compliance-box">
              <span class="compliance-score">{{ currentReport.overall_compliance_score }}%</span>
              <span class="compliance-label">门禁合规得分</span>
            </div>
          </div>
        </div>

        <!-- 规则裁决详细矩阵表格 -->
        <div class="section-title-bar">
          <span class="section-title">全要素质量门禁规则裁决矩阵 (Gate Rules Matrix)</span>
          <span class="section-sub">共 {{ currentReport.evaluated_rules.length }} 项企业级红线检查</span>
        </div>

        <a-table
          :data-source="currentReport.evaluated_rules"
          :columns="columns"
          row-key="rule_id"
          size="small"
          :pagination="false"
          class="rules-table"
        >
          <template #bodyCell="{ column, record }">
            <!-- 规则名称 -->
            <template v-if="column.key === 'rule_name'">
              <div class="rule-name-cell">
                <span class="rule-title">{{ record.rule_name }}</span>
                <span class="rule-id-text">ID: {{ record.rule_id }}</span>
              </div>
            </template>

            <!-- 裁决状态 -->
            <template v-else-if="column.key === 'passed'">
              <a-tag :color="record.passed ? 'success' : (record.severity === 'blocking' ? 'error' : 'warning')">
                <CheckCircleOutlined v-if="record.passed" />
                <CloseCircleOutlined v-else />
                <span style="margin-left: 4px">{{ record.passed ? '通过' : '未通过' }}</span>
              </a-tag>
            </template>

            <!-- 严重度 -->
            <template v-else-if="column.key === 'severity'">
              <a-tag :color="record.severity === 'blocking' ? 'red' : 'orange'" size="small">
                {{ record.severity === 'blocking' ? '阻断级 (Blocking)' : '警告级 (Warning)' }}
              </a-tag>
            </template>

            <!-- 实测值 vs 阈值 -->
            <template v-else-if="column.key === 'metrics'">
              <div class="metrics-cell">
                <span class="val-text" :class="record.passed ? 'text-success' : 'text-danger'">
                  实测: {{ formatVal(record.measured_value) }}
                </span>
                <span class="threshold-text">阈值: {{ formatVal(record.threshold_value) }}</span>
              </div>
            </template>

            <!-- 裁决信息 -->
            <template v-else-if="column.key === 'message'">
              <span class="message-text" :class="{ 'text-danger': !record.passed && record.severity === 'blocking' }">
                {{ record.message }}
              </span>
            </template>
          </template>
        </a-table>

        <!-- 整改行动项清单 (Remediation Steps) -->
        <div class="remediation-panel">
          <div class="remediation-header">
            <span class="panel-heading">
              <ToolOutlined /> 整改行动项与放行指南 (Remediation Steps)
            </span>
          </div>
          <div v-if="currentReport.remediation_steps.length > 0" class="remediation-steps-list">
            <div
              v-for="(step, idx) in currentReport.remediation_steps"
              :key="idx"
              class="step-item"
            >
              <span class="step-num">{{ idx + 1 }}</span>
              <span class="step-text">{{ step }}</span>
            </div>
          </div>
          <div v-else class="no-remediation">
            <CheckCircleOutlined class="text-success" />
            <span>无待整改项，当前 PR 满足所有合并红线，可随时由 Reviewer 确认合流！</span>
          </div>
        </div>
      </div>
    </a-spin>

    <!-- 自定义 PR 门禁评估模态框 -->
    <a-modal
      v-model:open="showCustomModal"
      title="自定义 PR 质量门禁合流裁决模拟"
      @ok="handleCustomSubmit"
    >
      <a-form layout="vertical">
        <a-form-item label="PR 编号与 Commit:">
          <a-space>
            <a-input v-model:value="customForm.pr_id" placeholder="#1024" style="width: 120px" />
            <a-input v-model:value="customForm.commit_sha" placeholder="commit sha" style="width: 180px" />
          </a-space>
        </a-form-item>
        <a-form-item label="单元测试通过率 (%):">
          <a-input-number v-model:value="customForm.test_pass_rate_pct" :min="0" :max="100" style="width: 140px" />
        </a-form-item>
        <a-form-item label="代码变异测试得分 (%):">
          <a-input-number v-model:value="customForm.mutation_score_pct" :min="0" :max="100" style="width: 140px" />
        </a-form-item>
        <a-form-item label="变更风险等级:">
          <a-select v-model:value="customForm.risk_level" style="width: 140px">
            <a-select-option value="LOW">LOW (低危)</a-select-option>
            <a-select-option value="MEDIUM">MEDIUM (中危)</a-select-option>
            <a-select-option value="HIGH">HIGH (高危)</a-select-option>
            <a-select-option value="CRITICAL">CRITICAL (极高危)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="是否具备双人专家审批复核:">
          <a-switch v-model:checked="customForm.has_dual_approvals" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ReloadOutlined,
  SlidersOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ToolOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type MergeGateVerdict,
  type PrGateVerdictReport,
} from '@/api/ciImpact'

const evaluating = ref(false)
const showCustomModal = ref(false)
const currentReport = ref<PrGateVerdictReport | null>(null)

const customForm = reactive({
  pr_id: '#1024',
  commit_sha: 'a1b2c3d4e5f',
  author: 'dev-lead',
  target_branch: 'main',
  test_pass_rate_pct: 100.0,
  test_failed_cases_count: 0,
  mutation_score_pct: 85.0,
  risk_level: 'LOW',
  has_dual_approvals: false,
})

const columns = [
  {
    title: '门禁规则名称',
    key: 'rule_name',
    width: 240,
  },
  {
    title: '判定结果',
    key: 'passed',
    width: 110,
  },
  {
    title: '规则严重度',
    key: 'severity',
    width: 140,
  },
  {
    title: '实测指标 vs 阈值',
    key: 'metrics',
    width: 220,
  },
  {
    title: '裁决依据与说明',
    key: 'message',
  },
]

// 预设样例数据
const PRESET_APPROVED: PrGateVerdictReport = {
  gate_id: 'gate_approved_001',
  pr_id: '#1024',
  commit_sha: 'a1b2c3d4e5f',
  author: 'dev-alice',
  target_branch: 'main',
  verdict: 'MERGE_APPROVED',
  is_mergeable: true,
  overall_compliance_score: 100.0,
  blocking_reasons: [],
  warning_reasons: [],
  evaluated_rules: [
    {
      rule_id: 'RULE_UNIT_TEST_PASS_RATE',
      rule_name: '单元测试全量通过硬门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '100.0%',
      threshold_value: '>= 100.0%',
      message: '单元测试通过率 100.0% 达到硬性准入标准 (0 失败用例)',
    },
    {
      rule_id: 'RULE_MUTATION_SCORE',
      rule_name: '代码变异测试充分性门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '85.0%',
      threshold_value: '>= 70.0%',
      message: '代码变异得分 85.0% 达到断言充分性门禁阈值',
    },
    {
      rule_id: 'RULE_CRITICAL_CHANGE_APPROVAL',
      rule_name: 'CRITICAL 极高危变更双人签批',
      passed: true,
      severity: 'blocking',
      measured_value: 'LOW (无需双人审批)',
      threshold_value: '双人已签批',
      message: '变更风险等级为 LOW，无需双人同行评审',
    },
  ],
  remediation_steps: [],
  evaluated_at: '2026-10-16T14:00:00Z',
}

const PRESET_BLOCKED: PrGateVerdictReport = {
  gate_id: 'gate_blocked_002',
  pr_id: '#1025',
  commit_sha: 'c3d4e5f6a7b',
  author: 'dev-bob',
  target_branch: 'main',
  verdict: 'MERGE_BLOCKED',
  is_mergeable: false,
  overall_compliance_score: 50.0,
  blocking_reasons: ['代码变异得分 50.0% 低于硬性门禁阈值 70.0% (存在严重断言盲区)'],
  warning_reasons: [],
  evaluated_rules: [
    {
      rule_id: 'RULE_UNIT_TEST_PASS_RATE',
      rule_name: '单元测试全量通过硬门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '100.0%',
      threshold_value: '>= 100.0%',
      message: '单元测试通过率 100.0% 达标',
    },
    {
      rule_id: 'RULE_MUTATION_SCORE',
      rule_name: '代码变异测试充分性门禁',
      passed: false,
      severity: 'blocking',
      measured_value: '50.0%',
      threshold_value: '>= 70.0%',
      message: '代码变异得分 50.0% 严重低于 70.0% 门禁线，存活变异体过多，暴露严重断言缺失',
    },
  ],
  remediation_steps: [
    '查看代码变异测试热力报告，定位存活变异体所在的代码行',
    '针对存活的一阶语法变异体补充针对性断言（如边界值 assert），重新运行变异测试使得分 ≥ 70%',
  ],
  evaluated_at: '2026-10-16T14:05:00Z',
}

const PRESET_CONDITIONAL: PrGateVerdictReport = {
  gate_id: 'gate_conditional_003',
  pr_id: '#1026',
  commit_sha: 'e5f6a7b8c9d',
  author: 'dev-charlie',
  target_branch: 'main',
  verdict: 'CONDITIONAL_PASS',
  is_mergeable: false,
  overall_compliance_score: 75.0,
  blocking_reasons: [],
  warning_reasons: ['变更风险评定为 CRITICAL 极高危，缺少双人同行专家审批签字'],
  evaluated_rules: [
    {
      rule_id: 'RULE_UNIT_TEST_PASS_RATE',
      rule_name: '单元测试全量通过硬门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '100.0%',
      threshold_value: '>= 100.0%',
      message: '单测通过率达标',
    },
    {
      rule_id: 'RULE_MUTATION_SCORE',
      rule_name: '代码变异测试充分性门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '88.0%',
      threshold_value: '>= 70.0%',
      message: '变异得分达标',
    },
    {
      rule_id: 'RULE_CRITICAL_CHANGE_APPROVAL',
      rule_name: 'CRITICAL 极高危变更双人签批',
      passed: false,
      severity: 'warning',
      measured_value: '未签批 (has_dual_approvals = false)',
      threshold_value: '至少 2 位专家 Approve',
      message: '触及核心敏感涉密模块，需在 PR 中满足双人审核',
    },
  ],
  remediation_steps: [
    '邀请至少 2 位研发专家或架构师完成 PR Code Review 并给出显式 Approve',
  ],
  evaluated_at: '2026-10-16T14:10:00Z',
}

const getVerdictTagColor = (verdict: MergeGateVerdict) => {
  switch (verdict) {
    case 'MERGE_APPROVED': return 'success'
    case 'MERGE_BLOCKED': return 'error'
    case 'CONDITIONAL_PASS': return 'warning'
    default: return 'default'
  }
}

const getVerdictIcon = (verdict: MergeGateVerdict) => {
  switch (verdict) {
    case 'MERGE_APPROVED': return CheckCircleOutlined
    case 'MERGE_BLOCKED': return CloseCircleOutlined
    case 'CONDITIONAL_PASS': return ExclamationCircleOutlined
    default: return SafetyCertificateOutlined
  }
}

const getVerdictLabel = (verdict: MergeGateVerdict) => {
  switch (verdict) {
    case 'MERGE_APPROVED': return 'MERGE_APPROVED (准入通过)'
    case 'MERGE_BLOCKED': return 'MERGE_BLOCKED (阻断合流)'
    case 'CONDITIONAL_PASS': return 'CONDITIONAL_PASS (带条件放行)'
    default: return verdict
  }
}

const formatVal = (val: any) => {
  if (val === null || val === undefined) return '-'
  return String(val)
}

const applyPreset = (type: 'approved' | 'blocked' | 'conditional') => {
  if (type === 'approved') currentReport.value = PRESET_APPROVED
  else if (type === 'blocked') currentReport.value = PRESET_BLOCKED
  else currentReport.value = PRESET_CONDITIONAL
  message.info(`已切换至「${type}」预设门禁裁决结果`)
}

const loadInitialReport = async () => {
  evaluating.value = true
  try {
    const res = await ciImpactApi.listPrGateReports()
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
    } else {
      currentReport.value = PRESET_APPROVED
    }
  } catch {
    currentReport.value = PRESET_APPROVED
  } finally {
    evaluating.value = false
  }
}

const handleCustomSubmit = async () => {
  evaluating.value = true
  showCustomModal.value = false
  try {
    const res = await ciImpactApi.evaluatePrGate({
      pr_id: customForm.pr_id,
      commit_sha: customForm.commit_sha,
      author: customForm.author,
      target_branch: customForm.target_branch,
      test_pass_rate_pct: customForm.test_pass_rate_pct,
      test_failed_cases_count: customForm.test_failed_cases_count,
      mutation_score_pct: customForm.mutation_score_pct,
      risk_level: customForm.risk_level,
      has_dual_approvals: customForm.has_dual_approvals,
    })
    currentReport.value = res.report
    message.success(res.message || 'PR 质量门禁准入裁决完成')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '门禁评估失败')
  } finally {
    evaluating.value = false
  }
}

onMounted(() => {
  loadInitialReport()
})
</script>

<style scoped>
.pr-quality-gatekeeper-card {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.card-header {
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-icon {
  font-size: 18px;
  color: #0284c7;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.verdict-pill {
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.card-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 核心裁决横幅 */
.verdict-banner {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 14px 18px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  transition: all 0.3s ease;
}

.banner-verdict-merge_approved {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border-color: #86efac;
}

.banner-verdict-merge_blocked {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border-color: #fca5a5;
}

.banner-verdict-conditional_pass {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-color: #fcd34d;
}

.verdict-left {
  flex-shrink: 0;
}

.verdict-badge-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 16px;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.verdict-tag-big {
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
}

.mergeable-text {
  font-size: 11px;
  font-weight: 700;
  margin-top: 4px;
}

.text-mergeable { color: #16a34a; }
.text-unmergeable { color: #dc2626; }

.verdict-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: #475569;
  flex-wrap: wrap;
}

.reasons-summary {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.reason-block {
  font-size: 12px;
  display: flex;
  gap: 6px;
}

.reason-label {
  font-weight: 700;
  flex-shrink: 0;
}

.reason-val {
  color: #334155;
}

.verdict-right {
  flex-shrink: 0;
}

.compliance-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 90px;
  height: 70px;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.compliance-score {
  font-size: 20px;
  font-weight: 800;
  color: #0284c7;
}

.compliance-label {
  font-size: 10px;
  color: #64748b;
}

/* 矩阵区域 */
.section-title-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.section-sub {
  font-size: 11px;
  color: #64748b;
}

.rule-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rule-title {
  font-weight: 600;
  color: #0f172a;
}

.rule-id-text {
  font-size: 10px;
  color: #94a3b8;
  font-family: monospace;
}

.metrics-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  font-family: monospace;
}

.val-text { font-weight: 600; }
.threshold-text { color: #64748b; }

.message-text {
  font-size: 12px;
  color: #334155;
}

.text-danger { color: #dc2626; }
.text-warning { color: #d97706; }
.text-success { color: #16a34a; }

/* 整改行动项 */
.remediation-panel {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  background: #f8fafc;
  padding: 12px 14px;
}

.remediation-header {
  margin-bottom: 8px;
}

.panel-heading {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.remediation-steps-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.step-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  color: #334155;
}

.step-num {
  font-size: 11px;
  font-weight: 700;
  background: #fee2e2;
  color: #dc2626;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.no-remediation {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #16a34a;
  font-weight: 600;
}
</style>
