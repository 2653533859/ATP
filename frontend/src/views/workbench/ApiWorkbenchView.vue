<template>
  <div class="page-shell api-workbench">
    <header class="api-toolbar">
      <div class="toolbar-left">
        <div class="toolbar-identity">
          <ApiOutlined class="toolbar-icon" />
          <span class="toolbar-name">{{ t('api_workbench.title') }}</span>
        </div>
        <div class="toolbar-project">
          <label class="sr-only">{{ t('api_workbench.project_label') }}</label>
          <a-select
            v-model:value="projectSelectId"
            :options="projectOptions"
            allow-clear
            size="small"
            class="project-select-dropdown"
            :placeholder="t('api_workbench.project_placeholder')"
            @change="handleProjectChange"
          />
        </div>
        <div class="toolbar-status">
          <span class="live-dot" />
          <span>{{ t('api_workbench.execution_rail') }}</span>
          <span v-if="selectedProjectName" class="project-pill-tag">{{ selectedProjectName }}</span>
        </div>
      </div>

      <div class="toolbar-right">
        <a-button v-if="selectedProjectId" size="small" class="toolbar-btn" @click="openSchemaManager">
          {{ t('api_workbench.schema_assets_manage') }}
        </a-button>
        <a-button v-if="selectedProjectId" size="small" class="toolbar-btn" @click="openRequestFilesManager">
          {{ t('api_workbench.request_files_manage') }}
        </a-button>
        <a-button size="small" :loading="loading || environmentsLoading" class="toolbar-btn" @click="refreshWorkbench">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
      </div>
    </header>

    <a-alert
      v-if="selectedProjectId && !canModify"
      class="readonly-alert"
      type="info"
      show-icon
      :message="t('api_workbench.readonly_title')"
      :description="t('api_workbench.readonly_description')"
    />
    <a-empty v-if="!selectedProjectId" class="project-empty" :description="t('api_workbench.select_project_hint')" />

    <template v-else>
      <section class="workspace-frame">
        <aside class="collections-pane">
          <!-- 顶部双胶囊分段模式切换器 -->
          <div class="workbench-mode-pill-container">
            <div class="workbench-mode-pill">
              <button
                type="button"
                class="mode-pill-item"
                :class="{ 'is-active': !isAutomationMode }"
                @click="setAutomationMode(false)"
              >
                <ApiOutlined class="mode-pill-icon" />
                <span>{{ t('api_workbench.mode_debug') }}</span>
              </button>
              <button
                type="button"
                class="mode-pill-item mode-pill-automation"
                :class="{ 'is-active': isAutomationMode }"
                @click="setAutomationMode(true)"
              >
                <ThunderboltOutlined class="mode-pill-icon" />
                <span>{{ t('api_workbench.mode_automation') }}</span>
              </button>
            </div>
          </div>

          <div class="collections-heading">
            <div>
              <span class="column-kicker">{{ t('api_workbench.console.collection') }}</span>
              <h2>{{ t('api_workbench.module_title') }}</h2>
            </div>
            <a-dropdown :trigger="['click']" placement="bottomRight">
              <a-button size="small" type="text" class="collection-plus-btn" :title="t('api_workbench.console.new_request')">
                <PlusOutlined />
              </a-button>
              <template #overlay>
                <a-menu @click="handlePlusMenuClick">
                  <a-menu-item key="debug">
                    <SendOutlined style="margin-right: 8px; color: var(--c-primary, #1677ff)" />
                    <span>{{ t('api_workbench.menu_new_debug') }}</span>
                  </a-menu-item>
                  <a-menu-item key="case" :disabled="!canModify">
                    <FileAddOutlined style="margin-right: 8px; color: #52c41a" />
                    <span>{{ t('api_workbench.menu_new_case') }}</span>
                  </a-menu-item>
                  <a-menu-item key="scenario" :disabled="!canModify">
                    <ThunderboltOutlined style="margin-right: 8px; color: #fa8c16" />
                    <span>{{ t('api_workbench.menu_new_scenario') }}</span>
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </div>
          <ModuleTree
            :key="selectedProjectId"
            :project-id="selectedProjectId"
            :selected-module-id="selectedModuleId"
            show-reset
            :reset-disabled="!selectedModuleId"
            :editable="canModify"
            @select="handleModuleSelect"
            @reset="handleModuleReset"
          />
          <!-- 独立保存的自动化场景列表（不混入普通用例管理库） -->
          <div v-if="isAutomationMode" class="saved-scenarios-section">
            <div class="collection-separator scenario-list-header">
              <div class="separator-left-meta">
                <span>{{ t('api_workbench.scenario_list_title') }}</span>
                <span class="count-tag">{{ scenarios.length }}</span>
              </div>
              <a-button v-if="canModify" type="link" size="small" style="padding: 0; font-size: 12px" @click="startNewBlankScenario">
                {{ t('api_workbench.new_scenario_btn') }}
              </a-button>
            </div>
            <div class="scenario-saved-list">
              <div v-if="!scenarios.length" class="scenario-saved-empty">
                {{ t('api_workbench.scenario_empty_tip') }}
              </div>
              <div
                v-for="sc in scenarios"
                :key="sc.id"
                class="request-list-item scenario-saved-item"
                :class="{ 'is-selected': activeScenarioRecord?.id === sc.id }"
                @click="selectSavedScenario(sc)"
              >
                <span class="request-list-method method-scenario">场景</span>
                <span class="request-list-text">
                  <strong>{{ sc.name }}</strong>
                  <small>{{ sc.scenario_code }} · {{ sc.step_count }} 步</small>
                </span>
                <span class="request-list-state" :class="`run-${sc.last_run_status || 'none'}`" />
                <a-popconfirm
                  v-if="canModify"
                  :title="t('api_workbench.scenario_delete_confirm')"
                  :ok-text="t('common.delete')"
                  :cancel-text="t('common.cancel')"
                  ok-type="danger"
                  @confirm="handleDeleteScenario(sc.id)"
                >
                  <button
                    type="button"
                    class="scenario-del-btn"
                    :title="t('common.delete')"
                    @click.stop
                  >
                    ×
                  </button>
                </a-popconfirm>
              </div>
            </div>
          </div>
          <div class="collection-separator">
            <div class="separator-left-meta">
              <span>{{ isAutomationMode ? t('api_workbench.pending_cases_title') : t('api_workbench.console.saved_requests') }}</span>
              <span class="count-tag">{{ filteredCases.length }}</span>
            </div>
            <div v-if="isAutomationMode" class="separator-right-meta">
              <span class="automation-badge-indicator">{{ t('api_workbench.batch_orchestrating') }}</span>
            </div>
          </div>
          <div class="collection-filters">
            <a-input-search v-model:value="keyword" allow-clear :placeholder="t('api_workbench.search_placeholder')" @search="loadCases" />
            <a-select v-model:value="protocolFilter" :options="protocolOptions" @change="loadCases" />
          </div>
          <div class="request-list" :aria-label="t('api_workbench.console.saved_requests')">
            <a-spin :spinning="loading">
              <div v-if="!filteredCases.length" class="request-list-empty">{{ t('api_workbench.empty_cases') }}</div>
              <div
                v-for="item in filteredCases"
                :key="item.id"
                class="request-list-item"
                :class="{ 'is-selected': selectedCase?.id === item.id, 'is-batch-checked': selectedBatchCaseIds.includes(item.id) }"
                @click="handleRequestItemClick(item)"
              >
                <a-checkbox
                  v-if="isAutomationMode"
                  :checked="selectedBatchCaseIds.includes(item.id)"
                  class="batch-checkbox"
                  @click.stop="toggleBatchSelectCase(item.id)"
                />
                <span v-if="item.is_scenario" class="request-list-method method-scenario">场景</span>
                <span v-else class="request-list-method" :class="`method-${item.case_type}`">{{ requestMethod(item) }}</span>
                <span class="request-list-text"><strong>{{ item.name }}</strong><small>{{ item.case_code }}</small></span>
                <span class="request-list-state" :class="`run-${lastRunStatus(item)}`" />
              </div>
            </a-spin>
          </div>

          <!-- 自动化编排模式悬浮操作栏 -->
          <div v-if="isAutomationMode && selectedBatchCaseIds.length" class="workbench-automation-bar">
            <div class="automation-bar-header">
              <span class="automation-selected-count">{{ t('api_workbench.batch_selected_count', { count: selectedBatchCaseIds.length }) }}</span>
              <a-space size="small">
                <a-button type="link" size="small" @click="selectAllFiltered">{{ t('api_workbench.batch_select_all') }}</a-button>
                <a-button type="link" size="small" @click="selectedBatchCaseIds = []">{{ t('api_workbench.batch_clear_all') }}</a-button>
              </a-space>
            </div>
            <div class="automation-bar-buttons">
              <a-button
                block
                type="primary"
                size="small"
                :disabled="!canModify"
                :loading="orchestratingLoading"
                @click="orchestrateSelectedIntoScenario"
              >
                <ClusterOutlined /> {{ t('api_workbench.batch_orchestrate_scenario') }}
              </a-button>
              <a-button
                block
                size="small"
                :disabled="!canModify"
                :loading="batchRunning"
                @click="openBatchRunModal"
              >
                <PlayCircleOutlined /> {{ t('api_workbench.batch_run_selected') }}
              </a-button>
            </div>
          </div>
          <div class="collection-actions">
            <a-button block :disabled="!selectedModuleId || !canModify" @click="openCreate"><PlusOutlined />{{ t('api_workbench.new_case') }}</a-button>
            <a-button block :disabled="!selectedModuleId || !canModify" @click="openImport"><ThunderboltOutlined />{{ t('api_workbench.import_generate') }}</a-button>
          </div>
        </aside>
        <ApiScenarioOrchestrator
          v-show="isAutomationMode"
          :project-id="selectedProjectId"
          :module-id="selectedModuleId"
          :can-modify="canModify"
          :cases="filteredCases"
          :scenarios="scenarios"
          :environments="environments"
          :schema-assets="schemaAssets"
          :contract-assets="contractAssets"
          :initial-steps="initialScenarioSteps"
          :initial-scenario="activeScenarioRecord"
          :initial-step-index="linkedStepIndex"
          :initial-case="scenarioEditingCase"
          @exit="setAutomationMode(false)"
          @saved="handleScenarioSaved"
          @run-created="openRunDetail"
        />
        <ApiRequestConsole
          v-show="!isAutomationMode"
          :project-id="selectedProjectId"
          :module-id="selectedModuleId"
          :can-modify="canModify"
          :case-detail="selectedCaseDetail"
          :schema-assets="schemaAssets"
          :contract-assets="contractAssets"
          :reset-key="consoleResetKey"
          @save-draft="saveDraftAsCase"
          @edit="editSelectedCase"
          @detail="viewSelectedCase"
          @run="runSelectedCase"
        />
      </section>
    </template>

    <a-drawer v-model:open="detailOpen" :title="selectedCase?.name || t('api_workbench.detail_title')" width="620px">
      <a-spin :spinning="detailLoading">
        <template v-if="selectedCase">
          <div class="detail-headline">
            <div>
              <span class="case-code">{{ selectedCase.case_code }}</span>
              <h2>{{ selectedCase.name }}</h2>
            </div>
            <a-tag :color="protocolColor(selectedCase.case_type)">{{ protocolLabel(selectedCase.case_type as ApiCaseType) }}</a-tag>
          </div>
          <div class="detail-actions">
            <a-button type="primary" :disabled="!canModify || !selectedCase.is_ready_for_execution" @click="openRun(selectedCase)">
              <PlayCircleOutlined /> {{ t('api_workbench.run_now') }}
            </a-button>
            <a-button :disabled="!canModify" @click="openEdit(selectedCase)">{{ t('common.edit') }}</a-button>
          </div>

          <section class="detail-block">
            <div class="detail-block-title">{{ t('api_workbench.request_snapshot') }}</div>
            <div class="request-snapshot">
              <div class="request-method">{{ selectedRequest.method }}</div>
              <code>{{ selectedRequest.target || t('api_workbench.target_missing') }}</code>
            </div>
            <div class="request-meta">
              <span>{{ t('api_workbench.request_steps', { count: selectedSteps.length }) }}</span>
              <span>{{ t('api_workbench.request_assertions', { count: selectedAssertionCount }) }}</span>
              <span>{{ selectedCase.dataset_id ? t('api_workbench.dataset_bound') : t('api_workbench.dataset_unbound') }}</span>
            </div>
          </section>

          <section class="detail-block">
            <div class="detail-block-title">{{ t('api_workbench.recent_runs') }}</div>
            <a-empty v-if="!selectedRunHistory.length" :description="t('api_workbench.no_runs')" />
            <div v-for="run in selectedRunHistory" :key="run.id" class="run-history-row">
              <div>
                <span class="run-state" :class="`run-${run.status}`"><span class="state-dot" />{{ runStatusLabel(run.status) }}</span>
                <span class="run-time">{{ formatTime(run.created_at) }}</span>
              </div>
              <div class="run-history-right">
                <span>{{ formatDuration(run.duration_ms) }}</span>
                <a-button type="link" size="small" @click="openRunDetail(run.id)">{{ t('api_workbench.open_result') }}</a-button>
              </div>
            </div>
          </section>
        </template>
      </a-spin>
    </a-drawer>

    <a-modal v-model:open="runModalOpen" :title="t('api_workbench.run_title')" :confirm-loading="runLoading" @ok="confirmRun">
      <a-form layout="vertical">
        <a-form-item :label="t('api_workbench.run_case_label')">
          <strong>{{ pendingRunCase?.name || '—' }}</strong>
        </a-form-item>
        <a-form-item :label="t('api_workbench.environment_label')">
          <a-select
            v-model:value="runEnvironmentId"
            allow-clear
            :options="environmentOptions"
            :placeholder="t('api_workbench.environment_placeholder')"
            style="width: 100%"
          />
          <div class="form-hint">{{ t('api_workbench.environment_hint') }}</div>
        </a-form-item>
      </a-form>
    </a-modal>

    <CaseFormDrawer
      :open="caseFormOpen"
      :project-id="selectedProjectId"
      :module-id="selectedModuleId"
      :edit-case="editingCase"
      :draft-request="draftRequest"
      :default-case-type="draftRequest ? 'api' : defaultCaseType"
      :initial-scenario-steps="initialScenarioSteps"
      @close="closeCaseForm"
      @saved="handleSaved"
    />

    <AIGenerateDrawer
      :open="importDrawerOpen"
      :project-id="selectedProjectId"
      :module-id="selectedModuleId"
      :allowed-case-types="API_CASE_TYPES"
      @close="importDrawerOpen = false"
      @saved="handleSaved"
    />

    <a-modal
      v-model:open="batchRunModalOpen"
      :title="t('api_workbench.batch_run_confirm_title')"
      :confirm-loading="batchRunning"
      @ok="confirmBatchRun"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('api_workbench.batch_selected_count', { count: selectedBatchCaseIds.length })">
          <div class="batch-run-cases-preview">
            <a-tag v-for="id in selectedBatchCaseIds" :key="id" color="blue">
              {{ cases.find(c => c.id === id)?.name || `#${id}` }}
            </a-tag>
          </div>
        </a-form-item>
        <a-form-item :label="t('api_workbench.environment_label')">
          <a-select
            v-model:value="batchRunEnvironmentId"
            allow-clear
            :options="environmentOptions"
            :placeholder="t('api_workbench.environment_placeholder')"
            style="width: 100%"
          />
          <div class="form-hint">{{ t('api_workbench.environment_hint') }}</div>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer
      v-model:open="schemaDrawerOpen"
      :title="t('api_workbench.schema_assets_title')"
      :width="660"
    >
      <div class="schema-drawer-toolbar">
        <a-button v-if="canModify" type="primary" size="small" @click="openSchemaEditor(null)">
          <PlusOutlined /> {{ t('api_workbench.schema_create') }}
        </a-button>
      </div>
      <a-table
        :columns="schemaColumns"
        :data-source="schemaAssets"
        :pagination="false"
        row-key="id"
        size="small"
        :locale="{ emptyText: t('api_workbench.schema_empty') }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'actions'">
            <a-space v-if="canModify">
              <a-button type="link" size="small" @click="openSchemaEditor(record as ApiSchemaAssetItem)">
                {{ t('common.edit') }}
              </a-button>
              <a-popconfirm
                :title="t('common.confirm_delete')"
                @confirm="handleDeleteSchema(record.id)"
              >
                <a-button type="link" size="small" danger :loading="deletingSchemaId === record.id">
                  {{ t('common.delete') }}
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <a-modal
      v-model:open="schemaEditorOpen"
      :title="editingSchemaId ? t('api_workbench.schema_edit') : t('api_workbench.schema_create')"
      :confirm-loading="savingSchema"
      width="620px"
      @ok="handleSaveSchema"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('common.name')" required>
          <a-input v-model:value="schemaFormName" />
        </a-form-item>
        <a-form-item :label="t('common.description')">
          <a-input v-model:value="schemaFormDescription" />
        </a-form-item>
        <a-form-item :label="t('api_workbench.schema_definition_json')" required>
          <a-textarea v-model:value="schemaFormDefinition" :rows="10" style="font-family: monospace" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer
      v-model:open="requestFilesDrawerOpen"
      :title="t('api_workbench.request_files_title')"
      :width="680"
    >
      <a-table
        :columns="requestFileColumns"
        :data-source="requestFiles"
        :loading="requestFilesLoading"
        :pagination="false"
        row-key="object_name"
        size="small"
        :locale="{ emptyText: t('api_workbench.request_files_empty') }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'size'">{{ formatBytes(record.size) }}</template>
          <template v-else-if="column.key === 'last_modified'">{{ record.last_modified ? formatTime(record.last_modified) : '-' }}</template>
          <template v-else-if="column.key === 'actions'">
            <a-space v-if="canModify">
              <a-button type="link" size="small" @click="openRenameRequestFile(record as { object_name: string; filename: string })">{{ t('web_assets.rename') }}</a-button>
              <a-popconfirm :title="t('common.confirm_delete')" @confirm="handleDeleteRequestFile(record.object_name)">
                <a-button type="link" size="small" danger :loading="deletingRequestFileName === record.object_name">{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <a-modal
      v-model:open="renameRequestFileOpen"
      :title="t('web_assets.rename_file_title')"
      :confirm-loading="renamingRequestFile"
      @ok="handleRenameRequestFile"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('web_assets.filename')" required>
          <a-input v-model:value="renameRequestFileForm.filename" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  FileAddOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SendOutlined,
  ThunderboltOutlined,
  ClusterOutlined,
} from '@ant-design/icons-vue'
import { parseStepFromCase, type ApiScenarioStep } from '@/types/apiScenario'
import { useI18n } from 'vue-i18n'
import { formatLocalDateTime } from '@/utils/dateTime'
import { useRoute, useRouter } from 'vue-router'
import {
  apiContractAssetApi,
  apiScenarioApi,
  apiSchemaAssetApi,
  caseApi,
  environmentApi,
  projectApi,
  runApi,
  type ApiContractAssetItem,
  type ApiRequestPreviewPayload,
  type ApiScenarioRecord,
  type ApiSchemaAssetItem,
  type CaseDetailItem,
  type CaseSummaryItem,
  type CaseType,
  type EnvironmentItem,
  type ProjectItem,
  type RunDetailItem,
} from '@/api'
import ModuleTree from '@/components/common/ModuleTree.vue'
import CaseFormDrawer from '@/components/common/CaseFormDrawer.vue'
import ApiRequestConsole from './components/ApiRequestConsole.vue'
import ApiScenarioOrchestrator from './components/ApiScenarioOrchestrator.vue'
import AIGenerateDrawer from '@/views/case/AIGenerateDrawer.vue'
import { canEditProjectByRole } from '@/utils/permissions'
import { extractApiError } from '@/utils/apiError'
import { useAuthStore } from '@/stores/auth'
function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

type ApiCaseType = 'api' | 'graphql' | 'websocket' | 'grpc'
type ProtocolFilter = 'all' | ApiCaseType

const API_CASE_TYPES: CaseType[] = ['api', 'graphql', 'websocket', 'grpc']

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(positiveInt(route.query.project_id))
const projectSelectId = computed<number | undefined>({
  get: () => selectedProjectId.value ?? undefined,
  set: (value) => { selectedProjectId.value = positiveInt(value) },
})
const selectedModuleId = ref<number | null>(positiveInt(route.query.module_id))
const linkedStepIndex = ref<number | null>(null)
const cases = ref<CaseSummaryItem[]>([])
const recentRuns = ref<RunDetailItem[]>([])
const environments = ref<EnvironmentItem[]>([])
const schemaAssets = ref<ApiSchemaAssetItem[]>([])
const contractAssets = ref<ApiContractAssetItem[]>([])
const keyword = ref('')
const protocolFilter = ref<ProtocolFilter>('all')
const loading = ref(false)
const environmentsLoading = ref(false)

const projectOptions = computed(() => projects.value.map((project) => ({
  label: project.name,
  value: project.id,
})))
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const canModify = computed(() => canEditProjectByRole(auth.user?.role, selectedProject.value?.current_user_role))
function protocolLabel(protocol: ApiCaseType | CaseType) {
  return t(`api_workbench.protocols.${protocol}`)
}

function protocolColor(protocol: CaseType) {
  return ({ api: 'blue', graphql: 'orange', websocket: 'cyan', grpc: 'purple' } as Record<string, string>)[protocol] || 'default'
}

function requestMethod(item: CaseSummaryItem) {
  return ({ api: 'HTTP', graphql: 'GQL', websocket: 'WS', grpc: 'RPC' } as Record<string, string>)[item.case_type] || 'API'
}

function formatTime(value?: string | null) {
  return formatLocalDateTime(value, '—')
}

function formatDuration(value?: number | null) {
  if (value == null) return '—'
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(2)} s`
}

function runStatusLabel(status?: string | null) {
  if (!status) return t('api_workbench.run_status.none')
  const key = ['pending', 'running', 'passed', 'failed', 'error', 'cancelled', 'stopped'].includes(status) ? status : 'unknown'
  return t(`api_workbench.run_status.${key}`)
}

function lastRunStatus(item: CaseSummaryItem) {
  return recentRuns.value.find((run) => run.case_id === item.id)?.status || 'none'
}

const defaultCaseType = computed<CaseType>(() => protocolFilter.value === 'all' ? 'api' : protocolFilter.value)
const protocolOptions = computed(() => [
  { label: t('api_workbench.protocol_all'), value: 'all' },
  ...API_CASE_TYPES.map((protocol) => ({ label: protocolLabel(protocol), value: protocol })),
])
const environmentOptions = computed(() => environments.value.map((environment) => ({
  label: environment.name,
  value: environment.id,
})))
const isAutomationMode = ref(false)
const filteredCases = computed(() => {
  return cases.value.filter((item) => {
    if (protocolFilter.value !== 'all' && item.case_type !== protocolFilter.value) {
      return false
    }
    if (isAutomationMode.value && item.is_scenario) {
      return false
    }
    return true
  })
})

watch(filteredCases, (visibleList) => {
  if (!selectedBatchCaseIds.value.length) return
  const visibleSet = new Set(visibleList.map((item) => item.id))
  const next = selectedBatchCaseIds.value.filter((id) => visibleSet.has(id))
  if (next.length !== selectedBatchCaseIds.value.length) {
    selectedBatchCaseIds.value = next
  }
})

const detailOpen = ref(false)
const detailLoading = ref(false)
const selectedCase = ref<CaseSummaryItem | null>(null)
const selectedCaseDetail = ref<CaseDetailItem | null>(null)
const caseFormOpen = ref(false)
const editingCase = ref<CaseDetailItem | null>(null)
const draftRequest = ref<ApiRequestPreviewPayload | null>(null)
const consoleResetKey = ref(0)
const selectedSteps = computed(() => {
  const raw = selectedCaseDetail.value?.config?.steps
  return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : []
})
const selectedRequest = computed(() => {
  const step = selectedSteps.value[0] || {}
  const type = selectedCaseDetail.value?.case_type
  if (type === 'graphql') return { method: 'POST', target: String(step.endpoint || '') }
  if (type === 'grpc') return { method: 'RPC', target: `${String(step.target || '')}/${String(step.service || '')}/${String(step.method || '')}` }
  return { method: String(step.method || (type === 'websocket' ? 'WS' : 'GET')), target: String(step.url || '') }
})
const selectedAssertionCount = computed(() =>
  selectedSteps.value.reduce(
    (sum, step) => sum + (Array.isArray(step.assertions) ? step.assertions.length : 0),
    0,
  ),
)
const selectedRunHistory = computed(() =>
  selectedCase.value
    ? recentRuns.value.filter((run) => run.case_id === selectedCase.value?.id).slice(0, 8)
    : [],
)
const importDrawerOpen = ref(false)
const runModalOpen = ref(false)
const runLoading = ref(false)
const pendingRunCase = ref<CaseSummaryItem | null>(null)
const runEnvironmentId = ref<number | undefined>(undefined)
const selectedBatchCaseIds = ref<number[]>([])
const orchestratingLoading = ref(false)
const batchRunning = ref(false)
const initialScenarioSteps = ref<ApiScenarioStep[] | null>(null)
const activeScenarioRecord = ref<ApiScenarioRecord | null>(null)
const scenarios = ref<ApiScenarioRecord[]>([])
const scenarioEditingCase = ref<CaseDetailItem | null>(null)
const batchRunModalOpen = ref(false)
const batchRunEnvironmentId = ref<number | undefined>(undefined)

let scenarioSequence = 0

async function loadScenarios() {
  const sequence = ++scenarioSequence
  if (!selectedProjectId.value || !apiScenarioApi?.list) {
    scenarios.value = []
    return
  }
  try {
    const list = await apiScenarioApi.list({ project_id: selectedProjectId.value })
    if (sequence !== scenarioSequence) return
    scenarios.value = list
  } catch {
    if (sequence === scenarioSequence) scenarios.value = []
  }
}

function selectSavedScenario(sc: ApiScenarioRecord) {
  linkedStepIndex.value = null
  activeScenarioRecord.value = sc
  initialScenarioSteps.value = null
  scenarioEditingCase.value = null
}

function startNewBlankScenario() {
  activeScenarioRecord.value = null
  scenarioEditingCase.value = null
  initialScenarioSteps.value = [
    {
      name: '请求步骤 1',
      method: 'POST',
      url: '/',
      headers: { 'Content-Type': 'application/json' },
      params: {},
      cookies: {},
      body_type: 'json',
      body: { pageNo: 1, pageSize: 10 },
      assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
      extractions: [],
    },
  ]
}

async function handleDeleteScenario(scenarioId: number) {
  if (!canModify.value) return
  try {
    await apiScenarioApi.delete(scenarioId)
    if (activeScenarioRecord.value?.id === scenarioId) {
      startNewBlankScenario()
    }
    await loadScenarios()
    message.success(t('api_workbench.scenario_delete_success'))
  } catch {
    message.error(t('api_workbench.scenario_delete_failed'))
  }
}

function setAutomationMode(val: boolean) {
  isAutomationMode.value = val
  if (!val) {
    selectedBatchCaseIds.value = []
  } else {
    void loadScenarios()
  }
}

async function handleScenarioSaved(scenarioId: number) {
  await loadScenarios()
  const found = scenarios.value.find((s) => s.id === scenarioId)
  if (found) {
    if (activeScenarioRecord.value && activeScenarioRecord.value.id === scenarioId) {
      Object.assign(activeScenarioRecord.value, found)
    } else {
      activeScenarioRecord.value = found
    }
  }
}

function toggleBatchSelectCase(id: number) {
  const idx = selectedBatchCaseIds.value.indexOf(id)
  if (idx > -1) {
    selectedBatchCaseIds.value.splice(idx, 1)
  } else {
    selectedBatchCaseIds.value.push(id)
  }
}

function selectAllFiltered() {
  selectedBatchCaseIds.value = filteredCases.value.map((c) => c.id)
}



async function orchestrateSelectedIntoScenario() {
  if (!canModify.value || !selectedBatchCaseIds.value.length || orchestratingLoading.value) return
  orchestratingLoading.value = true
  try {
    const steps: ApiScenarioStep[] = []
    let resolvedModuleId = selectedModuleId.value
    for (let i = 0; i < selectedBatchCaseIds.value.length; i++) {
      const id = selectedBatchCaseIds.value[i]
      try {
        const detail = await caseApi.get(id)
        if (!resolvedModuleId && detail.module_id) {
          resolvedModuleId = detail.module_id
        }
        const parsed = parseStepFromCase(detail)
        steps.push({
          ...parsed,
          sourceCaseId: id,
          depends_on: i > 0 ? [i - 1] : [],
        })
      } catch {
        const fallback = filteredCases.value.find((c) => c.id === id)
        if (fallback) {
          if (!resolvedModuleId && fallback.module_id) {
            resolvedModuleId = fallback.module_id
          }
          steps.push({
            name: fallback.name,
            method: requestMethod(fallback),
            url: '',
            headers: {},
            params: {},
            cookies: {},
            body_type: 'none',
            body: '',
            assertions: [],
            extractions: [],
            depends_on: i > 0 ? [i - 1] : [],
          })
        }
      }
    }
    if (!resolvedModuleId && filteredCases.value.length) {
      resolvedModuleId = filteredCases.value[0]?.module_id ?? null
    }
    if (resolvedModuleId) {
      selectedModuleId.value = resolvedModuleId
    }
    const stepNames = steps.map((s) => s.name || 'API').filter(Boolean)
    const autoName = `场景 - ${stepNames.slice(0, 2).join(' → ')}${stepNames.length > 2 ? ` 等${stepNames.length}步` : ''}`
    if (apiScenarioApi?.create && selectedProjectId.value) {
      const created = await apiScenarioApi.create({
        project_id: selectedProjectId.value,
        module_id: resolvedModuleId,
        name: autoName,
        description: `由 ${steps.length} 个接口编排生成`,
        steps: steps as unknown as Array<Record<string, unknown>>,
      })
      await loadScenarios()
      activeScenarioRecord.value = created
      initialScenarioSteps.value = null
      scenarioEditingCase.value = null
      selectedBatchCaseIds.value = []
      isAutomationMode.value = true
      message.success(t('api_workbench.orchestrate_saved_success', { code: created.scenario_code, count: steps.length }))
    } else {
      scenarioEditingCase.value = null
      activeScenarioRecord.value = null
      initialScenarioSteps.value = steps
      isAutomationMode.value = true
      message.success(t('api_workbench.orchestrate_loaded_success', { count: steps.length }))
    }
  } catch (error: unknown) {
    message.error(errorMessage(error, t('api_workbench.orchestrate_failed')))
  } finally {
    orchestratingLoading.value = false
  }
}
function openBatchRunModal() {
  if (!selectedBatchCaseIds.value.length) return
  batchRunModalOpen.value = true
  batchRunEnvironmentId.value = undefined
}

async function confirmBatchRun() {
  if (!selectedBatchCaseIds.value.length) return
  batchRunning.value = true
  try {
    let triggered = 0
    for (const id of selectedBatchCaseIds.value) {
      try {
        await caseApi.run(id, { env_id: batchRunEnvironmentId.value })
        triggered++
      } catch {
        // continue running other selected cases
      }
    }
    if (triggered > 0) {
      message.success(t('api_workbench.batch_run_success', { count: triggered }))
    } else {
      message.error(t('api_workbench.run_failed'))
    }
    batchRunModalOpen.value = false
    selectedBatchCaseIds.value = []
    if (selectedProjectId.value) {
      void loadRecentRuns(filteredCases.value.map((c) => c.id))
    }
  } finally {
    batchRunning.value = false
  }
}

let loadSequence = 0
let detailSequence = 0
let environmentSequence = 0
let schemaAssetsSequence = 0
let projectSequence = 0
function errorMessage(error: unknown, fallback: string) {
  return extractApiError(error, fallback)
}

function syncRoute() {
  void router.replace({
    query: {
      ...(selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {}),
      ...(selectedModuleId.value ? { module_id: String(selectedModuleId.value) } : {}),
    },
  })
}

async function loadEnvironments() {
  const projectId = selectedProjectId.value
  const sequence = ++environmentSequence
  if (!projectId) {
    environments.value = []
    environmentsLoading.value = false
    return
  }
  environmentsLoading.value = true
  try {
    const result = await environmentApi.list(projectId)
    if (sequence !== environmentSequence) return
    environments.value = result
  } catch {
    if (sequence === environmentSequence) environments.value = []
  } finally {
    if (sequence === environmentSequence) environmentsLoading.value = false
  }
}

async function loadSchemaAndContractAssets() {
  const projectId = selectedProjectId.value
  const sequence = ++schemaAssetsSequence
  if (!projectId) {
    schemaAssets.value = []
    contractAssets.value = []
    return
  }
  const [schemaRes, contractRes] = await Promise.allSettled([
    apiSchemaAssetApi?.list ? apiSchemaAssetApi.list(projectId) : Promise.resolve([]),
    apiContractAssetApi?.list ? apiContractAssetApi.list(projectId) : Promise.resolve([]),
  ])
  if (sequence !== schemaAssetsSequence || selectedProjectId.value !== projectId) return
  schemaAssets.value = schemaRes.status === 'fulfilled' && Array.isArray(schemaRes.value) ? schemaRes.value : []
  contractAssets.value = contractRes.status === 'fulfilled' && Array.isArray(contractRes.value) ? contractRes.value : []
}

async function loadRecentRuns(caseIds: number[], sequence?: number) {
  if (sequence !== undefined && sequence !== loadSequence) return
  if (!caseIds.length || !selectedProjectId.value) {
    recentRuns.value = []
    return
  }
  try {
    const result = await runApi.list({ project_id: selectedProjectId.value, page: 1, page_size: 100 })
    if (sequence !== undefined && sequence !== loadSequence) return
    recentRuns.value = result.items
      .filter((run) => caseIds.includes(run.case_id))
      .sort((left, right) => right.created_at.localeCompare(left.created_at))
  } catch {
    if (sequence === undefined || sequence === loadSequence) recentRuns.value = []
  }
}

async function loadCases() {
  const projectId = selectedProjectId.value
  const sequence = ++loadSequence
  if (!projectId) {
    cases.value = []
    recentRuns.value = []
    loading.value = false
    return
  }
  loading.value = true
  try {
    const result = await caseApi.list({
      project_id: projectId,
      module_id: selectedModuleId.value ?? undefined,
      keyword: keyword.value.trim() || undefined,
    })
    if (sequence !== loadSequence) return
    cases.value = result.filter((item) => API_CASE_TYPES.includes(item.case_type))
    await loadRecentRuns(cases.value.map((item) => item.id), sequence)
  } catch (error: unknown) {
    if (sequence === loadSequence) message.error(errorMessage(error, t('api_workbench.load_failed')))
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function loadProjects() {
  const sequence = ++projectSequence
  try {
    const result = await projectApi.list()
    if (sequence !== projectSequence) return
    projects.value = result
    if (!selectedProjectId.value || !projects.value.some((item) => item.id === selectedProjectId.value)) {
      selectedProjectId.value = projects.value[0]?.id ?? null
    }
    await Promise.all([loadEnvironments(), loadCases(), loadSchemaAndContractAssets()])
    if (sequence !== projectSequence) return
    const linkedScenarioId = positiveInt(route.query.scenario_id)
    if (linkedScenarioId) {
      const requestedStepIndex = Number(route.query.step_index)
      linkedStepIndex.value = Number.isInteger(requestedStepIndex) && requestedStepIndex >= 0 ? requestedStepIndex : null
      isAutomationMode.value = true
      await loadScenarios()
      const linkedScenario = scenarios.value.find((item) => item.id === linkedScenarioId)
      if (linkedScenario) activeScenarioRecord.value = linkedScenario
    }
    syncRoute()
  } catch (error: unknown) {
    if (sequence === projectSequence) message.error(errorMessage(error, t('api_workbench.load_failed')))
  }
}

async function handleProjectChange(value: unknown) {
  selectedProjectId.value = positiveInt(value)
  selectedModuleId.value = null
  linkedStepIndex.value = null
  selectedBatchCaseIds.value = []
  activeScenarioRecord.value = null
  scenarioEditingCase.value = null
  initialScenarioSteps.value = null
  scenarios.value = []
  startNewRequest()
  const tasks: Promise<unknown>[] = [loadEnvironments(), loadCases(), loadSchemaAndContractAssets()]
  if (isAutomationMode.value) {
    tasks.push(loadScenarios())
  }
  await Promise.all(tasks)
  syncRoute()
}

async function handleModuleSelect(moduleId: number | null) {
  selectedModuleId.value = moduleId
  if (selectedCase.value && selectedCase.value.module_id !== moduleId) {
    invalidateDetailRequest()
    selectedCase.value = null
    selectedCaseDetail.value = null
    consoleResetKey.value += 1
  }
  await loadCases()
  syncRoute()
}

async function handleModuleReset() {
  selectedModuleId.value = null
  await loadCases()
  syncRoute()
}

async function refreshWorkbench() {
  // loadProjects 会在确认当前项目后统一刷新环境、用例和 URL，避免刷新按钮触发重复请求。
  await loadProjects()
  if (isAutomationMode.value) {
    await loadScenarios()
  }
}

function openCreate() {
  if (!selectedModuleId.value) {
    message.warning(t('api_workbench.select_module_first'))
    return
  }
  if (!canModify.value) {
    message.warning(t('api_workbench.readonly_title'))
    return
  }
  invalidateDetailRequest()
  editingCase.value = null
  draftRequest.value = null
  initialScenarioSteps.value = null
  caseFormOpen.value = true
}

function invalidateDetailRequest() {
  detailSequence += 1
  detailLoading.value = false
}

async function openDetail(item: CaseSummaryItem) {
  const sequence = ++detailSequence
  selectedCase.value = item
  selectedCaseDetail.value = null
  detailOpen.value = true
  detailLoading.value = true
  try {
    const detail = await caseApi.get(item.id)
    if (sequence !== detailSequence) return
    selectedCaseDetail.value = detail
  } catch (error: unknown) {
    if (sequence === detailSequence) message.error(errorMessage(error, t('api_workbench.detail_failed')))
  } finally {
    if (sequence === detailSequence) detailLoading.value = false
  }
}

async function handleRequestItemClick(item: CaseSummaryItem) {
  if (isAutomationMode.value) {
    toggleBatchSelectCase(item.id)
  } else if (item.is_scenario) {
    setAutomationMode(true)
    try {
      const detail = await caseApi.get(item.id)
      activeScenarioRecord.value = null
      scenarioEditingCase.value = detail
      initialScenarioSteps.value = null
    } catch (error: unknown) {
      message.error(errorMessage(error, t('api_workbench.detail_failed')))
    }
  } else {
    selectRequest(item)
  }
}

function startNewRequest() {
  invalidateDetailRequest()
  selectedCase.value = null
  selectedCaseDetail.value = null
  detailOpen.value = false
  consoleResetKey.value += 1
}
function handlePlusMenuClick({ key }: { key: string | number }) {
  if (key === 'debug') {
    if (isAutomationMode.value) {
      setAutomationMode(false)
    }
    startNewRequest()
    message.success(t('api_workbench.new_debug_hint'))
  } else if (key === 'case') {
    if (!canModify.value) return
    openCreate()
  } else if (key === 'scenario') {
    if (!canModify.value) return
    if (!isAutomationMode.value) {
      setAutomationMode(true)
    }
    startNewBlankScenario()
    message.success(t('api_workbench.new_scenario_hint'))
  }
}


async function selectRequest(item: CaseSummaryItem) {
  if (item.case_type !== 'api') {
    startNewRequest()
    await openDetail(item)
    return
  }
  const sequence = ++detailSequence
  selectedCase.value = item
  selectedCaseDetail.value = null
  detailOpen.value = false
  detailLoading.value = true
  try {
    const detail = await caseApi.get(item.id)
    if (sequence !== detailSequence) return
    selectedCaseDetail.value = detail
  } catch (error: unknown) {
    if (sequence === detailSequence) message.error(errorMessage(error, t('api_workbench.detail_failed')))
  } finally {
    if (sequence === detailSequence) detailLoading.value = false
  }
}

function saveDraftAsCase(value: ApiRequestPreviewPayload) {
  if (!selectedModuleId.value || !canModify.value) {
    message.warning(t('api_workbench.select_module_first'))
    return
  }
  editingCase.value = null
  draftRequest.value = value
  initialScenarioSteps.value = null
  caseFormOpen.value = true
}

function editSelectedCase() {
  if (selectedCase.value) void openEdit(selectedCase.value)
}

function viewSelectedCase() {
  if (selectedCase.value) void openDetail(selectedCase.value)
}

function runSelectedCase() {
  if (selectedCase.value) openRun(selectedCase.value)
}

function closeCaseForm() {
  invalidateDetailRequest()
  caseFormOpen.value = false
  editingCase.value = null
  draftRequest.value = null
  initialScenarioSteps.value = null
}

async function openEdit(item: CaseSummaryItem) {
  if (!canModify.value) return
  draftRequest.value = null
  const sequence = ++detailSequence
  detailLoading.value = true
  try {
    const detail = await caseApi.get(item.id)
    if (sequence !== detailSequence) return
    editingCase.value = detail
    caseFormOpen.value = true
  } catch (error: unknown) {
    if (sequence === detailSequence) message.error(errorMessage(error, t('api_workbench.detail_failed')))
  } finally {
    if (sequence === detailSequence) detailLoading.value = false
  }
}


function openImport() {
  if (!canModify.value) {
    message.warning(t('api_workbench.readonly_title'))
    return
  }
  if (!selectedModuleId.value) {
    message.warning(t('api_workbench.select_module_first'))
    return
  }
  importDrawerOpen.value = true
}

function handleSaved() {
  invalidateDetailRequest()
  caseFormOpen.value = false
  draftRequest.value = null
  initialScenarioSteps.value = null
  importDrawerOpen.value = false
  const currentSelected = selectedCase.value
  void loadCases()
  if (currentSelected && currentSelected.case_type === 'api') {
    void selectRequest(currentSelected)
  }
}

function openRun(item: CaseSummaryItem) {
  if (!canModify.value || !item.is_ready_for_execution) return
  pendingRunCase.value = item
  runEnvironmentId.value = undefined
  runModalOpen.value = true
}

async function confirmRun() {
  if (!pendingRunCase.value) return
  runLoading.value = true
  try {
    const result = await caseApi.run(pendingRunCase.value.id, {
      env_id: runEnvironmentId.value,
    })
    runModalOpen.value = false
    message.success(t('api_workbench.run_started'))
    await loadCases()
    await router.push({ name: 'run-detail', params: { runId: String(result.id) } })
  } catch (error: unknown) {
    message.error(errorMessage(error, t('api_workbench.run_failed')))
  } finally {
    runLoading.value = false
  }
}

function openRunDetail(runId: number) {
  void router.push({ name: 'run-detail', params: { runId: String(runId) } })
}

const schemaDrawerOpen = ref(false)
const schemaEditorOpen = ref(false)
const editingSchemaId = ref<number | null>(null)
const savingSchema = ref(false)
const deletingSchemaId = ref<number | null>(null)
const schemaFormName = ref('')
const schemaFormDescription = ref('')
const schemaFormDefinition = ref('{\n  "type": "object",\n  "properties": {}\n}')

const schemaColumns = computed(() => [
  { title: t('common.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('common.description'), dataIndex: 'description', key: 'description', ellipsis: true },
  { title: t('common.actions'), key: 'actions', width: 140 },
])

function openSchemaManager() {
  schemaDrawerOpen.value = true
  void loadSchemaAndContractAssets()
}

function openSchemaEditor(asset: ApiSchemaAssetItem | null) {
  editingSchemaId.value = asset?.id ?? null
  schemaFormName.value = asset?.name || ''
  schemaFormDescription.value = asset?.description || ''
  schemaFormDefinition.value = asset
    ? JSON.stringify(asset.definition, null, 2)
    : '{\n  "type": "object",\n  "properties": {}\n}'
  schemaEditorOpen.value = true
}

async function handleSaveSchema() {
  if (!selectedProjectId.value) return
  const name = schemaFormName.value.trim()
  if (!name) {
    message.warning(t('api_workbench.schema_name_required'))
    return
  }
  let definition: Record<string, unknown>
  try {
    const parsed = JSON.parse(schemaFormDefinition.value)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('invalid')
    }
    definition = parsed as Record<string, unknown>
  } catch {
    message.error(t('api_workbench.schema_invalid_json'))
    return
  }
  savingSchema.value = true
  try {
    const payload = {
      name,
      description: schemaFormDescription.value.trim() || undefined,
      definition,
    }
    if (editingSchemaId.value) {
      await apiSchemaAssetApi.update(editingSchemaId.value, payload)
      message.success(t('api_workbench.schema_update_success'))
    } else {
      await apiSchemaAssetApi.create(selectedProjectId.value, payload)
      message.success(t('api_workbench.schema_create_success'))
    }
    schemaEditorOpen.value = false
    await loadSchemaAndContractAssets()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('api_workbench.schema_save_failed')))
  } finally {
    savingSchema.value = false
  }
}

async function handleDeleteSchema(id: number) {
  deletingSchemaId.value = id
  try {
    await apiSchemaAssetApi.delete(id)
    message.success(t('api_workbench.schema_delete_success'))
    await loadSchemaAndContractAssets()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('api_workbench.schema_delete_failed')))
  } finally {
    deletingSchemaId.value = null
  }
}

const requestFilesDrawerOpen = ref(false)
const requestFilesLoading = ref(false)
const requestFiles = ref<Array<{ object_name: string; filename: string; size: number; last_modified?: string | null }>>([])
const renameRequestFileOpen = ref(false)
const renamingRequestFile = ref(false)
const deletingRequestFileName = ref<string | null>(null)
const renameRequestFileForm = ref({ object_name: '', filename: '' })

const requestFileColumns = computed(() => [
  { title: t('web_assets.filename'), dataIndex: 'filename', key: 'filename', ellipsis: true },
  { title: t('performance.script_size'), key: 'size', width: 95 },
  { title: t('common.updated_at'), key: 'last_modified', width: 165 },
  { title: t('common.actions'), key: 'actions', width: 140 },
])

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 1024) return `${bytes || 0} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

async function loadRequestFiles() {
  if (!selectedProjectId.value) {
    requestFiles.value = []
    return
  }
  requestFilesLoading.value = true
  try {
    requestFiles.value = await caseApi.listRequestFiles(selectedProjectId.value)
  } catch (error: unknown) {
    requestFiles.value = []
    message.error(errorMessage(error, t('api_workbench.request_files_load_failed')))
  } finally {
    requestFilesLoading.value = false
  }
}

function openRequestFilesManager() {
  requestFilesDrawerOpen.value = true
  void loadRequestFiles()
}

function openRenameRequestFile(item: { object_name: string; filename: string }) {
  renameRequestFileForm.value = { object_name: item.object_name, filename: item.filename }
  renameRequestFileOpen.value = true
}

async function handleRenameRequestFile() {
  if (!selectedProjectId.value) return
  const filename = renameRequestFileForm.value.filename.trim()
  if (!filename) {
    message.warning(t('web_assets.filename_required'))
    return
  }
  renamingRequestFile.value = true
  try {
    await caseApi.renameRequestFile(selectedProjectId.value, {
      object_name: renameRequestFileForm.value.object_name,
      filename,
    })
    renameRequestFileOpen.value = false
    message.success(t('web_assets.rename_success'))
    await loadRequestFiles()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('web_assets.rename_failed')))
  } finally {
    renamingRequestFile.value = false
  }
}

async function handleDeleteRequestFile(objectName: string) {
  if (!selectedProjectId.value) return
  deletingRequestFileName.value = objectName
  try {
    await caseApi.deleteRequestFile(selectedProjectId.value, objectName)
    message.success(t('api_workbench.request_file_delete_success'))
    await loadRequestFiles()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('api_workbench.request_file_delete_failed')))
  } finally {
    deletingRequestFileName.value = null
  }
}

onMounted(() => {
  void loadProjects()
})
</script>

<style scoped>
.schema-drawer-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
.api-workbench {
  color: var(--c-text);
}

.api-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: 48px;
  padding: 0 16px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  margin-bottom: 14px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.toolbar-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-icon {
  font-size: 16px;
  color: var(--c-primary);
  background: var(--c-primary-soft);
  padding: 5px;
  border-radius: 6px;
}

.toolbar-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
}

.toolbar-sep {
  color: var(--c-text-tertiary);
  font-size: 13px;
}

.project-select-dropdown {
  width: 200px;
}

.toolbar-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--c-text-secondary);
  margin-left: 6px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-btn {
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.live-dot, .state-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--c-info); box-shadow: 0 0 8px var(--c-info-soft); }
.readonly-alert { margin-top: 16px; }
.project-empty { min-height: 320px; padding: 100px 0; }

.workspace-frame { display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 710px; overflow: hidden; border: 1px solid var(--c-border); border-radius: var(--radius-lg); background: var(--c-bg-elevated); box-shadow: var(--shadow-sm); }
.collections-pane { min-width: 0; display: flex; flex-direction: column; border-right: 1px solid var(--c-border); background: var(--c-bg-subtle); }
.collections-heading { display: flex; align-items: center; justify-content: space-between; padding: 17px 16px 12px; }
.collections-heading h2 { margin: 3px 0 0; color: var(--c-text); font-size: 15px; font-weight: 600; }
.collection-plus-btn { color: var(--c-text-secondary); border-radius: 6px; transition: color 0.15s ease, background-color 0.15s ease; }
.collection-plus-btn:hover { color: var(--c-primary); background: var(--c-bg-hover, rgba(0, 0, 0, 0.04)); }
.column-kicker { color: var(--c-text-tertiary); font-size: 11px; font-weight: 600; }
.collections-pane :deep(.module-tree) { padding: 0 12px; }
.collection-separator { display: flex; justify-content: space-between; padding: 15px 16px 8px; color: var(--c-text-secondary); font-size: 11px; font-weight: 600; }
.collection-filters { display: grid; gap: 8px; padding: 0 12px 12px; }
.collection-filters :deep(.ant-select) { width: 100%; }
.request-list { min-height: 220px; max-height: 48vh; flex: 1; overflow: auto; border-top: 1px solid var(--c-border-subtle); }
.request-list-empty { padding: 27px 18px; color: var(--c-text-tertiary); font-size: 12px; line-height: 1.6; }
.request-list-item { display: flex; align-items: center; width: 100%; gap: 9px; padding: 10px 13px; border: 0; border-bottom: 1px solid var(--c-border-subtle); background: transparent; text-align: left; cursor: pointer; color: var(--c-text); }
.request-list-item:hover, .request-list-item:focus-visible { background: var(--c-bg-muted); outline: none; }
.request-list-item.is-selected { background: var(--c-primary-soft); box-shadow: inset 3px 0 var(--c-primary); color: var(--c-primary); }
.request-list-method { width: 36px; flex-shrink: 0; color: var(--c-primary); font: 700 10px 'JetBrains Mono', Consolas, monospace; }
.request-list-method.method-graphql { color: #a87913; }.request-list-method.method-websocket { color: #208372; }.request-list-method.method-grpc { color: #7662bb; }
.request-list-text { min-width: 0; flex: 1; }
.request-list-text strong, .request-list-text small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.request-list-text strong { color: var(--c-text); font-size: 12px; font-weight: 600; }
.request-list-text small { margin-top: 3px; color: var(--c-text-tertiary); font: 10px 'JetBrains Mono', Consolas, monospace; }
.request-list-state { width: 6px; height: 6px; flex-shrink: 0; border-radius: 50%; background: var(--c-border-strong); }
.request-list-state.run-passed { background: var(--c-success); }.request-list-state.run-failed, .request-list-state.run-error { background: var(--c-error); }
.collection-actions { display: grid; gap: 7px; padding: 12px; border-top: 1px solid var(--c-border); background: var(--c-bg-subtle); }
.collection-actions :deep(.ant-btn) { margin: 0; text-align: left; }
.case-code { margin-top: 4px; color: var(--c-text-tertiary); font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.run-state { display: inline-flex; align-items: center; gap: 7px; color: var(--c-text-secondary); font-size: 12px; white-space: nowrap; }
.run-state .state-dot { width: 6px; height: 6px; background: var(--c-text-tertiary); box-shadow: none; }
.run-passed { color: var(--c-success); }.run-passed .state-dot { background: var(--c-success); }.run-failed, .run-error { color: var(--c-error); }.run-failed .state-dot, .run-error .state-dot { background: var(--c-error); }.run-running, .run-pending { color: var(--c-warning); }.run-running .state-dot, .run-pending .state-dot { background: var(--c-warning); }

.detail-headline { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.detail-headline h2 { margin: 4px 0 0; color: var(--c-text); font-size: 20px; font-weight: 600; }
.detail-actions { display: flex; gap: 8px; margin: 18px 0 24px; }
.detail-block { margin-top: 24px; padding-top: 18px; border-top: 1px solid var(--c-border); }
.detail-block-title { margin-bottom: 11px; color: var(--c-text-secondary); font-size: 12px; font-weight: 600; }
.request-snapshot { display: flex; align-items: center; gap: 11px; padding: 13px; border: 1px solid var(--c-border); border-radius: var(--radius-md); background: var(--c-bg-subtle); }
.request-method { color: var(--c-info); font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; }
.request-snapshot code { overflow: hidden; color: var(--c-text); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; font-family: 'JetBrains Mono', monospace; }
.request-meta { display: flex; flex-wrap: wrap; gap: 8px 15px; margin-top: 9px; color: var(--c-text-tertiary); font-size: 11px; }
.run-history-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-bottom: 1px solid var(--c-border-subtle); }
.run-time { margin-left: 10px; color: var(--c-text-tertiary); font-size: 11px; font-family: 'JetBrains Mono', monospace; }
.run-history-right { display: flex; align-items: center; gap: 7px; color: var(--c-text-secondary); font-size: 11px; }
.form-hint { margin-top: 6px; color: var(--c-text-tertiary); font-size: 12px; line-height: 1.5; }

@media (max-width: 960px) {
  .toolbar-status { display: none; }
  .workspace-frame { grid-template-columns: 235px minmax(0, 1fr); }
}

@media (max-width: 700px) {
  .api-toolbar { height: auto; min-height: 48px; flex-wrap: wrap; padding: 10px 12px; }
  .workspace-frame { display: block; }
  .collections-pane { border-right: 0; border-bottom: 1px solid #e4eaf0; }
  .request-list { max-height: 220px; }
}

@media (prefers-reduced-motion: reduce) {
  .request-list-item { scroll-behavior: auto; }
}
.separator-left-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.count-tag {
  padding: 1px 6px;
  font-size: 11px;
  background: var(--c-bg-muted);
  border-radius: 4px;
  color: var(--c-text-tertiary);
}

.workbench-mode-pill-container {
  padding: 14px 14px 4px;
}

.workbench-mode-pill {
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 3px;
  background: var(--c-bg-muted, #f1f5f9);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  gap: 4px;
}

.mode-pill-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  padding: 0 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--c-text-secondary, #64748b);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
}

.mode-pill-item:hover {
  color: var(--c-text, #1e293b);
}

.mode-pill-item.is-active {
  background: var(--c-bg-elevated, #fff);
  color: var(--c-text, #1e293b);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04);
}

.mode-pill-item.mode-pill-automation.is-active {
  background: var(--c-primary-soft);
  color: var(--c-primary);
  border: 1px solid var(--c-primary);
}

.mode-pill-icon {
  font-size: 13px;
}

.mode-pill-item.is-active .mode-pill-icon {
  color: var(--c-primary, #1677ff);
}

.automation-badge-indicator {
  font-size: 10px;
  font-weight: 600;
  color: var(--c-primary, #1677ff);
  background: var(--c-primary-soft, #e6f4ff);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--c-primary-soft, #bae0ff);
}

.batch-checkbox {
  margin-right: 6px;
}

.request-list-item.is-batch-checked {
  background: var(--c-primary-soft);
}

.workbench-automation-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border-top: 1px solid var(--c-border);
}

.automation-bar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}

.automation-selected-count {
  font-weight: 600;
  color: var(--c-primary);
}

.automation-bar-buttons {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.batch-run-cases-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 120px;
  overflow-y: auto;
  padding: 6px;
  background: var(--c-bg-subtle);
  border-radius: 6px;
  border: 1px solid var(--c-border);
}
.request-list-method.method-scenario {
  color: #722ed1;
  background: rgba(114, 46, 209, 0.1);
  font-weight: 600;
}

.saved-scenarios-section {
  border-bottom: 1px solid var(--c-border);
  padding-bottom: 8px;
  margin-bottom: 4px;
}

.scenario-saved-list {
  max-height: 180px;
  overflow-y: auto;
  padding: 0 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.scenario-saved-empty {
  padding: 10px 8px;
  font-size: 11.5px;
  color: var(--c-text-tertiary);
  text-align: center;
  background: var(--c-bg-subtle);
  border-radius: 6px;
}

.scenario-del-btn {
  border: none;
  background: transparent;
  color: var(--c-text-tertiary);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 4px;
}
.scenario-del-btn:hover {
  color: var(--c-error);
  background: var(--c-error-soft);
}
</style>
