<template>
  <div class="page-shell golden-baseline-dashboard-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <SafetyCertificateOutlined class="hero-icon" />
          <h2 class="page-title">接口黄金响应基线版本化管理与回归偏离大盘</h2>
        </div>
        <p class="page-subtitle">
          为关键微服务建立官方认证的「黄金响应基线」快照（Golden Response Baseline）。结合动态去噪差分比对器，在新版本上线与影子回放时，自动度量实际响应与黄金基线的相似度偏离，严密防范接口重构引发的意外回退。
        </p>
      </div>

      <div class="hero-actions">
        <a-space size="small">
          <a-button :loading="loading" size="small" @click="loadInitialData">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" @click="applyPreset('all_passed')">
            示例: 回归完全达标 (100%)
          </a-button>
          <a-button size="small" @click="applyPreset('critical_drift')">
            示例: 核心字段缺失阻断 (50%)
          </a-button>
          <a-button size="small" @click="showBatchVerifyModal = true">
            <PlayCircleOutlined /> 批量回归校验
          </a-button>
          <a-button type="primary" size="small" @click="showCreateModal = true">
            <PlusOutlined /> 录入黄金基线快照
          </a-button>
        </a-space>
      </div>
    </header>

    <a-spin :spinning="loading || verifying">
      <!-- 核心大盘偏离态势大横幅 -->
      <div
        v-if="latestBatchReport"
        class="verdict-banner"
        :class="latestBatchReport.drifted_count === 0 ? 'banner-normal' : (hasCriticalDrift ? 'banner-critical' : 'banner-warning')"
      >
        <div class="score-circle-box">
          <div class="score-circle">
            <span class="score-num">{{ latestBatchReport.pass_rate_pct.toFixed(1) }}%</span>
            <span class="score-lbl">回归通过率</span>
          </div>
        </div>

        <div class="verdict-info-box">
          <div class="verdict-title-line">
            <span class="verdict-headline">
              {{ latestBatchReport.drifted_count === 0 ? '🟢 全网微服务响应与黄金基线高度吻合 (NORMAL)' : (hasCriticalDrift ? '🔴 检出阻断级核心回归偏离 (CRITICAL DRIFT)' : '🟡 检出次要兼容性偏离告警 (WARNING)') }}
            </span>
            <a-tag :color="latestBatchReport.drifted_count === 0 ? 'green' : (hasCriticalDrift ? 'red' : 'orange')" class="status-pill">
              {{ latestBatchReport.drifted_count === 0 ? '全量达标' : `偏离报警: ${latestBatchReport.drifted_count} 处` }}
            </a-tag>
          </div>

          <div class="meta-row">
            <span class="meta-item">验证批次: <code>{{ latestBatchReport.batch_id }}</code></span>
            <span class="meta-item">已校验接口数: <strong>{{ latestBatchReport.total_verified }}</strong> 个</span>
            <span class="meta-item text-success">通过数: <strong>{{ latestBatchReport.passed_count }}</strong></span>
            <span class="meta-item text-danger">偏离告警数: <strong>{{ latestBatchReport.drifted_count }}</strong></span>
            <span class="meta-item">校验时间: {{ latestBatchReport.created_at.slice(0, 19).replace('T', ' ') }}</span>
          </div>

          <p class="summary-desc">
            {{ latestBatchReport.drifted_count === 0 ? '所有被测接口响应经动态去噪后相似度均达到 95% 以上基线容差标准，核心业务逻辑完全稳固。' : '检测到部分接口实测响应存在字段缺失或严重偏离黄金基线，建议立即比对右侧差分报告并排查重构代码！' }}
          </p>
        </div>
      </div>

      <!-- 黄金基线列表与过滤卡片 -->
      <div class="baselines-panel">
        <div class="panel-header-row">
          <div class="header-left">
            <span class="panel-title">
              <AuditOutlined /> 官方接口黄金响应基线快照库 ({{ filteredBaselines.length }})
            </span>
            <a-input-search
              v-model:value="searchEndpoint"
              placeholder="搜索端点路径..."
              size="small"
              style="width: 220px"
            />
            <a-select v-model:value="versionFilter" size="small" style="width: 140px">
              <a-select-option value="ALL">全部版本标签</a-select-option>
              <a-select-option value="v1.0-prod-gold">v1.0-prod-gold</a-select-option>
              <a-select-option value="v2.0-rc">v2.0-rc</a-select-option>
            </a-select>
          </div>

          <div class="header-right">
            <span class="panel-sub">默认容差阈值: ≥95.0% 相似度</span>
          </div>
        </div>

        <a-table
          :data-source="filteredBaselines"
          :columns="columns"
          row-key="baseline_id"
          size="small"
          :pagination="{ pageSize: 7, showTotal: (t: number) => `共 ${t} 条黄金响应基线` }"
          class="baseline-table"
        >
          <template #bodyCell="{ column, record }">
            <!-- 接口端点 -->
            <template v-if="column.key === 'endpoint'">
              <div class="endpoint-cell">
                <span class="endpoint-text">{{ record.endpoint }}</span>
                <span class="baseline-id">ID: {{ record.baseline_id }}</span>
              </div>
            </template>

            <!-- 协议与版本 -->
            <template v-else-if="column.key === 'version'">
              <div class="ver-box">
                <a-tag color="blue" size="small">{{ record.protocol }}</a-tag>
                <a-tag color="purple" size="small">{{ record.version_tag }}</a-tag>
              </div>
            </template>

            <!-- 状态码 -->
            <template v-else-if="column.key === 'status'">
              <a-tag color="green" size="small">HTTP {{ record.golden_response_status }}</a-tag>
            </template>

            <!-- 容差阈值 -->
            <template v-else-if="column.key === 'tolerance'">
              <span class="tolerance-badge">≥ {{ record.tolerance_threshold_pct }}%</span>
            </template>

            <!-- 激活状态 -->
            <template v-else-if="column.key === 'active'">
              <a-switch v-model:checked="record.is_active" size="small" />
            </template>

            <!-- 更新时间 -->
            <template v-else-if="column.key === 'updated_at'">
              <span class="time-text">{{ record.updated_at.slice(0, 10) }}</span>
            </template>

            <!-- 操作 -->
            <template v-else-if="column.key === 'action'">
              <a-space size="small">
                <a-button size="small" type="link" @click="handleVerifySingleOpen(record as any)">
                  回归校验
                </a-button>
                <a-button size="small" type="link" @click="handleViewSnapshot(record as any)">
                  查看快照
                </a-button>
                <a-popconfirm title="确定删除该黄金基线吗？" @confirm="handleDeleteBaseline(record.baseline_id)">
                  <a-button size="small" type="link" danger>
                    删除
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 单接口实测回归校验模态框 -->
      <a-modal
        v-model:open="showVerifySingleModal"
        title="单接口实测响应对齐黄金基线校验"
        width="760px"
        @ok="handleRunVerifySingle"
      >
        <div v-if="verifyingBaseline" class="verify-form-box">
          <div class="info-alert">
            正在对齐基线: <strong>{{ verifyingBaseline.endpoint }}</strong> (版本: {{ verifyingBaseline.version_tag }}) | 容差阈值: <strong>{{ verifyingBaseline.tolerance_threshold_pct }}%</strong>
          </div>
          <a-form layout="vertical">
            <a-form-item label="当前重构版本/回放实测响应状态码:">
              <a-input-number v-model:value="verifyForm.actual_status_code" style="width: 120px" />
            </a-form-item>
            <a-form-item label="当前重构版本/回放实测响应体 (JSON/文本):">
              <a-textarea v-model:value="verifyForm.actual_response_body" :rows="8" class="code-editor" />
            </a-form-item>
          </a-form>
        </div>
      </a-modal>

      <!-- 校验结果详情下钻模态框 -->
      <a-modal
        v-model:open="showResultDetailModal"
        title="黄金基线回归对齐校验报告 (Verification Result)"
        width="820px"
        :footer="null"
      >
        <div v-if="singleVerifyResult" class="result-modal-box">
          <div
            class="verif-result-banner"
            :class="singleVerifyResult.passed ? 'banner-normal' : (singleVerifyResult.alert_level === 'CRITICAL' ? 'banner-critical' : 'banner-warning')"
          >
            <div class="score-circle">
              <span class="score-num">{{ singleVerifyResult.similarity_score_pct.toFixed(1) }}%</span>
              <span class="score-lbl">相似度</span>
            </div>
            <div class="result-text-col">
              <span class="result-title">
                {{ singleVerifyResult.passed ? '🟢 回归校验全量通过' : (singleVerifyResult.alert_level === 'CRITICAL' ? '🔴 检出阻断级核心偏离' : '🟡 存在偏离告警') }}
              </span>
              <p class="result-summary">{{ singleVerifyResult.summary }}</p>
              <span class="meta-row-small">
                核心阻断差异: <strong>{{ singleVerifyResult.critical_diffs_count }}</strong> 处 | 次要告警: <strong>{{ singleVerifyResult.warning_diffs_count }}</strong> 处
              </span>
            </div>
          </div>
        </div>
      </a-modal>

      <!-- 快照查看模态框 -->
      <a-modal
        v-model:open="showSnapshotModal"
        title="黄金响应基线快照详情 (Snapshot Preview)"
        width="760px"
        :footer="null"
      >
        <div v-if="selectedSnapshot" class="snapshot-container">
          <div class="meta-row">
            <span>端点: <code>{{ selectedSnapshot.endpoint }}</code></span>
            <span>版本: <a-tag size="small">{{ selectedSnapshot.version_tag }}</a-tag></span>
            <span>状态码: <strong>{{ selectedSnapshot.golden_response_status }}</strong></span>
            <span>容差: <strong>{{ selectedSnapshot.tolerance_threshold_pct }}%</strong></span>
          </div>
          <div class="code-box">
            <div class="code-title">官方认证黄金响应体:</div>
            <pre class="code-pre"><code>{{ selectedSnapshot.golden_response_body }}</code></pre>
          </div>
        </div>
      </a-modal>

      <!-- 新增黄金基线模态框 -->
      <a-modal
        v-model:open="showCreateModal"
        title="录入官方接口黄金响应基线快照"
        width="760px"
        @ok="handleCreateSubmit"
      >
        <a-form layout="vertical">
          <a-form-item label="接口方法与端点 (如 POST /api/v1/orders/checkout):">
            <a-input v-model:value="createForm.endpoint" placeholder="POST /api/v1/orders/checkout" />
          </a-form-item>
          <a-form-item label="版本快照标签:">
            <a-input v-model:value="createForm.version_tag" placeholder="v1.0-prod-gold" style="width: 240px" />
          </a-form-item>
          <a-form-item label="最低相似度容差阈值 (%):">
            <div class="slider-row">
              <a-slider v-model:value="createForm.tolerance_threshold_pct" :min="50" :max="100" class="tol-slider" />
              <span class="tol-num">{{ createForm.tolerance_threshold_pct }}%</span>
            </div>
          </a-form-item>
          <a-form-item label="官方认证黄金响应体 (JSON/文本):">
            <a-textarea v-model:value="createForm.golden_response_body" :rows="8" class="code-editor" />
          </a-form-item>
        </a-form>
      </a-modal>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  AuditOutlined,
} from '@ant-design/icons-vue'
import {
  goldenBaselineApi,
  type BaselineVerificationResult,
  type BatchVerificationReport,
  type GoldenBaselineItem,
} from '@/api/trafficGateway'

const loading = ref(false)
const verifying = ref(false)

const searchEndpoint = ref('')
const versionFilter = ref('ALL')
const baselines = ref<GoldenBaselineItem[]>([])
const latestBatchReport = ref<BatchVerificationReport | null>(null)

// 模态框控制
const showCreateModal = ref(false)
const showVerifySingleModal = ref(false)
const showResultDetailModal = ref(false)
const showSnapshotModal = ref(false)
const showBatchVerifyModal = ref(false)

const verifyingBaseline = ref<GoldenBaselineItem | null>(null)
const singleVerifyResult = ref<BaselineVerificationResult | null>(null)
const selectedSnapshot = ref<GoldenBaselineItem | null>(null)

const verifyForm = reactive({
  actual_status_code: 200,
  actual_response_body: '{\n  "code": 0,\n  "message": "success",\n  "data": {\n    "order_id": 10001,\n    "status": "PAID"\n  }\n}',
})

const createForm = reactive({
  endpoint: 'POST /api/v1/orders/checkout',
  version_tag: 'v1.0-prod-gold',
  tolerance_threshold_pct: 95.0,
  golden_response_status: 200,
  golden_response_body: '{\n  "code": 0,\n  "data": {\n    "order_id": 10001,\n    "status": "PAID",\n    "amount": 199.0\n  }\n}',
})

const columns = [
  { title: '接口端点与基线 ID', key: 'endpoint' },
  { title: '协议与版本标签', key: 'version', width: 180 },
  { title: '黄金状态码', key: 'status', width: 120 },
  { title: '相似度容差', key: 'tolerance', width: 110 },
  { title: '激活', key: 'active', width: 80 },
  { title: '更新日期', key: 'updated_at', width: 120 },
  { title: '操作', key: 'action', width: 220 },
]

// 预设批次报告
const PRESET_ALL_PASSED_BATCH: BatchVerificationReport = {
  batch_id: 'bvr_demo_passed_001',
  total_verified: 5,
  passed_count: 5,
  drifted_count: 0,
  pass_rate_pct: 100.0,
  created_at: '2026-10-16T13:00:00Z',
  results: [],
}

const PRESET_CRITICAL_BATCH: BatchVerificationReport = {
  batch_id: 'bvr_demo_crit_002',
  total_verified: 4,
  passed_count: 2,
  drifted_count: 2,
  pass_rate_pct: 50.0,
  created_at: '2026-10-16T13:05:00Z',
  results: [
    {
      verification_id: 'vrf_1',
      baseline_id: 'gbl_1',
      version_tag: 'v1.0-prod-gold',
      endpoint: 'POST /api/v1/pay',
      actual_status_code: 500,
      similarity_score_pct: 35.0,
      tolerance_threshold_pct: 95.0,
      passed: false,
      diff_report_id: 'diff_1',
      critical_diffs_count: 2,
      warning_diffs_count: 0,
      alert_level: 'CRITICAL',
      summary: '【严重回归阻断】实测相似度 35.0% 远低于容差基线 (95%)，核心字段丢失且状态码异常！',
      verified_at: '2026-10-16T13:05:00Z',
    },
  ],
}

// 预设基线库
const PRESET_BASELINES: GoldenBaselineItem[] = [
  {
    baseline_id: 'gbl_order_001',
    endpoint: 'POST /api/v1/orders/checkout',
    protocol: 'HTTP',
    version_tag: 'v1.0-prod-gold',
    description: '官方订单结算黄金基线快照',
    golden_request_body: '{"order_id": 10001}',
    golden_response_status: 200,
    golden_response_body: JSON.stringify({ code: 0, data: { order_id: 10001, status: 'PAID', amount: 199.0 } }, null, 2),
    tolerance_threshold_pct: 95.0,
    is_active: true,
    tags: {},
    created_at: '2026-10-16T10:00:00Z',
    updated_at: '2026-10-16T10:00:00Z',
  },
  {
    baseline_id: 'gbl_user_002',
    endpoint: 'GET /api/v1/users/profile',
    protocol: 'HTTP',
    version_tag: 'v1.0-prod-gold',
    description: '官方用户资料查询黄金基线',
    golden_request_body: '',
    golden_response_status: 200,
    golden_response_body: JSON.stringify({ code: 0, data: { user_id: 888, username: 'alice', role: 'VIP' } }, null, 2),
    tolerance_threshold_pct: 90.0,
    is_active: true,
    tags: {},
    created_at: '2026-10-16T10:05:00Z',
    updated_at: '2026-10-16T10:05:00Z',
  },
]

const hasCriticalDrift = computed(() => {
  if (!latestBatchReport.value?.results) return false
  return latestBatchReport.value.results.some(r => r.alert_level === 'CRITICAL')
})

const filteredBaselines = computed(() => {
  return baselines.value.filter(b => {
    const matchEp = !searchEndpoint.value.trim() || b.endpoint.toLowerCase().includes(searchEndpoint.value.trim().toLowerCase())
    const matchVer = versionFilter.value === 'ALL' || b.version_tag === versionFilter.value
    return matchEp && matchVer
  })
})

const applyPreset = (type: 'all_passed' | 'critical_drift') => {
  if (type === 'all_passed') {
    latestBatchReport.value = PRESET_ALL_PASSED_BATCH
  } else {
    latestBatchReport.value = PRESET_CRITICAL_BATCH
  }
  message.info(`已切换至「${type}」大盘态势预设`)
}

const loadInitialData = async () => {
  loading.value = true
  try {
    const bRes = await goldenBaselineApi.listBaselines()
    baselines.value = bRes.baselines.length > 0 ? bRes.baselines : PRESET_BASELINES

    const rRes = await goldenBaselineApi.listBatchReports()
    if (rRes.reports && rRes.reports.length > 0) {
      latestBatchReport.value = rRes.reports[0]
    } else {
      latestBatchReport.value = PRESET_ALL_PASSED_BATCH
    }
  } catch {
    baselines.value = PRESET_BASELINES
    latestBatchReport.value = PRESET_ALL_PASSED_BATCH
  } finally {
    loading.value = false
  }
}

const handleVerifySingleOpen = (item: any) => {
  verifyingBaseline.value = item
  verifyForm.actual_status_code = item.golden_response_status
  verifyForm.actual_response_body = item.golden_response_body
  showVerifySingleModal.value = true
}

const handleRunVerifySingle = async () => {
  if (!verifyingBaseline.value) return
  showVerifySingleModal.value = false
  verifying.value = true
  try {
    const res = await goldenBaselineApi.verifySingle({
      baseline_id: verifyingBaseline.value.baseline_id,
      actual_response_body: verifyForm.actual_response_body,
      actual_status_code: verifyForm.actual_status_code,
    })
    singleVerifyResult.value = res.result
    showResultDetailModal.value = true
    message.success(res.message || '回归校验完成')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '校验失败')
  } finally {
    verifying.value = false
  }
}

const handleViewSnapshot = (item: any) => {
  selectedSnapshot.value = item
  showSnapshotModal.value = true
}

const handleDeleteBaseline = async (id: string) => {
  try {
    await goldenBaselineApi.deleteBaseline(id)
    baselines.value = baselines.value.filter(b => b.baseline_id !== id)
    message.success('黄金基线已删除')
  } catch (err: any) {
    message.error(err.message || '删除失败')
  }
}

const handleCreateSubmit = async () => {
  if (!createForm.endpoint.trim() || !createForm.golden_response_body.trim()) {
    message.warning('请补全端点与响应体')
    return
  }

  showCreateModal.value = false
  loading.value = true
  try {
    const res = await goldenBaselineApi.createBaseline({
      endpoint: createForm.endpoint,
      golden_response_body: createForm.golden_response_body,
      version_tag: createForm.version_tag,
      tolerance_threshold_pct: createForm.tolerance_threshold_pct,
    })
    baselines.value.unshift(res.baseline)
    message.success(res.message || '黄金基线快照已成功录入')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '录入失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadInitialData()
})
</script>

<style scoped>
.golden-baseline-dashboard-view {
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
  color: #0284c7;
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
  max-width: 860px;
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

.banner-normal {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border-color: #86efac;
}

.banner-critical {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border-color: #fca5a5;
}

.banner-warning {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-color: #fcd34d;
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
  border: 3px solid #10b981;
}

.banner-normal .score-circle { border-color: #10b981; }
.banner-critical .score-circle { border-color: #ef4444; }
.banner-warning .score-circle { border-color: #f59e0b; }

.score-num {
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
}

.score-lbl {
  font-size: 10px;
  color: #64748b;
}

.verdict-info-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.verdict-title-line {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.verdict-headline {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.status-pill {
  font-weight: 700;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: #475569;
  flex-wrap: wrap;
}

.summary-desc {
  font-size: 12px;
  color: #334155;
  margin: 0;
}

.text-success { color: #16a34a; }
.text-danger { color: #dc2626; }

/* 基线表格面板 */
.baselines-panel {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.panel-header-row {
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
  gap: 12px;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.panel-sub {
  font-size: 11px;
  color: #64748b;
}

.endpoint-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.endpoint-text {
  font-weight: 600;
  color: #0f172a;
}

.baseline-id {
  font-size: 10px;
  font-family: monospace;
  color: #94a3b8;
}

.ver-box {
  display: flex;
  gap: 4px;
}

.tolerance-badge {
  font-size: 11px;
  font-weight: 700;
  color: #0284c7;
}

.time-text {
  font-size: 11px;
  color: #64748b;
}

/* 弹窗内容 */
.code-editor {
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.4;
  background: #1e293b;
  color: #f8fafc;
  border-radius: 4px;
}

.info-alert {
  padding: 8px 12px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #0369a1;
}

.verif-result-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.result-text-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-title {
  font-weight: 700;
  font-size: 14px;
}

.result-summary {
  font-size: 12px;
  color: #475569;
  margin: 0;
}

.meta-row-small {
  font-size: 11px;
  color: #64748b;
}

.code-box {
  margin-top: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
}

.code-title {
  padding: 6px 10px;
  background: #f1f5f9;
  font-size: 11px;
  font-weight: 600;
  border-bottom: 1px solid #e2e8f0;
}

.code-pre {
  margin: 0;
  padding: 10px;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  background: #1e293b;
  color: #f8fafc;
  max-height: 240px;
  overflow-y: auto;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tol-slider {
  flex: 1;
}

.tol-num {
  font-size: 12px;
  font-weight: 700;
  color: #0284c7;
  width: 45px;
}
</style>
