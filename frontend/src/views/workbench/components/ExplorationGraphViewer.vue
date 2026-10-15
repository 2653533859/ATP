<template>
  <div class="exploration-graph-viewer">
    <!-- 顶部状态栏与覆盖率摘要 -->
    <div class="metrics-summary-bar">
      <div class="summary-col">
        <span class="lbl">已发现页面状态 (States)</span>
        <span class="val">{{ metrics.total_states }}</span>
      </div>
      <div class="summary-col">
        <span class="lbl">交互动作覆盖率 (Actions)</span>
        <div class="coverage-box">
          <span class="val">{{ metrics.coverage_percent.toFixed(1) }}%</span>
          <a-progress
            :percent="metrics.coverage_percent"
            :show-info="false"
            size="small"
            style="width: 120px"
          />
        </div>
      </div>
      <div class="summary-col">
        <span class="lbl">状态转移路径 (Transitions)</span>
        <span class="val">{{ metrics.total_transitions }}</span>
      </div>
      <div class="summary-col current-state-col">
        <span class="lbl">当前页面指纹 (State Hash)</span>
        <span class="hash-tag" :title="metrics.current_state_id || '未连接'">
          {{ metrics.current_state_id || '未连接' }}
        </span>
      </div>

      <div class="summary-actions">
        <a-input
          v-model:value="sessionIdInput"
          placeholder="探索会话 ID (exp_...)"
          size="small"
          style="width: 180px"
        />
        <a-button type="primary" size="small" :loading="loading" @click="fetchSessionGraph">
          刷新会话拓扑
        </a-button>
        <a-button size="small" @click="loadDemoGraph">
          载入示例状态树
        </a-button>
      </div>
    </div>

    <!-- 图表容器 -->
    <a-row :gutter="16" class="chart-row">
      <!-- 左侧：有限状态机 (FSM) 拓扑关系图 -->
      <a-col :span="16">
        <a-card title="页面有限状态机 (FSM) 拓扑关系图" size="small" class="graph-card">
          <div class="chart-box">
            <VChart
              :option="graphOption"
              autoresize
              class="echarts-view"
              @click="handleChartClick"
            />
          </div>
        </a-card>
      </a-col>

      <!-- 右侧：选中状态节点指纹与交互详情 -->
      <a-col :span="8">
        <a-card title="页面状态指纹与动作明细" size="small" class="detail-card">
          <div v-if="selectedNode" class="node-detail-panel">
            <div class="node-title-row">
              <span class="screen-title">{{ selectedNode.name }}</span>
              <a-tag :color="selectedNode.id === metrics.current_state_id ? 'blue' : 'default'">
                {{ selectedNode.id === metrics.current_state_id ? '当前停留' : `层级 ${selectedNode.depth}` }}
              </a-tag>
            </div>

            <div class="detail-item">
              <span class="detail-label">状态哈希指纹:</span>
              <code class="hash-code">{{ selectedNode.id }}</code>
            </div>

            <div class="detail-item">
              <span class="detail-label">动作探索进度:</span>
              <span>{{ selectedNode.visited_count }} / {{ selectedNode.actions_count }} 已探索</span>
            </div>

            <a-divider style="margin: 12px 0" />

            <div class="action-list-title">页面可交互元素动作槽 (Candidate Actions)</div>
            <div class="action-list">
              <div
                v-for="idx in selectedNode.actions_count"
                :key="idx"
                class="action-item"
                :class="{ visited: idx <= selectedNode.visited_count }"
              >
                <span class="action-badge">{{ idx <= selectedNode.visited_count ? '已遍历' : '待探索' }}</span>
                <span class="action-name">控件 #{{ idx }} [click / input]</span>
              </div>
            </div>
          </div>
          <a-empty v-else description="在左侧拓扑图中点击任意节点查看状态指纹详情" orientation="center" />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import { message } from 'ant-design-vue'
import {
  explorationApi,
  type ExplorationCoverageMetrics,
  type ExplorationNode,
  type ExplorationLink,
} from '@/api/exploration'

const loading = ref(false)
const sessionIdInput = ref('')
const selectedNode = ref<ExplorationNode | null>(null)

const metrics = ref<ExplorationCoverageMetrics>({
  total_states: 0,
  total_actions_discovered: 0,
  total_actions_visited: 0,
  coverage_percent: 0,
  total_transitions: 0,
  current_state_id: null,
  nodes: [],
  links: [],
})

const fetchSessionGraph = async () => {
  const sid = sessionIdInput.value.trim()
  if (!sid) {
    message.warning('请输入探索会话 ID')
    return
  }
  loading.value = true
  try {
    const res = await explorationApi.getSession(sid)
    metrics.value = res
    if (res.nodes && res.nodes.length > 0) {
      selectedNode.value = res.nodes[0]
    }
    message.success(`成功载入会话 ${sid} 状态图`)
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '获取探索会话图模型失败'
    message.error(msg)
  } finally {
    loading.value = false
  }
}

const loadDemoGraph = () => {
  const demoNodes: ExplorationNode[] = [
    { id: 'a1b2c3d4e5f60001', name: '登录页 (LoginScreen)', depth: 0, actions_count: 3, visited_count: 3 },
    { id: 'b2c3d4e5f6000002', name: '首页商品流 (HomeScreen)', depth: 1, actions_count: 6, visited_count: 5 },
    { id: 'c3d4e5f600000003', name: '商品详情页 (DetailScreen)', depth: 2, actions_count: 4, visited_count: 4 },
    { id: 'd4e5f60000000004', name: '购物车列表 (CartScreen)', depth: 2, actions_count: 3, visited_count: 2 },
    { id: 'e5f6000000000005', name: '结算支付收银台 (CheckoutScreen)', depth: 3, actions_count: 2, visited_count: 1 },
  ]

  const demoLinks: ExplorationLink[] = [
    { from: 'a1b2c3d4e5f60001', to: 'b2c3d4e5f6000002', action: 'click(btnLogin)' },
    { from: 'b2c3d4e5f6000002', to: 'c3d4e5f600000003', action: 'click(productCard)' },
    { from: 'b2c3d4e5f6000002', to: 'd4e5f60000000004', action: 'click(navCart)' },
    { from: 'c3d4e5f600000003', to: 'd4e5f60000000004', action: 'click(addToCart)' },
    { from: 'd4e5f60000000004', to: 'e5f6000000000005', action: 'click(btnCheckout)' },
    { from: 'e5f6000000000005', to: 'd4e5f60000000004', action: 'back(systemBack)' },
  ]

  metrics.value = {
    total_states: 5,
    total_actions_discovered: 18,
    total_actions_visited: 15,
    coverage_percent: 83.3,
    total_transitions: 6,
    current_state_id: 'e5f6000000000005',
    nodes: demoNodes,
    links: demoLinks,
  }
  selectedNode.value = demoNodes[4]
}

const graphOption = computed<EChartsOption>(() => {
  const nodes = metrics.value.nodes || []
  const links = metrics.value.links || []

  const chartNodes = nodes.map((n) => {
    const isCurrent = n.id === metrics.value.current_state_id
    const isComplete = n.visited_count >= n.actions_count
    return {
      id: n.id,
      name: n.name,
      symbolSize: isCurrent ? 52 : 44,
      itemStyle: {
        color: isCurrent ? '#1890ff' : isComplete ? '#52c41a' : '#faad14',
        borderColor: isCurrent ? 'rgba(24, 144, 255, 0.4)' : '#ffffff',
        borderWidth: isCurrent ? 6 : 2,
      },
      label: {
        show: true,
        position: 'bottom' as const,
        color: '#374151',
        fontSize: 11,
      },
      rawNode: n,
    }
  })

  const chartLinks = links.map((l) => ({
    source: l.from,
    target: l.to,
    label: {
      show: true,
      formatter: l.action,
      fontSize: 10,
      color: '#6b7280',
    },
    lineStyle: {
      color: '#9ca3af',
      curveness: 0.15,
      width: 2,
    },
    symbol: ['none', 'arrow'],
  }))

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        if (params && typeof params === 'object' && 'data' in params) {
          const d = (params as { data: { rawNode?: ExplorationNode; label?: { formatter?: string } } }).data
          if (d.rawNode) {
            return `<b>${d.rawNode.name}</b><br/>状态指纹: ${d.rawNode.id}<br/>探索深度: ${d.rawNode.depth}<br/>覆盖: ${d.rawNode.visited_count}/${d.rawNode.actions_count}`
          }
          if (d.label?.formatter) {
            return `操作转移: ${d.label.formatter}`
          }
        }
        return ''
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: chartNodes,
        links: chartLinks,
        roam: true,
        edgeSymbol: ['circle', 'arrow'],
        edgeSymbolSize: [4, 8],
        force: {
          repulsion: 350,
          edgeLength: [120, 180],
          gravity: 0.1,
        },
      },
    ],
  }
})

const handleChartClick = (params: unknown) => {
  if (params && typeof params === 'object' && 'data' in params) {
    const raw = (params as { data: { rawNode?: ExplorationNode } }).data?.rawNode
    if (raw) {
      selectedNode.value = raw
    }
  }
}

onMounted(() => {
  loadDemoGraph()
})
</script>

<style scoped>
.exploration-graph-viewer {
  padding: 4px 0;
}
.metrics-summary-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 16px;
}
.summary-col {
  display: flex;
  flex-direction: column;
}
.summary-col .lbl {
  font-size: 11px;
  color: var(--c-text-tertiary, #6b7280);
}
.summary-col .val {
  font-size: 16px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.coverage-box {
  display: flex;
  align-items: center;
  gap: 8px;
}
.current-state-col {
  max-width: 180px;
}
.hash-tag {
  font-family: monospace;
  font-size: 12px;
  color: #1890ff;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.summary-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.chart-row {
  margin-top: 4px;
}
.graph-card,
.detail-card {
  border-radius: 8px;
  min-height: 460px;
}
.chart-box {
  height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.echarts-view {
  width: 100%;
  height: 100%;
}
.node-detail-panel {
  padding: 4px;
}
.node-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.screen-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
}
.detail-label {
  color: var(--c-text-tertiary, #6b7280);
}
.hash-code {
  background: var(--c-bg-page, #f3f4f6);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}
.action-list-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--c-text-secondary, #374151);
}
.action-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  overflow-y: auto;
}
.action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--c-bg-page, #f9fafb);
  border-radius: 4px;
  font-size: 12px;
}
.action-item.visited {
  border-left: 3px solid #52c41a;
}
.action-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #e5e7eb;
  color: #4b5563;
}
.action-item.visited .action-badge {
  background: rgba(82, 196, 26, 0.15);
  color: #52c41a;
  font-weight: 600;
}
.action-name {
  font-family: monospace;
}
</style>
