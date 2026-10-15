<template>
  <div class="blast-radius-topology-graph">
    <!-- 头部控制栏：注入目标与爆炸半径红线阈值 -->
    <a-card size="small" class="control-card">
      <div class="control-header">
        <div class="header-desc">
          <h4 class="title">微服务调用依赖拓扑与混沌爆炸半径控制 (Blast Radius Guard)</h4>
          <p class="subtitle">
            基于微服务调用图执行逆向 BFS 级联影响推导，实时追踪故障注入波及的上游调用链路。当突破最大波及深度、影响节点上限或触碰核心受保护服务时，自动触发 Emergency Abort 紧急熔断！
          </p>
        </div>
        <div class="header-actions">
          <a-space>
            <a-button :loading="loadingTopology" @click="loadTopology">
              刷新全网拓扑
            </a-button>
            <a-button type="primary" :loading="evaluating" @click="handleEvaluateBlastRadius">
              评估爆炸半径
            </a-button>
            <a-button danger type="primary" :loading="enforcing" @click="handleEnforceSafety">
              安全管控强校验
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 参数调节与受保护黑名单 -->
      <a-form layout="inline" class="param-form">
        <a-form-item label="故障注入目标服务">
          <a-select v-model:value="injectedService" style="width: 170px">
            <a-select-option v-for="svc in topologyData.services" :key="svc" :value="svc">
              {{ svc }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="最大允许波及服务数">
          <a-input-number v-model:value="maxImpactedServices" :min="1" :max="10" style="width: 80px" />
        </a-form-item>

        <a-form-item label="最大传导深度">
          <a-input-number v-model:value="maxDepth" :min="1" :max="5" style="width: 80px" />
        </a-form-item>

        <a-form-item label="受保护核心服务红线">
          <a-space size="small">
            <a-tag v-for="psvc in protectedServices" :key="psvc" color="purple">
              {{ psvc }}
            </a-tag>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 紧急熔断告警横幅 -->
    <a-alert
      v-if="analysisResult?.emergency_aborted"
      type="error"
      show-icon
      class="abort-alert"
      message="[EMERGENCY ABORT 紧急熔断已触发] 混沌故障波及范围已突破安全红线！"
      :description="`违约原因: ${analysisResult.breach_reasons.join('；')}。已联动网关原子暂停实验注入，防止生产级联雪崩！`"
    />

    <a-alert
      v-else-if="analysisResult && !analysisResult.breached"
      type="success"
      show-icon
      class="safe-alert"
      message="[爆炸半径安全受控] 故障级联传导严格处于预设安全阈值内。"
      :description="`最大波及深度 ${analysisResult.max_depth_reached} <= ${maxDepth}，受波及节点数 ${analysisResult.total_impacted_count} <= ${maxImpactedServices}。`"
    />

    <!-- 统计指标胶囊行 -->
    <div class="metrics-row">
      <div class="metric-card">
        <span class="metric-label">已注册微服务</span>
        <div class="metric-value">
          <strong>{{ topologyData.services.length }}</strong>
          <small class="unit">个节点</small>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">注入靶点服务</span>
        <div class="metric-value">
          <a-tag color="red">{{ injectedService }}</a-tag>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">最大传导深度 (Depth)</span>
        <div class="metric-value">
          <strong>{{ analysisResult?.max_depth_reached ?? 0 }}</strong>
          <small class="unit">层 / 上限 {{ maxDepth }}</small>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">波及微服务总数</span>
        <div class="metric-value">
          <strong :class="analysisResult?.breached ? 'text-danger' : 'text-success'">
            {{ analysisResult?.total_impacted_count ?? 0 }}
          </strong>
          <small class="unit">/ 上限 {{ maxImpactedServices }}</small>
        </div>
      </div>
    </div>

    <!-- ECharts 微服务调用依赖拓扑与爆炸半径图 -->
    <a-row :gutter="16" class="chart-row">
      <a-col :span="17">
        <a-card size="small" title="微服务调用依赖拓扑与级联波及链路 (Topology Graph)" class="graph-card">
          <div class="chart-container">
            <VChart :option="chartOption" autoresize class="echarts-view" />
          </div>
        </a-card>
      </a-col>

      <a-col :span="7">
        <a-card size="small" title="受波及调用链明细 (BFS Derivation)" class="detail-card">
          <div class="detail-box">
            <div class="detail-group">
              <span class="detail-title">直接受波及微服务 (Direct):</span>
              <div class="tags-wrap">
                <a-tag v-for="s in analysisResult?.direct_services ?? []" :key="s" color="orange">
                  {{ s }}
                </a-tag>
                <span v-if="!analysisResult?.direct_services?.length" class="empty-hint">无直接受损</span>
              </div>
            </div>

            <div class="detail-group">
              <span class="detail-title">逆向级联波及上游 (Cascading):</span>
              <div class="tags-wrap">
                <a-tag v-for="s in analysisResult?.cascading_services ?? []" :key="s" color="red">
                  {{ s }}
                </a-tag>
                <span v-if="!analysisResult?.cascading_services?.length" class="empty-hint">无级联蔓延</span>
              </div>
            </div>

            <div class="legend-box">
              <span class="detail-title">图例标识:</span>
              <div class="legend-item"><span class="dot dot-red" /> 注入靶点微服务 (Target)</div>
              <div class="legend-item"><span class="dot dot-amber" /> 级联受波及节点 (Cascaded)</div>
              <div class="legend-item"><span class="dot dot-purple" /> 核心受保护服务 (Protected)</div>
              <div class="legend-item"><span class="dot dot-blue" /> 正常健康运行微服务</div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import { meshChaosApi } from '@/api/meshChaos'

const loadingTopology = ref(false)
const evaluating = ref(false)
const enforcing = ref(false)

const injectedService = ref('pay-service')
const maxImpactedServices = ref(3)
const maxDepth = ref(2)
const protectedServices = ref<string[]>(['user-auth', 'billing-core'])

const topologyData = reactive<{
  services: string[]
  dependencies: Array<{ caller: string; callee: string }>
}>({
  services: ['api-gateway', 'order-service', 'pay-service', 'billing-core', 'inventory-service', 'user-auth'],
  dependencies: [
    { caller: 'api-gateway', callee: 'order-service' },
    { caller: 'api-gateway', callee: 'user-auth' },
    { caller: 'order-service', callee: 'pay-service' },
    { caller: 'order-service', callee: 'inventory-service' },
    { caller: 'pay-service', callee: 'billing-core' },
  ],
})

const analysisResult = ref<{
  injected_service: string
  direct_services: string[]
  cascading_services: string[]
  all_impacted_services: string[]
  total_impacted_count: number
  max_depth_reached: number
  breached: boolean
  breach_reasons: string[]
  emergency_aborted: boolean
} | null>({
  injected_service: 'pay-service',
  direct_services: ['order-service'],
  cascading_services: ['api-gateway'],
  all_impacted_services: ['pay-service', 'order-service', 'api-gateway'],
  total_impacted_count: 3,
  max_depth_reached: 2,
  breached: false,
  breach_reasons: [],
  emergency_aborted: false,
})

const chartOption = computed<EChartsOption>(() => {
  const impactedSet = new Set(analysisResult.value?.all_impacted_services || [])
  const directSet = new Set(analysisResult.value?.direct_services || [])
  const cascadeSet = new Set(analysisResult.value?.cascading_services || [])
  const protectedSet = new Set(protectedServices.value)

  const nodes = topologyData.services.map((name) => {
    let color = '#3b82f6' // Default blue
    let symbolSize = 45

    if (name === injectedService.value) {
      color = '#ef4444' // Red for injected target
      symbolSize = 58
    } else if (cascadeSet.has(name)) {
      color = '#ea580c' // Orange for cascade
      symbolSize = 50
    } else if (directSet.has(name)) {
      color = '#f59e0b' // Amber for direct
      symbolSize = 48
    } else if (protectedSet.has(name)) {
      color = '#8b5cf6' // Purple for protected
      symbolSize = 45
    }

    return {
      id: name,
      name,
      symbolSize,
      itemStyle: {
        color,
        shadowBlur: name === injectedService.value ? 16 : 6,
        shadowColor: color,
      },
      label: {
        show: true,
        fontSize: 11,
        color: '#fff',
      },
    }
  })

  const links = topologyData.dependencies.map((dep) => {
    const isImpactedLink =
      impactedSet.has(dep.caller) && impactedSet.has(dep.callee)

    return {
      source: dep.caller,
      target: dep.callee,
      lineStyle: {
        color: isImpactedLink ? '#ef4444' : '#64748b',
        width: isImpactedLink ? 2.5 : 1.2,
        type: isImpactedLink ? ('dashed' as const) : ('solid' as const),
        curveness: 0.15,
      },
    }
  })

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          return `微服务: <strong>${params.data.name}</strong>`
        }
        return `调用依赖: ${params.data.source} → ${params.data.target}`
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: nodes,
        links,
        roam: true,
        label: {
          show: true,
          position: 'inside',
        },
        force: {
          repulsion: 380,
          edgeLength: [80, 160],
          gravity: 0.1,
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 8,
      },
    ],
  }
})

async function loadTopology() {
  loadingTopology.value = true
  try {
    const res = await meshChaosApi.getTopology()
    topologyData.services = res.services
    topologyData.dependencies = res.dependencies
    message.success('微服务调用依赖拓扑已刷新！')
  } catch (err: any) {
    message.error(err.message || '获取拓扑失败')
  } finally {
    loadingTopology.value = false
  }
}

async function handleEvaluateBlastRadius() {
  evaluating.value = true
  try {
    const res = await meshChaosApi.evaluateBlastRadius({
      injected_service: injectedService.value,
      max_impacted_services: maxImpactedServices.value,
      max_depth: maxDepth.value,
      protected_services: protectedServices.value,
    })
    analysisResult.value = res
    if (res.breached) {
      message.error(`检测到爆炸半径违约！波及深度: ${res.max_depth_reached}，原因: ${res.breach_reasons.join('；')}`)
    } else {
      message.success(`爆炸半径安全受控，共波及 ${res.total_impacted_count} 个服务节点`)
    }
  } catch (err: any) {
    message.error(err.message || '评估爆炸半径失败')
  } finally {
    evaluating.value = false
  }
}

async function handleEnforceSafety() {
  enforcing.value = true
  try {
    const res = await meshChaosApi.enforceBlastRadius({
      experiment_id: 'exp_mesh_active_01',
      injected_service: injectedService.value,
      max_impacted_services: maxImpactedServices.value,
      max_depth: maxDepth.value,
      protected_services: protectedServices.value,
    })
    analysisResult.value = res
    if (res.emergency_aborted) {
      message.error('安全强管控判定违规！已触发 Emergency Abort 紧急熔断！')
    } else {
      message.success('安全强管控校验通过，允许安全注入混沌故障！')
    }
  } catch (err: any) {
    message.error(err.message || '强管控执行失败')
  } finally {
    enforcing.value = false
  }
}

onMounted(() => {
  loadTopology()
})
</script>

<style scoped>
.blast-radius-topology-graph {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.control-card,
.graph-card,
.detail-card {
  border-radius: 8px;
}

.control-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
}

.title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.param-form {
  padding-top: 10px;
  border-top: 1px solid var(--c-border, #f1f5f9);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.abort-alert,
.safe-alert {
  border-radius: 6px;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  display: block;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  color: var(--c-text, #0f172a);
  display: flex;
  align-items: center;
  gap: 6px;
}

.unit {
  font-size: 12px;
  font-weight: normal;
  color: var(--c-text-tertiary, #94a3b8);
}

.text-danger {
  color: #dc2626;
}

.text-success {
  color: #16a34a;
}

.chart-container {
  height: 380px;
  background: #0f172a;
  border-radius: 6px;
}

.echarts-view {
  width: 100%;
  height: 100%;
}

.detail-box {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary, #64748b);
}

.tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.empty-hint {
  font-size: 11px;
  color: #94a3b8;
}

.legend-box {
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--c-border, #f1f5f9);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #475569;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-red {
  background: #ef4444;
}

.dot-amber {
  background: #f59e0b;
}

.dot-purple {
  background: #8b5cf6;
}

.dot-blue {
  background: #3b82f6;
}
</style>
