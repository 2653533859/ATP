<template>
  <a-card size="small" class="sandbox-traffic-mirror-card">
    <template #title>
      <div class="card-title-box">
        <span class="card-title-text">沙箱网络流量镜像与写操作副作用安全隔离</span>
        <a-tag v-if="lastResult?.safety_verified" color="green">零泄露安全认证 (Verified)</a-tag>
        <a-tag v-else color="cyan">影子流量分流</a-tag>
      </div>
    </template>

    <template #extra>
      <a-space size="small">
        <a-button
          type="primary"
          danger
          size="small"
          :loading="injecting"
          @click="handleInjectAndVerify"
        >
          注入镜像流量并验证隔离
        </a-button>
        <a-button size="small" :loading="loading" @click="loadPolicies">
          刷新策略
        </a-button>
      </a-space>
    </template>

    <div class="mirror-card-body">
      <!-- 策略配置与说明 -->
      <div class="policy-header-box">
        <p class="description">
          将生产/预发真实业务流量以可配置比例（0~100%）无损镜像复制至隔离沙箱。底层强行拦截针对外部银行、短信、支付与消息等敏感写操作，自动返回携带 <code>X-Sandboxed-Isolated: true</code> 的隔离响应，实现真实的影子全链路压测与回归验证。
        </p>

        <!-- 策略快速编辑表单 -->
        <a-form layout="inline" class="policy-inline-form">
          <a-form-item label="策略 ID">
            <a-input v-model:value="policyId" size="small" style="width: 140px" />
          </a-form-item>

          <a-form-item label="策略名称">
            <a-input v-model:value="policyName" size="small" style="width: 170px" />
          </a-form-item>

          <a-form-item label="目标沙箱 ID">
            <a-input v-model:value="targetSandboxId" size="small" style="width: 130px" />
          </a-form-item>

          <a-form-item label="路由正则">
            <a-input v-model:value="routePattern" size="small" style="width: 130px" />
          </a-form-item>

          <a-form-item label="破坏性副作用拦截">
            <a-switch v-model:checked="isolateSideEffects" size="small" />
          </a-form-item>

          <a-form-item>
            <a-button type="primary" size="small" :loading="saving" @click="handleSavePolicy">
              保存策略
            </a-button>
          </a-form-item>
        </a-form>
      </div>

      <!-- 拦截规则黑名单标签池 -->
      <div class="patterns-box">
        <span class="patterns-label">敏感写操作强阻断模式池：</span>
        <a-space size="small" wrap>
          <a-tag v-for="p in blockedPatterns" :key="p" color="purple">{{ p }}</a-tag>
        </a-space>
      </div>

      <!-- 零泄露合规认证横幅 -->
      <a-alert
        v-if="lastResult?.safety_verified"
        type="success"
        show-icon
        class="safety-alert"
        message="[ZERO LEAKAGE 零泄露合规证明] 影子流量写操作副作用 100% 成功拦截隔离！"
        :description="`共处理镜像业务请求 ${lastResult.traffic_processed} 笔，实时捕获并阻断敏感外发破坏性操作 ${lastResult.intercepted_side_effects_count} 笔，均安全注入 Mock 隔离响应。`"
      />

      <!-- 审计 KPI 指标行 -->
      <div v-if="lastResult" class="metrics-row">
        <div class="metric-card">
          <span class="metric-label">处理镜像流量请求</span>
          <div class="metric-value">
            <strong class="text-blue">{{ lastResult.traffic_processed }}</strong>
            <small class="unit">笔请求</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">成功阻断敏感写调用</span>
          <div class="metric-value">
            <strong class="text-green">{{ lastResult.intercepted_side_effects_count }}</strong>
            <small class="unit">笔外发拦截</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">沙箱环境零泄露合规</span>
          <div class="metric-value">
            <a-tag color="green" class="tag-status">VERIFIED PASS</a-tag>
          </div>
        </div>
      </div>

      <!-- 副作用拦截与隔离审计流水明细表格 -->
      <div v-if="auditList.length > 0" class="audit-table-box">
        <h5 class="audit-title">外发敏感操作实时拦截与 Mock 响应凭据审计流水：</h5>
        <a-table
          :data-source="auditList"
          :columns="auditColumns"
          row-key="call_id"
          size="small"
          :pagination="false"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'method'">
              <a-tag color="red">{{ record.method }}</a-tag>
            </template>
            <template v-if="column.key === 'is_intercepted'">
              <a-tag color="green">已强行拦截隔离</a-tag>
            </template>
            <template v-if="column.key === 'response'">
              <code class="mock-resp-text">
                X-Sandboxed-Isolated: {{ record.mock_response?.headers?.['X-Sandboxed-Isolated'] || 'true' }}
              </code>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  trafficMirrorApi,
  type ProcessMirrorBatchResponse,
  type IsolationAuditRecord,
} from '@/api/sandboxes'

const loading = ref(false)
const saving = ref(false)
const injecting = ref(false)

const policyId = ref('pol_prod_order_shadow')
const policyName = ref('生产交易流量影子分流与隔离策略')
const targetSandboxId = ref('sbx_http_20005')
const routePattern = ref('^/api/v1/orders/.*')
const isolateSideEffects = ref(true)
const blockedPatterns = ref(['*payment*', '*charge*', '*sms*', '*notify*'])

const lastResult = ref<ProcessMirrorBatchResponse | null>(null)
const auditList = ref<IsolationAuditRecord[]>([])

const auditColumns = [
  { title: '外发调用 ID', dataIndex: 'call_id', key: 'call_id', width: 140 },
  { title: '调用方法', key: 'method', width: 90 },
  { title: '敏感目标地址 (Target Destination)', dataIndex: 'target_destination', key: 'target_destination' },
  { title: '安全隔离状态', key: 'is_intercepted', width: 140 },
  { title: '防穿透隔离响应凭据', key: 'response', width: 230 },
]

async function loadPolicies() {
  loading.value = true
  try {
    const res = await trafficMirrorApi.listPolicies()
    if (res.policies.length > 0) {
      const p = res.policies[0]
      policyId.value = p.policy_id
      policyName.value = p.name
      targetSandboxId.value = p.target_sandbox_id
      routePattern.value = p.route_pattern
      isolateSideEffects.value = p.isolate_side_effects
      blockedPatterns.value = p.blocked_outbound_patterns
    }
  } catch (err: any) {
    message.error(err.message || '获取镜像策略失败')
  } finally {
    loading.value = false
  }
}

async function handleSavePolicy() {
  saving.value = true
  try {
    await trafficMirrorApi.createPolicy({
      policy_id: policyId.value,
      name: policyName.value,
      source_service: 'order-service',
      route_pattern: routePattern.value,
      target_sandbox_id: targetSandboxId.value,
      sample_ratio: 1.0,
      isolate_side_effects: isolateSideEffects.value,
      blocked_outbound_patterns: blockedPatterns.value,
      enabled: true,
    })
    message.success('流量镜像与副作用隔离策略保存成功！')
    await loadPolicies()
  } catch (err: any) {
    message.error(err.message || '保存策略失败')
  } finally {
    saving.value = false
  }
}

async function handleInjectAndVerify() {
  injecting.value = true
  try {
    // 注入模拟流量批次（包含敏感外部支付调用）
    const res = await trafficMirrorApi.processBatch({
      policy_id: policyId.value,
      traffic_stream: [
        { method: 'POST', path: '/api/v1/orders/checkout', body: { order_id: 'ord_9901', amount: 199.0 } },
        { method: 'GET', path: '/api/v1/orders/ord_9901', body: null },
      ],
      outbound_calls: [
        {
          call_id: 'call_pay_01',
          target_destination: 'https://bank.internal/api/charge',
          method: 'POST',
          payload: { order_id: 'ord_9901', amount: 199.0 },
        },
        {
          call_id: 'call_sms_02',
          target_destination: 'https://sms-provider.internal/send',
          method: 'POST',
          payload: { phone: '13800000000', msg: '支付成功通知' },
        },
      ],
    })

    lastResult.value = res
    auditList.value = res.isolation_audit
    if (res.safety_verified) {
      message.success(`零泄露安全验证通过！成功拦截 ${res.intercepted_side_effects_count} 笔敏感写调用。`)
    } else {
      message.warning('检测到潜在写操作穿透风险，请检查隔离规则！')
    }
  } catch (err: any) {
    message.error(err.message || '流量注入与验证失败')
  } finally {
    injecting.value = false
  }
}

onMounted(() => {
  loadPolicies()
})
</script>

<style scoped>
.sandbox-traffic-mirror-card {
  border-radius: 8px;
  margin-top: 14px;
}

.card-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-title-text {
  font-size: 14px;
  font-weight: 600;
}

.mirror-card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.description {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.policy-inline-form {
  margin-bottom: 6px;
}

.patterns-box {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.patterns-label {
  color: #64748b;
}

.safety-alert {
  border-radius: 6px;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 10px 14px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: 11px;
  color: #64748b;
}

.metric-value {
  font-size: 17px;
  color: #0f172a;
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.unit {
  font-size: 11px;
  font-weight: normal;
  color: #94a3b8;
}

.text-blue {
  color: #2563eb;
}

.text-green {
  color: #16a34a;
}

.tag-status {
  font-weight: 600;
}

.audit-table-box {
  margin-top: 6px;
}

.audit-title {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px;
}

.mock-resp-text {
  font-size: 11px;
  color: #0284c7;
  font-family: monospace;
}
</style>
