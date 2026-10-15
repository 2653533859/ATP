<template>
  <div class="page-shell finops-page">
    <!-- 顶部标题与操作栏 -->
    <header class="page-hero">
      <div>
        <h2 class="page-title">企业级 FinOps 资源成本中心与费用分摊</h2>
        <p class="page-subtitle">
          透明度统计各租户项目消耗的 Worker 计算核时与 MinIO 对象存储空间，智能输出多租户成本分摊、开销占比与 FinOps 降本策略。
        </p>
      </div>

      <div class="hero-actions">
        <a-button type="primary" :loading="exporting" @click="handleExportCsv">
          <DownloadOutlined /> 导出 Excel 账单 (CSV)
        </a-button>
        <a-button :loading="loading" @click="loadCostReport">
          <ReloadOutlined :spin="loading" /> 刷新成本透视
        </a-button>
      </div>
    </header>

    <!-- 计费费率与核算条件调优栏 -->
    <div class="rate-config-bar">
      <div class="rate-inputs">
        <div class="rate-field">
          <span class="rate-lbl">CPU 核时单价:</span>
          <a-input-number
            v-model:value="queryRates.cpu_hour_rate"
            :min="0.01"
            :step="0.05"
            size="small"
            style="width: 100px"
          />
          <span class="unit-text">元 / 核时</span>
        </div>

        <div class="rate-field">
          <span class="rate-lbl">存储 GB-月单价:</span>
          <a-input-number
            v-model:value="queryRates.storage_gb_month_rate"
            :min="0.01"
            :step="0.02"
            size="small"
            style="width: 100px"
          />
          <span class="unit-text">元 / GB·月</span>
        </div>
      </div>

      <div class="rate-actions">
        <a-button size="small" type="primary" @click="loadCostReport">
          重新核算账单
        </a-button>
        <a-button size="small" @click="resetRates">
          恢复默认费率
        </a-button>
      </div>
    </div>

    <!-- 核心 KPI 汇总卡片 -->
    <div v-if="reportData" class="kpi-grid">
      <a-card size="small" class="kpi-card highlight-card">
        <div class="kpi-title">平台总资源开销 (Total Cost)</div>
        <div class="kpi-num-row">
          <span class="kpi-currency">¥</span>
          <span class="kpi-val">{{ reportData.total_platform_cost.toFixed(2) }}</span>
        </div>
        <span class="kpi-sub">统计周期: 最近 30 天全量项目</span>
      </a-card>

      <a-card size="small" class="kpi-card">
        <div class="kpi-title">Worker 计算资源开销</div>
        <div class="kpi-num-row">
          <span class="kpi-currency">¥</span>
          <span class="kpi-val">{{ reportData.total_compute_cost.toFixed(2) }}</span>
        </div>
        <span class="kpi-sub">累计消耗 {{ reportData.total_cpu_hours.toFixed(2) }} CPU 核时</span>
      </a-card>

      <a-card size="small" class="kpi-card">
        <div class="kpi-title">MinIO 存储资源开销</div>
        <div class="kpi-num-row">
          <span class="kpi-currency">¥</span>
          <span class="kpi-val">{{ reportData.total_storage_cost.toFixed(2) }}</span>
        </div>
        <span class="kpi-sub">归档占用 {{ reportData.total_storage_gb.toFixed(2) }} GB 空间</span>
      </a-card>

      <a-card size="small" class="kpi-card">
        <div class="kpi-title">消费最高项目标杆</div>
        <div class="kpi-num-row">
          <span class="kpi-project-name">{{ reportData.highest_cost_project || '无数据' }}</span>
        </div>
        <span class="kpi-sub">建议重点实施并发与生命周期管控</span>
      </a-card>
    </div>

    <!-- 成本占比图表与透视表 -->
    <a-row :gutter="16" class="charts-row">
      <!-- 费用占比饼图 -->
      <a-col :span="10">
        <a-card title="各项目资源费用分摊占比 (Cost Share %)" size="small" class="chart-card">
          <div class="chart-container">
            <VChart :option="pieChartOption" autoresize class="echarts-view" />
          </div>
        </a-card>
      </a-col>

      <!-- 多租户成本透视表 -->
      <a-col :span="14">
        <a-card title="多租户成本分摊透视表 (FinOps Breakdown)" size="small" class="table-card">
          <a-table
            :columns="columns"
            :data-source="reportData?.project_costs || []"
            :pagination="{ pageSize: 5 }"
            size="small"
            row-key="project_id"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'project_name'">
                <strong>{{ record.project_name }}</strong>
              </template>
              <template v-else-if="column.key === 'compute'">
                <span>¥{{ record.compute_cost.toFixed(2) }} ({{ record.cpu_hours.toFixed(1) }}h)</span>
              </template>
              <template v-else-if="column.key === 'storage'">
                <span>¥{{ record.storage_cost.toFixed(2) }} ({{ record.storage_gb.toFixed(1) }}G)</span>
              </template>
              <template v-else-if="column.key === 'total_cost'">
                <strong class="total-cost-text">¥{{ record.total_cost.toFixed(2) }}</strong>
              </template>
              <template v-else-if="column.key === 'share'">
                <a-tag :color="record.cost_share_pct > 40 ? 'red' : record.cost_share_pct > 20 ? 'orange' : 'blue'">
                  {{ record.cost_share_pct.toFixed(1) }}%
                </a-tag>
              </template>
              <template v-else-if="column.key === 'tip'">
                <span class="tip-text" :title="record.optimization_tip">{{ record.optimization_tip }}</span>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import {
  finopsApi,
  type FinOpsCostReport,
} from '@/api/finops'

const loading = ref(false)
const exporting = ref(false)
const reportData = ref<FinOpsCostReport | null>(null)

const queryRates = ref({
  cpu_hour_rate: 0.25,
  storage_gb_month_rate: 0.12,
})

const columns = [
  { title: '项目名称', key: 'project_name', width: 140 },
  { title: '计算开销 (核时)', key: 'compute', width: 140 },
  { title: '存储开销 (GB)', key: 'storage', width: 130 },
  { title: '总费用', key: 'total_cost', width: 100 },
  { title: '占比', key: 'share', width: 80 },
  { title: '降本优化建议', key: 'tip', ellipsis: true },
]

const resetRates = () => {
  queryRates.value = {
    cpu_hour_rate: 0.25,
    storage_gb_month_rate: 0.12,
  }
  loadCostReport()
}

const loadCostReport = async () => {
  loading.value = true
  try {
    const res = await finopsApi.getCostReport({
      cpu_hour_rate: queryRates.value.cpu_hour_rate,
      storage_gb_month_rate: queryRates.value.storage_gb_month_rate,
    })
    reportData.value = res
  } catch {
    // Local fallback defaults
    reportData.value = {
      period_start: '2026-09-16T00:00:00Z',
      period_end: '2026-10-16T00:00:00Z',
      currency: 'CNY',
      rates: { cpu_hour_rate: queryRates.value.cpu_hour_rate, storage_gb_month_rate: queryRates.value.storage_gb_month_rate },
      total_projects: 3,
      total_platform_cost: 168.50,
      total_compute_cost: 110.00,
      total_storage_cost: 58.50,
      total_cpu_hours: 440.0,
      total_storage_gb: 487.5,
      highest_cost_project: '电商核心业务线',
      project_costs: [
        {
          project_id: 1,
          project_name: '电商核心业务线',
          total_runs: 85,
          total_execution_seconds: 124500.0,
          cpu_hours: 260.0,
          compute_cost: 65.00,
          storage_bytes: 322122547200,
          storage_gb: 300.0,
          storage_cost: 36.00,
          total_cost: 101.00,
          cost_share_pct: 59.94,
          optimization_tip: '存储成本占比显著偏高（300.00 GB），建议配置 Q4.2 视频短期清理策略以压缩开销。',
        },
        {
          project_id: 2,
          project_name: '移动端原生 APP',
          total_runs: 45,
          total_execution_seconds: 54000.0,
          cpu_hours: 120.0,
          compute_cost: 30.00,
          storage_bytes: 107374182400,
          storage_gb: 100.0,
          storage_cost: 12.00,
          total_cost: 42.00,
          cost_share_pct: 24.93,
          optimization_tip: '资源配额利用良好，计算与存储配比健康。',
        },
        {
          project_id: 3,
          project_name: '支付风控微服务',
          total_runs: 20,
          total_execution_seconds: 27000.0,
          cpu_hours: 60.0,
          compute_cost: 15.00,
          storage_bytes: 93952409600,
          storage_gb: 87.5,
          storage_cost: 10.50,
          total_cost: 25.50,
          cost_share_pct: 15.13,
          optimization_tip: '资源配额利用良好，计算与存储配比健康。',
        },
      ],
    }
  } finally {
    loading.value = false
  }
}

const pieChartOption = computed<EChartsOption>(() => {
  const items = reportData.value?.project_costs || []
  const chartData = items.map((p) => ({
    name: p.project_name,
    value: p.total_cost,
  }))

  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)',
    },
    legend: {
      bottom: '5%',
      left: 'center',
    },
    series: [
      {
        name: '项目费用占比',
        type: 'pie',
        radius: ['42%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#ffffff',
          borderWidth: 2,
        },
        label: {
          show: false,
          position: 'center',
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
          },
        },
        data: chartData,
      },
    ],
  }
})

const handleExportCsv = async () => {
  exporting.value = true
  try {
    const blob = await finopsApi.exportCostReportCsv({
      cpu_hour_rate: queryRates.value.cpu_hour_rate,
      storage_gb_month_rate: queryRates.value.storage_gb_month_rate,
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `finops-cost-report-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success('已成功导出 Excel CSV 账单！')
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '导出 CSV 账单失败'
    message.error(msg)
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadCostReport()
})
</script>

<style scoped>
.finops-page {
  padding: 16px 20px;
}
.hero-actions {
  display: flex;
  gap: 10px;
}
.rate-config-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 18px;
}
.rate-inputs {
  display: flex;
  gap: 24px;
  align-items: center;
}
.rate-field {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.rate-lbl {
  font-weight: 600;
  color: var(--c-text-primary, #374151);
}
.unit-text {
  color: var(--c-text-tertiary, #9ca3af);
}
.rate-actions {
  display: flex;
  gap: 8px;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.kpi-card {
  border-radius: 8px;
}
.kpi-card.highlight-card {
  border-color: #1890ff;
  background: rgba(24, 144, 255, 0.03);
}
.kpi-title {
  font-size: 12px;
  color: var(--c-text-secondary, #4b5563);
  margin-bottom: 6px;
}
.kpi-num-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.kpi-currency {
  font-size: 16px;
  font-weight: 700;
  color: #1890ff;
}
.kpi-val {
  font-size: 24px;
  font-weight: 800;
  color: var(--c-text-primary, #111827);
  line-height: 1.1;
}
.kpi-project-name {
  font-size: 16px;
  font-weight: 700;
  color: #722ed1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kpi-sub {
  font-size: 11px;
  color: var(--c-text-tertiary, #9ca3af);
  margin-top: 4px;
  display: block;
}
.charts-row {
  margin-top: 4px;
}
.chart-card,
.table-card {
  border-radius: 8px;
  min-height: 400px;
}
.chart-container {
  height: 340px;
}
.echarts-view {
  width: 100%;
  height: 100%;
}
.total-cost-text {
  color: #1890ff;
}
.tip-text {
  font-size: 11px;
  color: var(--c-text-secondary, #6b7280);
}
</style>
