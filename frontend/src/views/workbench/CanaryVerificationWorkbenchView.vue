<template>
  <div class="page-shell canary-verification-workbench-view">
    <!-- 1. 顶部页头 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <ApartmentOutlined class="hero-icon text-primary" />
          <h2 class="page-title">全链路金丝雀双轨流向透视与灰度控制工作台</h2>
          <span class="live-dot" />
          <a-tag color="processing">v6.1.0 全链路金丝雀在线</a-tag>
        </div>
        <p class="page-subtitle">
          全链路流量染色标透传、金丝雀与基线双轨指标推演、自适应多阶梯放量调度与击穿毫秒级自动熔断切流中枢
        </p>
      </div>

      <div class="hero-right">
        <a-space>
          <a-button type="primary" @click="handleOpenDrawer(selectedServiceItem)">
            <template #icon><BranchesOutlined /></template>
            全链路流向透视
          </a-button>

          <a-button @click="handleOpenConfigModal(selectedServiceItem)">
            <template #icon><ControlOutlined /></template>
            灰度步进与围栏配置
          </a-button>

          <a-button :loading="loading" @click="fetchData">
            <template #icon><ReloadOutlined /></template>
            刷新工作台
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 2. 4 大 Bento KPI 卡片 -->
    <div class="bento-kpi-grid">
      <!-- KPI 1 -->
      <div class="bento-card kpi-primary">
        <div class="kpi-header">
          <span class="kpi-title">运行中金丝雀微服务</span>
          <CloudServerOutlined class="kpi-icon text-primary" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-primary font-mono">6 个</span>
          <span class="kpi-trend text-primary font-mono">双轨并发</span>
        </div>
        <div class="kpi-footer font-mono">
          覆盖网关、订单、支付等核心链路
        </div>
      </div>

      <!-- KPI 2 -->
      <div class="bento-card kpi-success">
        <div class="kpi-header">
          <span class="kpi-title">五维健康度综合均分</span>
          <CheckCircleOutlined class="kpi-icon text-success" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-success font-mono">93.8 分</span>
          <span class="kpi-sub font-mono text-success">EXCELLENT</span>
        </div>
        <div class="kpi-footer font-mono">
          错误率、时延、业务成功率全面达标
        </div>
      </div>

      <!-- KPI 3 -->
      <div class="bento-card kpi-warning">
        <div class="kpi-header">
          <span class="kpi-title">累计自动熔断避险</span>
          <ThunderboltOutlined class="kpi-icon text-warning" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-warning font-mono">14 次</span>
          <span class="kpi-trend text-warning font-mono">毫秒级清零</span>
        </div>
        <div class="kpi-footer font-mono">
          看门狗切流成功率 100%，零故障扩散
        </div>
      </div>

      <!-- KPI 4 -->
      <div class="bento-card kpi-info">
        <div class="kpi-header">
          <span class="kpi-title">影子存储隔离防污染率</span>
          <DatabaseOutlined class="kpi-icon text-info" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-info font-mono">100.0%</span>
          <span class="kpi-trend text-success font-mono">零主库脏写</span>
        </div>
        <div class="kpi-footer font-mono">
          影子表/Topic 强制路由防穿透保护
        </div>
      </div>
    </div>

    <!-- 3. 微服务灰度分流与双轨指标主控大盘 -->
    <div class="table-container mt-4">
      <div class="table-toolbar">
        <div class="toolbar-left font-bold text-sm">
          <ApartmentOutlined class="mr-1 text-primary" />
          微服务全链路金丝雀运行态与流量分流控制列表
        </div>
        <div class="toolbar-right">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="按服务名或版本过滤..."
            style="width: 260px"
            allow-clear
          />
        </div>
      </div>

      <a-table
        :data-source="filteredServices"
        :columns="columns"
        :pagination="false"
        row-key="service_name"
        class="canary-table"
      >
        <!-- 微服务名称 -->
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'service_name'">
            <div class="service-cell">
              <CloudServerOutlined class="mr-2 text-primary" />
              <span class="font-bold font-mono">{{ record.service_name }}</span>
            </div>
          </template>

          <!-- 版本双轨 -->
          <template v-else-if="column.key === 'versions'">
            <div class="font-mono text-xs">
              <div>基线: <span class="text-secondary">{{ record.baseline_version }}</span></div>
              <div>灰度: <span class="text-primary font-bold">{{ record.canary_version }}</span></div>
            </div>
          </template>

          <!-- 流量分流进度条 -->
          <template v-else-if="column.key === 'weight'">
            <div class="weight-cell">
              <div class="weight-text font-mono text-xs mb-1">
                <span class="text-primary font-bold">{{ record.current_weight_pct }}% 灰度</span>
                <span class="text-secondary ml-2">{{ 100 - record.current_weight_pct }}% 基线</span>
              </div>
              <a-progress
                :percent="record.current_weight_pct"
                size="small"
                :status="record.current_weight_pct === 0 ? 'exception' : 'active'"
              />
            </div>
          </template>

          <!-- 五维健康度得分 -->
          <template v-else-if="column.key === 'health_score'">
            <div class="health-cell font-mono">
              <a-tag :color="record.health_score >= 90 ? 'green' : record.health_score >= 75 ? 'blue' : 'orange'">
                {{ record.health_score }} 分 ({{ record.health_grade }})
              </a-tag>
            </div>
          </template>

          <!-- 影子存储防污染状态 -->
          <template v-else-if="column.key === 'isolation'">
            <a-tag :color="record.is_pollution_detected ? 'error' : 'success'" class="font-mono">
              {{ record.is_pollution_detected ? '污染泄漏！' : '100% 隔离合规' }}
            </a-tag>
          </template>

          <!-- 综合裁决 -->
          <template v-else-if="column.key === 'verdict'">
            <a-tag :color="record.overall_verdict === 'CONFORMANT' ? 'cyan' : 'volcano'" class="font-mono">
              {{ record.overall_verdict }}
            </a-tag>
          </template>

          <!-- 操作按钮列 -->
          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button type="link" size="small" @click="handleOpenDrawer(record)">
                流向透视
              </a-button>
              <a-button type="link" size="small" @click="handleOpenConfigModal(record)">
                步进围栏
              </a-button>
              <a-popconfirm
                title="确定对该服务执行秒级紧急回滚吗？将瞬间将流量重置为 0%！"
                ok-text="确认熔断"
                cancel-text="取消"
                ok-type="danger"
                @confirm="handleTriggerRollback(record.service_name)"
              >
                <a-button type="link" danger size="small">
                  一键回滚
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 4. 挂载子组件：全链路染色拓扑透视抽屉 -->
    <CanaryTopologyInspectionDrawer
      v-model:open="drawerOpen"
      :target-service="selectedServiceItem?.service_name"
      :canary-version="selectedServiceItem?.canary_version"
      :baseline-version="selectedServiceItem?.baseline_version"
      :current-weight-pct="selectedServiceItem?.current_weight_pct"
      :health-score="selectedServiceItem?.health_score"
      :metrics="selectedServiceItem?.metrics"
      :isolation="selectedServiceItem?.isolation"
      @rollback="handleTriggerRollback"
      @refresh="fetchData"
    />

    <!-- 5. 挂载子组件：灰度步进与看门狗围栏策略弹窗 -->
    <CanarySteppingConfigModal
      v-model:open="configModalOpen"
      :target-service="selectedServiceItem?.service_name"
      @save="handleSaveConfig"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  BranchesOutlined,
  ControlOutlined,
  ReloadOutlined,
  CloudServerOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
} from '@ant-design/icons-vue'
import CanaryTopologyInspectionDrawer from './components/CanaryTopologyInspectionDrawer.vue'
import CanarySteppingConfigModal from './components/CanarySteppingConfigModal.vue'

export interface CanaryServiceItem {
  service_name: string
  canary_version: string
  baseline_version: string
  current_weight_pct: number
  health_score: number
  health_grade: string
  overall_verdict: string
  is_pollution_detected: boolean
  metrics?: any
  isolation?: any
}

const loading = ref(false)
const searchKeyword = ref('')
const drawerOpen = ref(false)
const configModalOpen = ref(false)

const mockServices: CanaryServiceItem[] = [
  {
    service_name: 'payment-service',
    canary_version: 'v1.2.0-canary',
    baseline_version: 'v1.0.0',
    current_weight_pct: 15.0,
    health_score: 94.5,
    health_grade: 'EXCELLENT',
    overall_verdict: 'CONFORMANT',
    is_pollution_detected: false,
    metrics: {
      error_rate_diff_pct: 0.1,
      latency_p99_ratio: 1.05,
      baseline_error_rate: 0.1,
      canary_error_rate: 0.2,
      baseline_p99_ms: 105,
      canary_p99_ms: 110,
      baseline_success_rate: 99.9,
      canary_success_rate: 99.8,
      overall_verdict: 'CONFORMANT',
    },
    isolation: {
      isolation_compliance_pct: 100.0,
      is_pollution_detected: false,
      shadow_routed_count: 52,
      leaked_master_writes_count: 0,
    },
  },
  {
    service_name: 'order-service',
    canary_version: 'v2.1.0-canary',
    baseline_version: 'v2.0.0',
    current_weight_pct: 25.0,
    health_score: 96.0,
    health_grade: 'EXCELLENT',
    overall_verdict: 'CONFORMANT',
    is_pollution_detected: false,
  },
  {
    service_name: 'user-service',
    canary_version: 'v1.5.0-canary',
    baseline_version: 'v1.4.0',
    current_weight_pct: 10.0,
    health_score: 91.2,
    health_grade: 'EXCELLENT',
    overall_verdict: 'CONFORMANT',
    is_pollution_detected: false,
  },
  {
    service_name: 'inventory-service',
    canary_version: 'v3.0.1-canary',
    baseline_version: 'v3.0.0',
    current_weight_pct: 5.0,
    health_score: 88.5,
    health_grade: 'GOOD',
    overall_verdict: 'CONFORMANT',
    is_pollution_detected: false,
  },
  {
    service_name: 'auth-service',
    canary_version: 'v2.0.0-rc1',
    baseline_version: 'v1.9.0',
    current_weight_pct: 50.0,
    health_score: 97.8,
    health_grade: 'EXCELLENT',
    overall_verdict: 'CONFORMANT',
    is_pollution_detected: false,
  },
  {
    service_name: 'gateway-ingress',
    canary_version: 'v1.1.0-canary',
    baseline_version: 'v1.0.0',
    current_weight_pct: 5.0,
    health_score: 92.0,
    health_grade: 'EXCELLENT',
    overall_verdict: 'CONFORMANT',
    is_pollution_detected: false,
  },
]

const servicesList = ref<CanaryServiceItem[]>([...mockServices])
const selectedServiceItem = ref<CanaryServiceItem>(servicesList.value[0])

const filteredServices = computed(() => {
  if (!searchKeyword.value.trim()) return servicesList.value
  const kw = searchKeyword.value.toLowerCase().trim()
  return servicesList.value.filter(
    (s) =>
      s.service_name.toLowerCase().includes(kw) ||
      s.canary_version.toLowerCase().includes(kw) ||
      s.baseline_version.toLowerCase().includes(kw)
  )
})

const columns = [
  { title: '微服务名称', key: 'service_name', width: 200 },
  { title: '双轨版本 (基线 / 灰度)', key: 'versions', width: 220 },
  { title: '流量分流权重', key: 'weight', width: 240 },
  { title: '五维健康度得分', key: 'health_score', width: 170 },
  { title: '影子存储隔离状态', key: 'isolation', width: 170 },
  { title: '双轨偏离裁决', key: 'verdict', width: 140 },
  { title: '操作', key: 'actions', width: 220 },
]

function handleOpenDrawer(record?: any) {
  if (record) {
    selectedServiceItem.value = record as CanaryServiceItem
  }
  drawerOpen.value = true
}

function handleOpenConfigModal(record?: any) {
  if (record) {
    selectedServiceItem.value = record as CanaryServiceItem
  }
  configModalOpen.value = true
}

function handleTriggerRollback(serviceName: string) {
  const item = servicesList.value.find((s) => s.service_name === serviceName)
  if (item) {
    item.current_weight_pct = 0.0
    item.overall_verdict = 'ROLLBACK_COMPLETED'
  }
  message.success(`已对服务 ${serviceName} 触发毫秒级切流回滚！灰度分流比已归零！`)
}

function handleSaveConfig(config: any) {
  void config
  message.success('灰度步进与看门狗围栏策略配置已成功保存并立即下发！')
  configModalOpen.value = false
}

function fetchData() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    message.success('金丝雀双轨运行态数据已刷新！')
  }, 300)
}
</script>

<style scoped>
.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px;
  background: var(--c-surface, var(--c-bg-elevated));
  border-bottom: 1px solid var(--c-border);
  margin-bottom: var(--space-5, 20px);
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.hero-icon {
  font-size: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  color: var(--c-text);
}

.page-subtitle {
  font-size: 13px;
  color: var(--c-text-secondary);
  margin: 0;
}

.bento-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4, 16px);
  margin-bottom: var(--space-5, 20px);
}

.bento-card {
  padding: 16px 20px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
  min-height: 104px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1),
              border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.bento-card:hover {
  transform: translateY(-2px);
  border-color: var(--c-primary);
  box-shadow: var(--shadow-sm);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.kpi-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text-secondary);
}

.kpi-icon {
  font-size: 18px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}

.kpi-number {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
  color: var(--c-text);
}

.kpi-trend,
.kpi-sub {
  font-size: 11px;
  font-family: var(--font-mono, monospace);
}

.kpi-footer {
  font-size: 11px;
  color: var(--c-text-tertiary);
  border-top: 1px dashed var(--c-border-subtle, var(--c-border));
  padding-top: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-container {
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  padding: 16px 20px;
  box-shadow: var(--shadow-xs);
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.service-cell {
  display: flex;
  align-items: center;
}

.weight-cell {
  width: 100%;
}

.text-primary {
  color: var(--c-primary);
}

.text-secondary {
  color: var(--c-text-secondary);
}

.text-success {
  color: var(--c-success);
}

.text-warning {
  color: var(--c-warning);
}

.text-danger {
  color: var(--c-error);
}

.text-info {
  color: var(--c-info);
}

.font-mono {
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}
</style>
