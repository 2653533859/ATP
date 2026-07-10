<template>
  <div class="ai-healing-stats">
    <div class="toolbar">
      <h2>AI 自愈采纳率</h2>
      <a-space>
        <a-select v-model:value="days" style="width: 120px" :options="dayOptions" @change="loadStats" />
        <a-button @click="loadStats">刷新</a-button>
      </a-space>
    </div>

    <a-spin :spinning="loading">
      <a-row :gutter="[16, 16]">
        <a-col :xs="12" :md="6">
          <a-card><a-statistic title="总反馈数" :value="stats.total_feedback_count" /></a-card>
        </a-col>
        <a-col :xs="12" :md="6">
          <a-card><a-statistic title="总采纳率" :value="stats.adopted_rate" suffix="%" :precision="2" /></a-card>
        </a-col>
        <a-col :xs="12" :md="6">
          <a-card><a-statistic title="已采纳" :value="stats.adopted_count" /></a-card>
        </a-col>
        <a-col :xs="12" :md="6">
          <a-card><a-statistic title="高质量示例" :value="stats.high_quality_example_count" /></a-card>
        </a-col>
        <a-col :xs="12" :md="6">
          <a-card><a-statistic title="回归触发" :value="stats.production_feedback.regression_triggered_count" /></a-card>
        </a-col>
        <a-col :xs="12" :md="6">
          <a-card><a-statistic title="回归通过率" :value="stats.production_feedback.regression_success_rate" suffix="%" :precision="2" /></a-card>
        </a-col>
        <a-col :xs="12" :md="6">
          <a-card><a-statistic title="回归通过" :value="stats.production_feedback.regression_success_count" /></a-card>
        </a-col>
        <a-col :xs="12" :md="6">
          <a-card><a-statistic title="聚合刷新" :value="formatAggregateTime(stats.production_feedback.latest_feedback_aggregated_at)" /></a-card>
        </a-col>
      </a-row>

      <a-card class="section" title="AI 用例生成漏斗">
        <a-row :gutter="[16, 16]">
          <a-col :xs="12" :md="6">
            <a-statistic title="生成会话" :value="funnelStats.generated_sessions" />
          </a-col>
          <a-col :xs="12" :md="6">
            <a-statistic title="生成草稿" :value="funnelStats.generated_drafts" />
          </a-col>
          <a-col :xs="12" :md="6">
            <a-statistic title="已保存草稿" :value="funnelStats.saved_drafts" />
          </a-col>
          <a-col :xs="12" :md="6">
            <a-statistic title="保存率" :value="funnelStats.save_rate" suffix="%" :precision="2" />
          </a-col>
          <a-col :xs="12" :md="6">
            <a-statistic title="生成失败" :value="funnelStats.failed_generations" />
          </a-col>
          <a-col :xs="12" :md="6">
            <a-statistic title="告警数" :value="funnelStats.warning_count" />
          </a-col>
          <a-col :xs="12" :md="6">
            <a-statistic title="漏斗刷新" :value="formatAggregateTime(funnelStats.latest_event_at)" />
          </a-col>
        </a-row>
      </a-card>

      <a-row :gutter="[16, 16]" class="section">
        <a-col :xs="24" :lg="12">
          <a-card title="按用例类型">
            <v-chart class="chart" :option="caseTypeOption" :theme="chartTheme" autoresize />
          </a-card>
        </a-col>
        <a-col :xs="24" :lg="12">
          <a-card title="最近趋势">
            <v-chart class="chart" :option="trendOption" :theme="chartTheme" autoresize />
          </a-card>
        </a-col>
      </a-row>

      <a-card class="section" title="错误特征 Top 10">
        <a-table
          :data-source="stats.top_error_fingerprints"
          :columns="columns"
          :pagination="false"
          row-key="error_fingerprint"
          :locale="{ emptyText: '暂无错误特征数据' }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'case_type'">
              <a-tag color="blue">{{ record.case_type }}</a-tag>
            </template>
            <template v-else-if="column.key === 'adopted_rate'">
              <a-progress :percent="record.adopted_rate" size="small" />
            </template>
          </template>
        </a-table>
      </a-card>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { message } from 'ant-design-vue'
import { aiCaseGenerationApi, aiHealingStatsApi, type AICaseFunnelStats, type AIHealingStats } from '@/api'
import { useChartTheme } from '@/utils/chartTheme'

const { chartTheme } = useChartTheme()
const loading = ref(false)
const days = ref(30)
const stats = ref<AIHealingStats>({
  total_feedback_count: 0,
  adopted_count: 0,
  rejected_count: 0,
  adopted_rate: 0,
  high_quality_example_count: 0,
  by_case_type: [],
  top_error_fingerprints: [],
  recent_trend: [],
  production_feedback: {
    regression_triggered_count: 0,
    regression_success_count: 0,
    regression_success_rate: 0,
    latest_feedback_aggregated_at: null,
  },
})
const funnelStats = ref<AICaseFunnelStats>({
  generated_sessions: 0,
  generated_drafts: 0,
  saved_drafts: 0,
  failed_generations: 0,
  warning_count: 0,
  save_rate: 0,
  latest_event_at: null,
})

const dayOptions = [
  { label: '7 天', value: 7 },
  { label: '30 天', value: 30 },
  { label: '90 天', value: 90 },
]

const columns = [
  { title: '错误特征', dataIndex: 'error_fingerprint', key: 'error_fingerprint', ellipsis: true },
  { title: '类型', key: 'case_type', width: 100 },
  { title: '反馈数', dataIndex: 'total_count', key: 'total_count', width: 90 },
  { title: '采纳', dataIndex: 'adopted_count', key: 'adopted_count', width: 80 },
  { title: '拒绝', dataIndex: 'rejected_count', key: 'rejected_count', width: 80 },
  { title: '采纳率', key: 'adopted_rate', width: 180 },
]

const caseTypeOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: stats.value.by_case_type.map((item) => item.case_type) },
  yAxis: { type: 'value', max: 100 },
  series: [
    {
      type: 'bar',
      data: stats.value.by_case_type.map((item) => item.adopted_rate),
    },
  ],
}))

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['反馈数', '采纳率'] },
  xAxis: { type: 'category', data: stats.value.recent_trend.map((item) => item.date) },
  yAxis: [
    { type: 'value', name: '反馈数' },
    { type: 'value', name: '采纳率', max: 100 },
  ],
  series: [
    { name: '反馈数', type: 'bar', data: stats.value.recent_trend.map((item) => item.total_count) },
    { name: '采纳率', type: 'line', yAxisIndex: 1, data: stats.value.recent_trend.map((item) => item.adopted_rate) },
  ],
}))

async function loadStats() {
  loading.value = true
  try {
    const [healingStats, funnel] = await Promise.all([
      aiHealingStatsApi.getStats({ days: days.value }),
      aiCaseGenerationApi.getFunnelStats({ days: days.value }),
    ])
    stats.value = healingStats
    funnelStats.value = funnel
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function formatAggregateTime(value?: string | null) {
  if (!value) return '-'
  return value.slice(0, 16).replace('T', ' ')
}

onMounted(loadStats)
</script>

<style scoped>
.ai-healing-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.toolbar h2 {
  margin: 0;
}
.section {
  margin-top: 16px;
}
.chart {
  height: 320px;
}
</style>
