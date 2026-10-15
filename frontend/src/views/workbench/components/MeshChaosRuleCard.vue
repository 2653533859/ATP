<template>
  <a-card size="small" class="mesh-chaos-rule-card">
    <template #title>
      <div class="card-header-title">
        <span class="title-text">微服务网关混沌故障注入规则编排卡片</span>
        <a-tag :color="rule.enabled ? 'green' : 'default'">
          {{ rule.enabled ? '规则已激活' : '规则已禁用' }}
        </a-tag>
      </div>
    </template>

    <template #extra>
      <a-space>
        <a-switch
          v-model:checked="rule.enabled"
          checked-children="启用"
          un-checked-children="停用"
        />
        <a-button type="primary" size="small" :loading="saving" @click="handleSaveExperiment">
          保存并下发实验
        </a-button>
      </a-space>
    </template>

    <div class="card-body-content">
      <!-- 实验名称与故障类型选择 -->
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="混沌演练实验名称" required>
              <a-input v-model:value="experimentName" placeholder="例如: 订单微服务高可用断路混沌演练" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="目标微服务名称" required>
              <a-input v-model:value="rule.service_name" placeholder="例如: order-service (或 * 全局)" />
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 故障动作单选 -->
        <a-form-item label="注入故障动作类型 (Chaos Action)" required>
          <a-radio-group v-model:value="rule.action" button-style="solid" class="action-radios">
            <a-radio-button value="service_down_503">503 实例宕机 (Service Down)</a-radio-button>
            <a-radio-button value="circuit_breaker_trip">连接断路熔断 (Trip Breaker)</a-radio-button>
            <a-radio-button value="latency_jitter">网络延迟抖动 (Latency Jitter)</a-radio-button>
            <a-radio-button value="corrupt_payload">报文畸形损坏 (Corrupt Payload)</a-radio-button>
          </a-radio-group>
        </a-form-item>

        <!-- 流量抽样比例滑块 -->
        <a-form-item label="流量抽样比例控制 (Traffic Ratio)">
          <div class="slider-wrapper">
            <a-slider
              v-model:value="sliderPercent"
              :min="0"
              :max="100"
              class="ratio-slider"
            />
            <div class="ratio-badge">
              <strong>{{ sliderPercent }}%</strong>
              <small class="ratio-hint">{{ sliderPercent === 100 ? '全量注入' : (sliderPercent === 0 ? '完全放行' : '灰度抽样') }}</small>
            </div>
          </div>
        </a-form-item>

        <!-- 路径正则与请求头过滤 -->
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="匹配 URL 正则表达式">
              <a-input v-model:value="rule.route_pattern" placeholder="例如: ^/api/v1/orders.*" />
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="金丝雀请求头标匹配 (Canary Header Matcher)">
              <a-input v-model:value="headerMatcherInput" placeholder="例如: x-canary=true, x-env=stress" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <!-- 在线快速评估与故障决策验证 -->
      <a-card size="small" title="网关请求在线评估与故障决策预演 (Online Evaluation)" class="eval-card">
        <template #extra>
          <a-button size="small" type="primary" ghost :loading="evaluating" @click="handleEvaluateRequest">
            发送试探评估请求
          </a-button>
        </template>

        <div class="eval-result-row">
          <div class="eval-status-box">
            <span class="eval-lbl">网关决策结果:</span>
            <a-tag v-if="evalDecision?.inject_fault" color="red">
              命中故障注入: {{ evalDecision.action }}
            </a-tag>
            <a-tag v-else color="green">
              放行通过 (Bypass Pass)
            </a-tag>
          </div>

          <div v-if="evalDecision?.status_code" class="eval-detail-pill">
            <span>HTTP 状态码:</span>
            <strong>{{ evalDecision.status_code }}</strong>
          </div>

          <div v-if="evalDecision?.latency_ms" class="eval-detail-pill">
            <span>注入延迟:</span>
            <strong>{{ evalDecision.latency_ms }} ms</strong>
          </div>
        </div>

        <div v-if="evalDecision?.response_body" class="response-preview">
          <pre class="json-box">{{ formatJson(evalDecision.response_body) }}</pre>
        </div>
      </a-card>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  meshChaosApi,
  type ChaosRule,
  type ChaosExperiment,
} from '@/api/meshChaos'

const emit = defineEmits<{
  (e: 'saved', val: ChaosExperiment): void
}>()

const experimentName = ref('微服务核心链路网关混沌故障实验')
const saving = ref(false)
const evaluating = ref(false)

const sliderPercent = ref(100)
const headerMatcherInput = ref('x-canary=true')

const rule = reactive<ChaosRule>({
  service_name: 'order-service',
  route_pattern: '^/api/v1/orders.*',
  action: 'service_down_503',
  traffic_ratio: 1.0,
  methods: ['*'],
  header_matchers: { 'x-canary': 'true' },
  enabled: true,
})

const evalDecision = ref<any | null>({
  inject_fault: true,
  action: 'service_down_503',
  status_code: 503,
  response_body: {
    error: 'Service Unavailable',
    chaos_injected: true,
    action: 'service_down_503',
  },
})

function formatJson(val: any): string {
  try {
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}

function parseHeaderMatchers(): Record<string, string> {
  const matchers: Record<string, string> = {}
  if (!headerMatcherInput.value.trim()) return matchers
  const pairs = headerMatcherInput.value.split(',')
  for (const pair of pairs) {
    const [k, v] = pair.split('=').map((s) => s.trim())
    if (k && v) {
      matchers[k] = v
    }
  }
  return matchers
}

async function handleSaveExperiment() {
  if (!experimentName.value.trim()) {
    message.warning('请输入混沌演练实验名称')
    return
  }
  saving.value = true
  try {
    rule.traffic_ratio = sliderPercent.value / 100.0
    rule.header_matchers = parseHeaderMatchers()

    const res = await meshChaosApi.createExperiment({
      name: experimentName.value.trim(),
      description: '由微服务网关混沌规则卡片创建下发',
      rules: [rule],
    })
    emit('saved', res)
    message.success(`混沌实验 #${res.experiment_id} 已成功创建并激活下发！`)
  } catch (err: any) {
    message.error(err.message || '保存混沌实验失败')
  } finally {
    saving.value = false
  }
}

async function handleEvaluateRequest() {
  evaluating.value = true
  try {
    const res = await meshChaosApi.evaluateMeshRequest({
      service_name: rule.service_name,
      path: '/api/v1/orders/checkout',
      method: 'POST',
      headers: parseHeaderMatchers(),
    })
    evalDecision.value = res
    if (res.inject_fault) {
      message.warning(`请求命中混沌规则，决策动作: ${res.action}`)
    } else {
      message.success('请求未命中或被流量抽样放行')
    }
  } catch (err: any) {
    message.error(err.message || '网关请求评估失败')
  } finally {
    evaluating.value = false
  }
}
</script>

<style scoped>
.mesh-chaos-rule-card {
  border-radius: 8px;
}

.card-header-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-text {
  font-weight: 600;
  font-size: 14px;
  color: var(--c-text, #0f172a);
}

.action-radios {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.slider-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 4px 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.ratio-slider {
  flex: 1;
}

.ratio-badge {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 70px;
}

.ratio-badge strong {
  font-size: 15px;
  color: #2563eb;
}

.ratio-hint {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
}

.eval-card {
  margin-top: 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 6px;
}

.eval-result-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 8px;
}

.eval-status-box {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.eval-lbl {
  color: var(--c-text-secondary, #64748b);
}

.eval-detail-pill {
  font-size: 12px;
  display: flex;
  gap: 4px;
}

.response-preview {
  margin-top: 8px;
}

.json-box {
  margin: 0;
  max-height: 120px;
  overflow-y: auto;
  font-size: 11px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 8px 12px;
  border-radius: 6px;
}
</style>
