<template>
  <div class="hybrid-workflow-drag-canvas">
    <!-- 顶部画布操作工具栏 -->
    <div class="canvas-top-toolbar">
      <div class="toolbar-left">
        <span class="workflow-name-display">
          <ApartmentOutlined class="wf-icon" />
          <strong>{{ workflowName }}</strong>
          <span class="nodes-badge">({{ nodes.length }} 节点 / {{ edges.length }} 连线)</span>
        </span>
      </div>

      <div class="toolbar-right">
        <a-space size="small">
          <a-button size="small" @click="loadEcommercePreset">
            <template #icon><ThunderboltOutlined /></template>
            载入典型电商多端跨协议链路
          </a-button>
          <a-button size="small" :loading="saving" @click="handleSaveDraft">
            <template #icon><SaveOutlined /></template>
            保存草稿
          </a-button>
          <a-button size="small" danger @click="clearCanvas">
            <template #icon><ClearOutlined /></template>
            清空画布
          </a-button>
          <a-button
            size="small"
            type="primary"
            :loading="executing"
            :disabled="nodes.length === 0"
            @click="handleExecuteWorkflow"
          >
            <template #icon><PlayCircleOutlined /></template>
            执行工作流 DAG
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 主工作区: 左侧节点工具箱 + 中央点阵连线画布 -->
    <div class="canvas-workspace">
      <!-- 左侧节点选择器 -->
      <div class="nodes-palette">
        <div class="palette-title">节点组件库</div>
        <div class="palette-desc">点击快速添加节点到工作流画布中</div>

        <div class="palette-group">
          <div class="group-label">接口与契约</div>
          <button
            class="palette-node-btn node-color-http"
            type="button"
            @click="addNode('http_request', 'HTTP / REST 接口')"
          >
            <ApiOutlined /> HTTP API 请求
          </button>
          <button
            class="palette-node-btn node-color-grpc"
            type="button"
            @click="addNode('grpc_call', 'gRPC 微服务调用')"
          >
            <ClusterOutlined /> gRPC 微服务调用
          </button>
        </div>

        <div class="palette-group">
          <div class="group-label">端侧自动化</div>
          <button
            class="palette-node-btn node-color-web"
            type="button"
            @click="addNode('web_ui_step', 'Web UI 浏览器操作')"
          >
            <DesktopOutlined /> Web UI (Playwright)
          </button>
          <button
            class="palette-node-btn node-color-android"
            type="button"
            @click="addNode('mobile_android', 'Android 设备执行')"
          >
            <AndroidOutlined /> Android 真机执行
          </button>
          <button
            class="palette-node-btn node-color-ios"
            type="button"
            @click="addNode('mobile_ios', 'iOS 物理真机执行')"
          >
            <AppleOutlined /> iOS 真机 WDA 执行
          </button>
        </div>

        <div class="palette-group">
          <div class="group-label">数据与逻辑</div>
          <button
            class="palette-node-btn node-color-db"
            type="button"
            @click="addNode('database_query', 'SQL 数据库对账')"
          >
            <DatabaseOutlined /> 数据库 SQL 校验
          </button>
          <button
            class="palette-node-btn node-color-condition"
            type="button"
            @click="addNode('condition_branch', '条件判断分支')"
          >
            <ForkOutlined /> 条件分支判断
          </button>
          <button
            class="palette-node-btn node-color-delay"
            type="button"
            @click="addNode('delay_sleep', '延时等待')"
          >
            <ClockCircleOutlined /> 延时等待 (Sleep)
          </button>
        </div>
      </div>

      <!-- 中央点阵交互画布 -->
      <div
        class="interactive-canvas-surface"
        @click="handleCanvasBackgroundClick"
      >
        <!-- SVG 贝塞尔曲线连接线层 -->
        <svg class="canvas-svg-layer">
          <defs>
            <marker
              id="arrowhead"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
            <marker
              id="arrowhead-true"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#52c41a" />
            </marker>
            <marker
              id="arrowhead-false"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#ff4d4f" />
            </marker>
          </defs>

          <!-- 渲染连接边 -->
          <g v-for="edge in edges" :key="edge.edge_id">
            <path
              :d="computeEdgePath(edge)"
              class="canvas-edge-path"
              :class="`edge-${edge.branch_type || 'default'}`"
              :marker-end="`url(#arrowhead${edge.branch_type ? '-' + edge.branch_type : ''})`"
            />
          </g>
        </svg>

        <!-- 节点渲染层 -->
        <div
          v-for="node in nodes"
          :key="node.node_id"
          class="canvas-node-card"
          :class="[
            `node-${node.node_type}`,
            `status-${nodeStatusMap[node.node_id] || 'pending'}`,
            { 'node-selected': selectedNode?.node_id === node.node_id },
          ]"
          :style="{
            left: `${node.x || 100}px`,
            top: `${node.y || 100}px`,
          }"
          @click.stop="selectNode(node)"
        >
          <!-- 节点状态徽标 -->
          <div class="node-status-indicator">
            <span class="status-pulse" :class="`pulse-${nodeStatusMap[node.node_id] || 'pending'}`" />
          </div>

          <!-- 节点内容头部 -->
          <div class="node-card-head">
            <span class="node-icon">
              <component :is="getNodeIcon(node.node_type)" />
            </span>
            <div class="node-title-wrap">
              <span class="node-title-text" :title="node.node_name">{{ node.node_name }}</span>
              <span class="node-type-label">{{ node.node_type }}</span>
            </div>
          </div>

          <!-- 节点操作端口与连线按钮 -->
          <div class="node-ports-row">
            <button
              class="connect-port-btn"
              title="连线到其他节点"
              type="button"
              @click.stop="startConnecting(node)"
            >
              ➔
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 侧边节点属性配置抽屉 -->
    <a-drawer
      :open="Boolean(selectedNode)"
      title="节点属性与变量总线配置"
      placement="right"
      :width="380"
      @close="selectedNode = null"
    >
      <div v-if="selectedNode" class="node-drawer-content">
        <a-descriptions bordered size="small" :column="1" style="margin-bottom: 16px">
          <a-descriptions-item label="节点 ID">
            <code>{{ selectedNode.node_id }}</code>
          </a-descriptions-item>
          <a-descriptions-item label="协议类型">
            <a-tag color="blue">{{ selectedNode.node_type }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <a-form layout="vertical">
          <a-form-item label="节点展示名称">
            <a-input v-model:value="selectedNode.node_name" />
          </a-form-item>

          <a-form-item v-if="selectedNode.node_type === 'condition_branch'" label="条件判断表达式 (如 output.status_code == 200)">
            <a-input v-model:value="selectedNode.condition_expr" placeholder="输入 Python 表达式" />
          </a-form-item>

          <!-- 变量总线使用说明与配置插值提示 -->
          <div class="variable-bus-hint-box">
            <div class="hint-title"><InfoCircleOutlined /> 变量总线动态注入提示</div>
              <p class="hint-desc">
                在参数中可直接使用 <code>&#123;&#123;上游节点ID.output.字段&#125;&#125;</code> 引用执行上下文。
              </p>
          </div>

          <!-- 节点配置 JSON -->
          <a-form-item label="节点参数配置 (JSON)">
            <a-textarea
              :value="JSON.stringify(selectedNode.config, null, 2)"
              :rows="6"
              style="font-family: monospace"
              @change="onConfigJsonChange"
            />
          </a-form-item>
        </a-form>

        <a-divider />

        <div class="drawer-actions">
          <a-button danger block @click="deleteSelectedNode">
            <DeleteOutlined /> 删除该节点
          </a-button>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  ThunderboltOutlined,
  SaveOutlined,
  ClearOutlined,
  PlayCircleOutlined,
  ApiOutlined,
  ClusterOutlined,
  DesktopOutlined,
  AndroidOutlined,
  AppleOutlined,
  DatabaseOutlined,
  ForkOutlined,
  ClockCircleOutlined,
  InfoCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import {
  hybridWorkflowApi,
  type WorkflowNodeItem,
  type WorkflowEdgeItem,
} from '@/api/hybridWorkflow'

const props = withDefaults(
  defineProps<{
    workflowId?: string
    workflowName?: string
  }>(),
  {
    workflowId: 'wf_hybrid_001',
    workflowName: '多协议跨端端到端混合测试工作流',
  }
)

const emit = defineEmits<{
  (e: 'executed', report: any): void
}>()

const nodes = ref<WorkflowNodeItem[]>([])
const edges = ref<WorkflowEdgeItem[]>([])
const selectedNode = ref<WorkflowNodeItem | null>(null)
const nodeStatusMap = ref<Record<string, string>>({})
const saving = ref(false)
const executing = ref(false)
const connectingSource = ref<WorkflowNodeItem | null>(null)

let nodeCounter = 1

function getNodeIcon(nodeType: string) {
  switch (nodeType) {
    case 'http_request':
      return ApiOutlined
    case 'grpc_call':
      return ClusterOutlined
    case 'web_ui_step':
      return DesktopOutlined
    case 'mobile_android':
      return AndroidOutlined
    case 'mobile_ios':
      return AppleOutlined
    case 'database_query':
      return DatabaseOutlined
    case 'condition_branch':
      return ForkOutlined
    case 'delay_sleep':
    default:
      return ClockCircleOutlined
  }
}

function addNode(type: string, defaultName: string) {
  const nid = `node_${nodeCounter++}`
  // 简易阶梯错开排版
  const offset = nodes.value.length * 40
  const newNode: WorkflowNodeItem = {
    node_id: nid,
    node_name: `${nodes.value.length + 1}. ${defaultName}`,
    node_type: type,
    config: { test_type: type },
    x: 80 + (offset % 300),
    y: 60 + (offset % 400),
  }
  nodes.value.push(newNode)
  message.success(`已添加节点: ${newNode.node_name}`)
}

function selectNode(node: WorkflowNodeItem) {
  if (connectingSource.value && connectingSource.value.node_id !== node.node_id) {
    // 建立连线
    const edgeId = `e_${connectingSource.value.node_id}_to_${node.node_id}`
    const branch = connectingSource.value.node_type === 'condition_branch' ? 'true' : 'default'
    edges.value.push({
      edge_id: edgeId,
      source_node_id: connectingSource.value.node_id,
      target_node_id: node.node_id,
      branch_type: branch,
    })
    message.success(`已连线: ${connectingSource.value.node_name} ➔ ${node.node_name}`)
    connectingSource.value = null
    return
  }
  selectedNode.value = node
}

function startConnecting(node: WorkflowNodeItem) {
  connectingSource.value = node
  message.info(`请点击目标节点以完成连线 (从 ${node.node_name})`)
}

function handleCanvasBackgroundClick() {
  connectingSource.value = null
}

function deleteSelectedNode() {
  if (!selectedNode.value) return
  const delId = selectedNode.value.node_id
  nodes.value = nodes.value.filter(n => n.node_id !== delId)
  edges.value = edges.value.filter(e => e.source_node_id !== delId && e.target_node_id !== delId)
  selectedNode.value = null
  message.success('节点已删除')
}

function onConfigJsonChange(e: any) {
  if (!selectedNode.value) return
  try {
    selectedNode.value.config = JSON.parse(e.target.value)
  } catch {
    // 忽略格式化中错误
  }
}

function computeEdgePath(edge: WorkflowEdgeItem): string {
  const source = nodes.value.find(n => n.node_id === edge.source_node_id)
  const target = nodes.value.find(n => n.node_id === edge.target_node_id)
  if (!source || !target) return ''

  const sx = (source.x || 100) + 200
  const sy = (source.y || 100) + 36
  const tx = target.x || 100
  const ty = (target.y || 100) + 36

  const cx1 = sx + 50
  const cy1 = sy
  const cx2 = tx - 50
  const cy2 = ty

  return `M ${sx} ${sy} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${tx} ${ty}`
}

function clearCanvas() {
  nodes.value = []
  edges.value = []
  selectedNode.value = null
  nodeStatusMap.value = {}
  message.info('画布已清空')
}

function loadEcommercePreset() {
  nodes.value = [
    {
      node_id: 'n1',
      node_name: '1. HTTP 创建商品',
      node_type: 'http_request',
      config: { url: '/api/v1/goods', method: 'POST' },
      x: 60,
      y: 60,
    },
    {
      node_id: 'n2',
      node_name: '2. Web 登录加购',
      node_type: 'web_ui_step',
      config: { action: 'login_and_add' },
      x: 320,
      y: 60,
    },
    {
      node_id: 'n3',
      node_name: '3. iOS 真机结账',
      node_type: 'mobile_ios',
      config: { action: 'tap_pay' },
      x: 580,
      y: 60,
    },
    {
      node_id: 'n4',
      node_name: '4. 数据库对账',
      node_type: 'database_query',
      config: { db: 'postgresql' },
      x: 840,
      y: 60,
    },
  ]
  edges.value = [
    { edge_id: 'e1', source_node_id: 'n1', target_node_id: 'n2' },
    { edge_id: 'e2', source_node_id: 'n2', target_node_id: 'n3' },
    { edge_id: 'e3', source_node_id: 'n3', target_node_id: 'n4' },
  ]
  nodeStatusMap.value = {}
  message.success('已载入典型电商多端跨协议混合工作流')
}

async function handleSaveDraft() {
  saving.value = true
  try {
    await hybridWorkflowApi.saveDraft({
      workflow_id: props.workflowId,
      workflow_name: props.workflowName,
      nodes: nodes.value,
      edges: edges.value,
    })
    message.success('工作流草稿保存成功')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '保存草稿失败')
  } finally {
    saving.value = false
  }
}

async function handleExecuteWorkflow() {
  executing.value = true
  // 逐个播放流光动画
  for (const n of nodes.value) {
    nodeStatusMap.value[n.node_id] = 'running'
  }

  try {
    const res = await hybridWorkflowApi.executeWorkflow({
      workflow_id: props.workflowId,
      workflow_name: props.workflowName,
      nodes: nodes.value,
      edges: edges.value,
    })
    // 渲染执行完成状态
    for (const r of res.report.node_records) {
      nodeStatusMap.value[r.node_id] = r.status.toLowerCase()
    }
    message.success('混合工作流 DAG 执行完成！')
    emit('executed', res.report)
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '执行工作流失败')
  } finally {
    executing.value = false
  }
}
</script>

<style scoped>
.hybrid-workflow-drag-canvas {
  display: flex;
  flex-direction: column;
  height: 680px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  overflow: hidden;
}

.canvas-top-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: var(--c-bg-subtle, #f8fafc);
  border-bottom: 1px solid var(--c-border, #e2e8f0);
}

.workflow-name-display {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.wf-icon {
  color: var(--c-primary, #1677ff);
  font-size: 16px;
}

.nodes-badge {
  color: var(--c-text-secondary, #64748b);
  font-size: 12px;
}

.canvas-workspace {
  display: grid;
  grid-template-columns: 200px 1fr;
  flex: 1;
  min-height: 0;
}

/* 左侧节点工具箱 */
.nodes-palette {
  background: var(--c-bg-subtle, #f8fafc);
  border-right: 1px solid var(--c-border, #e2e8f0);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.palette-title {
  font-weight: 700;
  font-size: 13px;
  color: #1e293b;
}

.palette-desc {
  font-size: 11px;
  color: #64748b;
  margin-top: -6px;
}

.palette-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.group-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
}

.palette-node-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #ffffff;
  border: 1px solid var(--c-border, #cbd5e1);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
}

.palette-node-btn:hover {
  border-color: var(--c-primary, #1677ff);
  transform: translateX(2px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

.node-color-http { border-left: 3px solid #1677ff; }
.node-color-grpc { border-left: 3px solid #722ed1; }
.node-color-web { border-left: 3px solid #13c2c2; }
.node-color-android { border-left: 3px solid #52c41a; }
.node-color-ios { border-left: 3px solid #2f54eb; }
.node-color-db { border-left: 3px solid #fa8c16; }
.node-color-condition { border-left: 3px solid #fa541c; }
.node-color-delay { border-left: 3px solid #8c8c8c; }

/* 点阵画布背景 */
.interactive-canvas-surface {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: auto;
  background-color: #fafbfc;
  background-image: radial-gradient(#cbd5e1 1px, transparent 1px);
  background-size: 20px 20px;
}

/* SVG 连接线 */
.canvas-svg-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 2000px;
  height: 2000px;
  pointer-events: none;
  z-index: 1;
}

.canvas-edge-path {
  fill: none;
  stroke: #94a3b8;
  stroke-width: 2px;
  stroke-dasharray: 4, 4;
}

.canvas-edge-path.edge-true {
  stroke: #52c41a;
  stroke-dasharray: none;
}

.canvas-edge-path.edge-false {
  stroke: #ff4d4f;
  stroke-dasharray: 2, 2;
}

/* 节点卡片 */
.canvas-node-card {
  position: absolute;
  width: 200px;
  background: #ffffff;
  border: 1px solid var(--c-border, #cbd5e1);
  border-radius: 8px;
  padding: 8px 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  z-index: 2;
  transition: all 0.2s ease;
  user-select: none;
}

.canvas-node-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
  border-color: var(--c-primary, #1677ff);
}

.canvas-node-card.node-selected {
  outline: 2px solid var(--c-primary, #1677ff);
}

.canvas-node-card.status-running {
  border-color: #1677ff;
  animation: pulse-border 1.2s infinite alternate;
}

.canvas-node-card.status-success {
  border-color: #52c41a;
}

.canvas-node-card.status-failed {
  border-color: #ff4d4f;
  background: #fff2f0;
}

.canvas-node-card.status-skipped {
  opacity: 0.55;
  border-style: dashed;
}

.node-status-indicator {
  position: absolute;
  top: -4px;
  right: -4px;
}

.status-pulse {
  display: block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.pulse-pending { background: #cbd5e1; }
.pulse-running { background: #1677ff; box-shadow: 0 0 8px #1677ff; }
.pulse-success { background: #52c41a; }
.pulse-failed { background: #ff4d4f; }
.pulse-skipped { background: #8c8c8c; }

.node-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  font-size: 16px;
  color: var(--c-primary, #1677ff);
}

.node-title-wrap {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.node-title-text {
  font-weight: 600;
  font-size: 12px;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-type-label {
  font-size: 10px;
  color: #94a3b8;
}

.node-ports-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

.connect-port-btn {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 10px;
  cursor: pointer;
  color: #475569;
}

.connect-port-btn:hover {
  background: var(--c-primary, #1677ff);
  color: #ffffff;
}

.variable-bus-hint-box {
  background: #f0f7ff;
  border: 1px solid #bae0ff;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 12px;
}

.hint-title {
  font-weight: 600;
  font-size: 12px;
  color: #0958d9;
}

.hint-desc {
  font-size: 11px;
  color: #334155;
  margin: 4px 0 0;
}

@keyframes pulse-border {
  0% { box-shadow: 0 0 0 rgba(22, 119, 255, 0.4); }
  100% { box-shadow: 0 0 12px rgba(22, 119, 255, 0.8); }
}
</style>
