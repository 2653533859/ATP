<template>
  <div class="page-shell stress-testing-workbench-view">
    <!-- 1. 顶部页头 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <ThunderboltOutlined class="hero-icon text-primary" />
          <h2 class="page-title">全链路生产影子压测与架构容量基线中枢</h2>
          <span class="live-dot" />
          <a-tag color="processing">v6.2.0 生产全链路压测在线</a-tag>
        </div>
        <p class="page-subtitle">
          基于 USL 通用可伸缩性定律推演系统容量拐点、全链路影子流量隔离、分布式发压调度与生产防击穿秒级自动熔断控制大盘
        </p>
      </div>

      <div class="hero-right">
        <a-space>
          <a-button type="primary" @click="handleOpenDrawer(selectedServiceItem)">
            <template #icon><BranchesOutlined /></template>
            发压链路透视
          </a-button>

          <a-button @click="handleOpenConfigModal(selectedServiceItem)">
            <template #icon><ControlOutlined /></template>
            发压策略与围栏
          </a-button>

          <a-button :loading="loading" @click="fetchData">
            <template #icon><ReloadOutlined /></template>
            刷新压测大盘
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 2. 4 大 Bento KPI 卡片 -->
    <div class="bento-kpi-grid">
      <!-- KPI 1 -->
      <div class="bento-card kpi-primary">
        <div class="kpi-header">
          <span class="kpi-title">生产当前实测峰值吞吐</span>
          <ThunderboltOutlined class="kpi-icon text-primary" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-primary font-mono">16,500</span>
          <span class="kpi-trend text-primary font-mono">TPS 峰值</span>
        </div>
        <div class="kpi-footer font-mono">
          全链路分布式发压，3 节点集群承载
        </div>
      </div>

      <!-- KPI 2 -->
      <div class="bento-card kpi-success">
        <div class="kpi-header">
          <span class="kpi-title">架构容量饱和度 (USL)</span>
          <CheckCircleOutlined class="kpi-icon text-success" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-success font-mono">82.5%</span>
          <span class="kpi-sub font-mono text-success">接近拐点</span>
        </div>
        <div class="kpi-footer font-mono">
          距离饱和极限 19,200 TPS 保留 17.5% 弹性
        </div>
      </div>

      <!-- KPI 3 -->
      <div class="bento-card kpi-warning">
        <div class="kpi-header">
          <span class="kpi-title">识别架构性能瓶颈节点</span>
          <AlertOutlined class="kpi-icon text-warning" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-warning font-mono">1 个</span>
          <span class="kpi-trend text-warning font-mono">延迟上翘</span>
        </div>
        <div class="kpi-footer font-mono">
          order-service 存在数据库分布式锁争用
        </div>
      </div>

      <!-- KPI 4 -->
      <div class="bento-card kpi-info">
        <div class="kpi-header">
          <span class="kpi-title">累计过载紧急熔断泄压</span>
          <StopOutlined class="kpi-icon text-info" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-info font-mono">6 次</span>
          <span class="kpi-trend text-success font-mono">零故障扩散</span>
        </div>
        <div class="kpi-footer font-mono">
          看门狗切流成功率 100%，毫秒级清零并发
        </div>
      </div>
    </div>

    <!-- 3. 微服务发压作业控制主大盘表格 -->
    <div class="table-container mt-4">
      <div class="table-toolbar">
        <div class="toolbar-left font-bold text-sm">
          <ApartmentOutlined class="mr-1 text-primary" />
          微服务生产全链路影子压测作业与容量监控列表
        </div>
        <div class="toolbar-right">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="按服务名或模型过滤..."
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
        class="stress-table"
      >
        <!-- 微服务名称 -->
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'service_name'">
            <div class="service-cell">
              <CloudServerOutlined class="mr-2 text-primary" />
              <span class="font-bold font-mono">{{ record.service_name }}</span>
            </div>
          </template>

          <!-- 负载模型 -->
          <template v-else-if="column.key === 'profile_type'">
            <a-tag color="blue" class="font-mono">
              {{ record.profile_type }}
            </a-tag>
          </template>

          <!-- 并发水位进度条 -->
          <template v-else-if="column.key === 'vu_concurrency'">
            <div class="vu-cell">
              <div class="vu-text font-mono text-xs mb-1">
                <span class="text-primary font-bold">{{ record.current_vu }} VU</span>
                <span class="text-secondary ml-2">/ 目标 {{ record.target_peak_vu }} VU</span>
              </div>
              <a-progress
                :percent="Math.round((record.current_vu / Math.max(1, record.target_peak_vu)) * 100)"
                size="small"
                :status="record.current_vu === 0 ? 'exception' : 'active'"
              />
            </div>
          </template>

          <!-- 实测性能 (TPS / RT) -->
          <template v-else-if="column.key === 'metrics'">
            <div class="font-mono text-xs">
              <div>吞吐: <strong class="text-primary">{{ record.measured_tps.toLocaleString() }} TPS</strong></div>
              <div>P99: <span class="text-warning">{{ record.measured_p99_ms.toFixed(1) }} ms</span></div>
            </div>
          </template>

          <!-- USL 容量拐点 -->
          <template v-else-if="column.key === 'knee_point'">
            <div class="font-mono text-xs">
              <div>拐点: <span class="text-success font-bold">{{ record.knee_point_vu }} VU</span></div>
              <div>天花板: <span class="text-secondary">{{ record.saturation_vu }} VU</span></div>
            </div>
          </template>

          <!-- 影子存储防污染状态 -->
          <template v-else-if="column.key === 'isolation'">
            <a-tag :color="record.is_pollution_detected ? 'error' : 'success'" class="font-mono">
              {{ record.is_pollution_detected ? '污染泄漏！' : '100% 影子隔离' }}
            </a-tag>
          </template>

          <!-- 操作按钮列 -->
          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button type="link" size="small" @click="handleOpenDrawer(record)">
                链路透视
              </a-button>
              <a-button type="link" size="small" @click="handleOpenConfigModal(record)">
                策略围栏
              </a-button>
              <a-popconfirm
                title="确定对该服务执行秒级紧急泄压急停吗？将瞬间清零并发并切断流量！"
                ok-text="确认泄压"
                cancel-text="取消"
                ok-type="danger"
                @confirm="handleTriggerEmergencyStop(record.service_name)"
              >
                <a-button type="link" danger size="small">
                  紧急泄压
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 4. 挂载子组件：全链路发压拓扑透视抽屉 -->
    <StressTopologyInspectionDrawer
      v-model:open="drawerOpen"
      :target-service="selectedServiceItem?.service_name"
      :current-vu="selectedServiceItem?.current_vu"
      :current-tps="selectedServiceItem?.measured_tps"
      :p99-latency-ms="selectedServiceItem?.measured_p99_ms"
      :error-rate-pct="selectedServiceItem?.error_rate_pct"
      :knee-point-vu="selectedServiceItem?.knee_point_vu"
      :bottleneck-node="selectedServiceItem?.bottleneck_node"
      @emergency-stop="handleTriggerEmergencyStop"
      @refresh="fetchData"
    />

    <!-- 5. 挂载子组件：分布式发压策略配置与围栏弹窗 -->
    <StressConfigModal
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
  ThunderboltOutlined,
  BranchesOutlined,
  ControlOutlined,
  ReloadOutlined,
  CloudServerOutlined,
  CheckCircleOutlined,
  AlertOutlined,
  StopOutlined,
  ApartmentOutlined,
} from '@ant-design/icons-vue'
import StressTopologyInspectionDrawer from './components/StressTopologyInspectionDrawer.vue'
import StressConfigModal from './components/StressConfigModal.vue'

export interface StressServiceItem {
  service_name: string
  profile_type: string
  current_vu: number
  target_peak_vu: number
  measured_tps: number
  measured_p99_ms: number
  error_rate_pct: number
  knee_point_vu: number
  saturation_vu: number
  bottleneck_node?: string
  is_pollution_detected: boolean
}

const loading = ref(false)
const searchKeyword = ref('')
const drawerOpen = ref(false)
const configModalOpen = ref(false)

const mockServices: StressServiceItem[] = [
  {
    service_name: 'payment-service',
    profile_type: 'STEP_RAMP_UP',
    current_vu: 5000,
    target_peak_vu: 6000,
    measured_tps: 14800,
    measured_p99_ms: 185.0,
    error_rate_pct: 0.08,
    knee_point_vu: 4200,
    saturation_vu: 7500,
    bottleneck_node: 't_payment_shadow (锁争用)',
    is_pollution_detected: false,
  },
  {
    service_name: 'order-service',
    profile_type: 'STEP_RAMP_UP',
    current_vu: 4000,
    target_peak_vu: 5000,
    measured_tps: 12500,
    measured_p99_ms: 220.0,
    error_rate_pct: 0.12,
    knee_point_vu: 3600,
    saturation_vu: 6200,
    bottleneck_node: 'db-writer-pod-02 (CPU高)',
    is_pollution_detected: false,
  },
  {
    service_name: 'cart-service',
    profile_type: 'CONSTANT_STEADY',
    current_vu: 3000,
    target_peak_vu: 3000,
    measured_tps: 9800,
    measured_p99_ms: 65.0,
    error_rate_pct: 0.01,
    knee_point_vu: 4500,
    saturation_vu: 8000,
    is_pollution_detected: false,
  },
  {
    service_name: 'inventory-service',
    profile_type: 'SPIKE_SURGE',
    current_vu: 8000,
    target_peak_vu: 10000,
    measured_tps: 16500,
    measured_p99_ms: 195.0,
    error_rate_pct: 0.05,
    knee_point_vu: 7200,
    saturation_vu: 12000,
    is_pollution_detected: false,
  },
]

const servicesList = ref<StressServiceItem[]>([...mockServices])
const selectedServiceItem = ref<StressServiceItem>(servicesList.value[0])

const filteredServices = computed(() => {
  if (!searchKeyword.value.trim()) return servicesList.value
  const kw = searchKeyword.value.toLowerCase().trim()
  return servicesList.value.filter(
    (s) =>
      s.service_name.toLowerCase().includes(kw) ||
      s.profile_type.toLowerCase().includes(kw)
  )
})

const columns = [
  { title: '微服务名称', key: 'service_name', width: 200 },
  { title: '加压模型', key: 'profile_type', width: 160 },
  { title: '并发水位 (当前 / 峰值)', key: 'vu_concurrency', width: 220 },
  { title: '实测性能 (TPS / RT)', key: 'metrics', width: 200 },
  { title: 'USL 容量拐点', key: 'knee_point', width: 180 },
  { title: '影子存储隔离', key: 'isolation', width: 160 },
  { title: '操作', key: 'actions', width: 200 },
]

function handleOpenDrawer(record?: any) {
  if (record) {
    selectedServiceItem.value = record as StressServiceItem
  }
  drawerOpen.value = true
}

function handleOpenConfigModal(record?: any) {
  if (record) {
    selectedServiceItem.value = record as StressServiceItem
  }
  configModalOpen.value = true
}

function handleTriggerEmergencyStop(serviceName: string) {
  const item = servicesList.value.find((s) => s.service_name === serviceName)
  if (item) {
    item.current_vu = 0
  }
  message.success(`已对服务 ${serviceName} 触发紧急泄压急停！发压并发已瞬间清零！`)
}

function handleSaveConfig(config: any) {
  void config
  message.success('分布式压测策略配置已成功保存并下发！')
  configModalOpen.value = false
}

function fetchData() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    message.success('全链路压测大盘监控态已刷新！')
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

.vu-cell {
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

.font-mono {
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}
</style>
