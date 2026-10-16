<template>
  <div class="page-shell mutation-score-report-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <FireOutlined class="hero-icon" />
          <h2 class="page-title">用例变异得分 (Mutation Score) 与断言盲区热力大盘</h2>
        </div>
        <p class="page-subtitle">
          量化单元测试集真实缺陷击毙能力与断言充分性等级（EXCELLENT ~ WEAK），通过五大算子雷达分布与代码行级盲区热力，精准暴露「跑了用例却无实质断言」的漏网之鱼。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button :loading="loading" size="small" @click="loadData">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" @click="applyPreset('excellent')">
            示例: 卓越断言 (88%)
          </a-button>
          <a-button size="small" @click="applyPreset('insufficient')">
            示例: 存在断言盲区 (50%)
          </a-button>
          <a-button type="primary" size="small" @click="showCalcModal = true">
            <CalculatorOutlined /> 重算变异得分
          </a-button>
        </a-space>
      </div>
    </header>

    <a-spin :spinning="loading">
      <template v-if="currentReport">
        <!-- 综合变异得分与充分性评级裁决大横幅 -->
        <div class="verdict-banner" :class="`banner-level-${currentReport.adequacy_level.toLowerCase()}`">
          <div class="score-circle-box">
            <div class="score-circle">
              <span class="score-num">{{ currentReport.mutation_score_pct.toFixed(1) }}%</span>
              <span class="score-lbl">变异得分</span>
            </div>
          </div>

          <div class="verdict-content">
            <div class="verdict-header">
              <span class="verdict-title">测试套件断言充分性裁决:</span>
              <a-tag :color="getLevelTagColor(currentReport.adequacy_level)" class="level-tag">
                {{ getLevelLabel(currentReport.adequacy_level) }}
              </a-tag>
              <span class="report-meta">
                报告 ID: <code>{{ currentReport.score_id }}</code> | 关联执行 Run: <code>{{ currentReport.execution_run_id }}</code>
              </span>
            </div>

            <p class="verdict-text">{{ currentReport.summary_verdict }}</p>

            <div class="action-guidance">
              <span class="guidance-prefix">
                <SafetyCertificateOutlined /> 质量门禁准入建议:
              </span>
              <span v-if="currentReport.adequacy_level === 'EXCELLENT'" class="guidance-text text-success">
                通过准入门禁 (≥85%)：单元测试断言覆盖度极其可靠，对边界与逻辑篡改均具备强大的捕获能力。
              </span>
              <span v-else-if="currentReport.adequacy_level === 'ADEQUATE'" class="guidance-text text-primary">
                准予通过 (70% ~ 84.9%)：已达到企业级基线门禁要求，建议针对存活变异体补充部分防御性断言。
              </span>
              <span v-else-if="currentReport.adequacy_level === 'INSUFFICIENT'" class="guidance-text text-warning">
                门禁告警 (50% ~ 69.9%)：半数一阶篡改未被用例断言捕获，需依据下方热力清单限期补齐断言。
              </span>
              <span v-else class="guidance-text text-danger">
                阻断合流门禁 (&lt;50%)：大量存活变异体表明用例断言形同虚设，必须重构用例断言逻辑后方可合并。
              </span>
            </div>
          </div>
        </div>

        <!-- 4 大指标拆解卡片 -->
        <div class="kpi-grid">
          <div class="kpi-card">
            <span class="kpi-label">已注入变异体总数</span>
            <span class="kpi-val text-primary">{{ currentReport.total_mutants }}</span>
            <span class="kpi-sub">一阶微小语法变异</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">成功击毙变异体 (Killed)</span>
            <span class="kpi-val text-success">{{ currentReport.killed_count }}</span>
            <span class="kpi-sub">用例断言成功生效拦截</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">存活变异体 (Survived)</span>
            <span class="kpi-val text-danger">{{ currentReport.survived_count }}</span>
            <span class="kpi-sub">断言缺失盲区/漏网之鱼</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">超时变异体 (Timed Out)</span>
            <span class="kpi-val text-warning">{{ currentReport.timed_out_count }}</span>
            <span class="kpi-sub">死循环篡改视同拦截</span>
          </div>
        </div>

        <!-- 中间双栏：左侧算子击毙率雷达图，右侧算子细分卡片列表 -->
        <div class="charts-row">
          <div class="chart-panel radar-panel">
            <div class="panel-header">
              <span class="panel-title">五大一阶变异算子击毙率雷达图 (Operator Breakdown)</span>
              <span class="panel-sub">满分 100% | 85% 为卓越基准线</span>
            </div>
            <div class="radar-box">
              <v-chart
                :option="radarChartOption"
                :theme="chartThemeName"
                autoresize
                style="height: 290px; width: 100%"
              />
            </div>
          </div>

          <div class="chart-panel breakdown-panel">
            <div class="panel-header">
              <span class="panel-title">算子分类拦截效能统计</span>
              <a-tag color="blue">一阶精确变异</a-tag>
            </div>
            <div class="breakdown-list">
              <div
                v-for="(item, key) in currentReport.operator_breakdowns"
                :key="key"
                class="breakdown-item"
              >
                <div class="item-top">
                  <a-tag :color="getOperatorColor(String(key))" class="op-tag">{{ key }}</a-tag>
                  <span class="op-name">{{ getOperatorName(String(key)) }}</span>
                  <span class="op-score" :class="getScoreClass(item.operator_mutation_score_pct)">
                    {{ item.operator_mutation_score_pct }}%
                  </span>
                </div>
                <div class="item-progress">
                  <a-progress
                    :percent="item.operator_mutation_score_pct"
                    size="small"
                    :status="item.operator_mutation_score_pct >= 85 ? 'success' : (item.operator_mutation_score_pct >= 60 ? 'normal' : 'exception')"
                  />
                </div>
                <div class="item-stats">
                  <span>总变异: {{ item.total_mutants }}</span>
                  <span class="text-success">击毙: {{ item.killed_mutants }}</span>
                  <span class="text-danger">存活: {{ item.survived_mutants }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部面板：断言盲区代码行级热力清单与修复指引 -->
        <div class="blindspots-panel">
          <div class="panel-header">
            <div class="header-left">
              <span class="panel-title">
                <ExclamationCircleOutlined class="text-danger" />
                断言盲区代码行级热力清单 (Assertion Blindspots: {{ currentReport.blindspots.length }})
              </span>
              <a-radio-group v-model:value="operatorFilter" size="small" button-style="solid">
                <a-radio-button value="ALL">全部 ({{ currentReport.blindspots.length }})</a-radio-button>
                <a-radio-button v-for="op in uniqueOperators" :key="op" :value="op">
                  {{ op }}
                </a-radio-button>
              </a-radio-group>
            </div>
            <div class="header-right">
              <a-tag v-if="currentReport.blindspots.length === 0" color="green">
                <CheckCircleOutlined /> 完美！当前无任何断言盲区
              </a-tag>
              <a-tag v-else color="red">
                需补齐 {{ currentReport.blindspots.length }} 处代码行断言
              </a-tag>
            </div>
          </div>

          <a-table
            :data-source="filteredBlindspots"
            :columns="blindspotColumns"
            row-key="mutant_id"
            size="small"
            :pagination="{ pageSize: 6, showTotal: (t: number) => `共 ${t} 处断言盲区代码行` }"
          >
            <template #bodyCell="{ column, record }">
              <!-- 位置 -->
              <template v-if="column.key === 'location'">
                <div class="loc-cell">
                  <span class="file-name">{{ record.file_path }}</span>
                  <span class="line-badge">Line {{ record.line_number }}</span>
                </div>
              </template>

              <!-- 算子 -->
              <template v-else-if="column.key === 'operator'">
                <a-tag :color="getOperatorColor(record.operator_type)">
                  {{ record.operator_type }}
                </a-tag>
              </template>

              <!-- 代码行差异 -->
              <template v-else-if="column.key === 'code_diff'">
                <div class="code-diff-box">
                  <div class="code-line old-line">
                    <span class="line-tag">原:</span>
                    <code>{{ record.original_line }}</code>
                  </div>
                  <div class="code-line new-line">
                    <span class="line-tag">变:</span>
                    <code>{{ record.mutated_line }}</code>
                  </div>
                  <div class="code-desc">{{ record.description }}</div>
                </div>
              </template>

              <!-- 修复指引 -->
              <template v-else-if="column.key === 'fix_guidance'">
                <div class="fix-cell">
                  <div class="fix-text">{{ record.suggested_assertion_fix }}</div>
                  <a-button size="small" type="link" @click="copyFix(record.suggested_assertion_fix)">
                    <CopyOutlined /> 复制指引
                  </a-button>
                </div>
              </template>
            </template>
          </a-table>
        </div>
      </template>

      <div v-else class="empty-placeholder">
        <a-empty description="暂无变异得分报告数据，请点击右上角重算或载入示例" />
      </div>
    </a-spin>

    <!-- 重算得分模态框 -->
    <a-modal
      v-model:open="showCalcModal"
      title="手动触发用例变异得分计算"
      @ok="handleCalculateSubmit"
    >
      <a-form layout="vertical">
        <a-form-item label="指定变异体执行 Run ID (选填):">
          <a-input
            v-model:value="calcRunId"
            placeholder="留空则自动选用最近一次变异体执行结果"
          />
        </a-form-item>
        <p class="form-hint">
          系统将提取该次沙箱执行报告中所有变异体的 Killed / Survived 状态，严格量化用例集的断言缺陷拦截率与盲区热力清单。
        </p>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import VChart from 'vue-echarts'
import {
  FireOutlined,
  ReloadOutlined,
  CalculatorOutlined,
  SafetyCertificateOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type AssertionAdequacyLevel,
  type MutationScoreReport,
} from '@/api/ciImpact'
import { useChartTheme } from '@/utils/chartTheme'

const { chartTheme: chartThemeName } = useChartTheme()

const loading = ref(false)
const showCalcModal = ref(false)
const calcRunId = ref('')
const operatorFilter = ref('ALL')

const currentReport = ref<MutationScoreReport | null>(null)

const blindspotColumns = [
  {
    title: '代码位置',
    key: 'location',
    width: 200,
  },
  {
    title: '变异算子',
    key: 'operator',
    width: 100,
  },
  {
    title: '代码行差异与篡改说明',
    key: 'code_diff',
  },
  {
    title: '用例断言修复指引 (Suggested Fix)',
    key: 'fix_guidance',
    width: 320,
  },
]

// 预设样例数据
const PRESET_EXCELLENT: MutationScoreReport = {
  score_id: 'score_demo_excellent',
  execution_run_id: 'run_mut_sample_888',
  mutation_score_pct: 87.5,
  adequacy_level: 'EXCELLENT',
  total_mutants: 8,
  killed_count: 7,
  survived_count: 1,
  timed_out_count: 0,
  operator_breakdowns: {
    ROR: { operator_type: 'ROR', total_mutants: 3, killed_mutants: 3, survived_mutants: 0, operator_mutation_score_pct: 100.0 },
    LCR: { operator_type: 'LCR', total_mutants: 2, killed_mutants: 2, survived_mutants: 0, operator_mutation_score_pct: 100.0 },
    AOR: { operator_type: 'AOR', total_mutants: 2, killed_mutants: 1, survived_mutants: 1, operator_mutation_score_pct: 50.0 },
    RVO: { operator_type: 'RVO', total_mutants: 1, killed_mutants: 1, survived_mutants: 0, operator_mutation_score_pct: 100.0 },
  },
  blindspots: [
    {
      mutant_id: 'mut_aor_survived_01',
      file_path: 'discount_service.py',
      line_number: 6,
      operator_type: 'AOR',
      original_line: '    discount = price * 0.20',
      mutated_line: '    discount = price / 0.20',
      description: '将第 6 行的算术运算符 * 替换为 /',
      suggested_assertion_fix: '当前用例断言仅校验了 discount > 0，未显式 assert discount == 20.0，建议补充精确数值断言',
    },
  ],
  summary_verdict: '测试用例集变异得分为 87.50% (7/8 击毙)，达到 EXCELLENT 卓越充分度级别。针对存活变异体补充精确数值断言即可实现 100% 盲区覆盖。',
  calculated_at: '2026-10-16T13:00:00Z',
}

const PRESET_INSUFFICIENT: MutationScoreReport = {
  score_id: 'score_demo_insufficient',
  execution_run_id: 'run_mut_sample_555',
  mutation_score_pct: 50.0,
  adequacy_level: 'INSUFFICIENT',
  total_mutants: 6,
  killed_count: 3,
  survived_count: 3,
  timed_out_count: 0,
  operator_breakdowns: {
    ROR: { operator_type: 'ROR', total_mutants: 2, killed_mutants: 1, survived_mutants: 1, operator_mutation_score_pct: 50.0 },
    LCR: { operator_type: 'LCR', total_mutants: 2, killed_mutants: 1, survived_mutants: 1, operator_mutation_score_pct: 50.0 },
    AOR: { operator_type: 'AOR', total_mutants: 2, killed_mutants: 1, survived_mutants: 1, operator_mutation_score_pct: 50.0 },
  },
  blindspots: [
    {
      mutant_id: 'mut_ror_blind_01',
      file_path: 'auth_guard.py',
      line_number: 2,
      operator_type: 'ROR',
      original_line: '    if retry_left <= 0:',
      mutated_line: '    if retry_left > 0:',
      description: '将第 2 行关系运算符 <= 替换为 >',
      suggested_assertion_fix: '缺失针对 retry_left == 0 临界边界的拦截用例，建议增加边界值与错误提示断言',
    },
    {
      mutant_id: 'mut_lcr_blind_02',
      file_path: 'auth_guard.py',
      line_number: 4,
      operator_type: 'LCR',
      original_line: '    if role == "ADMIN" or role == "SECURITY_AUDITOR":',
      mutated_line: '    if role == "ADMIN" and role == "SECURITY_AUDITOR":',
      description: '将第 4 行逻辑运算符 or 替换为 and',
      suggested_assertion_fix: '测试用例缺少单角色匹配断言，导致逻辑与逻辑或被篡改后未抛错，建议补充单角色验证',
    },
    {
      mutant_id: 'mut_aor_blind_03',
      file_path: 'discount_service.py',
      line_number: 6,
      operator_type: 'AOR',
      original_line: '    discount = price * 0.20',
      mutated_line: '    discount = price / 0.20',
      description: '将第 6 行算术运算符 * 替换为 /',
      suggested_assertion_fix: '缺少针对不同折扣率下的最终实付金额精确断言',
    },
  ],
  summary_verdict: '测试用例集变异得分仅为 50.00% (3/6 击毙)，处于 INSUFFICIENT 欠缺级别。存在 3 处致命断言盲区，需限期整改！',
  calculated_at: '2026-10-16T13:10:00Z',
}

const uniqueOperators = computed(() => {
  if (!currentReport.value?.blindspots) return []
  return Array.from(new Set(currentReport.value.blindspots.map(b => b.operator_type)))
})

const filteredBlindspots = computed(() => {
  if (!currentReport.value?.blindspots) return []
  if (operatorFilter.value === 'ALL') return currentReport.value.blindspots
  return currentReport.value.blindspots.filter(b => b.operator_type === operatorFilter.value)
})

const getLevelTagColor = (level: AssertionAdequacyLevel) => {
  switch (level) {
    case 'EXCELLENT': return 'success'
    case 'ADEQUATE': return 'processing'
    case 'INSUFFICIENT': return 'warning'
    case 'WEAK': return 'error'
    default: return 'default'
  }
}

const getLevelLabel = (level: AssertionAdequacyLevel) => {
  switch (level) {
    case 'EXCELLENT': return '卓越断言 (EXCELLENT)'
    case 'ADEQUATE': return '充分合格 (ADEQUATE)'
    case 'INSUFFICIENT': return '欠缺改进 (INSUFFICIENT)'
    case 'WEAK': return '脆弱虚设 (WEAK)'
    default: return level
  }
}

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

const getOperatorName = (op: string) => {
  switch (op) {
    case 'ROR': return '关系运算符 (ROR)'
    case 'LCR': return '逻辑连接词 (LCR)'
    case 'AOR': return '算术运算符 (AOR)'
    case 'RVO': return '返回值篡改 (RVO)'
    case 'BVO': return '常数边界值 (BVO)'
    default: return op
  }
}

const getScoreClass = (score: number) => {
  if (score >= 85) return 'text-success'
  if (score >= 60) return 'text-primary'
  return 'text-danger'
}

const radarChartOption = computed(() => {
  if (!currentReport.value) return {}
  const ops = ['ROR', 'LCR', 'AOR', 'RVO', 'BVO']
  const breakdowns = currentReport.value.operator_breakdowns || {}

  const indicators = ops.map(op => ({
    name: op,
    max: 100,
  }))

  const actualScores = ops.map(op => breakdowns[op]?.operator_mutation_score_pct || 0)
  const baseline = [85, 85, 85, 85, 85]

  return {
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      data: ['实测击毙率得分', '卓越断言基线 (85%)'],
    },
    radar: {
      indicator: indicators,
      radius: '65%',
      splitNumber: 4,
    },
    series: [
      {
        name: '变异算子得分分布',
        type: 'radar',
        data: [
          {
            value: actualScores,
            name: '实测击毙率得分',
            areaStyle: { color: 'rgba(2, 132, 199, 0.25)' },
            lineStyle: { color: '#0284c7', width: 2 },
            itemStyle: { color: '#0284c7' },
          },
          {
            value: baseline,
            name: '卓越断言基线 (85%)',
            lineStyle: { color: '#10b981', type: 'dashed', width: 2 },
            itemStyle: { color: '#10b981' },
          },
        ],
      },
    ],
  }
})

const applyPreset = (type: 'excellent' | 'insufficient') => {
  currentReport.value = type === 'excellent' ? PRESET_EXCELLENT : PRESET_INSUFFICIENT
  message.info(`已载入「${type === 'excellent' ? '卓越断言' : '存在盲区'}」示例报告`)
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await ciImpactApi.listMutationScoreReports()
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
    } else {
      currentReport.value = PRESET_EXCELLENT
    }
  } catch {
    currentReport.value = PRESET_EXCELLENT
  } finally {
    loading.value = false
  }
}

const handleCalculateSubmit = async () => {
  loading.value = true
  showCalcModal.value = false
  try {
    const res = await ciImpactApi.calculateMutationScore({
      execution_run_id: calcRunId.value || undefined,
    })
    currentReport.value = res.report
    message.success(res.message || '用例变异得分重新评估完成')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '计算变异得分失败')
  } finally {
    loading.value = false
  }
}

const copyFix = (fix: string) => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(fix)
    message.success('已复制用例断言修复指引')
  } else {
    message.info(fix)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.mutation-score-report-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-icon {
  font-size: 20px;
  color: #f97316;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
  color: #0f172a;
}

.page-subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 6px 0 0 0;
  max-width: 820px;
}

/* 裁决横幅 */
.verdict-banner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 20px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  transition: all 0.3s ease;
}

.banner-level-excellent {
  background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
  border-color: #86efac;
}

.banner-level-adequate {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-color: #7dd3fc;
}

.banner-level-insufficient {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-color: #fcd34d;
}

.banner-level-weak {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border-color: #fca5a5;
}

.score-circle-box {
  flex-shrink: 0;
}

.score-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 3px solid #0284c7;
}

.banner-level-excellent .score-circle { border-color: #10b981; }
.banner-level-adequate .score-circle { border-color: #0284c7; }
.banner-level-insufficient .score-circle { border-color: #f59e0b; }
.banner-level-weak .score-circle { border-color: #ef4444; }

.score-num {
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.1;
}

.score-lbl {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.verdict-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.verdict-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.verdict-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.level-tag {
  font-weight: 700;
  font-size: 12px;
}

.report-meta {
  font-size: 11px;
  color: #64748b;
  margin-left: auto;
}

.verdict-text {
  font-size: 13px;
  color: #334155;
  margin: 0;
  line-height: 1.5;
}

.action-guidance {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  margin-top: 4px;
}

.guidance-prefix {
  font-weight: 600;
  color: #475569;
}

.guidance-text {
  font-weight: 600;
}

.text-success { color: #16a34a; }
.text-primary { color: #0284c7; }
.text-warning { color: #d97706; }
.text-danger { color: #dc2626; }

/* KPI 卡片网格 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-card {
  padding: 12px 16px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.kpi-label {
  font-size: 12px;
  color: #64748b;
}

.kpi-val {
  font-size: 24px;
  font-weight: 700;
  margin: 4px 0;
}

.kpi-sub {
  font-size: 11px;
  color: #94a3b8;
}

/* 图表双栏 */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.chart-panel {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.panel-sub {
  font-size: 11px;
  color: #64748b;
}

.radar-box {
  padding: 8px;
  flex: 1;
}

.breakdown-list {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.breakdown-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.op-tag {
  font-weight: 600;
}

.op-name {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.op-score {
  margin-left: auto;
  font-size: 13px;
  font-weight: 700;
}

.item-stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #64748b;
}

/* 断言盲区面板 */
.blindspots-panel {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.loc-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-name {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}

.line-badge {
  font-size: 11px;
  color: #64748b;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
  width: fit-content;
}

.code-diff-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.code-line {
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.line-tag {
  font-weight: 700;
  font-size: 10px;
}

.old-line {
  background: #fee2e2;
  color: #991b1b;
}

.new-line {
  background: #dcfce7;
  color: #166534;
}

.code-desc {
  font-size: 11px;
  color: #64748b;
}

.fix-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fix-text {
  font-size: 12px;
  color: #0f172a;
  line-height: 1.4;
}

.empty-placeholder {
  padding: 40px 0;
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.form-hint {
  font-size: 12px;
  color: #64748b;
  margin: 0;
}
</style>
