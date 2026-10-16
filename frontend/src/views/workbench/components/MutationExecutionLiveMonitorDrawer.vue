<template>
  <a-drawer
    :open="open"
    :width="1060"
    placement="right"
    title="变异体沙箱执行实时进度与击毙/存活监控工作台"
    destroy-on-close
    class="mutation-monitor-drawer"
    @close="handleClose"
  >
    <div class="mutation-drawer-content">
      <!-- 头部介绍条 -->
      <div class="drawer-banner">
        <div class="banner-title">
          <BugOutlined class="banner-icon" />
          <span>变异体沙箱动态执行与击杀捕获流水线 (Mutation Execution Sandbox)</span>
        </div>
        <p class="banner-desc">
          在隔离沙箱中逐一注入一阶语法变异体并执行自动化测试套件。若测试用例失败抛出 AssertionError，表明变异体被成功击毙（Killed）；若用例全部无感通过，则变异体存活（Survived），直接暴露用例断言的盲区！
        </p>
      </div>

      <!-- 执行配置与操作栏 -->
      <div class="exec-control-card">
        <div class="control-row">
          <div class="control-col">
            <span class="control-label">待验证变异体清单:</span>
            <a-input
              v-model:value="mutantIdsInput"
              placeholder="输入变异体 ID（英文逗号分隔），或点击右侧载入"
              style="width: 380px"
              size="small"
            />
            <a-button size="small" type="link" @click="loadSampleMutants">
              载入示例变异体 (3个)
            </a-button>
          </div>
          <div class="control-col">
            <span class="control-label">单变异体超时:</span>
            <a-input-number
              v-model:value="timeoutSec"
              :min="0.5"
              :max="30"
              :step="0.5"
              size="small"
              style="width: 80px"
            />
            <span class="unit-text">秒</span>
          </div>
          <a-button
            type="primary"
            size="small"
            :loading="executing"
            class="start-btn"
            @click="handleRunExecution"
          >
            <PlayCircleOutlined /> 运行变异体沙箱验证
          </a-button>
        </div>
      </div>

      <!-- 核心指标看板 (KPI Cards) -->
      <div v-if="report" class="kpi-banner-grid">
        <div class="kpi-metric-card">
          <span class="metric-label">已验证变异体总数</span>
          <span class="metric-value text-default">{{ report.total_mutants_tested }}</span>
          <span class="metric-sub">执行耗时总计 {{ totalDurationMs }} ms</span>
        </div>
        <div class="kpi-metric-card">
          <span class="metric-label">变异体被击毙 (KILLED)</span>
          <span class="metric-value text-success">{{ report.killed_count }}</span>
          <span class="metric-sub">断言成功拦截缺陷</span>
        </div>
        <div class="kpi-metric-card">
          <span class="metric-label">变异体存活 (SURVIVED)</span>
          <span class="metric-value text-danger">{{ report.survived_count }}</span>
          <span class="metric-sub">断言盲区/漏网之鱼</span>
        </div>
        <div class="kpi-metric-card">
          <span class="metric-label">变异引发超时 (TIMED OUT)</span>
          <span class="metric-value text-warning">{{ report.timed_out_count }}</span>
          <span class="metric-sub">死循环/超时视同捕获</span>
        </div>
        <div class="kpi-metric-card kpi-rate-card">
          <span class="metric-label">综合击毙率 (Kill Rate)</span>
          <div class="rate-box">
            <span class="metric-value text-rate">{{ report.kill_rate_pct }}%</span>
            <a-progress
              :percent="report.kill_rate_pct"
              size="small"
              :status="report.kill_rate_pct >= 80 ? 'success' : 'exception'"
              :show-info="false"
              class="rate-progress"
            />
          </div>
          <span class="metric-sub">
            {{ report.kill_rate_pct >= 80 ? '测试断言质量极高' : '存在显著断言盲区，需补充断言' }}
          </span>
        </div>
      </div>

      <!-- 变异体执行结果状态流与表格 -->
      <a-spin :spinning="executing">
        <div v-if="report" class="results-table-panel">
          <div class="table-header-bar">
            <div class="header-left">
              <span class="table-title">变异体验证结果明细 ({{ filteredResults.length }} / {{ report.results.length }})</span>
              <a-radio-group v-model:value="statusFilter" size="small" button-style="solid">
                <a-radio-button value="ALL">全部 ({{ report.results.length }})</a-radio-button>
                <a-radio-button value="KILLED">仅击毙 ({{ report.killed_count }})</a-radio-button>
                <a-radio-button value="SURVIVED">仅存活 ({{ report.survived_count }})</a-radio-button>
                <a-radio-button value="TIMED_OUT">超时 ({{ report.timed_out_count }})</a-radio-button>
              </a-radio-group>
            </div>
            <div class="header-right">
              <a-tag v-if="report.survived_count === 0" color="green">
                <CheckCircleOutlined /> 100% 变异体全数击毙
              </a-tag>
              <a-tag v-else color="red">
                <ExclamationCircleOutlined /> 检出 {{ report.survived_count }} 个存活变异体
              </a-tag>
            </div>
          </div>

          <a-table
            :data-source="filteredResults"
            :columns="columns"
            row-key="mutant_id"
            size="small"
            :pagination="{ pageSize: 8, showTotal: (t: number) => `共 ${t} 个变异体验证记录` }"
          >
            <!-- 变异体基本信息 -->
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'mutant_info'">
                <div class="mutant-info-cell">
                  <div class="mutant-top">
                    <a-tag :color="getOperatorColor(record.operator_type)" size="small">
                      {{ record.operator_type }}
                    </a-tag>
                    <span class="line-badge">Line {{ record.line_number }}</span>
                    <span class="mutant-id-text">ID: {{ record.mutant_id.slice(0, 8) }}</span>
                  </div>
                  <div class="mutant-desc-text">{{ record.description }}</div>
                </div>
              </template>

              <!-- 执行状态徽章 -->
              <template v-else-if="column.key === 'status'">
                <a-tag :color="getStatusTagColor(record.status)" class="status-tag">
                  <component :is="getStatusIcon(record.status)" />
                  <span class="status-name">{{ record.status }}</span>
                </a-tag>
              </template>

              <!-- 耗时 -->
              <template v-else-if="column.key === 'duration'">
                <span class="duration-text">{{ record.execution_duration_ms }} ms</span>
              </template>

              <!-- 击毙定位与异常信息 -->
              <template v-else-if="column.key === 'killing_case'">
                <div v-if="record.status === 'KILLED'" class="killing-cell">
                  <div class="case-badge">
                    <CheckCircleOutlined class="text-success" />
                    <span class="case-name">
                      {{ record.killing_test_case_name || ('用例 #' + record.killing_test_case_id) }}
                    </span>
                  </div>
                  <div v-if="record.error_message" class="error-msg-box">
                    <code>{{ record.error_message }}</code>
                  </div>
                </div>
                <div v-else-if="record.status === 'SURVIVED'" class="survived-cell">
                  <span class="survived-warn">
                    <ExclamationCircleOutlined /> 变异体存活：所有用例测试均未拦截该代码篡改！
                  </span>
                </div>
                <div v-else-if="record.status === 'TIMED_OUT'" class="timeout-cell">
                  <span class="timeout-text">执行超时（超过 {{ timeoutSec }} 秒上限）</span>
                </div>
                <div v-else class="error-cell">
                  <span class="error-text">{{ record.error_message || '沙箱执行异常' }}</span>
                </div>
              </template>
            </template>
          </a-table>
        </div>
      </a-spin>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  BugOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type MutantStatus,
  type MutationExecutionRunReport,
} from '@/api/ciImpact'

const props = defineProps<{
  open: boolean
  initialMutantIds?: string[]
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'execution-finished', report: MutationExecutionRunReport): void
}>()

const mutantIdsInput = ref(props.initialMutantIds?.join(', ') || '')
const timeoutSec = ref(3.0)
const executing = ref(false)
const statusFilter = ref<'ALL' | MutantStatus>('ALL')

const report = ref<MutationExecutionRunReport | null>(null)

const columns = [
  {
    title: '变异体与算子',
    key: 'mutant_info',
    width: 280,
  },
  {
    title: '执行状态',
    key: 'status',
    width: 130,
  },
  {
    title: '耗时',
    key: 'duration',
    width: 90,
  },
  {
    title: '击毙用例定位与断言拦截分析',
    key: 'killing_case',
  },
]

const SAMPLE_MUTANTS = [
  'mut_ror_demo_01',
  'mut_lcr_demo_02',
  'mut_aor_demo_03',
]

const loadSampleMutants = () => {
  mutantIdsInput.value = SAMPLE_MUTANTS.join(', ')
  message.info('已载入 3 个示例变异体 ID')
}

const parseMutantIds = (): string[] => {
  if (!mutantIdsInput.value.trim()) return []
  return mutantIdsInput.value
    .split(/[,，\s]+/)
    .map(s => s.trim())
    .filter(Boolean)
}

const totalDurationMs = computed(() => {
  if (!report.value?.results) return 0
  const sum = report.value.results.reduce((acc, r) => acc + (r.execution_duration_ms || 0), 0)
  return Math.round(sum)
})

const filteredResults = computed(() => {
  if (!report.value?.results) return []
  if (statusFilter.value === 'ALL') return report.value.results
  return report.value.results.filter(r => r.status === statusFilter.value)
})

const getOperatorColor = (op: string) => {
  switch (op) {
    case 'ROR': return 'magenta'
    case 'LCR': return 'purple'
    case 'AOR': return 'blue'
    case 'RVO': return 'red'
    case 'BVO': return 'orange'
    default: return 'cyan'
  }
}

const getStatusTagColor = (status: MutantStatus) => {
  switch (status) {
    case 'KILLED': return 'success'
    case 'SURVIVED': return 'error'
    case 'TIMED_OUT': return 'warning'
    case 'ERROR': return 'default'
  }
}

const getStatusIcon = (status: MutantStatus) => {
  switch (status) {
    case 'KILLED': return CheckCircleOutlined
    case 'SURVIVED': return ExclamationCircleOutlined
    case 'TIMED_OUT': return ClockCircleOutlined
    case 'ERROR': return CloseCircleOutlined
  }
}

const handleRunExecution = async () => {
  const ids = parseMutantIds()
  if (ids.length === 0) {
    message.warning('请输入或载入至少一个待验证的变异体 ID')
    return
  }

  executing.value = true
  try {
    const res = await ciImpactApi.runMutationExecution({
      mutant_ids: ids,
      timeout_sec_per_mutant: timeoutSec.value,
    })

    report.value = res.report
    message.success(res.message || `变异体验证执行完成，击毙率 ${res.report.kill_rate_pct}%`)
    emit('execution-finished', res.report)
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '变异体验证执行失败')
  } finally {
    executing.value = false
  }
}

const handleClose = () => {
  emit('update:open', false)
}

watch(
  () => props.open,
  (newVal) => {
    if (newVal) {
      if (props.initialMutantIds && props.initialMutantIds.length > 0) {
        mutantIdsInput.value = props.initialMutantIds.join(', ')
      } else if (!mutantIdsInput.value) {
        mutantIdsInput.value = SAMPLE_MUTANTS.join(', ')
      }
      if (!report.value) {
        handleRunExecution()
      }
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.mutation-drawer-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-banner {
  background: linear-gradient(135deg, #fef2f2 0%, #fff7ed 100%);
  border: 1px solid #fed7aa;
  border-radius: 8px;
  padding: 12px 16px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #c2410c;
  margin-bottom: 4px;
}

.banner-icon {
  font-size: 18px;
  color: #ea580c;
}

.banner-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin: 0;
}

.exec-control-card {
  padding: 12px 14px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #f8fafc;
}

.control-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.control-col {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.unit-text {
  font-size: 12px;
  color: #64748b;
}

.start-btn {
  margin-left: auto;
}

/* KPI 卡片 */
.kpi-banner-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.kpi-metric-card {
  padding: 10px 14px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.metric-label {
  font-size: 12px;
  color: #64748b;
}

.metric-value {
  font-size: 22px;
  font-weight: 700;
  margin: 2px 0;
}

.metric-sub {
  font-size: 11px;
  color: #94a3b8;
}

.text-default { color: #0284c7; }
.text-success { color: #16a34a; }
.text-danger { color: #dc2626; }
.text-warning { color: #d97706; }
.text-rate { color: #0891b2; }

.kpi-rate-card .rate-box {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.rate-progress {
  flex: 1;
  margin-bottom: 0;
}

/* 结果表格面板 */
.results-table-panel {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.table-header-bar {
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.mutant-info-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mutant-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.line-badge {
  font-size: 11px;
  font-weight: 600;
  color: #334155;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
}

.mutant-id-text {
  font-size: 11px;
  color: #94a3b8;
  font-family: monospace;
}

.mutant-desc-text {
  font-size: 12px;
  color: #475569;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  padding: 2px 8px;
}

.duration-text {
  font-size: 12px;
  font-family: monospace;
  color: #64748b;
}

.killing-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.case-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #15803d;
}

.error-msg-box code {
  font-size: 11px;
  color: #b91c1c;
  background: #fee2e2;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.survived-cell {
  padding: 4px 0;
}

.survived-warn {
  font-size: 12px;
  color: #dc2626;
  font-weight: 600;
}

.timeout-text {
  font-size: 12px;
  color: #d97706;
}

.error-text {
  font-size: 12px;
  color: #64748b;
}
</style>
