<template>
  <div class="cross-protocol-session-bus-panel">
    <!-- 头部控制栏：总线选择与初始化 -->
    <a-card size="small" class="bus-header-card">
      <div class="header-top">
        <div class="desc-box">
          <div class="title-row">
            <h4 class="title">跨协议数据透传与会话上下文共享总线</h4>
            <a-tag color="blue">HTTP ⇄ gRPC ⇄ WS 全局共享树</a-tag>
          </div>
          <p class="subtitle">
            支持在跨协议复杂链路中维持单会话全局状态树（Session Bus）；自动完成 HTTP 鉴权 Token 到 gRPC Metadata 和 WebSocket 握手凭据的主动透传，并对递归嵌套结构执行 <code v-text="'{{variable}}'" /> 动态模板插值。
          </p>
        </div>

        <div class="bus-ctrl-actions">
          <a-space size="small">
            <span class="ctrl-label">总线 ID:</span>
            <a-input v-model:value="activeBusId" size="small" style="width: 170px" />
            <a-button type="primary" size="small" :loading="initializing" @click="handleInitBus">
              初始化总线
            </a-button>
            <a-button size="small" @click="loadPresetVariables">
              载入全链路预设
            </a-button>
            <a-button size="small" :loading="loadingVars" @click="loadVariables">
              刷新变量
            </a-button>
          </a-space>
        </div>
      </div>
    </a-card>

    <a-row :gutter="14" class="content-row">
      <!-- 左侧：全局共享状态变量树与快速写入 -->
      <a-col :span="12">
        <a-card size="small" title="会话总线全局变量表 (Shared Variables)" class="var-table-card">
          <!-- 快捷添加变量 -->
          <div class="add-var-bar">
            <a-input v-model:value="newVarKey" placeholder="变量键 (如 token)" size="small" style="width: 130px" />
            <a-input v-model:value="newVarValue" placeholder="变量值 (如 eyJhbG...)" size="small" style="flex: 1" />
            <a-button type="primary" size="small" :loading="settingVar" @click="handleSetVariable">
              写入变量
            </a-button>
          </div>

          <a-table
            :data-source="variableRows"
            :columns="varColumns"
            row-key="key"
            size="small"
            :pagination="{ pageSize: 5 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'key'">
                <code>{{ record.key }}</code>
              </template>
              <template v-if="column.key === 'value'">
                <span class="val-text">{{ String(record.value) }}</span>
              </template>
              <template v-if="column.key === 'type'">
                <a-tag size="small" color="blue">{{ typeof record.value }}</a-tag>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>

      <!-- 右侧：跨协议透传验证与动态模板插值 -->
      <a-col :span="12">
        <!-- 协议上下文主动透传卡片 -->
        <a-card size="small" title="协议凭据上下文自动透传 (Protocol Propagation)" class="propagate-card">
          <div class="propagate-box">
            <div class="dir-choice-row">
              <span class="dir-label">透传方向:</span>
              <a-radio-group v-model:value="propagateDirection" size="small">
                <a-radio-button value="http_to_grpc">HTTP → gRPC</a-radio-button>
                <a-radio-button value="http_to_websocket">HTTP → WebSocket</a-radio-button>
              </a-radio-group>
              <a-button
                type="primary"
                size="small"
                :loading="propagating"
                @click="handlePropagate"
              >
                执行上下文透传
              </a-button>
            </div>

            <div v-if="propagationResult" class="propagate-result-box">
              <span class="res-title">透传生成的目标协议凭据上下文:</span>
              <pre class="json-code">{{ JSON.stringify(propagationResult, null, 2) }}</pre>
            </div>
          </div>
        </a-card>

        <!-- 动态模板递归插值实时预览 -->
        <a-card size="small" title="动态模板递归插值预览 (Template Interpolation)" class="render-card">
          <div class="render-box">
            <div class="render-input-block">
              <span class="render-label">待插值模板 (JSON 或字符串):</span>
              <a-textarea
                v-model:value="templateInput"
                :rows="4"
                class="template-textarea"
                placeholder="请输入包含 {{variable}} 的模板..."
              />
            </div>

            <div class="render-action-row">
              <a-button type="primary" size="small" :loading="rendering" @click="handleRenderTemplate">
                执行插值渲染
              </a-button>
            </div>

            <div v-if="renderedResult" class="rendered-result-box">
              <span class="res-title">插值完成的实际有效载荷:</span>
              <pre class="json-code">{{ JSON.stringify(renderedResult, null, 2) }}</pre>
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
import {
  sessionBusApi,
} from '@/api/sandboxes'

const activeBusId = ref('bus_cross_demo_01')
const initializing = ref(false)
const loadingVars = ref(false)
const settingVar = ref(false)
const propagating = ref(false)
const rendering = ref(false)

const newVarKey = ref('')
const newVarValue = ref('')
const variables = ref<Record<string, any>>({})

const propagateDirection = ref<'http_to_grpc' | 'http_to_websocket'>('http_to_grpc')
const propagationResult = ref<any>(null)

const defaultTemplate = {
  request_id: '{{trace_id}}',
  authorization: 'Bearer {{user_token}}',
  endpoint: '/api/v1/checkout/{{order_sn}}',
  user_info: {
    uid: '{{user_id}}',
  },
}
const templateInput = ref(JSON.stringify(defaultTemplate, null, 2))
const renderedResult = ref<any>(null)

const varColumns = [
  { title: '变量键名 (Key)', key: 'key', width: 140 },
  { title: '变量值 (Value)', key: 'value' },
  { title: '类型', key: 'type', width: 80 },
]

const variableRows = computed(() => {
  return Object.entries(variables.value).map(([key, value]) => ({
    key,
    value,
  }))
})

async function handleInitBus() {
  initializing.value = true
  try {
    const res = await sessionBusApi.initBus(activeBusId.value)
    message.success(`总线初始化成功: ${res.bus_id}`)
    await loadVariables()
  } catch (err: any) {
    message.error(err.message || '初始化总线失败')
  } finally {
    initializing.value = false
  }
}

async function loadVariables() {
  loadingVars.value = true
  try {
    const res = await sessionBusApi.getVars(activeBusId.value)
    variables.value = res.variables
  } catch (err: any) {
    message.error(err.message || '获取会话总线变量失败')
  } finally {
    loadingVars.value = false
  }
}

async function handleSetVariable() {
  if (!newVarKey.value) {
    message.warning('请输入变量键名')
    return
  }
  settingVar.value = true
  try {
    let parsedVal: any = newVarValue.value
    try {
      parsedVal = JSON.parse(newVarValue.value)
    } catch {
      // 保持原始字符串
    }

    await sessionBusApi.setVar(activeBusId.value, newVarKey.value, parsedVal)
    message.success(`变量 [${newVarKey.value}] 写入成功！`)
    newVarKey.value = ''
    newVarValue.value = ''
    await loadVariables()
  } catch (err: any) {
    message.error(err.message || '写入变量失败')
  } finally {
    settingVar.value = false
  }
}

async function loadPresetVariables() {
  settingVar.value = true
  try {
    await sessionBusApi.setVar(activeBusId.value, 'user_token', 'jwt_eyJhbGciOiJIUzI1NiJ9_token')
    await sessionBusApi.setVar(activeBusId.value, 'order_sn', 'ORD-20261016-9901')
    await sessionBusApi.setVar(activeBusId.value, 'user_id', 'usr_88201')
    await sessionBusApi.setVar(activeBusId.value, 'trace_id', 'tr_9f182c81')
    message.success('已自动向当前总线写入全链路预设变量！')
    await loadVariables()
  } catch (err: any) {
    message.error(err.message || '载入预设变量失败')
  } finally {
    settingVar.value = false
  }
}

async function handlePropagate() {
  propagating.value = true
  try {
    const res = await sessionBusApi.propagateContext(activeBusId.value, propagateDirection.value)
    propagationResult.value = res.grpc_metadata || res.websocket_context || res
    message.success(`跨协议透传成功 (${propagateDirection.value})！`)
  } catch (err: any) {
    message.error(err.message || '协议上下文透传失败')
  } finally {
    propagating.value = false
  }
}

async function handleRenderTemplate() {
  rendering.value = true
  try {
    let payload: any = templateInput.value
    try {
      payload = JSON.parse(templateInput.value)
    } catch {
      // 字符串模板
    }

    const res = await sessionBusApi.renderTemplate(activeBusId.value, payload)
    renderedResult.value = res.rendered
    message.success('模板动态插值渲染成功！')
  } catch (err: any) {
    message.error(err.message || '模板插值失败')
  } finally {
    rendering.value = false
  }
}

onMounted(() => {
  handleInitBus()
})
</script>

<style scoped>
.cross-protocol-session-bus-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bus-header-card,
.var-table-card,
.propagate-card,
.render-card {
  border-radius: 8px;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.title {
  margin: 0;
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

.ctrl-label {
  font-size: 12px;
  color: #64748b;
}

.add-var-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.val-text {
  font-size: 11px;
  font-family: monospace;
  color: #334155;
  word-break: break-all;
}

.propagate-card {
  margin-bottom: 12px;
}

.propagate-box,
.render-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dir-choice-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dir-label,
.render-label {
  font-size: 12px;
  color: #64748b;
}

.propagate-result-box,
.rendered-result-box {
  background: #0f172a;
  border-radius: 6px;
  padding: 10px;
}

.res-title {
  font-size: 11px;
  color: #94a3b8;
  display: block;
  margin-bottom: 4px;
}

.json-code {
  margin: 0;
  font-size: 11px;
  font-family: monospace;
  color: #38bdf8;
  max-height: 130px;
  overflow-y: auto;
}

.template-textarea {
  font-family: monospace;
  font-size: 11px;
  background: var(--c-bg-subtle, #f8fafc);
}

.render-action-row {
  display: flex;
  justify-content: flex-end;
}
</style>
