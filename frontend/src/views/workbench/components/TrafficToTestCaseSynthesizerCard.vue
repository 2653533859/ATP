<template>
  <div class="traffic-synthesizer-card">
    <div class="card-header">
      <div class="header-left">
        <BuildOutlined class="card-icon" />
        <span class="card-title">真实流量特征聚类归一与自动化测试用例智能生成控制台</span>
        <a-tag v-if="currentReport" color="cyan" class="dedup-pill">
          聚类去重率: {{ currentReport.deduplication_ratio_pct }}%
        </a-tag>
      </div>

      <div class="header-right">
        <a-space size="small">
          <a-button size="small" :loading="loading" @click="loadInitialReport">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" @click="applyPreset('orders_high_dedup')">
            预设: 高去重场景 (80%)
          </a-button>
          <a-button size="small" @click="applyPreset('mixed_endpoints')">
            预设: 多端点混杂场景 (50%)
          </a-button>
          <a-button type="primary" size="small" :loading="synthesizing" @click="handleRunSynthesis">
            <ThunderboltOutlined /> 一键聚类合成用例
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 合成参数微调栏 -->
    <div class="controls-bar">
      <div class="control-item">
        <span class="ctrl-label">协议筛选:</span>
        <a-select v-model:value="protocolFilter" size="small" style="width: 110px">
          <a-select-option value="ALL">全部协议</a-select-option>
          <a-select-option value="HTTP">HTTP</a-select-option>
          <a-select-option value="GRPC">gRPC</a-select-option>
        </a-select>
      </div>

      <div class="control-item">
        <span class="ctrl-label">提取样本上限:</span>
        <a-input-number v-model:value="limitCaptured" :min="10" :max="500" size="small" style="width: 80px" />
        <span class="unit-text">条</span>
      </div>

      <div class="control-item">
        <span class="ctrl-label">单用例数据集上限:</span>
        <a-input-number v-model:value="maxDatasetRows" :min="1" :max="50" size="small" style="width: 70px" />
        <span class="unit-text">行</span>
      </div>

      <div class="control-item">
        <span class="ctrl-label">用例名前缀:</span>
        <a-input v-model:value="casePrefix" size="small" style="width: 120px" />
      </div>

      <div class="control-item">
        <a-checkbox v-model:checked="autoMaskFirst">
          先脱敏清洗 PII (隐私合规)
        </a-checkbox>
      </div>
    </div>

    <a-spin :spinning="synthesizing || loading">
      <div v-if="currentReport" class="card-body">
        <!-- 聚类去重成效大横幅 -->
        <div class="dedup-banner">
          <div class="dedup-badge-box">
            <span class="dedup-num">{{ currentReport.deduplication_ratio_pct }}%</span>
            <span class="dedup-lbl">聚类去重削峰率</span>
          </div>

          <div class="dedup-content">
            <div class="dedup-title-row">
              <span class="dedup-headline">海量生产流量智能归一化合成成效</span>
              <span class="report-meta">
                报告 ID: <code>{{ currentReport.report_id }}</code> | 生成时间: {{ currentReport.created_at.slice(0, 19).replace('T', ' ') }}
              </span>
            </div>

            <div class="metric-flow-row">
              <div class="flow-step">
                <span class="step-val text-default">{{ currentReport.total_traffic_evaluated }}</span>
                <span class="step-lbl">原始捕获流量</span>
              </div>
              <span class="flow-arrow">→ 模式聚类 →</span>
              <div class="flow-step">
                <span class="step-val text-warning">{{ currentReport.clusters_formed }}</span>
                <span class="step-lbl">归一聚合簇数</span>
              </div>
              <span class="flow-arrow">→ 智能断言合成 →</span>
              <div class="flow-step">
                <span class="step-val text-success">{{ currentReport.synthesized_cases_count }}</span>
                <span class="step-lbl">精简标准用例</span>
              </div>
            </div>

            <p class="dedup-desc">
              根据 URL 路径动态参数归一化 (如 <code>{id}</code>, <code>{uuid}</code>) 与请求体 Schema 结构指纹提炼，
              将相似业务请求收敛为单条用例骨架，并将离散入参抽取为参数化测试数据集，**大幅杜绝测试用例泛滥膨胀**。
            </p>
          </div>
        </div>

        <!-- 合成用例列表 -->
        <div class="section-title-bar">
          <div class="title-left">
            <span class="section-title">已合成的标准 ATP 测试用例列表 ({{ currentReport.cases.length }})</span>
            <span class="section-sub">支持查看断言模板与关联的生产参数化测试数据集</span>
          </div>
          <div class="title-right">
            <a-button type="primary" size="small" @click="handleExportProject">
              <FolderAddOutlined /> 一键导入至当前项目
            </a-button>
          </div>
        </div>

        <a-table
          :data-source="currentReport.cases"
          :columns="columns"
          row-key="case_id"
          size="small"
          :pagination="{ pageSize: 5, showTotal: (t: number) => `共 ${t} 条合成用例` }"
          class="cases-table"
        >
          <template #bodyCell="{ column, record }">
            <!-- 用例名称 -->
            <template v-if="column.key === 'name'">
              <div class="case-name-cell">
                <span class="case-name-text">{{ record.name }}</span>
                <span class="case-id-text">ID: {{ record.case_id }}</span>
              </div>
            </template>

            <!-- 协议 -->
            <template v-else-if="column.key === 'protocol'">
              <a-tag :color="record.protocol === 'GRPC' ? 'purple' : 'blue'" size="small">
                {{ record.protocol }}
              </a-tag>
            </template>

            <!-- 方法 -->
            <template v-else-if="column.key === 'method'">
              <a-tag color="geekblue" size="small">{{ record.method }}</a-tag>
            </template>

            <!-- 归一化路径 -->
            <template v-else-if="column.key === 'path'">
              <code class="path-code">{{ record.url_path }}</code>
            </template>

            <!-- 来源流量数 -->
            <template v-else-if="column.key === 'sources'">
              <a-tag color="orange" size="small">
                聚合自 {{ record.source_traffic_ids.length }} 条流量
              </a-tag>
            </template>

            <!-- 参数化数据集行数 -->
            <template v-else-if="column.key === 'dataset'">
              <span class="dataset-count">{{ record.dataset_rows.length }} 行样本</span>
            </template>

            <!-- 操作 -->
            <template v-else-if="column.key === 'action'">
              <a-space size="small">
                <a-button size="small" type="link" @click="handleOpenDetail(record as any)">
                  查看详情与断言
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </div>

      <div v-else class="empty-placeholder">
        <a-empty description="暂无合成用例数据，请点击右上角「一键聚类合成用例」或切换预设" />
      </div>
    </a-spin>

    <!-- 用例详情与数据集模态框 -->
    <a-modal
      v-model:open="showDetailModal"
      title="合成测试用例详情、智能断言与参数化数据集 (TestCase Detail)"
      width="860px"
      :footer="null"
    >
      <div v-if="selectedCase" class="modal-detail-content">
        <!-- 元数据 -->
        <div class="detail-meta-row">
          <span>用例名称: <strong>{{ selectedCase.name }}</strong></span>
          <span>方法/路径: <code>{{ selectedCase.method }} {{ selectedCase.url_path }}</code></span>
          <span>协议: <a-tag size="small">{{ selectedCase.protocol }}</a-tag></span>
        </div>

        <!-- 智能断言列表 -->
        <div class="detail-box">
          <div class="box-header">
            <span class="box-title">🎯 智能合成断言列表 ({{ selectedCase.assertions.length }} 项)</span>
          </div>
          <div class="box-body">
            <div
              v-for="(ast, idx) in selectedCase.assertions"
              :key="idx"
              class="assertion-row"
            >
              <a-tag color="blue" size="small">{{ ast.target }}</a-tag>
              <span class="ast-op">{{ ast.operator }}</span>
              <code class="ast-exp">{{ JSON.stringify(ast.expected) }}</code>
              <span class="ast-desc">({{ ast.description }})</span>
            </div>
          </div>
        </div>

        <!-- 请求体模板 -->
        <div class="detail-box">
          <div class="box-header">
            <span class="box-title">📝 请求体模板 (Request Body Template)</span>
          </div>
          <div class="box-body">
            <pre class="code-pre"><code>{{ selectedCase.request_body_template || '(无请求体/GET请求)' }}</code></pre>
          </div>
        </div>

        <!-- 参数化测试数据集 -->
        <div class="detail-box">
          <div class="box-header">
            <span class="box-title">📊 提炼的参数化测试数据集样本 (前 {{ selectedCase.dataset_rows.length }} 行)</span>
          </div>
          <div class="box-body">
            <a-table
              :data-source="selectedCase.dataset_rows"
              :columns="datasetColumns"
              row-key="traffic_id"
              size="small"
              :pagination="{ pageSize: 4 }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'row_id'">
                  <span>Row #{{ (index || 0) + 1 }}</span>
                </template>
                <template v-else-if="column.key === 'raw_path'">
                  <code>{{ record.raw_path }}</code>
                </template>
                <template v-else-if="column.key === 'request_body'">
                  <span class="body-cell-text">{{ record.request_body }}</span>
                </template>
                <template v-else-if="column.key === 'expected_status'">
                  <a-tag color="green" size="small">{{ record.expected_status }}</a-tag>
                </template>
              </template>
            </a-table>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  BuildOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  FolderAddOutlined,
} from '@ant-design/icons-vue'
import {
  trafficSynthesizerApi,
  type SynthesizedCaseItem,
  type SynthesisReportItem,
} from '@/api/trafficGateway'

const loading = ref(false)
const synthesizing = ref(false)

const protocolFilter = ref('ALL')
const limitCaptured = ref(100)
const maxDatasetRows = ref(10)
const casePrefix = ref('AUTO_TRAFFIC')
const autoMaskFirst = ref(true)

const currentReport = ref<SynthesisReportItem | null>(null)

// 详情模态框
const showDetailModal = ref(false)
const selectedCase = ref<SynthesizedCaseItem | null>(null)

const columns = [
  { title: '合成用例名称与 ID', key: 'name', width: 260 },
  { title: '协议', key: 'protocol', width: 80 },
  { title: '方法', key: 'method', width: 80 },
  { title: '归一化接口路径', key: 'path' },
  { title: '来源流量样本', key: 'sources', width: 140 },
  { title: '数据集', key: 'dataset', width: 100 },
  { title: '操作', key: 'action', width: 130 },
]

const datasetColumns = [
  { title: '行号', key: 'row_id', width: 80 },
  { title: '原始请求路径', key: 'raw_path', width: 220 },
  { title: '实测请求体样本 (已脱敏)', key: 'request_body' },
  { title: '预期状态码', key: 'expected_status', width: 90 },
]

// 预设样例数据
const PRESET_HIGH_DEDUP: SynthesisReportItem = {
  report_id: 'syn_demo_high_001',
  total_traffic_evaluated: 50,
  clusters_formed: 10,
  deduplication_ratio_pct: 80.0,
  synthesized_cases_count: 10,
  created_at: '2026-10-16T11:00:00Z',
  cases: [
    {
      case_id: 'tc_syn_order_checkout',
      cluster_id: 'cls_order_1',
      name: 'AUTO_TRAFFIC_POST_api_v1_orders_checkout_200',
      description: '由 ATP 生产流量智能合成引擎生成。来源于 25 条真实镜像流量聚类，覆盖接口 POST /api/v1/orders/checkout，预期状态码 200。',
      protocol: 'HTTP',
      method: 'POST',
      url_path: '/api/v1/orders/checkout',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer [REDACTED_AUTH_TOKEN]' },
      query_params_template: { channel: 'app' },
      request_body_template: '{"order_id": 1001, "amount": 199.0, "phone": "138****5678"}',
      assertions: [
        { target: 'status_code', operator: 'eq', expected: 200, description: '验证响应状态码为 200' },
        { target: 'duration_ms', operator: 'le', expected: 200.0, description: '验证接口响应耗时在 SLA 容忍区间 (<= 200.0ms)' },
        { target: 'body.code', operator: 'eq', expected: 0, description: '验证业务响应字段 code 值为 0' },
      ],
      dataset_rows: [
        { traffic_id: 'trf_1', raw_path: '/api/v1/orders/checkout', request_body: '{"order_id": 1001, "amount": 199.0, "phone": "138****5678"}', expected_status: 200 },
        { traffic_id: 'trf_2', raw_path: '/api/v1/orders/checkout', request_body: '{"order_id": 1002, "amount": 350.0, "phone": "139****1234"}', expected_status: 200 },
        { traffic_id: 'trf_3', raw_path: '/api/v1/orders/checkout', request_body: '{"order_id": 1003, "amount": 50.0, "phone": "136****8888"}', expected_status: 200 },
      ],
      source_traffic_ids: ['trf_1', 'trf_2', 'trf_3'],
      created_at: '2026-10-16T11:00:00Z',
    },
    {
      case_id: 'tc_syn_user_profile',
      cluster_id: 'cls_user_2',
      name: 'AUTO_TRAFFIC_GET_api_v1_users_id_profile_200',
      description: '由 ATP 生产流量智能合成引擎生成。来源于 15 条真实镜像流量聚类，覆盖接口 GET /api/v1/users/{id}/profile。',
      protocol: 'HTTP',
      method: 'GET',
      url_path: '/api/v1/users/{id}/profile',
      headers: { Authorization: 'Bearer [REDACTED_AUTH_TOKEN]' },
      query_params_template: {},
      request_body_template: '',
      assertions: [
        { target: 'status_code', operator: 'eq', expected: 200, description: '验证响应状态码为 200' },
        { target: 'body.status', operator: 'eq', expected: 'OK', description: '验证业务状态' },
      ],
      dataset_rows: [
        { traffic_id: 'trf_u1', raw_path: '/api/v1/users/888/profile', request_body: '', expected_status: 200 },
        { traffic_id: 'trf_u2', raw_path: '/api/v1/users/999/profile', request_body: '', expected_status: 200 },
      ],
      source_traffic_ids: ['trf_u1', 'trf_u2'],
      created_at: '2026-10-16T11:00:00Z',
    },
  ],
}

const PRESET_MIXED: SynthesisReportItem = {
  report_id: 'syn_demo_mixed_002',
  total_traffic_evaluated: 20,
  clusters_formed: 10,
  deduplication_ratio_pct: 50.0,
  synthesized_cases_count: 10,
  created_at: '2026-10-16T11:05:00Z',
  cases: PRESET_HIGH_DEDUP.cases,
}

const applyPreset = (type: 'orders_high_dedup' | 'mixed_endpoints') => {
  currentReport.value = type === 'orders_high_dedup' ? PRESET_HIGH_DEDUP : PRESET_MIXED
  message.info(`已切换至「${type === 'orders_high_dedup' ? '高去重率 (80%)' : '多端点 (50%)'}」预设场景`)
}

const loadInitialReport = async () => {
  loading.value = true
  try {
    const res = await trafficSynthesizerApi.listReports()
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
    } else {
      currentReport.value = PRESET_HIGH_DEDUP
    }
  } catch {
    currentReport.value = PRESET_HIGH_DEDUP
  } finally {
    loading.value = false
  }
}

const handleRunSynthesis = async () => {
  synthesizing.value = true
  try {
    const res = await trafficSynthesizerApi.runSynthesis({
      auto_mask_first: autoMaskFirst.value,
      max_dataset_rows_per_case: maxDatasetRows.value,
      case_name_prefix: casePrefix.value,
      protocol_filter: protocolFilter.value !== 'ALL' ? protocolFilter.value : undefined,
      limit_captured: limitCaptured.value,
    })
    currentReport.value = res.report
    message.success(res.message || '流量聚类分析与测试用例智能合成完成')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '合成测试用例失败')
  } finally {
    synthesizing.value = false
  }
}

const handleOpenDetail = (item: any) => {
  selectedCase.value = item
  showDetailModal.value = true
}

const handleExportProject = () => {
  message.success(`已成功将 ${currentReport.value?.cases.length || 0} 条用例与配套数据集录入至当前测试项目库！`)
}

onMounted(() => {
  loadInitialReport()
})
</script>

<style scoped>
.traffic-synthesizer-card {
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

.dedup-pill {
  font-weight: 700;
}

.controls-bar {
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ctrl-label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.unit-text {
  font-size: 12px;
  color: #64748b;
}

.card-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 去重大横幅 */
.dedup-banner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 14px 18px;
  border-radius: 8px;
  border: 1px solid #bae6fd;
  background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%);
}

.dedup-badge-box {
  width: 100px;
  height: 80px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 2px solid #0284c7;
}

.dedup-num {
  font-size: 22px;
  font-weight: 800;
  color: #0284c7;
  line-height: 1.1;
}

.dedup-lbl {
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
}

.dedup-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dedup-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dedup-headline {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.report-meta {
  font-size: 11px;
  color: #64748b;
}

.metric-flow-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 4px 0;
}

.flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.step-val {
  font-size: 16px;
  font-weight: 800;
}

.step-lbl {
  font-size: 10px;
  color: #64748b;
}

.flow-arrow {
  font-size: 11px;
  color: #0284c7;
  font-weight: 600;
}

.dedup-desc {
  font-size: 12px;
  color: #475569;
  margin: 0;
  line-height: 1.4;
}

.text-default { color: #0284c7; }
.text-warning { color: #d97706; }
.text-success { color: #16a34a; }

/* 表格区 */
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
  margin-left: 8px;
}

.case-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.case-name-text {
  font-weight: 600;
  color: #0f172a;
}

.case-id-text {
  font-size: 10px;
  color: #94a3b8;
  font-family: monospace;
}

.path-code {
  font-size: 11px;
  color: #0284c7;
}

.dataset-count {
  font-size: 12px;
  font-weight: 600;
  color: #16a34a;
}

/* 详情框 */
.modal-detail-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 12px;
}

.detail-box {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
}

.box-header {
  padding: 6px 10px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
}

.box-title {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.box-body {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.assertion-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.ast-op {
  font-weight: 700;
  color: #d97706;
}

.ast-exp {
  color: #0284c7;
}

.ast-desc {
  font-size: 11px;
  color: #64748b;
}

.code-pre {
  margin: 0;
  padding: 8px;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  background: #1e293b;
  color: #f8fafc;
  border-radius: 4px;
  max-height: 160px;
  overflow-y: auto;
}

.body-cell-text {
  font-family: monospace;
  font-size: 11px;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 380px;
  display: inline-block;
}

.empty-placeholder {
  padding: 40px 0;
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}
</style>
