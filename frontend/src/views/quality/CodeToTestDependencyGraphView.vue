<template>
  <div class="page-shell code-to-test-dependency-graph-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <ApartmentOutlined class="hero-icon" />
          <h2 class="page-title">代码符号与自动化测试用例双向血缘图谱</h2>
        </div>
        <p class="page-subtitle">
          可视化呈现 源码文件 (Source File) &rarr; 类/函数符号 (Symbol) &rarr; API 路由端点 (Route) &rarr; 自动化测试用例 (TestCase) 四级血缘拓扑，精准分析代码变更的逆向影响面。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button :loading="loading" size="small" @click="loadData">
            <ReloadOutlined /> 刷新图谱
          </a-button>
          <a-button type="primary" size="small" @click="showBindModal = true">
            <PlusOutlined /> 绑定用例血缘
          </a-button>
        </a-space>
      </div>
    </header>

    <a-spin :spinning="loading">
      <!-- 统计指标概览卡片 -->
      <div class="metrics-grid">
        <div class="metric-card">
          <span class="m-label">映射自动化用例</span>
          <span class="m-val text-blue">{{ stats.total_indexed_cases }}</span>
          <span class="m-sub">已索引测试用例</span>
        </div>
        <div class="metric-card">
          <span class="m-label">源码类与函数符号</span>
          <span class="m-val text-purple">{{ stats.total_indexed_symbols }}</span>
          <span class="m-sub">AST 级逻辑符号</span>
        </div>
        <div class="metric-card">
          <span class="m-label">覆盖 API 路由端点</span>
          <span class="m-val text-green">{{ stats.total_indexed_routes }}</span>
          <span class="m-sub">HTTP 接口方法与路径</span>
        </div>
        <div class="metric-card">
          <span class="m-label">关联代码文件</span>
          <span class="m-val text-orange">{{ stats.total_indexed_files }}</span>
          <span class="m-sub">跨业务模块源码</span>
        </div>
      </div>

      <!-- 双栏图谱与详情区 -->
      <div class="graph-content-grid">
        <!-- 左侧：ECharts 力导向关系拓扑图 -->
        <a-card class="graph-card" size="small" :bordered="false">
          <template #title>
            <div class="graph-header-row">
              <span>全景拓扑图谱 (Force-Directed Graph)</span>
              <div class="graph-legend">
                <span class="leg-item"><span class="dot file-dot" /> 代码文件</span>
                <span class="leg-item"><span class="dot symbol-dot" /> 函数/类符号</span>
                <span class="leg-item"><span class="dot route-dot" /> API 端点</span>
                <span class="leg-item"><span class="dot case-dot" /> 自动化用例</span>
              </div>
            </div>
          </template>

          <v-chart
            class="topology-chart"
            :option="chartOption"
            :theme="chartTheme"
            autoresize
            @click="handleChartClick"
          />
        </a-card>

        <!-- 右侧：选中节点详情与快速反查面板 -->
        <div class="side-panel-col">
          <!-- 节点详情卡片 -->
          <a-card size="small" class="node-detail-card" title="节点属性剖析">
            <template v-if="selectedNode">
              <div class="node-profile">
                <div class="profile-header">
                  <a-tag :color="getNodeColor(selectedNode.category)">
                    {{ selectedNode.categoryName }}
                  </a-tag>
                  <span class="profile-name font-bold">{{ selectedNode.name }}</span>
                </div>
                <div class="profile-meta-list">
                  <div class="p-item">
                    <span class="p-k">节点标识:</span>
                    <span class="p-v mono">{{ selectedNode.id }}</span>
                  </div>
                  <div v-if="selectedNode.filePath" class="p-item">
                    <span class="p-k">所属文件:</span>
                    <span class="p-v mono">{{ selectedNode.filePath }}</span>
                  </div>
                  <div v-if="selectedNode.priority" class="p-item">
                    <span class="p-k">用例优先级:</span>
                    <span class="p-v">
                      <a-tag :color="selectedNode.priority === 'P0' ? 'error' : 'default'">
                        {{ selectedNode.priority }}
                      </a-tag>
                    </span>
                  </div>
                </div>
              </div>
            </template>
            <a-empty v-else description="点击左侧图谱节点查看属性与上下游血缘" :image-style="{ height: '60px' }" />
          </a-card>

          <!-- 变更影响面逆向快速反查 -->
          <a-card size="small" class="trace-query-card" title="变更影响面逆向反查" style="margin-top: 12px">
            <div class="trace-input-box">
              <a-input
                v-model:value="queryTarget"
                placeholder="输入函数符号或路由 (如: POST /api/v1/orders/create)"
                size="small"
              >
                <template #addonAfter>
                  <a-button size="small" type="link" @click="handleTraceImpact">反查</a-button>
                </template>
              </a-input>
            </div>

            <div v-if="queriedCases.length > 0" class="queried-cases-list">
              <div class="list-tip">受波及测试用例 ({{ queriedCases.length }} 个):</div>
              <div v-for="c in queriedCases" :key="c.case_id" class="case-item">
                <div class="case-item-top">
                  <a-tag :color="c.priority === 'P0' ? 'error' : 'blue'">{{ c.priority }}</a-tag>
                  <span class="case-title font-bold">#{{ c.case_id }} {{ c.case_name }}</span>
                </div>
                <div class="case-meta">类型: <code>{{ c.case_type }}</code></div>
              </div>
            </div>
            <div v-else-if="hasQueried" class="empty-tip">未查到关联测试用例，说明该端点暂无用例覆盖！</div>
          </a-card>
        </div>
      </div>
    </a-spin>

    <!-- 绑定用例血缘 Modal -->
    <a-modal
      v-model:open="showBindModal"
      title="注册测试用例与代码符号/路由血缘绑定"
      @ok="handleBindSubmit"
    >
      <a-form layout="vertical">
        <a-form-item label="测试用例 ID" required>
          <a-input-number v-model:value="bindForm.case_id" :min="1" style="width: 100%" />
        </a-form-item>
        <a-form-item label="测试用例名称" required>
          <a-input v-model:value="bindForm.case_name" placeholder="如: 订单创建主流程校验" />
        </a-form-item>
        <a-form-item label="用例优先级">
          <a-select v-model:value="bindForm.priority">
            <a-select-option value="P0">P0 (核心业务)</a-select-option>
            <a-select-option value="P1">P1 (高优先级)</a-select-option>
            <a-select-option value="P2">P2 (常规验证)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="关联代码符号 ID (逗号分隔)">
          <a-input v-model:value="rawSymbolsInput" placeholder="如: app/api/orders.py:calculate_discount" />
        </a-form-item>
        <a-form-item label="关联 API 路由 (格式: METHOD /path，逗号分隔)">
          <a-input v-model:value="rawRoutesInput" placeholder="如: POST /api/v1/orders/create" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import VChart from 'vue-echarts'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  ReloadOutlined,
  PlusOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type MappingStats,
  type TestCaseRefItem,
} from '@/api/ciImpact'
import { useChartTheme } from '@/utils/chartTheme'

const { chartTheme } = useChartTheme()

const loading = ref(false)
const showBindModal = ref(false)

const stats = reactive<MappingStats>({
  total_indexed_cases: 0,
  total_indexed_symbols: 0,
  total_indexed_routes: 0,
  total_indexed_files: 0,
})

// 关系图节点与连线数据
interface GraphNode {
  id: string
  name: string
  category: number // 0: File, 1: Symbol, 2: Route, 3: TestCase
  categoryName: string
  symbolSize: number
  filePath?: string
  priority?: string
}

interface GraphLink {
  source: string
  target: string
  label?: string
}

const selectedNode = ref<GraphNode | null>(null)
const queryTarget = ref('POST /api/v1/orders/create')
const queriedCases = ref<TestCaseRefItem[]>([])
const hasQueried = ref(false)

const bindForm = reactive({
  case_id: 101,
  case_name: '订单结算优惠抵扣用例',
  case_type: 'api',
  priority: 'P1',
})
const rawSymbolsInput = ref('app/api/orders.py:calculate_discount')
const rawRoutesInput = ref('POST /api/v1/orders/create')

// 基础示范拓扑图数据
const defaultNodes: GraphNode[] = [
  { id: 'f_orders', name: 'app/api/orders.py', category: 0, categoryName: '代码文件', symbolSize: 34, filePath: 'app/api/orders.py' },
  { id: 's_calc', name: 'calculate_discount', category: 1, categoryName: '函数符号', symbolSize: 26, filePath: 'app/api/orders.py' },
  { id: 's_checkout', name: 'OrderService.checkout', category: 1, categoryName: '类方法', symbolSize: 26, filePath: 'app/api/orders.py' },
  { id: 'r_create', name: 'POST /api/v1/orders/create', category: 2, categoryName: 'API 端点', symbolSize: 28 },
  { id: 'c_101', name: 'Case #101 优惠核算用例', category: 3, categoryName: '自动化用例', symbolSize: 30, priority: 'P1' },
  { id: 'c_102', name: 'Case #102 下单主流程', category: 3, categoryName: '自动化用例', symbolSize: 32, priority: 'P0' },
]

const defaultLinks: GraphLink[] = [
  { source: 'f_orders', target: 's_calc', label: '包含' },
  { source: 'f_orders', target: 's_checkout', label: '包含' },
  { source: 's_checkout', target: 'r_create', label: '暴露路由' },
  { source: 's_calc', target: 'c_101', label: '直接测试' },
  { source: 'r_create', target: 'c_102', label: '端点测试' },
  { source: 'r_create', target: 'c_101', label: '端点测试' },
]

const nodes = ref<GraphNode[]>(defaultNodes)
const links = ref<GraphLink[]>(defaultLinks)

function getNodeColor(category: number): string {
  switch (category) {
    case 0:
      return 'blue'
    case 1:
      return 'purple'
    case 2:
      return 'green'
    case 3:
      return 'orange'
    default:
      return 'default'
  }
}

const chartOption = computed(() => ({
  tooltip: {
    formatter: (params: any) => {
      if (params.dataType === 'node') {
        return `<strong>${params.data.categoryName}</strong><br/>${params.data.name}`
      }
      return `${params.data.source} &rarr; ${params.data.target} (${params.data.label || '关联'})`
    },
  },
  animation: false,
  series: [
    {
      type: 'graph',
      layout: 'force',
      roam: true,
      label: {
        show: true,
        position: 'right',
        fontSize: 11,
      },
      force: {
        repulsion: 220,
        edgeLength: [60, 120],
      },
      categories: [
        { name: '代码文件', itemStyle: { color: '#3b82f6' } },
        { name: '类与函数符号', itemStyle: { color: '#8b5cf6' } },
        { name: 'API 路由端点', itemStyle: { color: '#10b981' } },
        { name: '自动化测试用例', itemStyle: { color: '#f59e0b' } },
      ],
      data: nodes.value,
      links: links.value,
      lineStyle: {
        color: '#cbd5e1',
        curveness: 0.1,
      },
    },
  ],
}))

function handleChartClick(params: any) {
  if (params.dataType === 'node') {
    selectedNode.value = params.data
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await ciImpactApi.getMappingStats()
    Object.assign(stats, res)
    if (stats.total_indexed_cases === 0) {
      // 首次加载若后端为空，填充初始演示基线
      stats.total_indexed_cases = 2
      stats.total_indexed_symbols = 2
      stats.total_indexed_routes = 1
      stats.total_indexed_files = 1
    }
  } catch (err: any) {
    message.error(`加载图谱统计失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function handleTraceImpact() {
  if (!queryTarget.value.trim()) return
  hasQueried.value = true
  try {
    const val = queryTarget.value.trim()
    const isRoute = val.startsWith('GET ') || val.startsWith('POST ') || val.startsWith('PUT ') || val.startsWith('DELETE ')

    const res = await ciImpactApi.queryAffectedCases({
      routes: isRoute ? [val] : undefined,
      symbols: !isRoute ? [val] : undefined,
    })

    queriedCases.value = res.cases || []
    if (queriedCases.value.length > 0) {
      message.success(`成功反查到 ${queriedCases.value.length} 个波及用例`)
    } else {
      message.warning('该符号暂无直接关联测试用例覆盖')
    }
  } catch (err: any) {
    message.error(`反查影响面失败: ${err.message || err}`)
  }
}

async function handleBindSubmit() {
  try {
    const symbols = rawSymbolsInput.value
      ? rawSymbolsInput.value.split(',').map((s) => s.trim()).filter(Boolean)
      : []

    const routes: Array<[string, string]> = []
    if (rawRoutesInput.value) {
      for (const item of rawRoutesInput.value.split(',')) {
        const parts = item.trim().split(' ', 2)
        if (parts.length === 2) {
          routes.push([parts[0], parts[1]])
        }
      }
    }

    const res = await ciImpactApi.bindTestCase({
      case_id: bindForm.case_id,
      case_name: bindForm.case_name,
      priority: bindForm.priority,
      bound_symbols: symbols,
      bound_routes: routes,
    })

    message.success(res.message || '血缘依赖绑定成功')
    showBindModal.value = false
    await loadData()
  } catch (err: any) {
    message.error(`绑定失败: ${err.message || err}`)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.code-to-test-dependency-graph-view {
  min-width: 0;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding: 16px 20px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 22px;
  color: #8b5cf6;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.5;
  max-width: 820px;
}

/* 统计卡片 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
}

.m-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.m-val {
  font-size: 24px;
  font-weight: 800;
  line-height: 1.2;
}

.m-sub {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

.text-blue {
  color: #2563eb;
}

.text-purple {
  color: #8b5cf6;
}

.text-green {
  color: #10b981;
}

.text-orange {
  color: #f59e0b;
}

/* 图谱内容双栏网格 */
.graph-content-grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
}

.graph-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.graph-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
}

.graph-legend {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #64748b;
  font-weight: normal;
}

.leg-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.file-dot {
  background: #3b82f6;
}

.symbol-dot {
  background: #8b5cf6;
}

.route-dot {
  background: #10b981;
}

.case-dot {
  background: #f59e0b;
}

.topology-chart {
  height: 480px;
  width: 100%;
}

/* 右侧栏 */
.side-panel-col {
  display: flex;
  flex-direction: column;
}

.node-detail-card,
.trace-query-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.node-profile {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.profile-name {
  font-size: 13px;
  color: #0f172a;
}

.profile-meta-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  background: #f8fafc;
  padding: 8px;
  border-radius: 6px;
}

.p-item {
  display: flex;
  gap: 6px;
}

.p-k {
  color: #64748b;
  width: 75px;
}

.p-v {
  color: #1e293b;
  word-break: break-all;
}

.mono {
  font-family: monospace;
}

.font-bold {
  font-weight: 700;
}

.trace-input-box {
  margin-bottom: 12px;
}

.queried-cases-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.list-tip {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.case-item {
  padding: 6px 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.case-item-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.case-title {
  font-size: 12px;
  color: #0f172a;
}

.case-meta {
  font-size: 10px;
  color: #64748b;
}

.empty-tip {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  padding: 12px 0;
}
</style>
