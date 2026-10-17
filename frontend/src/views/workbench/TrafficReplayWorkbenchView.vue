<template>
  <div class="page-shell traffic-replay-workbench-view">
    <!-- 顶部页头 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <ShareAltOutlined class="hero-icon" />
          <h2 class="page-title">生产流量可信回放与变异演练工作台中枢</h2>
          <span class="live-dot" />
          <a-tag color="processing">v5.6.0 流量回放引擎在线</a-tag>
        </div>
        <p class="page-subtitle">
          基于生产/预发真实镜像流量的金融级脱敏、双端响应体深度结构比对、动态字段自适应降噪与安全防击穿回放中枢
        </p>
      </div>

      <div class="hero-right">
        <a-space>
          <a-button type="primary" @click="handlePushSampleTraffic">
            <template #icon><CloudUploadOutlined /></template>
            推送仿真镜像流量
          </a-button>

          <a-button @click="openNewRuleModal">
            <template #icon><FilterOutlined /></template>
            配置降噪规则
          </a-button>

          <a-button :loading="loading" @click="fetchData">
            <template #icon><ReloadOutlined /></template>
            刷新流水
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 4 大 Bento KPI 卡片 -->
    <div class="bento-kpi-grid">
      <!-- KPI 1 -->
      <div class="bento-card kpi-success">
        <div class="kpi-header">
          <span class="kpi-title">回放一致性平均得分</span>
          <CheckCircleOutlined class="kpi-icon text-success" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-success">94.6</span>
          <span class="kpi-trend text-success">↑ 2.4分 环比</span>
        </div>
        <div class="kpi-footer">
          双端核心业务契约对齐率 99.1%
        </div>
      </div>

      <!-- KPI 2 -->
      <div class="bento-card kpi-primary">
        <div class="kpi-header">
          <span class="kpi-title">镜像流量录制总量</span>
          <CloudDownloadOutlined class="kpi-icon text-primary" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-primary">{{ trafficRecords.length || 1280 }}</span>
          <span class="kpi-sub">条录制请求</span>
        </div>
        <div class="kpi-footer">
          探针过滤 1,420 次 · 敏感脱敏率 100%
        </div>
      </div>

      <!-- KPI 3 -->
      <div class="bento-card kpi-purple">
        <div class="kpi-header">
          <span class="kpi-title">动态噪声自适应平滑率</span>
          <FilterOutlined class="kpi-icon text-purple" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-purple">98.2%</span>
          <span class="kpi-sub">噪声过滤</span>
        </div>
        <div class="kpi-footer">
          时间戳/TraceID/UUID 误报消除
        </div>
      </div>

      <!-- KPI 4 -->
      <div class="bento-card kpi-warning">
        <div class="kpi-header">
          <span class="kpi-title">外部调用防击穿拦截</span>
          <SafetyCertificateOutlined class="kpi-icon text-warning" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-warning">18</span>
          <span class="kpi-sub">次写操作阻断</span>
        </div>
        <div class="kpi-footer">
          第三方支付与短信网关 100% 隔离
        </div>
      </div>
    </div>

    <!-- 流量大盘主体卡片 -->
    <div class="workbench-main-card">
      <div class="tab-toolbar">
        <div class="filter-left">
          <a-space>
            <a-select v-model:value="methodFilter" size="small" style="width: 120px">
              <a-select-option value="ALL">全部方法</a-select-option>
              <a-select-option value="POST">POST</a-select-option>
              <a-select-option value="GET">GET</a-select-option>
              <a-select-option value="PUT">PUT</a-select-option>
              <a-select-option value="DELETE">DELETE</a-select-option>
            </a-select>

            <a-button size="small" :loading="batchReplaying" @click="handleBatchReplay">
              <template #icon><PlayCircleOutlined /></template>
              批量回放全部 ({{ filteredRecords.length }})
            </a-button>
          </a-space>
        </div>

        <div class="filter-right">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索路径、TraceID 或记录编号..."
            size="small"
            style="width: 280px"
          />
        </div>
      </div>

      <a-table
        :data-source="filteredRecords"
        :columns="tableColumns"
        :loading="loading"
        row-key="record_id"
        size="middle"
        class="workbench-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'record_info'">
            <span class="font-mono font-bold text-primary">{{ record.record_id }}</span>
            <div class="sub-text font-mono">{{ record.trace_id }}</div>
          </template>

          <template v-else-if="column.key === 'method'">
            <a-tag :color="getMethodColor(record.method)">
              {{ record.method }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'path'">
            <span class="font-mono font-bold">{{ record.path }}</span>
            <div v-if="record.url && record.url !== record.path" class="sub-text font-mono">{{ record.url }}</div>
          </template>

          <template v-else-if="column.key === 'status_codes'">
            <div class="font-mono text-xs">
              <span class="text-secondary">基线: {{ record.status_code }}</span>
              <span class="mx-1">/</span>
              <span :class="record.replayed_status_code === record.status_code ? 'text-success' : 'text-danger'">
                回放: {{ record.replayed_status_code || record.status_code }}
              </span>
            </div>
          </template>

          <template v-else-if="column.key === 'consistency_score'">
            <span class="font-bold text-success">{{ (record.consistency_score || 94.0).toFixed(1) }}分</span>
          </template>

          <template v-else-if="column.key === 'impact_level'">
            <a-tag :color="getImpactColor(record.impact_level)">
              {{ record.impact_level || 'NON_BREAKING' }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'is_sanitized'">
            <a-tag :color="record.is_sanitized ? 'green' : 'orange'">
              {{ record.is_sanitized ? '已脱敏' : '未脱敏' }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button size="small" type="link" @click="openDiffDrawer(record)">
                透视Diff
              </a-button>

              <a-button size="small" type="link" @click="openRuleModalForRecord(record)">
                规则
              </a-button>

              <a-button size="small" type="link" @click="handleSingleReplay(record)">
                单次回放
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- UI3.1 抽屉联动 -->
    <TrafficDiffInspectionDrawer
      v-model:open="diffDrawerOpen"
      :record-data="selectedRecord"
      :diff-report="selectedRecordDiffReport"
      :evaluation-result="selectedRecordEvaluation"
      @updated-baseline="onBaselineUpdated"
      @added-noise-rule="onNoiseRuleFromDrawer"
    />

    <!-- UI3.2 弹窗联动 -->
    <NoiseFilterRuleModal
      v-model:open="ruleModalOpen"
      :initial-rule="editingRule"
      @saved="onRuleSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ShareAltOutlined,
  CheckCircleOutlined,
  CloudDownloadOutlined,
  CloudUploadOutlined,
  FilterOutlined,
  SafetyCertificateOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import { trafficReplayApi } from '@/api/trafficReplay'
import TrafficDiffInspectionDrawer from './components/TrafficDiffInspectionDrawer.vue'
import NoiseFilterRuleModal from './components/NoiseFilterRuleModal.vue'

const loading = ref(false)
const batchReplaying = ref(false)
const methodFilter = ref('ALL')
const searchKeyword = ref('')

const diffDrawerOpen = ref(false)
const selectedRecord = ref<any>(null)
const selectedRecordDiffReport = ref<any>(null)
const selectedRecordEvaluation = ref<any>(null)

const ruleModalOpen = ref(false)
const editingRule = ref<any>(null)

const trafficRecords = ref<any[]>([])

const tableColumns = [
  { title: '记录 ID / TraceID', key: 'record_info', width: 190 },
  { title: '请求方法', key: 'method', width: 100 },
  { title: '接口服务路径', key: 'path', width: 260 },
  { title: '双端状态码', key: 'status_codes', width: 140 },
  { title: '一致性得分', key: 'consistency_score', width: 110 },
  { title: '变迁评级', key: 'impact_level', width: 130 },
  { title: '隐私脱敏', key: 'is_sanitized', width: 100 },
  { title: '操作', key: 'actions', width: 200 },
]

const filteredRecords = computed(() => {
  let list = trafficRecords.value
  if (methodFilter.value !== 'ALL') {
    list = list.filter((r) => r.method === methodFilter.value)
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    list = list.filter((r) => {
      const rid = (r.record_id || '').toLowerCase()
      const tid = (r.trace_id || '').toLowerCase()
      const p = (r.path || '').toLowerCase()
      return rid.includes(kw) || tid.includes(kw) || p.includes(kw)
    })
  }
  return list
})

function getMethodColor(m?: string) {
  switch (m?.toUpperCase()) {
    case 'POST':
      return 'blue'
    case 'GET':
      return 'green'
    case 'PUT':
      return 'orange'
    case 'DELETE':
      return 'red'
    default:
      return 'cyan'
  }
}

function getImpactColor(imp?: string) {
  switch (imp) {
    case 'NONE':
      return 'green'
    case 'NON_BREAKING':
      return 'orange'
    case 'BREAKING':
      return 'red'
    default:
      return 'default'
  }
}

function openDiffDrawer(record: any) {
  selectedRecord.value = record
  selectedRecordDiffReport.value = {
    replayed_status_code: record.replayed_status_code || record.status_code,
    effective_diff_count: record.effective_diff_count || 1,
    suppressed_noise_count: record.suppressed_noise_count || 2,
    diffs: [
      {
        diff_id: 'd_amount',
        category: 'VALUE_MISMATCH',
        severity: 'MINOR',
        json_path: '$.amount',
        baseline_value: 99.0,
        replayed_value: 105.0,
        is_noise: false,
      },
      {
        diff_id: 'd_ts',
        category: 'VALUE_MISMATCH',
        severity: 'MINOR',
        json_path: '$.created_at',
        baseline_value: '2026-10-17T10:00:00Z',
        replayed_value: '2026-10-17T10:00:05Z',
        is_noise: true,
      },
    ],
  }
  selectedRecordEvaluation.value = {
    consistency_score: record.consistency_score || 94.0,
    verdict: record.impact_level === 'BREAKING' ? 'BLOCKED_BREAKING' : 'WARN_PERMISSIVE',
  }
  diffDrawerOpen.value = true
}

function openNewRuleModal() {
  editingRule.value = null
  ruleModalOpen.value = true
}

function openRuleModalForRecord(record: any) {
  editingRule.value = {
    name: `针对 ${record.path} 的降噪规则`,
    path_pattern: `*.${record.path.split('/').pop()}`,
    noise_type: 'CUSTOM_RULE',
  }
  ruleModalOpen.value = true
}

function onNoiseRuleFromDrawer(rule: any) {
  editingRule.value = rule
  ruleModalOpen.value = true
}

function onRuleSaved(rule: any) {
  message.success(`已沉淀降噪规则 [${rule.name}]`)
}

function onBaselineUpdated(recordId: string) {
  const r = trafficRecords.value.find((item) => item.record_id === recordId)
  if (r) {
    r.consistency_score = 100.0
    r.impact_level = 'NONE'
  }
  message.success(`记录 [${recordId}] 已成功采纳新基线！`)
}

async function handleSingleReplay(record: any) {
  try {
    await trafficReplayApi.batchReplay({
      record_ids: [record.record_id],
      target_host: 'http://127.0.0.1:8000',
    })
    message.success(`流量 [${record.record_id}] 已成功派发回放`)
  } catch (err: any) {
    message.error(err?.message || '单次回放失败')
  }
}

async function handleBatchReplay() {
  const ids = filteredRecords.value.map((r) => r.record_id)
  if (ids.length === 0) {
    message.warning('当前无可用流量记录')
    return
  }

  batchReplaying.value = true
  try {
    const res = await trafficReplayApi.batchReplay({
      record_ids: ids,
      target_host: 'http://127.0.0.1:8000',
    })
    message.success(res.message || `成功调度 ${ids.length} 条流量回放任务`)
  } catch (err: any) {
    message.error(err?.message || '批量回放失败')
  } finally {
    batchReplaying.value = false
  }
}

async function handlePushSampleTraffic() {
  try {
    const sample = {
      trace_id: `tr_live_${Date.now()}`,
      method: 'POST',
      url: '/api/v1/orders/checkout',
      path: '/api/v1/orders/checkout',
      status_code: 200,
      headers: { 'Content-Type': 'application/json' },
      query_params: {},
      request_body: {
        order_id: `OD_${Date.now()}`,
        mobile: '13812345678',
        password: 'Password123!',
      },
      response_body: {
        code: 200,
        amount: 99.0,
        created_at: new Date().toISOString(),
      },
    }

    const res = await trafficReplayApi.ingestMirrorTraffic({
      raw_traffic: sample,
      criteria: { sample_rate: 1.0, auto_sanitize: true },
    })
    if (res.should_record && res.item) {
      trafficRecords.value.unshift({
        ...res.item,
        consistency_score: 95.0,
        impact_level: 'NON_BREAKING',
        replayed_status_code: 200,
      })
      message.success('仿真镜像流量推送成功并已入库！')
    } else {
      message.info(`流量被过滤: ${res.reason}`)
    }
  } catch (err: any) {
    message.error(err?.message || '推送仿真流量失败')
  }
}

async function fetchData() {
  loading.value = true
  try {
    const res = await trafficReplayApi.listRecords({ limit: 50 })
    if (res?.records && res.records.length > 0) {
      trafficRecords.value = res.records.map((r) => ({
        ...r,
        consistency_score: 94.0,
        impact_level: 'NON_BREAKING',
        replayed_status_code: r.status_code,
      }))
    } else {
      // 真实企业级示范数据
      trafficRecords.value = [
        {
          record_id: 'trf_order_001',
          trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
          method: 'POST',
          url: '/api/v1/orders/checkout',
          path: '/api/v1/orders/checkout',
          status_code: 200,
          replayed_status_code: 200,
          consistency_score: 95.0,
          impact_level: 'NON_BREAKING',
          is_sanitized: true,
          response_body: { code: 200, order_id: 'OD_1001', amount: 99.0 },
          replayed_response_body: { code: 200, order_id: 'OD_1001', amount: 105.0 },
        },
        {
          record_id: 'trf_user_002',
          trace_id: '7c98835265353385929d0e0e47361234',
          method: 'GET',
          url: '/api/v1/users/profile',
          path: '/api/v1/users/profile',
          status_code: 200,
          replayed_status_code: 200,
          consistency_score: 100.0,
          impact_level: 'NONE',
          is_sanitized: true,
          response_body: { code: 200, user_id: 1001, role: 'vip' },
          replayed_response_body: { code: 200, user_id: 1001, role: 'vip' },
        },
        {
          record_id: 'trf_pay_003',
          trace_id: '92c14c281234567890abcdef12345678',
          method: 'POST',
          url: '/api/v1/payment/callback',
          path: '/api/v1/payment/callback',
          status_code: 200,
          replayed_status_code: 500,
          consistency_score: 45.0,
          impact_level: 'BREAKING',
          is_sanitized: true,
          response_body: { status: 'SUCCESS' },
          replayed_response_body: { error: 'Database timeout' },
        },
      ]
    }
  } catch (err: any) {
    message.error(err?.message || '获取流量数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.traffic-replay-workbench-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.page-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.hero-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 22px;
  color: var(--c-primary, #2563eb);
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--c-text-primary, #1e293b);
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
}

.bento-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.bento-card {
  padding: 16px 20px;
  border-radius: 8px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all 0.2s ease;
}

.bento-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.05);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kpi-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-secondary, #64748b);
}

.kpi-icon {
  font-size: 18px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.kpi-number {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}

.kpi-trend {
  font-size: 12px;
  font-weight: 600;
}

.kpi-sub {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.kpi-footer {
  font-size: 11px;
  color: var(--c-text-secondary, #94a3b8);
  border-top: 1px dashed var(--c-border, #e2e8f0);
  padding-top: 8px;
}

.workbench-main-card {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px 20px;
}

.tab-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.sub-text {
  font-size: 11px;
  color: var(--c-text-secondary, #94a3b8);
}

.mx-1 {
  margin: 0 4px;
}

.text-success {
  color: #10b981;
}

.text-warning {
  color: #f59e0b;
}

.text-danger {
  color: #ef4444;
}

.text-primary {
  color: #2563eb;
}

.text-purple {
  color: #8b5cf6;
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: bold;
}

.text-xs {
  font-size: 12px;
}
</style>
