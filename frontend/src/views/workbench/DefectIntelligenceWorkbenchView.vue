<template>
  <div class="page-shell defect-intelligence-workbench-view">
    <!-- 1. 顶部页头 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <BugOutlined class="hero-icon text-danger" />
          <h2 class="page-title">智能缺陷聚类去重与全生命周期治理中枢</h2>
          <span class="live-dot" />
          <a-tag color="volcano">v6.0.0 智能缺陷聚类在线</a-tag>
        </div>
        <p class="page-subtitle">
          失败堆栈 64 位异常语义指纹提取、海量失败智能去重聚合、微服务责任归因与 Jira/GitHub 双向联动中枢
        </p>
      </div>

      <div class="hero-right">
        <a-space>
          <a-button type="primary" danger @click="openInspectionDrawer(selectedCluster)">
            <template #icon><EyeOutlined /></template>
            堆栈指纹拓扑透视
          </a-button>

          <a-button @click="openConfigModal">
            <template #icon><SyncOutlined /></template>
            跨平台与 SLA 策略
          </a-button>

          <a-button :loading="loading" @click="fetchData">
            <template #icon><ReloadOutlined /></template>
            刷新缺陷大盘
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 2. 4 大 Bento KPI 卡片 -->
    <div class="bento-kpi-grid">
      <!-- KPI 1 -->
      <div class="bento-card kpi-success">
        <div class="kpi-header">
          <span class="kpi-title">失败用例去重收敛率</span>
          <CheckCircleOutlined class="kpi-icon text-success" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-success font-mono">91.5%</span>
          <span class="kpi-trend text-success font-mono">杜绝垃圾提单</span>
        </div>
        <div class="kpi-footer font-mono">
          94 处同源失败收敛为 8 起主缺陷
        </div>
      </div>

      <!-- KPI 2 -->
      <div class="bento-card kpi-danger">
        <div class="kpi-header">
          <span class="kpi-title">当前活跃 Master 主缺陷</span>
          <BugOutlined class="kpi-icon text-danger" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-danger font-mono">8 起</span>
          <span class="kpi-sub font-mono text-secondary">已自动指派</span>
        </div>
        <div class="kpi-footer font-mono">
          涉及 4 个微服务领域与 3 个专班
        </div>
      </div>

      <!-- KPI 3 -->
      <div class="bento-card kpi-primary">
        <div class="kpi-header">
          <span class="kpi-title">缺陷解决 SLA 履约率</span>
          <FieldTimeOutlined class="kpi-icon text-primary" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-primary font-mono">96.2%</span>
          <span class="kpi-badge">SLA 达标</span>
        </div>
        <div class="kpi-footer font-mono">
          P0 时效: 2h 响应 / 24h 解决 (0 起超时阻断)
        </div>
      </div>

      <!-- KPI 4 -->
      <div class="bento-card kpi-purple">
        <div class="kpi-header">
          <span class="kpi-title">跨平台双向同步健康度</span>
          <ApartmentOutlined class="kpi-icon text-purple" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-purple font-mono">100%</span>
          <span class="kpi-trend text-success font-mono">双向闭环联动</span>
        </div>
        <div class="kpi-footer font-mono">
          Jira &amp; GitHub 回归自动 Resolve/Reopen
        </div>
      </div>
    </div>

    <!-- 3. 聚类主缺陷流水大盘表 -->
    <a-card class="clusters-table-card mt-4" title="智能聚类 Master 主缺陷大盘 (Deduplicated Defect Clusters)">
      <template #extra>
        <a-space>
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="按缺陷标题 / 微服务检索..."
            style="width: 260px;"
            size="small"
            @search="handleSearch"
          />
          <a-tag color="blue">当前主缺陷数: {{ filteredClusters.length }}</a-tag>
        </a-space>
      </template>

      <a-table
        :data-source="filteredClusters"
        :columns="tableColumns"
        :pagination="false"
        row-key="cluster_id"
        size="middle"
        class="clusters-table font-mono"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'master_title'">
            <a class="cluster-link font-bold text-primary" @click="openInspectionDrawer(record)">
              {{ record.master_title }}
            </a>
          </template>

          <template v-else-if="column.key === 'target_service'">
            <a-tag color="purple">{{ record.target_service }}</a-tag>
          </template>

          <template v-else-if="column.key === 'exception_type'">
            <a-tag color="volcano">{{ record.exception_type }}</a-tag>
          </template>

          <template v-else-if="column.key === 'total_failures_count'">
            <span class="badge-failures font-bold text-danger">
              {{ record.total_failures_count }} 个用例失败
            </span>
          </template>

          <template v-else-if="column.key === 'sla_status'">
            <a-tag :color="getSlaColor(record.sla_status)">
              {{ record.sla_status }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'external_sync'">
            <a-tag color="blue">
              {{ record.external_ticket_key || 'Jira 联动待同步' }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space size="small">
              <a-button size="small" type="link" @click="openInspectionDrawer(record)">
                指纹透视
              </a-button>
              <a-button size="small" type="link" @click="openConfigModal">
                同步策略
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 4. 联动组件: 堆栈指纹透视抽屉 (UI3.1) -->
    <DefectClusterInspectionDrawer
      v-model:open="inspectionDrawerOpen"
      :cluster="selectedCluster"
      @mergeToExternal="handleMergeExternal"
    />

    <!-- 5. 联动组件: 跨平台同步与 SLA 弹窗 (UI3.2) -->
    <DefectSyncConfigModal
      v-model:open="configModalOpen"
      @save="handleSaveSyncConfig"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  BugOutlined,
  EyeOutlined,
  SyncOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  FieldTimeOutlined,
  ApartmentOutlined,
} from '@ant-design/icons-vue'
import DefectClusterInspectionDrawer, { type ClusteredDefectItem } from './components/DefectClusterInspectionDrawer.vue'
import DefectSyncConfigModal, { type DefectSyncConfig } from './components/DefectSyncConfigModal.vue'

interface ClusterTableItem extends ClusteredDefectItem {
  sla_status: string
  external_ticket_key?: string
}

const loading = ref(false)
const searchKeyword = ref('')
const inspectionDrawerOpen = ref(false)
const configModalOpen = ref(false)

const clustersList = ref<ClusterTableItem[]>([
  {
    cluster_id: 'cl_master_01',
    primary_fingerprint: 'fp_hash_7fa8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8',
    master_title: '[payment-service] DatabaseConnectionTimeout in payment.py:execute_charge',
    exception_type: 'DatabaseConnectionTimeout',
    target_service: 'payment-service',
    root_cause_file: '/app/services/payment.py',
    total_failures_count: 14,
    linked_case_ids: ['case_checkout_wechat', 'case_checkout_alipay', 'case_order_retry_01'],
    associated_case_names: ['收银台微信支付验证', '收银台支付宝验证', '订单异步重试01'],
    sla_status: 'HEALTHY (剩余 18h)',
    external_ticket_key: 'JIRA-BUG-4021',
    responsible_team: '资金结算与计费组',
    suggested_assignee: '李强 (支付架构师)',
  },
  {
    cluster_id: 'cl_master_02',
    primary_fingerprint: 'fp_hash_11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff',
    master_title: '[auth-service] AuthTokenExpiredError in auth.py:verify_token',
    exception_type: 'AuthTokenExpiredError',
    target_service: 'auth-service',
    root_cause_file: '/app/services/auth.py',
    total_failures_count: 8,
    linked_case_ids: ['case_user_login', 'case_token_refresh'],
    associated_case_names: ['用户密码登录', 'Token自动续约'],
    sla_status: 'HEALTHY (剩余 40h)',
    external_ticket_key: 'GitHub: #452',
    responsible_team: '统一身份与安全中台组',
    suggested_assignee: '张雪 (安全工程师)',
  },
  {
    cluster_id: 'cl_master_03',
    primary_fingerprint: 'fp_hash_99887766554433221100ffeeddccbbaa99887766554433221100ffeeddccbbaa',
    master_title: '[order-service] 502 Bad Gateway: upstream order-service crashed',
    exception_type: 'BadGatewayError',
    target_service: 'order-service',
    root_cause_file: '/app/services/order.py',
    total_failures_count: 22,
    linked_case_ids: ['case_cart_submit', 'case_order_create'],
    associated_case_names: ['购物车提交', '订单创建主流程'],
    sla_status: 'WARNING (剩余 5h)',
    external_ticket_key: 'JIRA-BUG-4088',
    responsible_team: '订单与履约中台组',
    suggested_assignee: '王建国 (订单负责人)',
  },
])

const selectedCluster = ref<ClusterTableItem>(clustersList.value[0])

const tableColumns = [
  { title: 'Master 主缺陷标题', key: 'master_title', width: 340 },
  { title: '责任微服务', key: 'target_service', width: 150 },
  { title: '异常类型', key: 'exception_type', width: 180 },
  { title: '同源聚合失败数', key: 'total_failures_count', width: 150 },
  { title: 'SLA 履约倒计时', key: 'sla_status', width: 170 },
  { title: '外部平台联动', key: 'external_sync', width: 160 },
  { title: '快捷操作', key: 'actions', width: 160 },
]

const filteredClusters = computed(() => {
  if (!searchKeyword.value.trim()) return clustersList.value
  const kw = searchKeyword.value.trim().toLowerCase()
  return clustersList.value.filter(
    (c) =>
      c.master_title.toLowerCase().includes(kw) ||
      c.target_service.toLowerCase().includes(kw) ||
      c.exception_type.toLowerCase().includes(kw)
  )
})

function getSlaColor(status: string): string {
  if (status.includes('WARNING')) return 'orange'
  if (status.includes('BREACHED')) return 'red'
  return 'green'
}

function openInspectionDrawer(clusterItem?: any) {
  if (clusterItem) {
    selectedCluster.value = clusterItem
  }
  inspectionDrawerOpen.value = true
}

function openConfigModal() {
  configModalOpen.value = true
}

function fetchData() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
  }, 400)
}

function handleSearch() {
  // filteredClusters handles filter
}

function handleMergeExternal(clusterId: string, externalId: string) {
  const target = clustersList.value.find((c) => c.cluster_id === clusterId)
  if (target) {
    target.external_ticket_key = externalId
  }
}

function handleSaveSyncConfig(_config: DefectSyncConfig) {
  // config saved
}
</script>

<style scoped>
.defect-intelligence-workbench-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 18px 24px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #f0f0f0);
  border-radius: 8px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 22px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--c-text-secondary, #666);
}

.bento-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.bento-card {
  padding: 16px;
  border-radius: 8px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #f0f0f0);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.2s ease;
}

.bento-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--c-border-strong, #d9d9d9);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kpi-title {
  font-size: 13px;
  color: var(--c-text-secondary, #666);
}

.kpi-icon {
  font-size: 18px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 12px 0 8px;
}

.kpi-number {
  font-size: 26px;
  font-weight: 700;
}

.kpi-trend,
.kpi-sub {
  font-size: 12px;
}

.kpi-badge {
  font-size: 11px;
  padding: 2px 6px;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #52c41a;
  border-radius: 4px;
}

.kpi-footer {
  font-size: 11px;
  color: var(--c-text-tertiary, #999);
}

.mt-4 {
  margin-top: 16px;
}

.text-danger {
  color: #ff4d4f;
}

.text-success {
  color: #52c41a;
}

.text-warning {
  color: #faad14;
}

.text-primary {
  color: #1677ff;
}

.text-purple {
  color: #722ed1;
}

@media (max-width: 1024px) {
  .bento-kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .bento-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
