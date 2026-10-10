<template>
  <a-drawer
    :open="open"
    :title="t('api_scenario.picker_title')"
    :width="960"
    :body-style="{ overflowX: 'hidden', padding: '16px 24px' }"
    :destroy-on-close="true"
    @close="handleClose"
  >
    <div class="picker-container">
      <!-- 顶部功能说明与过滤栏 -->
      <div class="picker-toolbar">
        <div class="toolbar-search">
          <a-input-search
            v-model:value="searchKeyword"
            :placeholder="t('api_scenario.picker_search_placeholder')"
            allow-clear
            size="small"
            style="width: 260px"
          />
          <a-select
            v-model:value="protocolFilter"
            size="small"
            style="width: 140px"
            :options="protocolOptions"
          />
          <a-tree-select
            v-if="moduleTree.length"
            v-model:value="selectedModuleId"
            size="small"
            style="width: 200px"
            allow-clear
            :tree-data="moduleTree"
            :placeholder="t('api_scenario.picker_module_placeholder')"
            :tree-default-expand-all="true"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
          />
        </div>
        <div class="toolbar-stats">
          <span class="toolbar-stat-tag">
            {{ t('api_scenario.picker_available_count', { count: filteredCases.length }) }}
          </span>
        </div>
      </div>

      <!-- 双列穿梭核心布局 -->
      <div class="picker-shuttle-grid">
        <!-- 左侧：接口库候选池 -->
        <div class="shuttle-pane library-pane">
          <div class="pane-header">
            <div class="pane-title">
              <ApiOutlined class="pane-icon" />
              <span>{{ t('api_scenario.picker_library_heading') }}</span>
              <span class="count-badge">{{ filteredCases.length }}</span>
            </div>
            <div class="pane-actions">
              <a-button type="link" size="small" :disabled="!filteredCases.length" @click="addAllFiltered">
                {{ t('api_scenario.picker_add_all') }}
              </a-button>
            </div>
          </div>

          <div class="pane-body">
            <a-spin :spinning="loading">
              <div v-if="!filteredCases.length" class="empty-state">
                <a-empty :description="t('api_scenario.picker_no_cases')" />
              </div>
              <div v-else class="case-items-list">
                <div
                  v-for="item in filteredCases"
                  :key="item.id"
                  class="case-item-card"
                  @click="addCaseToPipeline(item)"
                >
                  <div class="case-method-tag" :class="`method-${getMethod(item)}`">
                    {{ getMethod(item) }}
                  </div>
                  <div class="case-meta-info">
                    <div class="case-name-row">
                      <strong class="case-name" :title="item.name">{{ item.name }}</strong>
                      <span class="case-code">{{ item.case_code }}</span>
                    </div>
                    <div class="case-target-path" :title="getTargetUrl(item)">
                      {{ getTargetUrl(item) }}
                    </div>
                  </div>
                  <div class="case-add-action">
                    <a-button type="primary" shape="circle" size="small" class="add-btn" :title="t('api_scenario.picker_add_step')">
                      <PlusOutlined />
                    </a-button>
                  </div>
                </div>
              </div>
            </a-spin>
          </div>
        </div>

        <!-- 右侧：待编排自动化步骤流水线 -->
        <div class="shuttle-pane pipeline-pane">
          <div class="pane-header">
            <div class="pane-title">
              <ThunderboltOutlined class="pane-icon accent-icon" />
              <span>{{ t('api_scenario.picker_pipeline_heading') }}</span>
              <span class="count-badge active-badge">{{ pipelineSteps.length }}</span>
            </div>
            <div class="pane-actions">
              <a-button
                type="link"
                danger
                size="small"
                :disabled="!pipelineSteps.length"
                @click="pipelineSteps = []"
              >
                {{ t('api_scenario.picker_clear_all') }}
              </a-button>
            </div>
          </div>

          <div class="pipeline-hint-bar">
            <span>{{ t('api_scenario.picker_drag_hint') }}</span>
          </div>

          <div class="pane-body pipeline-body">
            <div v-if="!pipelineSteps.length" class="empty-state">
              <a-empty :description="t('api_scenario.picker_empty_pipeline')" />
            </div>
            <draggable
              v-else
              v-model="pipelineSteps"
              item-key="_uid"
              handle=".drag-handle"
              animation="180"
              class="pipeline-draggable-list"
            >
              <template #item="{ element, index }">
                <div class="pipeline-step-card">
                  <div class="step-card-left">
                    <HolderOutlined class="drag-handle" :title="t('api_scenario.drag_to_reorder')" />
                    <span class="step-badge">Step {{ (currentStepCount || 0) + index + 1 }}</span>
                    <span class="case-method-tag" :class="`method-${element.method || 'GET'}`">
                      {{ element.method || 'GET' }}
                    </span>
                  </div>
                  <div class="step-card-center">
                    <div class="step-name-display">{{ element.name }}</div>
                    <div class="step-url-display">{{ element.url || '—' }}</div>
                  </div>
                  <div class="step-card-actions">
                    <a-button
                      type="text"
                      danger
                      size="small"
                      :title="t('common.delete')"
                      @click="removeStep(index)"
                    >
                      <DeleteOutlined />
                    </a-button>
                  </div>
                </div>
              </template>
            </draggable>
          </div>
        </div>
      </div>
    </div>

    <!-- 抽屉吸底按钮 -->
    <template #footer>
      <div class="picker-footer-actions">
        <div class="footer-stats">
          <span>{{ t('api_scenario.picker_selected_summary', { count: pipelineSteps.length }) }}</span>
        </div>
        <div class="footer-btns">
          <a-button @click="handleClose">{{ t('common.cancel') }}</a-button>
          <a-button
            type="primary"
            :disabled="!pipelineSteps.length"
            :loading="importing"
            @click="confirmImport"
          >
            {{ t('api_scenario.picker_confirm_import', { count: pipelineSteps.length }) }}
          </a-button>
        </div>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  DeleteOutlined,
  HolderOutlined,
} from '@ant-design/icons-vue'
import draggable from 'vuedraggable'
import { useI18n } from 'vue-i18n'
import {
  caseApi,
  projectApi,
  type CaseSummaryItem,
  type ModuleTreeItem,
  type CaseDetailItem,
} from '@/api'
import {
  parseStepFromCase,
  type ApiScenarioStep,
} from '@/types/apiScenario'

interface PipelineStepItem extends ApiScenarioStep {
  _uid: string
  _sourceCaseId?: number
}

const props = defineProps<{
  open: boolean
  projectId?: number | null
  currentStepCount?: number
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
  (e: 'import', steps: ApiScenarioStep[]): void
}>()

const { t } = useI18n()

const loading = ref(false)
const importing = ref(false)
const searchKeyword = ref('')
const protocolFilter = ref('all')
const selectedModuleId = ref<number | undefined>(undefined)

const rawCases = ref<CaseSummaryItem[]>([])
const moduleTree = ref<ModuleTreeItem[]>([])
const pipelineSteps = ref<PipelineStepItem[]>([])

let uidCounter = 0
function generateUid(): string {
  return `step_${Date.now()}_${++uidCounter}`
}

const protocolOptions = computed(() => [
  { label: t('api_workbench.protocol_all'), value: 'all' },
  { label: 'HTTP / REST', value: 'api' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'WebSocket', value: 'websocket' },
])

const filteredCases = computed(() => {
  return rawCases.value.filter((item) => {
    if (protocolFilter.value !== 'all' && item.case_type !== protocolFilter.value) {
      return false
    }
    if (selectedModuleId.value != null && item.module_id !== selectedModuleId.value) {
      return false
    }
    if (searchKeyword.value.trim()) {
      const q = searchKeyword.value.trim().toLowerCase()
      const matchName = item.name.toLowerCase().includes(q)
      const matchCode = (item.case_code || '').toLowerCase().includes(q)
      const matchSummary = (item.summary || '').toLowerCase().includes(q)
      if (!matchName && !matchCode && !matchSummary) {
        return false
      }
    }
    return true
  })
})

function getMethod(item: CaseSummaryItem): string {
  if (item.case_type === 'graphql') return 'GRAPHQL'
  if (item.case_type === 'websocket') return 'WS'
  const summary = item.summary || ''
  const m = summary.match(/^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)/i)
  return m ? m[1].toUpperCase() : 'API'
}

function getTargetUrl(item: CaseSummaryItem): string {
  const summary = item.summary || ''
  const parts = summary.split(' ')
  if (parts.length > 1 && parts[1].startsWith('/')) {
    return parts[1]
  }
  return summary || t('api_workbench.target_missing')
}

async function loadData() {
  if (!props.projectId) return
  loading.value = true
  try {
    const [caseList, modules] = await Promise.all([
      caseApi.list({ project_id: props.projectId }),
      projectApi.getModules(props.projectId).catch(() => []),
    ])
    // 过滤出接口库候选列表：仅限单接口原子请求（过滤掉已编排好的多步场景链路，杜绝混淆）
    rawCases.value = (caseList || []).filter((c) =>
      ['api', 'graphql', 'websocket'].includes(c.case_type) && !c.is_scenario,
    )
    moduleTree.value = modules || []
  } catch (error) {
    message.error(t('api_scenario.picker_load_failed'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      pipelineSteps.value = []
      searchKeyword.value = ''
      selectedModuleId.value = undefined
      void loadData()
    }
  },
  { immediate: true },
)

function addCaseToPipeline(item: CaseSummaryItem) {
  const step = parseStepFromCase(item as unknown as CaseDetailItem)
  pipelineSteps.value.push({
    ...step,
    _uid: generateUid(),
    _sourceCaseId: item.id,
  })
}

function addAllFiltered() {
  filteredCases.value.forEach((item) => {
    addCaseToPipeline(item)
  })
}

function removeStep(index: number) {
  pipelineSteps.value.splice(index, 1)
}

function handleClose() {
  emit('update:open', false)
  emit('close')
}

async function confirmImport() {
  if (!pipelineSteps.value.length) return
  importing.value = true
  try {
    // 针对被选中的用例，如果需要加载更详细的接口配置，获取最新详情
    const enrichedSteps: ApiScenarioStep[] = []
    for (let i = 0; i < pipelineSteps.value.length; i++) {
      const step = pipelineSteps.value[i]
      if (step._sourceCaseId && (!step.url || !step.method)) {
        try {
          const detail = await caseApi.get(step._sourceCaseId)
          const parsed = parseStepFromCase(detail)
          enrichedSteps.push({
            ...parsed,
            name: step.name || parsed.name,
            depends_on: i > 0 ? [i - 1] : [],
          })
          continue
        } catch {
          // ignore error, fallback to initial step
        }
      }
      enrichedSteps.push({
        name: step.name,
        method: step.method,
        url: step.url,
        headers: step.headers,
        params: step.params,
        cookies: step.cookies,
        body_type: step.body_type,
        body: step.body,
        assertions: step.assertions,
        extractions: step.extractions,
        depends_on: i > 0 ? [i - 1] : [],
      })
    }
    emit('import', enrichedSteps)
    message.success(t('api_scenario.picker_import_success', { count: enrichedSteps.length }))
    handleClose()
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.picker-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 520px;
}

.picker-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.toolbar-search {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-stats {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.toolbar-stat-tag {
  background: var(--c-bg-elevated, #fff);
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.picker-shuttle-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  min-height: 480px;
}

.shuttle-pane {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: var(--c-bg-elevated, #fff);
  overflow: hidden;
}

.pane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--c-bg-subtle, #f8fafc);
  border-bottom: 1px solid var(--c-border, #e2e8f0);
}

.pane-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text, #1e293b);
}

.pane-icon {
  font-size: 15px;
  color: var(--c-primary, #1677ff);
}

.accent-icon {
  color: #fa8c16;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 10px;
  background: var(--c-border, #e2e8f0);
  color: var(--c-text-secondary, #64748b);
}

.active-badge {
  background: var(--c-primary-soft, #e6f4ff);
  color: var(--c-primary, #1677ff);
}

.pipeline-hint-bar {
  padding: 6px 14px;
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  background: #fbfcfe;
  border-bottom: 1px dashed var(--c-border, #e2e8f0);
}

.pane-body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  max-height: 460px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 260px;
}

.case-items-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.case-item-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  background: var(--c-bg-elevated, #fff);
  cursor: pointer;
  transition: all 0.2s ease;
}

.case-item-card:hover {
  border-color: var(--c-primary, #1677ff);
  background: var(--c-primary-soft, #f0f7ff);
  transform: translateY(-1px);
}

.case-method-tag {
  display: inline-block;
  padding: 2px 6px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 4px;
  text-align: center;
  min-width: 44px;
}

.method-GET { background: #e6f4ff; color: #0958d9; border: 1px solid #91caff; }
.method-POST { background: #f6ffed; color: #389e0d; border: 1px solid #b7eb8f; }
.method-PUT { background: #fff7e6; color: #d46b08; border: 1px solid #ffd591; }
.method-DELETE { background: #fff1f0; color: #cf1322; border: 1px solid #ffa39e; }
.method-PATCH { background: #f9f0ff; color: #722ed1; border: 1px solid #d3adf7; }
.method-GRAPHQL { background: #fff0f6; color: #c41d7f; border: 1px solid #ffadd2; }
.method-WS { background: #e6fffb; color: #08979c; border: 1px solid #87e8de; }
.method-API { background: #f5f5f5; color: #595959; border: 1px solid #d9d9d9; }

.case-meta-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.case-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.case-name {
  font-size: 13px;
  color: var(--c-text, #1e293b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.case-code {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  font-family: monospace;
}

.case-target-path {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.case-add-action {
  flex-shrink: 0;
}

.add-btn {
  box-shadow: none;
}

.pipeline-draggable-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pipeline-step-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  background: var(--c-bg-elevated, #fff);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

.step-card-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.drag-handle {
  cursor: grab;
  color: var(--c-text-tertiary, #94a3b8);
  padding: 4px;
}

.drag-handle:hover {
  color: var(--c-primary, #1677ff);
}

.step-badge {
  font-size: 11px;
  font-weight: 700;
  color: #fa8c16;
  background: #fff7e6;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid #ffd591;
}

.step-card-center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.step-name-display {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text, #1e293b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-url-display {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-card-actions {
  flex-shrink: 0;
}

.picker-footer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.footer-stats {
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
  font-weight: 500;
}

.footer-btns {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
