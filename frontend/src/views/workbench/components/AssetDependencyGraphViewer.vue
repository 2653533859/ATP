<template>
  <div class="asset-dependency-graph-viewer">
    <!-- 头部控制栏：项目选择与拓扑重新索引 -->
    <a-card size="small" class="control-card">
      <div class="control-header">
        <div class="header-desc">
          <h4 class="title">全域测试资产依赖拓扑图谱与孤儿资产治理看板</h4>
          <p class="subtitle">
            基于资产依赖图谱索引引擎构建「Plan → Suite → Case → API / Dataset」全景调用引用拓扑，支持双向正逆向链路溯源与无引用孤儿资产全网透视治理。
          </p>
        </div>
        <div class="header-actions">
          <a-space>
            <span class="param-label">项目:</span>
            <a-input-number
              v-model:value="projectId"
              :min="1"
              size="small"
              style="width: 70px"
            />
            <a-button :loading="loading" size="small" @click="loadGraph">
              刷新拓扑
            </a-button>
            <a-button type="primary" size="small" :loading="reindexing" @click="handleReindex">
              重新全量索引
            </a-button>
            <a-button danger size="small" :loading="loadingOrphans" @click="handleLoadOrphans">
              孤儿资产巡检
            </a-button>
          </a-space>
        </div>
      </div>
    </a-card>

    <!-- 拓扑指标 KPI 概览 -->
    <div class="metrics-row">
      <div class="metric-card">
        <span class="metric-label">全域资产节点数</span>
        <div class="metric-value">
          <strong class="text-blue">{{ graphData.total_nodes }}</strong>
          <small class="unit">个资产</small>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">正向依赖边 (Forward Edges)</span>
        <div class="metric-value">
          <strong class="text-green">{{ graphData.total_forward_edges }}</strong>
          <small class="unit">条关联</small>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">孤儿测试用例 (Orphan Cases)</span>
        <div class="metric-value">
          <strong :class="orphanData.orphan_cases.length > 0 ? 'text-red' : 'text-slate'">
            {{ orphanData.orphan_cases.length }}
          </strong>
          <small class="unit">个未绑定</small>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">孤儿测试数据源 (Orphan Datasets)</span>
        <div class="metric-value">
          <strong :class="orphanData.orphan_datasets.length > 0 ? 'text-orange' : 'text-slate'">
            {{ orphanData.orphan_datasets.length }}
          </strong>
          <small class="unit">个未引用</small>
        </div>
      </div>
    </div>

    <!-- 孤儿资产治理预警横幅 -->
    <a-alert
      v-if="orphanData.total_orphans_count > 0"
      type="warning"
      show-icon
      closable
      class="orphan-alert"
      :message="`[孤儿资产治理预警] 发现 ${orphanData.total_orphans_count} 个未被任何套件绑定的游离资产！`"
      :description="`其中未绑套件的孤儿用例 ${orphanData.orphan_cases.length} 个，未被用例引用的孤儿数据集 ${orphanData.orphan_datasets.length} 个。请在下方治理列表中核查处理。`"
    />

    <!-- 主体区域：ECharts 图谱 + 右侧依赖聚焦面板 -->
    <a-row :gutter="14" class="content-row">
      <a-col :span="17">
        <a-card size="small" title="资产引用关系力导向拓扑图谱 (ECharts Force Graph)" class="chart-card">
          <div class="chart-container">
            <VChart
              :option="chartOption"
              autoresize
              class="echarts-view"
              @click="handleNodeClick"
            />
          </div>
        </a-card>
      </a-col>

      <a-col :span="7">
        <a-card size="small" title="选定节点依赖链聚焦 (Trace Focus)" class="focus-card">
          <div v-if="selectedNode" class="node-focus-box">
            <div class="focus-header">
              <a-tag :color="getNodeColor(selectedNode.asset_type)">
                {{ selectedNode.asset_type.toUpperCase() }}
              </a-tag>
              <strong>{{ selectedNode.name }}</strong>
            </div>
            <div class="node-meta">
              <span>节点 ID: <code>{{ selectedNode.node_id }}</code></span>
            </div>

            <!-- 下游影响资产 -->
            <div class="trace-group">
              <h5 class="trace-title text-green">正向被依赖项 (Downstream / Visited {{ downstreamNodes.length }})</h5>
              <div v-if="downstreamNodes.length > 0" class="trace-list">
                <div v-for="d in downstreamNodes" :key="d.node_id" class="trace-item">
                  <a-tag size="small" :color="getNodeColor(d.asset_type)">{{ d.asset_type }}</a-tag>
                  <span>{{ d.name }}</span>
                </div>
              </div>
              <span v-else class="empty-hint">无下游依赖节点</span>
            </div>

            <!-- 上游前置依赖 -->
            <div class="trace-group">
              <h5 class="trace-title text-blue">上游来源依赖项 (Upstream / Visited {{ upstreamNodes.length }})</h5>
              <div v-if="upstreamNodes.length > 0" class="trace-list">
                <div v-for="u in upstreamNodes" :key="u.node_id" class="trace-item">
                  <a-tag size="small" :color="getNodeColor(u.asset_type)">{{ u.asset_type }}</a-tag>
                  <span>{{ u.name }}</span>
                </div>
              </div>
              <span v-else class="empty-hint">无上游依赖节点</span>
            </div>
          </div>

          <div v-else class="empty-focus-box">
            <p class="empty-text">点击左侧图谱中的任意节点，即可实时进行正逆向上下游依赖溯源分析。</p>
          </div>
        </a-card>

        <!-- 孤儿用例快速处理卡片 -->
        <a-card
          v-if="orphanData.orphan_cases.length > 0"
          size="small"
          title="待治理孤儿用例清单"
          class="orphan-card"
        >
          <div class="orphan-list">
            <div v-for="c in orphanData.orphan_cases.slice(0, 5)" :key="c.node_id" class="orphan-item">
              <a-tag color="red" class="mini-tag">孤儿</a-tag>
              <span class="orphan-name">{{ c.name }}</span>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import {
  assetGraphApi,
  type AssetNode,
  type AssetType,
  type ProjectAssetGraphResponse,
  type OrphanAssetsResponse,
} from '@/api/assetGraph'

const projectId = ref<number>(1)
const loading = ref<boolean>(false)
const reindexing = ref<boolean>(false)
const loadingOrphans = ref<boolean>(false)

const graphData = ref<ProjectAssetGraphResponse>({
  project_id: 1,
  total_nodes: 0,
  total_forward_edges: 0,
  nodes: [],
  forward_edges: {},
  reverse_edges: {},
})

const orphanData = ref<OrphanAssetsResponse>({
  orphan_cases: [],
  orphan_datasets: [],
  total_orphans_count: 0,
})

const selectedNode = ref<AssetNode | null>(null)
const downstreamNodes = ref<AssetNode[]>([])
const upstreamNodes = ref<AssetNode[]>([])

function getNodeColor(type: AssetType): string {
  switch (type) {
    case 'plan':
      return '#2563eb'
    case 'suite':
      return '#16a34a'
    case 'case':
      return '#8b5cf6'
    case 'api_endpoint':
      return '#f59e0b'
    case 'dataset':
      return '#06b6d4'
    case 'device':
      return '#ec4899'
    default:
      return '#64748b'
  }
}

const chartOption = computed<EChartsOption>(() => {
  const nodes = graphData.value.nodes.map((node) => {
    const isSelected = selectedNode.value?.node_id === node.node_id
    const isOrphan = orphanData.value.orphan_cases.some((o) => o.node_id === node.node_id) ||
      orphanData.value.orphan_datasets.some((o) => o.node_id === node.node_id)

    return {
      id: node.node_id,
      name: node.name,
      symbolSize: node.asset_type === 'plan' ? 36 : node.asset_type === 'suite' ? 30 : 24,
      itemStyle: {
        color: isOrphan ? '#ef4444' : getNodeColor(node.asset_type),
        borderColor: isSelected ? '#ffffff' : isOrphan ? '#dc2626' : undefined,
        borderWidth: isSelected ? 3 : isOrphan ? 2 : 0,
        shadowBlur: isSelected ? 12 : 0,
        shadowColor: isSelected ? '#3b82f6' : undefined,
      },
      category: node.asset_type,
    }
  })

  const links: any[] = []
  for (const [sourceId, targetIds] of Object.entries(graphData.value.forward_edges)) {
    for (const targetId of targetIds) {
      links.push({
        source: sourceId,
        target: targetId,
        lineStyle: {
          color: '#94a3b8',
          width: 1.5,
          curveness: 0.1,
        },
      })
    }
  }

  const categories = [
    { name: 'plan', itemStyle: { color: '#2563eb' } },
    { name: 'suite', itemStyle: { color: '#16a34a' } },
    { name: 'case', itemStyle: { color: '#8b5cf6' } },
    { name: 'api_endpoint', itemStyle: { color: '#f59e0b' } },
    { name: 'dataset', itemStyle: { color: '#06b6d4' } },
  ]

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          return `<strong>${params.name}</strong><br/>类型: ${params.data.category}<br/>节点 ID: ${params.data.id}`
        }
        return `${params.data.source} → ${params.data.target}`
      },
    },
    legend: [
      {
        data: categories.map((c) => c.name),
        textStyle: { color: '#64748b', fontSize: 11 },
        orient: 'horizontal',
        top: 0,
      },
    ],
    series: [
      {
        type: 'graph',
        layout: 'force',
        animation: false,
        data: nodes,
        links,
        categories,
        roam: true,
        label: {
          show: true,
          position: 'right',
          fontSize: 10,
          color: '#334155',
        },
        force: {
          repulsion: 180,
          edgeLength: 60,
          gravity: 0.1,
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 6,
      },
    ],
  }
})

async function loadGraph() {
  loading.value = true
  try {
    const res = await assetGraphApi.getProjectGraph(projectId.value)
    graphData.value = res
  } catch (err: any) {
    message.error(err.message || '获取资产依赖图谱失败')
  } finally {
    loading.value = false
  }
}

async function handleReindex() {
  reindexing.value = true
  try {
    const res = await assetGraphApi.reindex(projectId.value)
    message.success(`资产依赖索引重建成功！已索引 ${res.total_nodes} 个资产节点，${res.total_forward_edges} 条关联边。`)
    await loadGraph()
  } catch (err: any) {
    message.error(err.message || '重建索引失败')
  } finally {
    reindexing.value = false
  }
}

async function handleLoadOrphans() {
  loadingOrphans.value = true
  try {
    const res = await assetGraphApi.getOrphans(projectId.value)
    orphanData.value = res
    if (res.total_orphans_count > 0) {
      message.warning(`检测到 ${res.total_orphans_count} 个游离孤儿资产！`)
    } else {
      message.success('全域资产健康：未发现孤儿资产，所有用例与数据源均存在有效父级引用。')
    }
  } catch (err: any) {
    message.error(err.message || '获取孤儿资产失败')
  } finally {
    loadingOrphans.value = false
  }
}

async function handleNodeClick(params: any) {
  if (params.dataType !== 'node') return
  const nodeId = params.data.id
  const node = graphData.value.nodes.find((n) => n.node_id === nodeId)
  if (!node) return
  selectedNode.value = node

  try {
    const [downRes, upRes] = await Promise.all([
      assetGraphApi.getDownstream(nodeId),
      assetGraphApi.getUpstream(nodeId),
    ])
    downstreamNodes.value = downRes.downstream_nodes
    upstreamNodes.value = upRes.upstream_nodes
  } catch (err: any) {
    message.error(err.message || '追溯上下游依赖失败')
  }
}

onMounted(() => {
  loadGraph()
  handleLoadOrphans()
})
</script>

<style scoped>
.asset-dependency-graph-viewer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.control-card,
.chart-card,
.focus-card,
.orphan-card {
  border-radius: 8px;
}

.control-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
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

.param-label {
  font-size: 12px;
  color: #64748b;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  display: block;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  color: var(--c-text, #0f172a);
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.unit {
  font-size: 11px;
  font-weight: normal;
  color: var(--c-text-tertiary, #94a3b8);
}

.text-blue {
  color: #2563eb;
}

.text-green {
  color: #16a34a;
}

.text-red {
  color: #ef4444;
}

.text-orange {
  color: #ea580c;
}

.text-slate {
  color: #64748b;
}

.orphan-alert {
  border-radius: 6px;
}

.chart-container {
  height: 480px;
  width: 100%;
}

.echarts-view {
  height: 100%;
  width: 100%;
}

.focus-card {
  margin-bottom: 12px;
}

.node-focus-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.focus-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.node-meta {
  font-size: 11px;
  color: #64748b;
}

.trace-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trace-title {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
}

.trace-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 120px;
  overflow-y: auto;
}

.trace-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

.empty-hint {
  font-size: 11px;
  color: #94a3b8;
  font-style: italic;
}

.empty-focus-box {
  padding: 24px 12px;
  text-align: center;
}

.empty-text {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.6;
}

.orphan-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.orphan-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.mini-tag {
  font-size: 10px;
  padding: 0 4px;
}

.orphan-name {
  color: #334155;
}
</style>
