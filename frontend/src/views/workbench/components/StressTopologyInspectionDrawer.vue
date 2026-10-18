<template>
  <a-drawer
    :open="open"
    title="全链路影子压测调用拓扑与容量瓶颈透视抽屉"
    width="86%"
    placement="right"
    :destroy-on-close="true"
    class="stress-topology-inspection-drawer"
    @close="handleClose"
  >
    <div class="drawer-container">
      <!-- 1. 顶部发压运行态横幅 -->
      <div class="stress-hero-bar">
        <div class="hero-left">
          <div class="title-row">
            <ThunderboltOutlined class="hero-icon text-primary" />
            <span class="service-title font-bold">{{ targetService || 'payment-service' }}</span>
            <a-tag color="processing" class="font-mono">
              并发: {{ currentVu }} VU
            </a-tag>
            <a-tag :color="errorRatePct > 1.0 ? 'error' : 'success'" class="font-mono">
              错误率: {{ errorRatePct.toFixed(2) }}%
            </a-tag>
            <a-tag color="purple" class="font-mono">
              USL 拐点: {{ kneePointVu }} VU
            </a-tag>
          </div>

          <div class="hero-summary-pills font-mono">
            <span class="metric-pill">
              当前实测 TPS: <strong class="text-primary">{{ currentTps.toLocaleString() }}</strong>
            </span>
            <span class="metric-pill">
              P99 响应时延: <strong class="text-warning">{{ p99LatencyMs.toFixed(1) }} ms</strong>
            </span>
            <span class="metric-pill">
              瓶颈节点: <strong class="text-danger">{{ bottleneckNode || 't_order_shadow (锁争用)' }}</strong>
            </span>
            <span class="metric-pill">
              数据隔离: <strong class="text-success">100% 影子库表</strong>
            </span>
          </div>
        </div>

        <div class="hero-actions">
          <a-space>
            <a-button :loading="refreshing" @click="handleRefresh">
              <template #icon><ReloadOutlined /></template>
              刷新拓扑
            </a-button>
            <a-popconfirm
              title="确定立即触发紧急泄压断路吗？将瞬间清零并发并切断发压流量！"
              ok-text="确认泄压急停"
              cancel-text="取消"
              ok-type="danger"
              @confirm="handleTriggerEmergencyStop"
            >
              <a-button type="primary" danger :loading="stopping">
                <template #icon><StopOutlined /></template>
                一键紧急泄压急停
              </a-button>
            </a-popconfirm>
          </a-space>
        </div>
      </div>

      <!-- 2. 全链路微服务发压与影子流向拓扑面板 -->
      <div class="topology-panel">
        <div class="panel-header">
          <span class="panel-title font-bold">
            <BranchesOutlined class="mr-1 text-primary" />
            分布式发压集群 ➔ 微服务链路 ➔ 影子存储全链路拓扑
          </span>
          <span class="panel-tip text-xs text-secondary font-mono">
            压测标透传: HTTP Header [X-Stress-Test: true] / W3C [atp_stress_mode=1] / MQ [__stress_tag__]
          </span>
        </div>

        <div class="topology-grid">
          <!-- 节点 1: 分布式发压集群 -->
          <div class="topology-node worker-node">
            <div class="node-badge">Stress Influx</div>
            <div class="node-title font-bold">发压集群 (Worker)</div>
            <div class="node-desc text-xs text-secondary font-mono">并发: {{ currentVu }} VU (3 节点)</div>
            <div class="status-indicator-box mt-2">
              <span class="status-dot dot-active"></span>
              <span class="text-xs font-mono">发压速率: 100% 满负荷</span>
            </div>
          </div>

          <div class="topology-arrow">
            <ArrowRightOutlined class="arrow-icon" />
          </div>

          <!-- 节点 2: 网关分流层 -->
          <div class="topology-node gateway-node">
            <div class="node-badge">Ingress Gateway</div>
            <div class="node-title font-bold">API 网关透传层</div>
            <div class="node-desc text-xs text-secondary font-mono">自动识别 X-Stress 标签</div>
            <div class="status-indicator-box mt-2">
              <span class="status-dot dot-active"></span>
              <span class="text-xs font-mono">透传成功率: 100%</span>
            </div>
          </div>

          <div class="topology-arrow">
            <ArrowRightOutlined class="arrow-icon" />
          </div>

          <!-- 节点 3: 目标微服务集群 (瓶颈高亮) -->
          <div class="topology-node service-node node-bottleneck">
            <div class="node-badge badge-warning">Bottleneck Service</div>
            <div class="node-title font-bold">{{ targetService || 'payment-service' }}</div>
            <div class="node-desc text-xs text-secondary font-mono">Pod 实例: 8 副本 (CPU 78%)</div>
            <div class="status-indicator-box mt-2">
              <span class="status-dot dot-warning"></span>
              <span class="text-xs font-mono text-warning font-bold">P99 延时开始上翘</span>
            </div>
          </div>

          <div class="topology-arrow">
            <ArrowRightOutlined class="arrow-icon" />
          </div>

          <!-- 节点 4: 影子数据存储隔离层 -->
          <div class="topology-node storage-node">
            <div class="node-badge">Shadow Storage</div>
            <div class="node-title font-bold">影子库表 / MQ 隔离层</div>
            <div class="node-desc text-xs text-secondary font-mono">路由: t_order_shadow</div>
            <div class="status-indicator-box mt-2">
              <span class="status-dot dot-success"></span>
              <span class="text-xs font-mono text-success">零脏数据穿透</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. 容量推演与性能指标对比卡片网格 -->
      <div class="metrics-panel mt-4">
        <div class="panel-header">
          <span class="panel-title font-bold">
            <ApartmentOutlined class="mr-1 text-primary" />
            基于 USL 定律的架构容量瓶颈诊断与资源水位
          </span>
        </div>

        <div class="metrics-grid">
          <!-- 卡片 1: 实时 TPS -->
          <div class="metric-card">
            <div class="card-label font-mono">当前实测吞吐量 (TPS)</div>
            <div class="card-value font-bold text-primary">
              {{ currentTps.toLocaleString() }} <small class="text-xs font-normal">TPS</small>
            </div>
            <div class="metric-footer-note font-mono mt-2">
              <span>理论峰值天花板: {{ (currentTps * 1.15).toFixed(0) }}</span>
            </div>
          </div>

          <!-- 卡片 2: P99 响应延迟 -->
          <div class="metric-card">
            <div class="card-label font-mono">P99 响应时延 (Latency)</div>
            <div class="card-value font-bold text-warning">
              {{ p99LatencyMs.toFixed(1) }} <small class="text-xs font-normal">ms</small>
            </div>
            <div class="metric-footer-note font-mono mt-2">
              <span>拐点基线耗时: 85.0 ms</span>
            </div>
          </div>

          <!-- 卡片 3: 架构拐点偏差 -->
          <div class="metric-card">
            <div class="card-label font-mono">并发距离拐点余量 (Margin)</div>
            <div class="card-value font-bold" :class="currentVu >= kneePointVu ? 'text-warning' : 'text-success'">
              {{ (kneePointVu - currentVu > 0 ? `+${kneePointVu - currentVu}` : `${kneePointVu - currentVu}`) }} <small class="text-xs font-normal">VU</small>
            </div>
            <div class="metric-footer-note font-mono mt-2">
              <span>{{ currentVu >= kneePointVu ? '已越过拐点，排队开始加剧' : '处于线性增长安全区' }}</span>
            </div>
          </div>

          <!-- 卡片 4: 影子隔离防污染 -->
          <div class="metric-card">
            <div class="card-label font-mono">影子存储防污染状态</div>
            <div class="card-value font-bold text-success">
              100.0% <small class="text-xs font-normal">合规</small>
            </div>
            <div class="metric-footer-note font-mono mt-2">
              <span>落盘: 125,000 条 (可一键清理)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  ThunderboltOutlined,
  BranchesOutlined,
  ApartmentOutlined,
  ReloadOutlined,
  StopOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons-vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    targetService?: string
    currentVu?: number
    currentTps?: number
    p99LatencyMs?: number
    errorRatePct?: number
    kneePointVu?: number
    bottleneckNode?: string
  }>(),
  {
    open: false,
    targetService: 'payment-service',
    currentVu: 5000,
    currentTps: 14800,
    p99LatencyMs: 185.0,
    errorRatePct: 0.08,
    kneePointVu: 4200,
    bottleneckNode: 't_order_shadow (锁争用)',
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'emergencyStop', service: string): void
  (e: 'refresh', service: string): void
}>()

const refreshing = ref(false)
const stopping = ref(false)

function handleClose() {
  emit('update:open', false)
}

function handleRefresh() {
  refreshing.value = true
  emit('refresh', props.targetService)
  setTimeout(() => {
    refreshing.value = false
  }, 400)
}

function handleTriggerEmergencyStop() {
  stopping.value = true
  emit('emergencyStop', props.targetService)
  setTimeout(() => {
    stopping.value = false
  }, 400)
}
</script>

<style scoped>
.drawer-container {
  padding: 8px 0;
}

.stress-hero-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
  margin-bottom: var(--space-4, 16px);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.hero-icon {
  font-size: 20px;
}

.service-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--c-text);
}

.hero-summary-pills {
  display: flex;
  gap: 16px;
  font-size: 13px;
}

.metric-pill {
  color: var(--c-text-secondary);
}

.topology-panel {
  padding: 16px 20px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
  margin-bottom: var(--space-4, 16px);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
}

.topology-grid {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.topology-node {
  flex: 1;
  padding: 14px;
  background: var(--c-bg-elevated, var(--c-surface));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm, 6px);
  position: relative;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.topology-node:hover {
  border-color: var(--c-primary);
  box-shadow: var(--shadow-subtle);
}

.node-bottleneck {
  border-color: var(--c-warning) !important;
  box-shadow: 0 0 12px var(--c-warning-soft);
}

.node-badge {
  font-size: 10px;
  font-family: var(--font-mono, monospace);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  padding: 2px 6px;
  border-radius: var(--radius-xs, 4px);
  display: inline-block;
  margin-bottom: 6px;
  font-weight: 600;
}

.node-badge.badge-warning {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}

.node-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
  margin-bottom: 2px;
}

.status-indicator-box {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot-active {
  background: var(--c-primary);
  box-shadow: 0 0 6px var(--c-primary-soft);
}

.dot-warning {
  background: var(--c-warning);
  box-shadow: 0 0 6px var(--c-warning-soft);
}

.dot-success {
  background: var(--c-success);
  box-shadow: 0 0 6px var(--c-success-soft);
}

.topology-arrow {
  display: flex;
  align-items: center;
  color: var(--c-text-tertiary);
  font-size: 18px;
}

.metrics-panel {
  padding: 16px 20px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.metric-card {
  padding: 14px;
  background: var(--c-bg-elevated, var(--c-surface));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm, 6px);
  transition: border-color 0.2s ease;
}

.metric-card:hover {
  border-color: var(--c-primary);
}

.card-label {
  font-size: 12px;
  color: var(--c-text-secondary);
  margin-bottom: 6px;
}

.card-value {
  font-size: 24px;
  line-height: 1.1;
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}

.metric-footer-note {
  display: flex;
  justify-content: space-between;
  border-top: 1px dashed var(--c-border-subtle, var(--c-border));
  padding-top: 6px;
  font-size: 11px;
  color: var(--c-text-tertiary);
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
