<template>
  <a-modal
    :open="open"
    :width="1080"
    title="自然语言意图驱动多端混合工作流合成中枢"
    :footer="null"
    destroy-on-close
    class="intent-workflow-modal"
    @cancel="handleClose"
  >
    <div class="intent-modal-body">
      <!-- 头部说明条 -->
      <div class="modal-banner">
        <div class="banner-title">
          <ThunderboltOutlined class="banner-icon" />
          <span>Intent-to-DAG 混合工作流智能合成引擎</span>
          <a-tag color="processing">v5.2.0 AI Core</a-tag>
        </div>
        <p class="banner-desc">
          输入一段自然语言业务测试意图，AI 语义规划器将自动提取协议矩阵（HTTP / Web / Android / iOS / SQL），逆向推导拓扑有向边与跨节点变量动态上下文绑定，一键合成完整可执行测试工作流。
        </p>
      </div>

      <!-- 意图输入与模板区 -->
      <div class="intent-input-panel">
        <div class="preset-templates">
          <span class="template-label">推荐业务意图示例:</span>
          <a-button
            v-for="tpl in presetTemplates"
            :key="tpl.label"
            size="small"
            class="template-btn"
            @click="selectTemplate(tpl.text)"
          >
            {{ tpl.label }}
          </a-button>
        </div>

        <a-textarea
          v-model:value="intentPrompt"
          :rows="3"
          placeholder="例如：在电商系统用接口创建测试商品，随后在 Web 端加购，在 iOS 真机上完成结算支付，最后在数据库中核验订单状态为已付款。"
          class="intent-textarea"
          :disabled="synthesizing || refining"
        />

        <div class="intent-toolbar">
          <div class="workflow-name-input">
            <span class="toolbar-label">生成工作流名称:</span>
            <a-input
              v-model:value="customWorkflowName"
              placeholder="默认由 AI 意图自动命名"
              size="small"
              style="width: 260px"
              :disabled="synthesizing"
            />
          </div>
          <div class="toolbar-actions">
            <a-button
              type="primary"
              :loading="synthesizing"
              :disabled="!intentPrompt.trim()"
              @click="handleGenerate"
            >
              <ThunderboltOutlined /> 一键智能推导工作流 DAG
            </a-button>
          </div>
        </div>
      </div>

      <!-- AI 语义解析与槽位卡片 -->
      <div v-if="synthesisResult" class="semantic-insights-card">
        <div class="insights-header">
          <span class="insights-title"><CheckCircleOutlined style="color: #52c41a" /> AI 语义槽位推导结果</span>
          <span class="insights-id">Synthesis ID: <code>{{ synthesisResult.synthesis_id }}</code></span>
        </div>
        <div class="insights-tags">
          <div class="tag-group">
            <span class="tag-group-title">业务领域:</span>
            <a-tag color="blue">{{ synthesisResult.slots.business_domain || '通用业务' }}</a-tag>
          </div>
          <div class="tag-group">
            <span class="tag-group-title">跨端协议矩阵:</span>
            <a-tag
              v-for="proto in synthesisResult.slots.protocols"
              :key="proto"
              color="cyan"
            >
              {{ proto }}
            </a-tag>
          </div>
          <div class="tag-group">
            <span class="tag-group-title">拓扑统计:</span>
            <span class="stat-badge">{{ synthesisResult.nodes.length }} 节点</span>
            <span class="stat-badge">{{ synthesisResult.edges.length }} 有向边</span>
            <span class="stat-badge">{{ Object.keys(synthesisResult.variable_bindings).length }} 变量绑定</span>
          </div>
        </div>
      </div>

      <!-- 生成的 DAG 节点拓扑预览 -->
      <div v-if="synthesisResult" class="dag-preview-panel">
        <div class="panel-header">
          <span class="panel-title"><ApartmentOutlined /> 工作流拓扑时序步骤预览</span>
          <span class="panel-subtitle">已自动完成节点入参、连线与上下文变量传递装配</span>
        </div>

        <div class="nodes-flow-container">
          <div
            v-for="(node, index) in synthesisResult.nodes"
            :key="node.node_id"
            class="flow-node-item"
          >
            <div class="node-card" :class="'node-card-' + node.node_type">
              <div class="node-card-header">
                <span class="node-step-index">#{{ index + 1 }}</span>
                <span class="node-type-badge">{{ getNodeTypeLabel(node.node_type) }}</span>
              </div>
              <div class="node-card-name">{{ node.node_name }}</div>
              <div v-if="hasBoundVariables(node.node_id)" class="node-variable-tag">
                <span class="var-badge">变量依赖: {{ getBoundVariable(node.node_id) }}</span>
              </div>
            </div>
            <!-- 连接指示箭头 -->
            <div v-if="index < synthesisResult.nodes.length - 1" class="flow-arrow">
              <ArrowRightOutlined />
            </div>
          </div>
        </div>
      </div>

      <!-- 对话式自然语言微调与迭代 -->
      <div v-if="synthesisResult" class="refinement-panel">
        <div class="refinement-header">
          <span class="refine-title"><MessageOutlined /> 对话式自然语言迭代扩充</span>
          <span class="refine-hint">不满意拓扑？直接输入指令让 AI 在当前工作流基础上增补节点或调整逻辑</span>
        </div>
        <div class="refinement-input-bar">
          <a-input
            v-model:value="refineInstruction"
            placeholder="例如：在支付后增加一个延时等待 1000ms，或者追加一个异常分支校验"
            class="refine-input"
            :disabled="refining"
            @pressEnter="handleRefine"
          />
          <a-button
            type="default"
            :loading="refining"
            :disabled="!refineInstruction.trim()"
            @click="handleRefine"
          >
            <SendOutlined /> 对话微调
          </a-button>
        </div>
      </div>

      <!-- 底部控制按钮条 -->
      <div class="modal-footer-bar">
        <a-button @click="handleClose">关闭</a-button>
        <a-button
          v-if="synthesisResult"
          type="primary"
          @click="applyToCanvas"
        >
          <CheckOutlined /> 一键应用到工作流画布
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  CheckCircleOutlined,
  ApartmentOutlined,
  ArrowRightOutlined,
  MessageOutlined,
  SendOutlined,
  CheckOutlined,
} from '@ant-design/icons-vue'
import {
  intentWorkflowApi,
  type SynthesizedWorkflowDAGDTO,
} from '@/api/intentWorkflow'
import type { WorkflowNodeItem, WorkflowEdgeItem } from '@/api/hybridWorkflow'

interface Props {
  open: boolean
  workflowId?: string
  workflowName?: string
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  workflowId: '',
  workflowName: '',
})

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'applied', payload: { nodes: WorkflowNodeItem[]; edges: WorkflowEdgeItem[]; name?: string }): void
}>()

const intentPrompt = ref('')
const customWorkflowName = ref('')
const synthesizing = ref(false)
const refining = ref(false)
const refineInstruction = ref('')
const synthesisResult = ref<SynthesizedWorkflowDAGDTO | null>(null)

const presetTemplates = [
  {
    label: '电商端到端履约',
    text: '在电商系统首先用 HTTP 接口创建订单，随后在 Web 端加购，在 iOS 真机上结算支付，并在数据库中核验订单状态为 PAID。',
  },
  {
    label: '金融风控与转账',
    text: '在金融系统发起用户转账，调用 gRPC 校验风控额度，在 Android 真机完成生物认证，写入数据库流水并延时核验。',
  },
  {
    label: '移动端多协议对账',
    text: '启动 iOS 客户端登录账号，调用后端 API 发送测试优惠券，在客户端刷新页面并在 SQL 数据库核销流水。',
  },
  {
    label: '分布式微服务容灾',
    text: '通过 HTTP 网关下发高频请求，调用 gRPC 检查微服务健康度，延时等待 1000ms 后核查数据库读写分离状态。',
  },
]

function selectTemplate(text: string) {
  intentPrompt.value = text
}

function getNodeTypeLabel(type: string): string {
  const map: Record<string, string> = {
    http: 'REST API',
    grpc: 'gRPC 远程调用',
    web_ui: 'Web UI 交互',
    mobile_android: 'Android 真机',
    mobile_ios: 'iOS 真机',
    database_query: 'SQL 数据库',
    condition_branch: '条件分支',
    delay_sleep: '延时等待',
  }
  return map[type] || type
}

function hasBoundVariables(nodeId: string): boolean {
  if (!synthesisResult.value) return false
  return Boolean(synthesisResult.value.variable_bindings[nodeId])
}

function getBoundVariable(nodeId: string): string {
  if (!synthesisResult.value) return ''
  return synthesisResult.value.variable_bindings[nodeId] || ''
}

async function handleGenerate() {
  if (!intentPrompt.value.trim()) return
  synthesizing.value = true
  try {
    const res = await intentWorkflowApi.generateWorkflow({
      prompt: intentPrompt.value.trim(),
      workflow_id: props.workflowId || undefined,
      workflow_name: customWorkflowName.value.trim() || undefined,
    })
    synthesisResult.value = res.synthesis
    message.success(res.message || '工作流 DAG 智能推导成功！')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '意图工作流合成失败')
  } finally {
    synthesizing.value = false
  }
}

async function handleRefine() {
  if (!synthesisResult.value || !refineInstruction.value.trim()) return
  refining.value = true
  try {
    const res = await intentWorkflowApi.refineWorkflow({
      synthesis_id: synthesisResult.value.synthesis_id,
      refinement_prompt: refineInstruction.value.trim(),
    })
    synthesisResult.value = res.synthesis
    refineInstruction.value = ''
    message.success('已根据微调指令迭代扩充工作流！')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '微调迭代失败')
  } finally {
    refining.value = false
  }
}

function applyToCanvas() {
  if (!synthesisResult.value) return
  emit('applied', {
    nodes: synthesisResult.value.nodes,
    edges: synthesisResult.value.edges,
    name: synthesisResult.value.workflow_name,
  })
  message.success('已成功将 AI 生成的工作流拓扑应用到当前画布！')
  handleClose()
}

function handleClose() {
  emit('update:open', false)
}
</script>

<style scoped>
.intent-modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-banner {
  background: var(--c-bg-subtle, #f6f8fb);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 12px 16px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  margin-bottom: 4px;
}

.banner-icon {
  color: #1677ff;
  font-size: 16px;
}

.banner-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  margin: 0;
  line-height: 1.6;
}

.intent-input-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preset-templates {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.template-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.template-btn {
  font-size: 12px;
  border-radius: 12px;
}

.intent-textarea {
  border-radius: 6px;
  font-size: 13px;
}

.intent-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  margin-right: 8px;
}

.semantic-insights-card {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 10px 14px;
}

.insights-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.insights-title {
  font-size: 13px;
  font-weight: 600;
  color: #166534;
  display: flex;
  align-items: center;
  gap: 6px;
}

.insights-id code {
  font-size: 11px;
  background: #dcfce7;
  padding: 2px 6px;
  border-radius: 4px;
  color: #15803d;
}

.insights-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
}

.tag-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tag-group-title {
  font-size: 12px;
  color: #15803d;
  font-weight: 500;
}

.stat-badge {
  font-size: 12px;
  background: #ffffff;
  border: 1px solid #86efac;
  padding: 1px 8px;
  border-radius: 10px;
  color: #166534;
}

.dag-preview-panel {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--c-bg-container, #ffffff);
}

.panel-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
}

.panel-subtitle {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.nodes-flow-container {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow-x: auto;
  padding: 8px 4px;
}

.flow-node-item {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.node-card {
  width: 170px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle, #cbd5e1);
  background: #fafafa;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.node-card-http {
  border-left: 4px solid #1677ff;
}
.node-card-grpc {
  border-left: 4px solid #722ed1;
}
.node-card-web_ui {
  border-left: 4px solid #52c41a;
}
.node-card-mobile_android {
  border-left: 4px solid #13c2c2;
}
.node-card-mobile_ios {
  border-left: 4px solid #fa8c16;
}
.node-card-database_query {
  border-left: 4px solid #eb2f96;
}
.node-card-condition_branch {
  border-left: 4px solid #fadb14;
}
.node-card-delay_sleep {
  border-left: 4px solid #8c8c8c;
}

.node-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.node-step-index {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-text-tertiary, #94a3b8);
}

.node-type-badge {
  font-size: 10px;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--c-text-secondary, #475569);
}

.node-card-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.node-variable-tag {
  font-size: 10px;
  color: #0284c7;
}

.var-badge {
  background: #e0f2fe;
  padding: 2px 4px;
  border-radius: 4px;
  display: inline-block;
  max-width: 150px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.flow-arrow {
  color: #94a3b8;
  font-size: 16px;
}

.refinement-panel {
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 10px 14px;
}

.refinement-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.refine-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  display: flex;
  align-items: center;
  gap: 4px;
}

.refine-hint {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.refinement-input-bar {
  display: flex;
  gap: 8px;
}

.refine-input {
  font-size: 12px;
}

.modal-footer-bar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--c-border-subtle, #e2e8f0);
}
</style>
