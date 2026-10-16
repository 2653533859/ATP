<template>
  <div class="page-shell contract-topology-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <ApartmentOutlined class="hero-icon" />
          <h2 class="page-title">契约漂移微服务级联依赖拓扑图谱与爆炸半径告警大盘</h2>
        </div>
        <p class="page-subtitle">
          在接口契约发生破坏性变更时，基于字段级消费依赖（consumed_fields）实时逆向推导全网微服务多跳级联波及链路，量化爆炸半径（Blast Radius），精准拦截级联故障并派发定向修复工单。
        </p>
      </div>
      <div class="hero-actions">
        <a-space>
          <a-button :loading="loadingTopology" @click="fetchTopology">
            <ReloadOutlined /> 刷新拓扑
          </a-button>
          <a-popconfirm
            title="确定将微服务调用拓扑重置为出厂基线吗？"
            ok-text="确认重置"
            cancel-text="取消"
            @confirm="handleResetTopology"
          >
            <a-button danger>
              重置出厂拓扑
            </a-button>
          </a-popconfirm>
        </a-space>
      </div>
    </header>

    <!-- 控制卡片与预设切换 -->
    <a-card size="small" class="control-card">
      <div class="control-grid">
        <div class="form-row">
          <span class="field-label">受损接口端点:</span>
          <a-input
            v-model:value="currentEndpoint"
            placeholder="例如: POST /api/v1/orders/checkout"
            style="width: 280px"
            size="small"
          />

          <span class="field-label">受损字段集合:</span>
          <a-input
            v-model:value="brokenFieldsInput"
            placeholder="逗号分隔，例如: amount, order_id"
            style="width: 260px"
            size="small"
          />

          <span class="field-label">接口提供方服务:</span>
          <a-input
            v-model:value="producerServiceInput"
            placeholder="例如: order-service"
            style="width: 180px"
            size="small"
          />

          <a-button
            type="primary"
            size="small"
            :loading="analyzing"
            @click="runImpactAnalysis"
          >
            <ThunderboltOutlined /> 评估级联爆炸半径
          </a-button>
        </div>

        <div class="preset-row">
          <span class="preset-label">快捷演练场景:</span>
          <a-space :size="8">
            <a-button
              size="small"
              :type="presetKey === 'critical' ? 'primary' : 'default'"
              danger
              @click="applyPreset('critical')"
            >
              场景 1: 订单核心结算字段篡改 (amount, order_id -> CRITICAL 扩散)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'medium' ? 'primary' : 'default'"
              @click="applyPreset('medium')"
            >
              场景 2: 次要优惠券字段破坏 (coupon_code -> MEDIUM 仅波及 1 个服务)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'isolated' ? 'primary' : 'default'"
              @click="applyPreset('isolated')"
            >
              场景 3: 内部自用字段变更 (internal_trace -> LOW 零扩散)
            </a-button>
          </a-space>
        </div>
      </div>
    </a-card>

    <!-- 爆炸半径裁决大横幅 (Blast Radius Banner) -->
    <div v-if="report" class="verdict-banner" :class="`banner-${report.blast_radius_level.toLowerCase()}`">
      <div class="verdict-header">
        <div class="badge-title">
          <span class="level-badge" :class="`badge-${report.blast_radius_level.toLowerCase()}`">
            {{ report.blast_radius_level }} BLAST RADIUS
          </span>
          <span class="verdict-summary">{{ report.verdict_summary }}</span>
        </div>
        <div class="score-display">
          <div class="score-sub">爆炸半径风险指数</div>
          <div class="score-num" :class="`num-${report.blast_radius_level.toLowerCase()}`">
            {{ report.blast_radius_score }}%
          </div>
        </div>
      </div>

      <!-- 4 项微指标卡片 -->
      <div class="kpi-grid">
        <div class="kpi-box">
          <div class="kpi-val text-red">{{ report.total_impacted_services }}</div>
          <div class="kpi-label">全网波及受损服务总数</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-val text-orange">{{ report.direct_services_count }}</div>
          <div class="kpi-label">一级直接受损微服务 (Direct)</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-val text-purple">{{ report.transitive_services_count }}</div>
          <div class="kpi-label">多跳级联扩散微服务 (Transitive)</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-val text-blue">{{ report.dispatched_alerts.length }}</div>
          <div class="kpi-label">已精准派发告警与工单</div>
        </div>
      </div>
    </div>

    <!-- 拓扑图谱与受波及明细左右并排栅格 -->
    <div class="topology-grid">
      <!-- 左侧：微服务 ECharts 力导向拓扑关系图 -->
      <div class="chart-container">
        <div class="chart-header">
          <div class="chart-title">
            <span>全网微服务依赖与字段碰撞拓扑图谱</span>
            <small class="chart-sub">
              红色节点为一级直接受损，橙色为多跳级联波及，红色连线表示下游消费了被破坏字段
            </small>
          </div>
          <div class="chart-legend">
            <span class="legend-item"><span class="dot dot-producer"></span> 破坏源头</span>
            <span class="legend-item"><span class="dot dot-direct"></span> 直接受损</span>
            <span class="legend-item"><span class="dot dot-transitive"></span> 级联波及</span>
            <span class="legend-item"><span class="dot dot-normal"></span> 正常服务</span>
          </div>
        </div>

        <div class="chart-body">
          <v-chart
            ref="chartRef"
            :option="chartOption"
            autoresize
            class="echart-view"
          />
        </div>
      </div>

      <!-- 右侧：受波及微服务明细与修复指引 -->
      <div class="side-panel">
        <div class="panel-card">
          <div class="card-title">🚨 受损微服务清单与定向修复指引</div>
          <div v-if="!report || report.impacted_services.length === 0" class="empty-panel">
            <a-empty description="当前无受损微服务或尚未执行分析" />
          </div>
          <div v-else class="service-list">
            <div
              v-for="svc in report.impacted_services"
              :key="svc.service_id"
              class="service-item"
              :class="`tier-${svc.impact_tier.toLowerCase()}`"
            >
              <div class="item-head">
                <div class="item-name">
                  <strong>{{ svc.service_name }}</strong>
                  <code class="svc-code">({{ svc.service_id }})</code>
                  <a-tag v-if="svc.is_critical_asset" color="purple" size="small">核心资产</a-tag>
                </div>
                <a-tag :color="svc.impact_tier === 'DIRECT' ? 'red' : 'orange'">
                  {{ svc.impact_tier }} (深度: {{ svc.cascade_depth }})
                </a-tag>
              </div>

              <div class="item-meta">
                <span>负责人/团队: <strong>{{ svc.owner }}</strong></span>
              </div>

              <div class="item-fields">
                <span class="fields-label">消费碰撞受损字段:</span>
                <a-tag v-for="f in svc.hit_broken_fields" :key="f" color="red">
                  {{ f }}
                </a-tag>
              </div>

              <div class="item-remediation">
                <span class="remed-title">修复指导:</span>
                <span class="remed-text">{{ svc.remediation_advice }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 告警派发日志卡片 -->
        <div v-if="report && report.dispatched_alerts.length > 0" class="panel-card">
          <div class="card-title">📢 定向安全告警派发记录</div>
          <div class="alert-list">
            <div v-for="al in report.dispatched_alerts" :key="al.alert_id" class="alert-item">
              <div class="alert-top">
                <span class="alert-target">{{ al.target_service_id }}</span>
                <a-tag color="blue">{{ al.alert_channel }}</a-tag>
                <a-tag color="green">{{ al.status }}</a-tag>
              </div>
              <div class="alert-sub">
                接收方: {{ al.recipient }} | 端点: {{ al.endpoint }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import {
  contractTopologyApi,
  type CascadeImpactAnalysisReport,
  type ServiceTopologyResponse,
} from '@/api/trafficGateway'

const loadingTopology = ref(false)
const analyzing = ref(false)
const topologyData = ref<ServiceTopologyResponse>({
  services_count: 0,
  dependencies_count: 0,
  nodes: [],
  edges: [],
})

const report = ref<CascadeImpactAnalysisReport | null>(null)
const currentEndpoint = ref('POST /api/v1/orders/checkout')
const brokenFieldsInput = ref('amount, order_id')
const producerServiceInput = ref('order-service')
const presetKey = ref<'critical' | 'medium' | 'isolated'>('critical')

const PRESETS = {
  critical: {
    endpoint: 'POST /api/v1/orders/checkout',
    broken_fields: ['amount', 'order_id'],
    producer_service_id: 'order-service',
  },
  medium: {
    endpoint: 'POST /api/v1/orders/checkout',
    broken_fields: ['coupon_code'],
    producer_service_id: 'order-service',
  },
  isolated: {
    endpoint: 'POST /api/v1/orders/checkout',
    broken_fields: ['internal_memo'],
    producer_service_id: 'order-service',
  },
}

function applyPreset(key: 'critical' | 'medium' | 'isolated') {
  presetKey.value = key
  const p = PRESETS[key]
  currentEndpoint.value = p.endpoint
  brokenFieldsInput.value = p.broken_fields.join(', ')
  producerServiceInput.value = p.producer_service_id
  runImpactAnalysis()
}

async function fetchTopology() {
  loadingTopology.value = true
  try {
    const res = await contractTopologyApi.getTopology()
    topologyData.value = res
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '获取服务拓扑失败')
  } finally {
    loadingTopology.value = false
  }
}

async function handleResetTopology() {
  try {
    await contractTopologyApi.clearTopology()
    message.success('微服务依赖拓扑与报告已重置为出厂基准')
    await fetchTopology()
    await runImpactAnalysis()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '重置失败')
  }
}

async function runImpactAnalysis() {
  analyzing.value = true
  try {
    const brokenFields = brokenFieldsInput.value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

    const res = await contractTopologyApi.analyzeImpact({
      endpoint: currentEndpoint.value,
      broken_fields: brokenFields,
      producer_service_id: producerServiceInput.value || undefined,
      dispatch_alerts: true,
    })
    report.value = res.report
    message.success(res.message || '级联影响分析完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '影响分析计算失败')
  } finally {
    analyzing.value = false
  }
}

// 拓扑图配置
const chartOption = computed<EChartsOption>(() => {
  const nodesMap = new Map<string, any>()
  const impactedServiceMap = new Map<string, any>()

  if (report.value) {
    for (const item of report.value.impacted_services) {
      impactedServiceMap.set(item.service_id, item)
    }
  }

  const producerId = report.value?.producer_service || producerServiceInput.value

  for (const node of topologyData.value.nodes) {
    const isProducer = node.service_id === producerId
    const impacted = impactedServiceMap.get(node.service_id)

    let nodeColor = '#64748b' // 普通服务 (Slate)
    let symbolSize = 42

    if (isProducer) {
      nodeColor = '#f59e0b' // 破坏源头 (金色)
      symbolSize = 54
    } else if (impacted) {
      if (impacted.impact_tier === 'DIRECT') {
        nodeColor = '#ef4444' // 直接受损 (红)
        symbolSize = 48
      } else {
        nodeColor = '#f97316' // 间接受损 (橙)
        symbolSize = 44
      }
    }

    nodesMap.set(node.service_id, {
      id: node.service_id,
      name: node.service_name,
      symbolSize,
      itemStyle: {
        color: nodeColor,
        shadowBlur: impacted || isProducer ? 14 : 4,
        shadowColor: nodeColor,
      },
      label: {
        show: true,
        fontSize: 11,
        color: '#ffffff',
      },
      extra: {
        node,
        impacted,
        isProducer,
      },
    })
  }

  // 连线
  const links = topologyData.value.edges.map((edge) => {
    const isImpactedEdge =
      edge.producer_service_id === producerId &&
      impactedServiceMap.has(edge.consumer_service_id)

    return {
      source: edge.consumer_service_id,
      target: edge.producer_service_id,
      lineStyle: {
        color: isImpactedEdge ? '#ef4444' : '#94a3b8',
        width: isImpactedEdge ? 3.0 : 1.2,
        type: isImpactedEdge ? ('dashed' as const) : ('solid' as const),
        curveness: 0.18,
      },
      extra: {
        edge,
        isImpactedEdge,
      },
    }
  })

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: '#0f172a',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const ex = params.data.extra
          if (!ex) return params.data.name
          let html = `<div style="font-weight:700;margin-bottom:4px">${ex.node.service_name} (${ex.node.service_id})</div>`
          html += `<div>负责人: ${ex.node.owner}</div>`
          html += `<div>核心资产: ${ex.node.is_critical_asset ? '是 ★' : '否'}</div>`
          if (ex.isProducer) {
            html += `<div style="color:#f59e0b;font-weight:700;margin-top:4px">⚠️ 破坏性契约发生源服务</div>`
          } else if (ex.impacted) {
            html += `<div style="color:#ef4444;font-weight:700;margin-top:4px">🚨 受损层级: ${ex.impacted.impact_tier} (深度 ${ex.impacted.cascade_depth})</div>`
            html += `<div>碰撞受损字段: ${ex.impacted.hit_broken_fields.join(', ')}</div>`
          }
          return html
        }
        if (params.dataType === 'edge') {
          const ex = params.data.extra
          if (!ex) return ''
          let html = `<div style="font-weight:700">${ex.edge.consumer_service_id} → ${ex.edge.producer_service_id}</div>`
          html += `<div>调用接口: ${ex.edge.endpoint}</div>`
          html += `<div>消费字段: ${ex.edge.consumed_fields.join(', ')}</div>`
          html += `<div>调用频次: ${ex.edge.call_frequency}</div>`
          if (ex.isImpactedEdge) {
            html += `<div style="color:#ef4444;font-weight:700;margin-top:4px">💥 存在契约破坏字段消费碰撞！</div>`
          }
          return html
        }
        return ''
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: Array.from(nodesMap.values()),
        links,
        roam: true,
        label: {
          show: true,
          position: 'inside',
        },
        force: {
          repulsion: 420,
          edgeLength: [90, 180],
          gravity: 0.08,
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 8,
      },
    ],
  }
})

onMounted(async () => {
  await fetchTopology()
  await runImpactAnalysis()
})
</script>

<style scoped>
.contract-topology-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
}

.hero-icon {
  font-size: 20px;
  color: #0284c7;
}

.control-card {
  border-radius: 8px;
}

.control-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.field-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

/* 裁决大横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid transparent;
}

.banner-critical {
  background: #fef2f2;
  border-color: #fecaca;
}

.banner-high {
  background: #fff7ed;
  border-color: #fed7aa;
}

.banner-medium {
  background: #fffbeb;
  border-color: #fde68a;
}

.banner-low {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.verdict-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.badge-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.level-badge {
  font-size: 13px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.badge-critical {
  background: #dc2626;
  color: #ffffff;
}

.badge-high {
  background: #ea580c;
  color: #ffffff;
}

.badge-medium {
  background: #d97706;
  color: #ffffff;
}

.badge-low {
  background: #16a34a;
  color: #ffffff;
}

.verdict-summary {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.score-display {
  text-align: right;
}

.score-sub {
  font-size: 11px;
  color: #64748b;
}

.score-num {
  font-size: 24px;
  font-weight: 800;
  line-height: 1.2;
}

.num-critical {
  color: #dc2626;
}

.num-high {
  color: #ea580c;
}

.num-medium {
  color: #d97706;
}

.num-low {
  color: #16a34a;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-box {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
  text-align: center;
}

.kpi-val {
  font-size: 20px;
  font-weight: 800;
}

.kpi-label {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.text-red {
  color: #dc2626;
}

.text-orange {
  color: #ea580c;
}

.text-purple {
  color: #9333ea;
}

.text-blue {
  color: #0284c7;
}

/* 拓扑栅格 */
.topology-grid {
  display: grid;
  grid-template-columns: 1fr 420px;
  gap: 16px;
  min-height: 520px;
}

.chart-container {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
}

.chart-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.chart-sub {
  display: block;
  font-size: 11px;
  color: #64748b;
  font-weight: normal;
  margin-top: 2px;
}

.chart-legend {
  display: flex;
  align-items: center;
  gap: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #475569;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot-producer {
  background: #f59e0b;
}

.dot-direct {
  background: #ef4444;
}

.dot-transitive {
  background: #f97316;
}

.dot-normal {
  background: #64748b;
}

.chart-body {
  flex: 1;
  min-height: 480px;
}

.echart-view {
  width: 100%;
  height: 100%;
}

.side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
}

.card-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 10px;
}

.empty-panel {
  padding: 24px 0;
}

.service-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 380px;
  overflow-y: auto;
}

.service-item {
  border-radius: 6px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
}

.tier-direct {
  background: #fef2f2;
  border-color: #fecaca;
}

.tier-transitive {
  background: #fff7ed;
  border-color: #fed7aa;
}

.item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.item-name {
  font-size: 12px;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 6px;
}

.svc-code {
  font-size: 11px;
  color: #64748b;
}

.item-meta {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 6px;
}

.item-fields {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.fields-label {
  font-size: 11px;
  color: #475569;
}

.item-remediation {
  font-size: 11px;
  line-height: 1.4;
  color: #334155;
  background: rgba(255, 255, 255, 0.6);
  padding: 6px;
  border-radius: 4px;
}

.remed-title {
  font-weight: 700;
  color: #0f172a;
  margin-right: 4px;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 180px;
  overflow-y: auto;
}

.alert-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 6px 10px;
}

.alert-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2px;
}

.alert-target {
  font-size: 11px;
  font-weight: 700;
  color: #0369a1;
}

.alert-sub {
  font-size: 10px;
  color: #64748b;
}
</style>
