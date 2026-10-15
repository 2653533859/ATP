<template>
  <a-drawer
    :open="open"
    :width="920"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <span>动态参数依赖提取与占位符规则配置</span>
    </template>

    <div class="dynamic-param-extractor">
      <!-- 顶部摘要与分析触发栏 -->
      <a-card size="small" class="header-card">
        <div class="header-content">
          <div class="desc-box">
            <h4 class="title">跨步骤参数上下文自动推导与占位符动态替换</h4>
            <p class="subtitle">
              深度解析上游响应体（JSONPath）中产生的 ID、UUID、Token，自动在下游请求路径、请求头或 JSON 请求体中识别并替换为 <code>&#123;&#123;variable&#125;&#125;</code> 占位符。
            </p>
          </div>
          <div class="action-box">
            <a-button type="primary" :loading="extracting" @click="handleRunExtract">
              执行依赖分析与参数化
            </a-button>
          </div>
        </div>

        <!-- 统计指标胶囊 -->
        <div class="metrics-bar">
          <div class="metric-pill">
            <span class="lbl">输入抓包条目:</span>
            <strong>{{ entries.length }} 条</strong>
          </div>
          <div class="arrow">→</div>
          <div class="metric-pill highlight">
            <span class="lbl">推导跨步依赖:</span>
            <strong>{{ result?.total_dependencies_count ?? 0 }} 条</strong>
          </div>
          <a-tag color="blue" class="tag-status">
            {{ result ? '已完成参数化推导' : '等待分析' }}
          </a-tag>
        </div>
      </a-card>

      <!-- 依赖关系明细表格 -->
      <a-card size="small" title="已推导跨步参数依赖链路 (Data Linkage Graph)" class="dep-card">
        <a-empty v-if="!result?.discovered_dependencies?.length" description="暂无推导依赖，请点击上方「执行依赖分析」按钮" />
        <a-table
          v-else
          :data-source="result.discovered_dependencies"
          :columns="depColumns"
          row-key="variable"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'step_flow'">
              <a-space>
                <a-tag color="cyan">步骤 #{{ record.producer_step + 1 }} 生产</a-tag>
                <span>→</span>
                <a-tag color="purple">步骤 #{{ record.consumer_step + 1 }} 消费</a-tag>
              </a-space>
            </template>

            <template v-if="column.key === 'variable'">
              <code class="var-badge">&#123;&#123;{{ record.variable }}&#125;&#125;</code>
            </template>

            <template v-if="column.key === 'jsonpath'">
              <code class="code-text">{{ record.jsonpath }}</code>
            </template>

            <template v-if="column.key === 'matched_value'">
              <span class="val-text">{{ record.matched_value }}</span>
            </template>

            <template v-if="column.key === 'location'">
              <a-tag :color="getLocationColor(record.location)">
                {{ record.location }}
              </a-tag>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 参数化前后对比预览 -->
      <a-card size="small" title="下游请求替换预览 (Before & After Preview)" class="preview-card">
        <a-tabs size="small">
          <a-tab-pane key="parameterized" tab="参数化后抓包请求 (包含占位符)">
            <div class="json-preview-container">
              <pre class="json-box">{{ formatJson(result?.parameterized_entries ?? entries) }}</pre>
            </div>
          </a-tab-pane>

          <a-tab-pane key="extractions" tab="自动注入的前置提取规则 (Extractions)">
            <div class="extractions-list">
              <div
                v-for="(dep, idx) in result?.discovered_dependencies ?? []"
                :key="idx"
                class="extraction-item"
              >
                <div class="ext-header">
                  <strong>提取变量: <code>{{ dep.variable }}</code></strong>
                  <a-tag color="blue">JSONPath 表达式</a-tag>
                </div>
                <div class="ext-expr">
                  表达式: <code>{{ dep.jsonpath }}</code>
                </div>
                <div class="ext-desc">
                  从步骤 #{{ dep.producer_step + 1 }} 响应中提取运行时值 (示例: {{ dep.matched_value }})，并在步骤 #{{ dep.consumer_step + 1 }} 的 {{ dep.location }} 中注入 <code>&#123;&#123;{{ dep.variable }}&#125;&#125;</code>
                </div>
              </div>
              <a-empty v-if="!result?.discovered_dependencies?.length" description="暂无提取规则" />
            </div>
          </a-tab-pane>
        </a-tabs>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  trafficRecordingApi,
  type RecordedTrafficEntry,
  type ExtractParamsResponse,
} from '@/api/trafficRecording'

const props = withDefaults(
  defineProps<{
    open: boolean
    sessionId?: string
    entries?: RecordedTrafficEntry[]
  }>(),
  {
    open: false,
    sessionId: undefined,
    entries: () => [],
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'extracted', val: ExtractParamsResponse): void
}>()

const extracting = ref(false)
const result = ref<ExtractParamsResponse | null>(null)

const depColumns = [
  { title: '流转链路', key: 'step_flow', width: 220 },
  { title: '推导占位符变量', key: 'variable', width: 160 },
  { title: '提取 JSONPath', key: 'jsonpath', width: 160 },
  { title: '抓包真实值', key: 'matched_value', ellipsis: true },
  { title: '注入位置', key: 'location', width: 110 },
]

function getLocationColor(loc: string): string {
  switch (loc) {
    case 'url_path':
      return 'blue'
    case 'query_param':
      return 'orange'
    case 'header':
      return 'purple'
    case 'request_body':
      return 'green'
    default:
      return 'default'
  }
}

function formatJson(val: any): string {
  try {
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}

function handleClose() {
  emit('update:open', false)
}

async function handleRunExtract() {
  extracting.value = true
  try {
    let res: ExtractParamsResponse
    if (props.sessionId) {
      res = await trafficRecordingApi.extractSessionParams(props.sessionId)
    } else {
      res = await trafficRecordingApi.extractParams(props.entries)
    }
    result.value = res
    emit('extracted', res)
    message.success(`成功推导提取 ${res.total_dependencies_count} 项动态参数依赖！`)
  } catch (err: any) {
    message.error(err.message || '参数依赖分析失败')
  } finally {
    extracting.value = false
  }
}
</script>

<style scoped>
.dynamic-param-extractor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-card {
  border-radius: 8px;
}

.header-content {
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

.metrics-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border, #f1f5f9);
}

.metric-pill {
  padding: 4px 10px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-pill.highlight {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.arrow {
  color: var(--c-text-tertiary, #94a3b8);
}

.dep-card,
.preview-card {
  border-radius: 8px;
}

.var-badge {
  font-weight: 600;
  color: #2563eb;
  background: #eff6ff;
  padding: 2px 6px;
  border-radius: 4px;
}

.code-text {
  font-family: monospace;
  font-size: 11px;
  color: #0f172a;
}

.val-text {
  font-family: monospace;
  font-size: 11px;
  color: #059669;
}

.json-preview-container {
  max-height: 220px;
  overflow-y: auto;
}

.json-box {
  margin: 0;
  font-size: 11px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 10px;
  border-radius: 6px;
}

.extractions-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 220px;
  overflow-y: auto;
}

.extraction-item {
  padding: 8px 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  font-size: 12px;
}

.ext-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.ext-expr {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  margin-bottom: 4px;
}

.ext-desc {
  font-size: 11px;
  color: #475569;
}
</style>
