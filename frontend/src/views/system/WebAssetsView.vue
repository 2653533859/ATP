<template>
  <div class="web-assets-page">
    <div class="page-header">
      <div>
        <h2>{{ t('web_assets.title') }}</h2>
      </div>
      <a-space>
        <a-select v-model:value="selectedProjectId" :options="projectOptions" :placeholder="t('web_assets.select_project')" style="width: 220px" @change="handleProjectChange" />
        <a-button :loading="loading" @click="loadAll">{{ t('common.refresh') }}</a-button>
      </a-space>
    </div>

    <a-alert v-if="!selectedProjectId" type="info" show-icon :message="t('web_assets.select_project_hint')" />
    <template v-else>
      <a-alert
        v-if="!canModify"
        type="info"
        show-icon
        :message="t('ui_workbench.readonly_title')"
        :description="t('ui_workbench.readonly_description')"
        style="margin-bottom: 12px"
      />
      <a-tabs v-model:active-key="activeTab">
        <a-tab-pane key="elements" :tab="t('web_assets.elements_tab')">
          <div class="toolbar">
            <a-space>
              <a-button type="primary" :disabled="!canModify" @click="openRecorder('elements')">{{ t('web_assets.record_elements') }}</a-button>
              <a-button :disabled="!canModify" @click="openElementCreate">{{ t('web_assets.new_element') }}</a-button>
            </a-space>
            <span class="toolbar-hint">{{ t('web_assets.record_elements_hint') }}</span>
          </div>
          <a-table :data-source="elements" :columns="elementColumns" :loading="loading" row-key="id" :pagination="{ pageSize: 10 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'locator'">
                <span class="mono">{{ locatorLabel(record.locator) }}</span>
                <a-tag v-if="record.fallback_locators?.length" color="blue">+{{ record.fallback_locators.length }}</a-tag>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.last_failed_at ? 'orange' : 'green'">{{ record.last_failed_at ? t('web_assets.has_failure') : t('web_assets.healthy') }}</a-tag>
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button v-if="record.last_failed_at" type="link" size="small" :disabled="!canModify" @click="openRepair(asElement(record))">{{ t('web_assets.repair') }}</a-button>
                  <a-button type="link" size="small" :disabled="!canModify" @click="openElementEdit(asElement(record))">{{ t('common.edit') }}</a-button>
                  <a-popconfirm :title="t('common.confirm_delete')" :disabled="!canModify" @confirm="deleteElement(record.id)">
                    <a-button type="link" danger size="small" :disabled="!canModify">{{ t('common.delete') }}</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="page_objects" :tab="t('web_assets.page_objects_tab')">
          <div class="toolbar">
            <a-space>
              <a-button type="primary" :disabled="!canModify" @click="openRecorder('page_object')">{{ t('web_assets.record_page_object') }}</a-button>
              <a-button :disabled="!canModify" @click="openPageObjectCreate">{{ t('web_assets.new_page_object') }}</a-button>
            </a-space>
            <span class="toolbar-hint">{{ t('web_assets.record_page_object_hint') }}</span>
          </div>
          <a-table :data-source="pageObjects" :columns="pageObjectColumns" :loading="loading" row-key="id" :pagination="{ pageSize: 10 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'counts'">
                {{ t('web_assets.page_object_counts', { elements: record.element_refs?.length || 0, actions: record.actions?.length || 0 }) }}
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button type="link" size="small" :disabled="!canModify" @click="openPageObjectEdit(asPageObject(record))">{{ t('common.edit') }}</a-button>
                  <a-popconfirm :title="t('common.confirm_delete')" :disabled="!canModify" @confirm="deletePageObject(record.id)">
                    <a-button type="link" danger size="small" :disabled="!canModify">{{ t('common.delete') }}</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="visual_baselines" :tab="t('web_assets.visual_baselines_tab')">
          <div class="toolbar">
            <a-space>
              <a-button type="primary" :disabled="!canModify" @click="openRecorder('visual_baseline')">{{ t('web_assets.capture_visual_baseline') }}</a-button>
              <a-button :disabled="!canModify" @click="openVisualBaselineCreate">{{ t('web_assets.new_visual_baseline') }}</a-button>
            </a-space>
            <span class="toolbar-hint">{{ t('web_assets.capture_visual_baseline_hint') }}</span>
          </div>
          <a-table :data-source="visualBaselines" :columns="visualBaselineColumns" :loading="loading" row-key="id" :pagination="{ pageSize: 10 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'preview'">
                <a-image
                  v-if="record.object_name"
                  :src="visualMediaUrl(record.object_name)"
                  :width="64"
                  :preview="{ src: visualMediaUrl(record.object_name) }"
                />
                <span v-else>-</span>
              </template>
              <template v-else-if="column.key === 'size'">{{ record.width || '-' }} × {{ record.height || '-' }}</template>
              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button type="link" size="small" :disabled="!canModify" @click="openVisualBaselineEdit(asVisualBaseline(record))">{{ t('common.edit') }}</a-button>
                  <a-popconfirm :title="t('common.confirm_delete')" :disabled="!canModify" @confirm="deleteVisualBaseline(record.id)">
                    <a-button type="link" danger size="small" :disabled="!canModify">{{ t('common.delete') }}</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="storage_states" :tab="t('web_assets.storage_states_tab')">
          <a-table :data-source="storageStates" :columns="storageStateColumns" :loading="loading" row-key="name" :pagination="{ pageSize: 10 }" :locale="{ emptyText: t('web_assets.empty_storage_states') }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'size'">{{ formatBytes(record.size) }}</template>
              <template v-else-if="column.key === 'updated_at'">{{ record.updated_at ? formatTime(record.updated_at) : '-' }}</template>
              <template v-else-if="column.key === 'actions'">
                <a-popconfirm :title="t('common.confirm_delete')" :disabled="!canModify" @confirm="deleteStorageState(record.name)">
                  <a-button type="link" danger size="small" :disabled="!canModify">{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="uploaded_files" :tab="t('web_assets.uploaded_files_tab')">
          <a-table :data-source="uploadedFiles" :columns="uploadedFileColumns" :loading="loading" row-key="object_name" :pagination="{ pageSize: 10 }" :locale="{ emptyText: t('web_assets.empty_uploaded_files') }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'size'">{{ formatBytes(record.size) }}</template>
              <template v-else-if="column.key === 'last_modified'">{{ record.last_modified ? formatTime(record.last_modified) : '-' }}</template>
              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button type="link" size="small" :disabled="!canModify" @click="openRenameFileModal(record as { object_name: string; filename: string })">{{ t('web_assets.rename') }}</a-button>
                  <a-popconfirm :title="t('common.confirm_delete')" :disabled="!canModify" @confirm="deleteUploadedFile(record.object_name)">
                    <a-button type="link" danger size="small" :disabled="!canModify">{{ t('common.delete') }}</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </template>

    <a-modal
      v-model:open="renameFileModalOpen"
      :title="t('web_assets.rename_file_title')"
      :confirm-loading="saving"
      @ok="handleRenameFile"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('web_assets.filename')" required>
          <a-input v-model:value="renameFileForm.filename" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="elementModalOpen"
      :title="editingElement ? t('web_assets.edit_element') : t('web_assets.new_element')"
      :confirm-loading="saving"
      :mask-closable="false"
      width="680px"
      @ok="saveElement"
      @cancel="resetElementModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('web_assets.name')" required><a-input v-model:value="elementForm.name" /></a-form-item>
        <a-form-item :label="t('web_assets.page_url')"><a-input v-model:value="elementForm.page_url" /></a-form-item>
        <a-form-item :label="t('web_assets.locator')" required>
          <WebAssetFieldEditor
            v-model:value="elementForm.locatorText"
            kind="locator"
            :rows="4"
            placeholder='{"strategy":"role","value":"button"}'
          />
        </a-form-item>
        <a-form-item :label="t('web_assets.fallback_locators')">
          <WebAssetFieldEditor
            v-model:value="elementForm.fallbackText"
            kind="fallbacks"
            :rows="3"
            placeholder="[]"
          />
        </a-form-item>
        <a-form-item :label="t('common.description')"><a-textarea v-model:value="elementForm.description" :rows="2" /></a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="pageObjectModalOpen"
      :title="editingPageObject ? t('web_assets.edit_page_object') : t('web_assets.new_page_object')"
      :confirm-loading="saving"
      :mask-closable="false"
      width="720px"
      @ok="savePageObject"
      @cancel="resetPageObjectModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="webAssetsLabel('name')" required><a-input v-model:value="pageObjectForm.name" /></a-form-item>
        <a-form-item :label="t('web_assets.url_pattern')"><a-input v-model:value="pageObjectForm.url_pattern" /></a-form-item>
        <a-form-item :label="t('web_assets.element_refs')">
          <WebAssetFieldEditor
            v-model:value="pageObjectForm.elementRefsText"
            kind="element_refs"
            :elements="elements"
            :rows="4"
            placeholder='[{"asset_id":1,"alias":"submit"}]'
          />
        </a-form-item>
        <a-form-item :label="t('web_assets.actions')">
          <WebAssetFieldEditor
            v-model:value="pageObjectForm.actionsText"
            kind="actions"
            :element-refs-text="pageObjectForm.elementRefsText"
            :rows="4"
            placeholder='[{"name":"submit","step":"click"}]'
          />
        </a-form-item>
        <a-form-item :label="t('common.description')"><a-textarea v-model:value="pageObjectForm.description" :rows="2" /></a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="visualBaselineModalOpen"
      :title="editingVisualBaseline ? t('web_assets.edit_visual_baseline') : (visualBaselineFromRecorder ? t('web_assets.capture_baseline_title') : t('web_assets.new_visual_baseline'))"
      :confirm-loading="saving"
      :mask-closable="false"
      width="640px"
      @ok="saveVisualBaseline"
      @cancel="resetVisualBaselineModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('web_assets.name')" required><a-input v-model:value="visualBaselineForm.name" :disabled="Boolean(editingVisualBaseline)" /></a-form-item>
        <a-form-item :label="t('web_assets.page_url')"><a-input v-model:value="visualBaselineForm.page_url" :disabled="Boolean(editingVisualBaseline)" /></a-form-item>
        <a-form-item :label="t('web_assets.visual_threshold')"><a-input-number v-model:value="visualBaselineForm.threshold" :min="0" :max="1" :step="0.001" /></a-form-item>
        <a-form-item :label="t('web_assets.pixel_threshold')"><a-input-number v-model:value="visualBaselineForm.pixel_threshold" :min="0" :max="255" /></a-form-item>
        <a-form-item :label="t('web_assets.ignore_regions')">
          <WebAssetFieldEditor
            v-model:value="visualBaselineForm.ignoreText"
            kind="ignore_regions"
            :rows="3"
            placeholder="[]"
          />
        </a-form-item>
        <a-upload
          v-if="!editingVisualBaseline"
          :file-list="visualBaselineFileList"
          :before-upload="selectVisualBaselineFile"
          :show-upload-list="true"
          :max-count="1"
          accept=".png"
          @remove="clearVisualBaselineFile"
        >
          <a-button>{{ t('web_assets.choose_visual_baseline') }}</a-button>
        </a-upload>
        <a-alert v-if="visualBaselineFromRecorder && !editingVisualBaseline" type="info" show-icon :message="t('web_assets.capture_visual_baseline_hint')" style="margin-top: 12px" />
      </a-form>
    </a-modal>

    <WebRecorderModal
      :open="recorderOpen"
      :project-id="selectedProjectId"
      :show-capture="recorderMode === 'visual_baseline'"
      :auto-apply="recorderMode !== 'visual_baseline'"
      source="assets"
      @close="handleRecorderClose"
      @recorded="handleRecorded"
      @captured="handleScreenshotCaptured"
    />

    <a-modal
      v-model:open="repairModalOpen"
      :title="t('web_assets.repair_title')"
      :confirm-loading="repairLoading"
      :mask-closable="false"
      :ok-button-props="{ disabled: selectedRepairIndex == null || !canModify }"
      @ok="applyRepair"
      @cancel="resetRepairModal"
    >
      <a-alert type="info" show-icon :message="t('web_assets.repair_hint')" />
      <a-radio-group v-model:value="selectedRepairIndex" style="width: 100%; margin-top: 12px">
        <a-space direction="vertical" style="width: 100%">
          <a-radio v-for="(candidate, index) in repairCandidates" :key="index" :value="index">
            <span class="mono">{{ JSON.stringify(candidate.locator) }}</span>
            <a-tag color="blue">{{ Math.round(candidate.confidence * 100) }}%</a-tag>
            <span class="repair-reason">{{ candidate.reason }}</span>
          </a-radio>
        </a-space>
      </a-radio-group>
      <a-empty v-if="!repairCandidates.length" :description="t('web_assets.no_repair_candidates')" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { projectApi, webAssetsApi, webFilesApi, webVisualApi, type ProjectItem, type WebElementAssetItem, type WebLocatorRepairCandidate, type WebPageObjectItem, type WebRecordingStep, type WebStorageStateItem, type WebVisualBaselineItem } from '@/api'
import { formatLocalDateTime } from '@/utils/dateTime'
import WebRecorderModal from '@/components/common/WebRecorderModal.vue'
import WebAssetFieldEditor from '@/components/common/WebAssetFieldEditor.vue'
import { useAuthStore } from '@/stores/auth'
import { extractApiError } from '@/utils/apiError'
import { canEditProjectByRole } from '@/utils/permissions'
import { projectIdFromQuery, selectAvailableProjectId } from '@/utils/projectContext'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const activeTab = ref('elements')
const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | undefined>()
const elements = ref<WebElementAssetItem[]>([])
const pageObjects = ref<WebPageObjectItem[]>([])
const visualBaselines = ref<WebVisualBaselineItem[]>([])
const storageStates = ref<WebStorageStateItem[]>([])
const uploadedFiles = ref<Array<{ object_name: string; filename: string; size: number; last_modified?: string | null }>>([])
const renameFileModalOpen = ref(false)
const renameFileForm = ref({ object_name: '', filename: '' })
const editingElement = ref<WebElementAssetItem | null>(null)
const editingPageObject = ref<WebPageObjectItem | null>(null)
const editingVisualBaseline = ref<WebVisualBaselineItem | null>(null)
const elementModalOpen = ref(false)
const pageObjectModalOpen = ref(false)
const visualBaselineModalOpen = ref(false)
const visualBaselineFile = ref<File | null>(null)
const visualBaselineFromRecorder = ref(false)
const recorderOpen = ref(false)
const recorderMode = ref<'elements' | 'page_object' | 'visual_baseline' | null>(null)
const pageObjectFromRecorder = ref(false)
const repairModalOpen = ref(false)
const repairLoading = ref(false)
const repairAsset = ref<WebElementAssetItem | null>(null)
const repairCandidates = ref<WebLocatorRepairCandidate[]>([])
const selectedRepairIndex = ref<number | null>(null)
let loadSeq = 0
let repairSeq = 0

const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const currentProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const canModify = computed(() => canEditProjectByRole(auth.user?.role, currentProject.value?.current_user_role))
const visualBaselineFileList = computed(() =>
  visualBaselineFile.value
    ? [{ uid: 'visual-baseline', name: visualBaselineFile.value.name, status: 'done' as const }]
    : [],
)
const elementColumns = computed(() => [
  { title: t('web_assets.name'), key: 'name', dataIndex: 'name' },
  { title: t('web_assets.page_url'), key: 'page_url', dataIndex: 'page_url', ellipsis: true },
  { title: t('web_assets.locator'), key: 'locator' },
  { title: t('web_assets.version'), key: 'version', dataIndex: 'version', width: 80 },
  { title: t('web_assets.status'), key: 'status', width: 100 },
  { title: t('common.actions'), key: 'actions', width: 150 },
])
const pageObjectColumns = computed(() => [
  { title: t('web_assets.name'), key: 'name', dataIndex: 'name' },
  { title: t('web_assets.url_pattern'), key: 'url_pattern', dataIndex: 'url_pattern', ellipsis: true },
  { title: t('web_assets.counts'), key: 'counts', width: 160 },
  { title: t('web_assets.version'), key: 'version', dataIndex: 'version', width: 80 },
  { title: t('common.actions'), key: 'actions', width: 120 },
])
const visualBaselineColumns = computed(() => [
  { title: t('web_assets.preview'), key: 'preview', width: 96 },
  { title: t('web_assets.name'), key: 'name', dataIndex: 'name' },
  { title: t('web_assets.page_url'), key: 'page_url', dataIndex: 'page_url', ellipsis: true },
  { title: t('web_assets.size'), key: 'size', width: 120 },
  { title: t('web_assets.visual_threshold'), key: 'threshold', dataIndex: 'threshold', width: 100 },
  { title: t('web_assets.version'), key: 'version', dataIndex: 'version', width: 80 },
  { title: t('common.actions'), key: 'actions', width: 130 },
])
const storageStateColumns = computed(() => [
  { title: t('web_assets.name'), key: 'name', dataIndex: 'name' },
  { title: t('web_assets.size'), key: 'size', width: 110 },
  { title: t('common.updated_at'), key: 'updated_at', width: 175 },
  { title: t('common.actions'), key: 'actions', width: 95 },
])
const uploadedFileColumns = computed(() => [
  { title: t('web_assets.filename'), key: 'filename', dataIndex: 'filename', ellipsis: true },
  { title: t('web_assets.object_key'), key: 'object_name', dataIndex: 'object_name', ellipsis: true },
  { title: t('web_assets.size'), key: 'size', width: 110 },
  { title: t('common.updated_at'), key: 'last_modified', width: 175 },
  { title: t('common.actions'), key: 'actions', width: 150 },
])

const elementForm = ref({ name: '', page_url: '', locatorText: '{}', fallbackText: '[]', description: '' })
const pageObjectForm = ref({ name: '', url_pattern: '', elementRefsText: '[]', actionsText: '[]', description: '' })
const visualBaselineForm = ref({ name: '', page_url: '', threshold: 0.01, pixel_threshold: 10, ignoreText: '[]' })

const asElement = (record: unknown) => record as WebElementAssetItem
const asPageObject = (record: unknown) => record as WebPageObjectItem
const asVisualBaseline = (record: unknown) => record as WebVisualBaselineItem

function webAssetsLabel(key: 'name') {
  return t(`web_assets.${key}`)
}

function visualMediaUrl(objectName: string) {
  return `/api/v1/storage/media/${objectName.replace(/^\/+/, '')}`
}

function locatorLabel(locator: Record<string, unknown>) {
  return `${String(locator.strategy || 'locator')}: ${String(locator.value || '')}`
}

function formatTime(value?: string | null) {
  return formatLocalDateTime(value)
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 1024) return `${bytes || 0} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function parseJson<T>(text: string, label: string): T | null {
  try {
    return JSON.parse(text) as T
  } catch {
    message.warning(t('web_assets.invalid_json', { value: label }))
    return null
  }
}

function clearAssets() {
  elements.value = []
  pageObjects.value = []
  visualBaselines.value = []
  storageStates.value = []
  uploadedFiles.value = []
}

async function handleProjectChange() {
  loadSeq += 1
  repairSeq += 1
  clearAssets()
  resetElementModal()
  resetPageObjectModal()
  resetVisualBaselineModal()
  resetRepairModal()
  await loadAll()
}

async function loadAll() {
  const projectId = selectedProjectId.value
  if (!projectId) {
    loadSeq += 1
    clearAssets()
    return
  }
  const seq = ++loadSeq
  loading.value = true
  try {
    const [elementItems, pageItems, baselineItems, storageItems, fileItems] = await Promise.all([
      webAssetsApi.listElements(projectId),
      webAssetsApi.listPageObjects(projectId),
      webVisualApi.listBaselines(projectId),
      webAssetsApi.listStorageStates ? webAssetsApi.listStorageStates(projectId).catch(() => []) : Promise.resolve([]),
      webFilesApi?.list ? webFilesApi.list(projectId).catch(() => []) : Promise.resolve([]),
    ])
    if (seq !== loadSeq || selectedProjectId.value !== projectId) return
    elements.value = elementItems
    pageObjects.value = pageItems
    visualBaselines.value = baselineItems
    storageStates.value = storageItems
    uploadedFiles.value = fileItems
  } catch (error: unknown) {
    if (seq !== loadSeq || selectedProjectId.value !== projectId) return
    message.error(extractApiError(error, t('web_assets.load_failed')))
  } finally {
    if (seq === loadSeq) {
      loading.value = false
    }
  }
}

function applyRequestedTab(value: unknown) {
  const requestedTab = Array.isArray(value) ? value[0] : value
  if (
    requestedTab === 'elements' ||
    requestedTab === 'page_objects' ||
    requestedTab === 'visual_baselines' ||
    requestedTab === 'storage_states' ||
    requestedTab === 'uploaded_files'
  ) {
    activeTab.value = requestedTab
  }
}

async function deleteStorageState(name: string) {
  if (!selectedProjectId.value || !canModify.value) return
  try {
    await webAssetsApi.deleteStorageState(selectedProjectId.value, name)
    message.success(t('web_assets.storage_state_deleted'))
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.delete_failed')))
  }
}

function openRenameFileModal(item: { object_name: string; filename: string }) {
  if (!canModify.value) return
  renameFileForm.value = { object_name: item.object_name, filename: item.filename }
  renameFileModalOpen.value = true
}

async function handleRenameFile() {
  if (!selectedProjectId.value || !canModify.value) return
  const filename = renameFileForm.value.filename.trim()
  if (!filename) {
    message.warning(t('web_assets.filename_required'))
    return
  }
  saving.value = true
  try {
    await webFilesApi.rename(selectedProjectId.value, {
      object_name: renameFileForm.value.object_name,
      filename,
    })
    renameFileModalOpen.value = false
    message.success(t('web_assets.rename_success'))
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.rename_failed')))
  } finally {
    saving.value = false
  }
}

async function deleteUploadedFile(objectName: string) {
  if (!selectedProjectId.value || !canModify.value) return
  try {
    await webFilesApi.delete(selectedProjectId.value, objectName)
    message.success(t('web_assets.file_deleted'))
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.delete_failed')))
  }
}

function resetVisualBaselineModal() {
  visualBaselineModalOpen.value = false
  editingVisualBaseline.value = null
  visualBaselineForm.value = { name: '', page_url: '', threshold: 0.01, pixel_threshold: 10, ignoreText: '[]' }
  visualBaselineFile.value = null
  visualBaselineFromRecorder.value = false
}

function openVisualBaselineCreate() {
  if (!canModify.value) return
  resetVisualBaselineModal()
  visualBaselineModalOpen.value = true
}

function openVisualBaselineEdit(item: WebVisualBaselineItem) {
  if (!canModify.value) return
  resetVisualBaselineModal()
  editingVisualBaseline.value = item
  visualBaselineForm.value = {
    name: item.name,
    page_url: item.page_url || '',
    threshold: item.threshold,
    pixel_threshold: item.pixel_threshold,
    ignoreText: JSON.stringify(item.ignore_regions || [], null, 2),
  }
  visualBaselineModalOpen.value = true
}

function selectVisualBaselineFile(file: File) {
  visualBaselineFile.value = file
  visualBaselineFromRecorder.value = false
  return false
}

function clearVisualBaselineFile() {
  visualBaselineFile.value = null
}

async function saveVisualBaseline() {
  if (!canModify.value || !selectedProjectId.value) return
  if (visualBaselineForm.value.threshold == null || visualBaselineForm.value.pixel_threshold == null) {
    message.warning(t('web_assets.save_failed'))
    return
  }
  const ignoreRegions = parseJson<Array<Record<string, unknown>>>(visualBaselineForm.value.ignoreText, t('web_assets.ignore_regions'))
  if (!ignoreRegions || !Array.isArray(ignoreRegions)) return
  if (editingVisualBaseline.value) {
    saving.value = true
    try {
      await webVisualApi.updateBaseline(editingVisualBaseline.value.id, {
        threshold: visualBaselineForm.value.threshold,
        pixel_threshold: visualBaselineForm.value.pixel_threshold,
        ignore_regions: ignoreRegions,
      })
      resetVisualBaselineModal()
      message.success(t('common.success'))
      await loadAll()
    } catch (error: unknown) {
      message.error(extractApiError(error, t('web_assets.save_failed')))
    } finally {
      saving.value = false
    }
    return
  }
  if (!visualBaselineForm.value.name.trim()) {
    message.warning(t('web_assets.name_required', t('web_assets.name')))
    return
  }
  if (!visualBaselineFile.value) {
    message.warning(t('web_assets.save_failed'))
    return
  }
  saving.value = true
  try {
    await webVisualApi.uploadBaseline(selectedProjectId.value, {
      name: visualBaselineForm.value.name.trim(),
      page_url: visualBaselineForm.value.page_url.trim() || undefined,
      threshold: visualBaselineForm.value.threshold,
      pixel_threshold: visualBaselineForm.value.pixel_threshold,
      ignore_regions: ignoreRegions,
      file: visualBaselineFile.value,
    })
    resetVisualBaselineModal()
    message.success(t('common.success'))
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.save_failed')))
  } finally {
    saving.value = false
  }
}

async function deleteVisualBaseline(id: number) {
  if (!canModify.value) return
  try {
    await webVisualApi.deleteBaseline(id)
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.delete_failed')))
  }
}

function nextGeneratedName(prefix: string, names: string[]) {
  let index = 1
  while (names.includes(`${prefix}_${index}`)) index += 1
  return `${prefix}_${index}`
}

function openRecorder(mode: 'elements' | 'page_object' | 'visual_baseline') {
  if (!selectedProjectId.value || !canModify.value) return
  recorderMode.value = mode
  recorderOpen.value = true
}

function handleRecorderClose() {
  recorderOpen.value = false
  recorderMode.value = null
}

function buildRecordedPageObject(steps: WebRecordingStep[], assetIds: number[]) {
  const aliases = new Map<number, string>()
  const elementRefs: Array<Record<string, unknown>> = []
  let aliasIndex = 1
  const ensureAlias = (assetId: number) => {
    const existing = aliases.get(assetId)
    if (existing) return existing
    const alias = `element_${aliasIndex++}`
    aliases.set(assetId, alias)
    elementRefs.push({ asset_id: assetId, alias })
    return alias
  }

  for (const assetId of assetIds) {
    if (Number.isInteger(assetId) && assetId > 0) ensureAlias(assetId)
  }

  const actions = steps
    .filter((step) => ['goto', 'click', 'fill', 'select', 'press'].includes(step.action))
    .map((step) => {
      const params = { ...step.params }
      const rawAssetId = Number(params.element_asset_id)
      delete params.element_asset_id
      const action: Record<string, unknown> = {
        name: step.name,
        step: step.action,
        params,
      }
      if (Number.isInteger(rawAssetId) && rawAssetId > 0) action.alias = ensureAlias(rawAssetId)
      return action
    })

  const lastGoto = [...steps].reverse().find((step) => step.action === 'goto')
  const url = String(lastGoto?.params.url || '').trim()
  return { elementRefs, actions, url }
}

async function handleRecorded(steps: WebRecordingStep[], assetIds: number[]) {
  if (recorderMode.value === 'elements') {
    await loadAll()
    message.success(t('web_assets.recorded_elements', { count: assetIds.length }))
    return
  }
  if (recorderMode.value !== 'page_object' || !canModify.value) return

  const generated = buildRecordedPageObject(steps, assetIds)
  if (!generated.actions.length) {
    message.warning(t('web_assets.no_recorded_steps'))
    return
  }
  editingPageObject.value = null
  pageObjectFromRecorder.value = true
  pageObjectForm.value = {
    name: nextGeneratedName(t('web_assets.recorded_page_object_prefix'), pageObjects.value.map((item) => item.name)),
    url_pattern: generated.url,
    elementRefsText: JSON.stringify(generated.elementRefs, null, 2),
    actionsText: JSON.stringify(generated.actions, null, 2),
    description: t('web_assets.recorded_page_object_description'),
  }
  pageObjectModalOpen.value = true
}

function handleScreenshotCaptured(file: File, pageUrl: string) {
  if (!canModify.value) return
  editingVisualBaseline.value = null
  visualBaselineFile.value = file
  visualBaselineFromRecorder.value = true
  visualBaselineForm.value = {
    name: nextGeneratedName(t('web_assets.recorded_visual_baseline_prefix'), visualBaselines.value.map((item) => item.name)),
    page_url: pageUrl,
    threshold: 0.01,
    pixel_threshold: 10,
    ignoreText: '[]',
  }
  visualBaselineModalOpen.value = true
}

function resetElementModal() {
  elementModalOpen.value = false
  editingElement.value = null
  elementForm.value = { name: '', page_url: '', locatorText: '{}', fallbackText: '[]', description: '' }
}

function openElementCreate() {
  if (!canModify.value) return
  resetElementModal()
  elementModalOpen.value = true
}

function openElementEdit(item: WebElementAssetItem) {
  if (!canModify.value) return
  editingElement.value = item
  elementForm.value = {
    name: item.name,
    page_url: item.page_url || '',
    locatorText: JSON.stringify(item.locator, null, 2),
    fallbackText: JSON.stringify(item.fallback_locators, null, 2),
    description: item.description || '',
  }
  elementModalOpen.value = true
}

async function saveElement() {
  if (!canModify.value || !selectedProjectId.value) return
  if (!elementForm.value.name.trim()) {
    message.warning(t('web_assets.name_required', t('web_assets.name')))
    return
  }
  const locator = parseJson<Record<string, unknown>>(elementForm.value.locatorText, t('web_assets.locator'))
  const fallback = parseJson<Array<Record<string, unknown>>>(elementForm.value.fallbackText, t('web_assets.fallback_locators'))
  if (!locator || !fallback || !Array.isArray(fallback)) return
  saving.value = true
  try {
    const body = {
      name: elementForm.value.name.trim(),
      page_url: elementForm.value.page_url.trim() || null,
      locator,
      fallback_locators: fallback,
      description: elementForm.value.description.trim() || null,
    }
    if (editingElement.value) await webAssetsApi.updateElement(editingElement.value.id, body)
    else await webAssetsApi.createElement(selectedProjectId.value, body)
    resetElementModal()
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.save_failed')))
  } finally {
    saving.value = false
  }
}

async function deleteElement(id: number) {
  if (!canModify.value) return
  try {
    await webAssetsApi.deleteElement(id)
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.delete_failed')))
  }
}

function resetRepairModal() {
  repairModalOpen.value = false
  repairLoading.value = false
  repairAsset.value = null
  repairCandidates.value = []
  selectedRepairIndex.value = null
}

async function openRepair(item: WebElementAssetItem) {
  if (!canModify.value) return
  const seq = ++repairSeq
  repairAsset.value = item
  repairCandidates.value = []
  selectedRepairIndex.value = null
  repairModalOpen.value = true
  repairLoading.value = true
  try {
    const result = await webAssetsApi.previewElementRepair(item.id)
    if (seq !== repairSeq || !repairModalOpen.value) return
    repairCandidates.value = result.candidates
    selectedRepairIndex.value = result.candidates.length ? 0 : null
  } catch (error: unknown) {
    if (seq !== repairSeq) return
    message.error(extractApiError(error, t('web_assets.repair_failed')))
  } finally {
    if (seq === repairSeq) {
      repairLoading.value = false
    }
  }
}

async function applyRepair() {
  if (!canModify.value || !repairAsset.value || selectedRepairIndex.value == null) return
  const candidate = repairCandidates.value[selectedRepairIndex.value]
  if (!candidate) return
  repairLoading.value = true
  try {
    await webAssetsApi.updateElement(repairAsset.value.id, {
      locator: candidate.locator,
      fallback_locators: repairAsset.value.fallback_locators,
    })
    resetRepairModal()
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.repair_failed')))
  } finally {
    repairLoading.value = false
  }
}

function resetPageObjectModal() {
  pageObjectModalOpen.value = false
  editingPageObject.value = null
  pageObjectFromRecorder.value = false
  pageObjectForm.value = { name: '', url_pattern: '', elementRefsText: '[]', actionsText: '[]', description: '' }
}

function openPageObjectCreate() {
  if (!canModify.value) return
  resetPageObjectModal()
  pageObjectModalOpen.value = true
}

function openPageObjectEdit(item: WebPageObjectItem) {
  if (!canModify.value) return
  editingPageObject.value = item
  pageObjectFromRecorder.value = false
  pageObjectForm.value = {
    name: item.name,
    url_pattern: item.url_pattern || '',
    elementRefsText: JSON.stringify(item.element_refs, null, 2),
    actionsText: JSON.stringify(item.actions, null, 2),
    description: item.description || '',
  }
  pageObjectModalOpen.value = true
}

async function savePageObject() {
  if (!canModify.value || !selectedProjectId.value) return
  if (!pageObjectForm.value.name.trim()) {
    message.warning(t('web_assets.name_required', t('web_assets.name')))
    return
  }
  const refs = parseJson<Array<Record<string, unknown>>>(pageObjectForm.value.elementRefsText, t('web_assets.element_refs'))
  const actions = parseJson<Array<Record<string, unknown>>>(pageObjectForm.value.actionsText, t('web_assets.actions'))
  if (!refs || !actions || !Array.isArray(refs) || !Array.isArray(actions)) return
  saving.value = true
  try {
    const body = {
      name: pageObjectForm.value.name.trim(),
      url_pattern: pageObjectForm.value.url_pattern.trim() || null,
      element_refs: refs,
      actions,
      description: pageObjectForm.value.description.trim() || null,
    }
    if (editingPageObject.value) await webAssetsApi.updatePageObject(editingPageObject.value.id, body)
    else await webAssetsApi.createPageObject(selectedProjectId.value, body)
    message.success(pageObjectFromRecorder.value ? t('web_assets.recorded_page_object') : t('common.success'))
    resetPageObjectModal()
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.save_failed')))
  } finally {
    saving.value = false
  }
}

async function deletePageObject(id: number) {
  if (!canModify.value) return
  try {
    await webAssetsApi.deletePageObject(id)
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.delete_failed')))
  }
}

onMounted(async () => {
  try {
    projects.value = await projectApi.list()
    selectedProjectId.value = selectAvailableProjectId(projectIdFromQuery(route.query.project_id), projects.value)
    applyRequestedTab(route.query.tab)
    await loadAll()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('web_assets.load_failed')))
  }
})

watch(() => route.query.tab, applyRequestedTab)
</script>

<style scoped>
.page-header, .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.page-header { margin-bottom: 18px; }
.page-header h2 { margin: 0; }
.subtitle { color: var(--c-text-secondary); margin-top: 4px; }
.toolbar { margin-bottom: 12px; }
.toolbar-hint { color: var(--c-text-secondary); font-size: 12px; text-align: right; }
.mono { font-family: var(--font-mono, monospace); }
</style>
