<template>
  <div class="exploration-circuit-breaker-card">
    <!-- 熔断状态警示条 -->
    <div
      class="status-banner"
      :class="statusData.is_tripped ? 'banner-tripped' : 'banner-healthy'"
    >
      <div class="banner-icon">
        <AlertOutlined v-if="statusData.is_tripped" />
        <CheckCircleOutlined v-else />
      </div>
      <div class="banner-content">
        <div class="banner-title">
          <span>{{ statusData.is_tripped ? '已触发自动熔断保护并终止会话' : '探索健康监控与熔断保护中 (NORMAL)' }}</span>
          <a-tag v-if="statusData.is_tripped" color="red" class="trip-tag">
            {{ getCategoryLabel(statusData.trip_category) }}
          </a-tag>
          <a-tag v-else color="green">
            正常探索中
          </a-tag>
        </div>
        <p class="banner-reason">
          {{ statusData.trip_reason || '实时监控应用黑屏、白屏假死、乒乓死循环振荡与连续驱动执行故障。' }}
        </p>
      </div>
      <div class="banner-action">
        <a-button v-if="statusData.is_tripped" type="primary" danger size="small" @click="resetCircuitBreaker">
          重置熔断状态
        </a-button>
      </div>
    </div>

    <!-- 4 大核心安全探针指标条 -->
    <a-row :gutter="16" class="probe-row">
      <!-- 探针 1：零元素黑屏 -->
      <a-col :span="6">
        <a-card size="small" class="probe-card" :class="{ danger: statusData.consecutive_zero_elements >= 3 }">
          <div class="probe-head">
            <span class="probe-title">黑屏/假死探针</span>
            <span class="probe-val">{{ statusData.consecutive_zero_elements }} / 3 步</span>
          </div>
          <a-progress
            :percent="Math.min(100, (statusData.consecutive_zero_elements / 3) * 100)"
            :status="statusData.consecutive_zero_elements >= 3 ? 'exception' : 'normal'"
            :show-info="false"
            size="small"
          />
          <span class="probe-tip">连续 3 步无元素即刻熔断</span>
        </a-card>
      </a-col>

      <!-- 探针 2：连续动作失败 -->
      <a-col :span="6">
        <a-card size="small" class="probe-card" :class="{ danger: statusData.consecutive_failures >= 4 }">
          <div class="probe-head">
            <span class="probe-title">动作失败探针</span>
            <span class="probe-val">{{ statusData.consecutive_failures }} / 4 次</span>
          </div>
          <a-progress
            :percent="Math.min(100, (statusData.consecutive_failures / 4) * 100)"
            :status="statusData.consecutive_failures >= 4 ? 'exception' : 'normal'"
            :show-info="false"
            size="small"
          />
          <span class="probe-tip">无障碍/驱动脱节连续 4 次熔断</span>
        </a-card>
      </a-col>

      <!-- 探针 3：死循环振荡 -->
      <a-col :span="6">
        <a-card size="small" class="probe-card" :class="{ danger: statusData.oscillation_count >= 5 }">
          <div class="probe-head">
            <span class="probe-title">死循环振荡探针</span>
            <span class="probe-val">{{ statusData.oscillation_count }} / 5 轮</span>
          </div>
          <a-progress
            :percent="Math.min(100, (statusData.oscillation_count / 5) * 100)"
            :status="statusData.oscillation_count >= 5 ? 'exception' : 'normal'"
            :show-info="false"
            size="small"
          />
          <span class="probe-tip">乒乓振荡连续 5 轮熔断</span>
        </a-card>
      </a-col>

      <!-- 探针 4：最大步数边界 -->
      <a-col :span="6">
        <a-card size="small" class="probe-card">
          <div class="probe-head">
            <span class="probe-title">探索步数进度</span>
            <span class="probe-val">{{ statusData.step_count }} / 50 步</span>
          </div>
          <a-progress
            :percent="Math.min(100, (statusData.step_count / 50) * 100)"
            :show-info="false"
            size="small"
          />
          <span class="probe-tip">达到 50 步安全收敛</span>
        </a-card>
      </a-col>
    </a-row>

    <!-- 交互式模拟验证与事故快照 -->
    <div class="simulation-section">
      <div class="sim-header">
        <span class="sim-title">异常熔断场景模拟与演练 (Circuit Breaker Simulation)</span>
        <div class="sim-buttons">
          <a-button size="small" @click="simulateBlackScreen">
            模拟黑屏崩溃 (3步0元素)
          </a-button>
          <a-button size="small" @click="simulateOscillation">
            模拟乒乓死循环 (5轮振荡)
          </a-button>
          <a-button size="small" @click="simulateActionFailure">
            模拟驱动失联 (4次失败)
          </a-button>
        </div>
      </div>

      <!-- 事故快照 -->
      <div v-if="statusData.is_tripped" class="incident-snapshot-box">
        <div class="snapshot-header">
          <span class="snapshot-title">🚨 事故终止快照归档 (Exploration Abort Snapshot)</span>
          <span class="snapshot-time">归档时间: {{ currentTimestamp }}</span>
        </div>
        <pre class="snapshot-json">{{ JSON.stringify(incidentSnapshot, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { AlertOutlined, CheckCircleOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import {
  explorationApi,
  type CircuitBreakerEvaluateResponse,
} from '@/api/exploration'

const statusData = ref<CircuitBreakerEvaluateResponse>({
  is_tripped: false,
  trip_reason: null,
  trip_category: null,
  consecutive_zero_elements: 0,
  consecutive_failures: 0,
  oscillation_count: 0,
  step_count: 12,
  status: 'normal',
})

const currentTimestamp = ref(new Date().toISOString())

const getCategoryLabel = (cat: string | null | undefined): string => {
  switch (cat) {
    case 'black_screen_detected':
      return '黑屏假死/页面崩溃'
    case 'infinite_loop_oscillation':
      return '乒乓死循环振荡'
    case 'consecutive_action_failures':
      return '驱动/无障碍服务失联'
    case 'max_steps_exceeded':
      return '达到探索步数上限'
    default:
      return '未知异常'
  }
}

const incidentSnapshot = computed(() => {
  return {
    incident_type: statusData.value.trip_category,
    trip_reason: statusData.value.trip_reason,
    consecutive_zero_elements: statusData.value.consecutive_zero_elements,
    consecutive_failures: statusData.value.consecutive_failures,
    oscillation_cycles: statusData.value.oscillation_count,
    total_steps_executed: statusData.value.step_count,
    suggested_action: statusData.value.trip_category === 'black_screen_detected'
      ? '建议检查应用进程崩溃日志 (Crash/ANR) 或重启测试目标 App'
      : statusData.value.trip_category === 'infinite_loop_oscillation'
      ? '建议优化页面反向脱困（Back）逻辑或放宽探索深度限制'
      : '建议检查 Android UIAutomator2 或 Appium 服务连接状态',
    timestamp: currentTimestamp.value,
  }
})

const resetCircuitBreaker = () => {
  statusData.value = {
    is_tripped: false,
    trip_reason: null,
    trip_category: null,
    consecutive_zero_elements: 0,
    consecutive_failures: 0,
    oscillation_count: 0,
    step_count: 0,
    status: 'normal',
  }
  message.success('熔断器状态已成功重置！')
}

const simulateBlackScreen = async () => {
  try {
    await explorationApi.evaluateCircuitBreaker({
      element_count: 0,
      last_action_success: true,
      is_oscillation: false,
      screen_name: 'BlackScreenView',
    })
    statusData.value = {
      is_tripped: true,
      trip_category: 'black_screen_detected',
      trip_reason: '连续 3 步屏幕无任何可交互元素（黑屏/白屏/崩溃），触发熔断保护',
      consecutive_zero_elements: 3,
      consecutive_failures: 0,
      oscillation_count: 0,
      step_count: statusData.value.step_count + 3,
      status: 'tripped',
    }
    currentTimestamp.value = new Date().toISOString()
    message.error('已触发黑屏/崩溃自动熔断！')
  } catch {
    // Local fallback simulation
    statusData.value.is_tripped = true
    statusData.value.trip_category = 'black_screen_detected'
    statusData.value.trip_reason = '连续 3 步屏幕无任何可交互元素（黑屏/白屏/崩溃），触发熔断保护'
    statusData.value.consecutive_zero_elements = 3
  }
}

const simulateOscillation = async () => {
  statusData.value = {
    is_tripped: true,
    trip_category: 'infinite_loop_oscillation',
    trip_reason: '检测到连续 5 次状态往复振荡且无法跳出死循环，触发熔断保护',
    consecutive_zero_elements: 0,
    consecutive_failures: 0,
    oscillation_count: 5,
    step_count: statusData.value.step_count + 5,
    status: 'tripped',
  }
  currentTimestamp.value = new Date().toISOString()
  message.error('已触发死循环振荡自动熔断！')
}

const simulateActionFailure = async () => {
  statusData.value = {
    is_tripped: true,
    trip_category: 'consecutive_action_failures',
    trip_reason: '连续 4 次动作执行异常（驱动/Accessibility 脱节），触发熔断保护',
    consecutive_zero_elements: 0,
    consecutive_failures: 4,
    oscillation_count: 0,
    step_count: statusData.value.step_count + 4,
    status: 'tripped',
  }
  currentTimestamp.value = new Date().toISOString()
  message.error('已触发驱动执行异常自动熔断！')
}
</script>

<style scoped>
.exploration-circuit-breaker-card {
  padding: 4px 0;
}
.status-banner {
  display: flex;
  align-items: center;
  padding: 14px 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid transparent;
}
.banner-healthy {
  background: rgba(82, 196, 26, 0.08);
  border-color: rgba(82, 196, 26, 0.25);
}
.banner-healthy .banner-icon {
  font-size: 24px;
  color: #52c41a;
  margin-right: 16px;
}
.banner-healthy .banner-title {
  font-size: 15px;
  font-weight: 700;
  color: #274916;
  display: flex;
  align-items: center;
  gap: 8px;
}
.banner-tripped {
  background: rgba(245, 34, 45, 0.08);
  border-color: rgba(245, 34, 45, 0.3);
}
.banner-tripped .banner-icon {
  font-size: 24px;
  color: #f5222d;
  margin-right: 16px;
}
.banner-tripped .banner-title {
  font-size: 15px;
  font-weight: 700;
  color: #a8071a;
  display: flex;
  align-items: center;
  gap: 8px;
}
.trip-tag {
  font-weight: 600;
}
.banner-reason {
  font-size: 12px;
  color: var(--c-text-secondary, #6b7280);
  margin: 4px 0 0 0;
}
.banner-action {
  margin-left: auto;
}
.probe-row {
  margin-bottom: 20px;
}
.probe-card {
  border-radius: 8px;
}
.probe-card.danger {
  border-color: #ff4d4f;
  background: rgba(255, 77, 79, 0.03);
}
.probe-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.probe-title {
  font-size: 13px;
  font-weight: 600;
}
.probe-val {
  font-size: 12px;
  font-weight: 700;
}
.probe-tip {
  font-size: 11px;
  color: var(--c-text-tertiary, #9ca3af);
  margin-top: 6px;
  display: block;
}
.simulation-section {
  padding: 16px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
}
.sim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sim-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #111827);
}
.sim-buttons {
  display: flex;
  gap: 8px;
}
.incident-snapshot-box {
  margin-top: 16px;
  padding: 12px;
  background: #1e1e1e;
  border-radius: 6px;
  border: 1px solid #333333;
}
.snapshot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.snapshot-title {
  font-size: 12px;
  font-weight: 700;
  color: #ff7875;
}
.snapshot-time {
  font-size: 11px;
  color: #8c8c8c;
}
.snapshot-json {
  color: #98c379;
  font-size: 11px;
  margin: 0;
  max-height: 160px;
  overflow: auto;
  font-family: monospace;
}
</style>
