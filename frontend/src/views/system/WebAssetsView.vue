<template>
  <div class="web-assets-page">
    <div class="page-header">
      <div>
        <h2>{{ t('web_assets.title') }}</h2>
        <div class="subtitle">{{ t('web_assets.subtitle') }}</div>
      </div>
      <a-space>
        <a-select v-model:value="selectedProjectId" :options="projectOptions" :placeholder="t('web_assets.select_project')" style="width: 220px" @change="loadAll" />
        <a-button :loading="loading" @click="loadAll">{{ t('common.refresh') }}</a-button>
      </a-space>
    </div>

    <a-alert v-if="!selectedProjectId" type="info" show-icon :message="t('web_assets.select_project_hint')" />
    <a-tabs v-else v-model:active-key="activeTab">
      <a-tab-pane key="elements" :tab="t('web_assets.elements_tab')">
        <div class="toolbar">
          <a-button type="primary" @click="openElementCreate">{{ t('web_assets.new_element') }}</a-button>
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
                <a-button v-if="record.last_failed_at" type="link" size="small" @click="openRepair(asElement(record))">{{ t('web_assets.repair') }}</a-button>
                <a-button type="link" size="small" @click="openElementEdit(asElement(record))">{{ t('common.edit') }}</a-button>
                <a-popconfirm :title="t('common.confirm_delete')" @confirm="deleteElement(record.id)">
                  <a-button type="link" danger size="small">{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-tab-pane>
      <a-tab-pane key="page_objects" :tab="t('web_assets.page_objects_tab')">
        <div class="toolbar">
          <a-button type="primary" @click="openPageObjectCreate">{{ t('web_assets.new_page_object') }}</a-button>
        </div>
        <a-table :data-source="pageObjects" :columns="pageObjectColumns" :loading="loading" row-key="id" :pagination="{ pageSize: 10 }">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'counts'">
              {{ t('web_assets.page_object_counts', { elements: record.element_refs?.length || 0, actions: record.actions?.length || 0 }) }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-space>
                <a-button type="link" size="small" @click="openPageObjectEdit(asPageObject(record))">{{ t('common.edit') }}</a-button>
                <a-popconfirm :title="t('common.confirm_delete')" @confirm="deletePageObject(record.id)">
                  <a-button type="link" danger size="small">{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-tab-pane>
      <a-tab-pane key="visual_baselines" :tab="t('web_assets.visual_baselines_tab')">
        <div class="toolbar">
          <a-button type="primary" @click="openVisualBaselineCreate">{{ t('web_assets.new_visual_baseline') }}</a-button>
        </div>
        <a-table :data-source="visualBaselines" :columns="visualBaselineColumns" :loading="loading" row-key="id" :pagination="{ pageSize: 10 }">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'size'">{{ record.width || '-' }} × {{ record.height || '-' }}</template>
            <template v-else-if="column.key === 'actions'">
              <a-popconfirm :title="t('common.confirm_delete')" @confirm="deleteVisualBaseline(record.id)">
                <a-button type="link" danger size="small">{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
      </a-tab-pane>
    </a-tabs>

    <a-modal v-model:open="elementModalOpen" :title="editingElement ? t('web_assets.edit_element') : t('web_assets.new_element')" :confirm-loading="saving" @ok="saveElement">
      <a-form layout="vertical">
        <a-form-item :label="t('web_assets.name')" required><a-input v-model:value="elementForm.name" /></a-form-item>
        <a-form-item :label="t('web_assets.page_url')"><a-input v-model:value="elementForm.page_url" /></a-form-item>
        <a-form-item :label="t('web_assets.locator')" required><a-textarea v-model:value="elementForm.locatorText" class="mono" :rows="4" placeholder="{&quot;strategy&quot;:&quot;role&quot;,&quot;value&quot;:&quot;button&quot;}" /></a-form-item>
        <a-form-item :label="t('web_assets.fallback_locators')"><a-textarea v-model:value="elementForm.fallbackText" class="mono" :rows="3" placeholder="[]" /></a-form-item>
        <a-form-item :label="t('common.description')"><a-textarea v-model:value="elementForm.description" :rows="2" /></a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="pageObjectModalOpen" :title="editingPageObject ? t('web_assets.edit_page_object') : t('web_assets.new_page_object')" :confirm-loading="saving" @ok="savePageObject">
      <a-form layout="vertical">
        <a-form-item :label="webAssetsLabel('name')" required><a-input v-model:value="pageObjectForm.name" /></a-form-item>
        <a-form-item :label="t('web_assets.url_pattern')"><a-input v-model:value="pageObjectForm.url_pattern" /></a-form-item>
        <a-form-item :label="t('web_assets.element_refs')"><a-textarea v-model:value="pageObjectForm.elementRefsText" class="mono" :rows="4" placeholder="[{&quot;asset_id&quot;:1,&quot;alias&quot;:&quot;submit&quot;}]" /></a-form-item>
        <a-form-item :label="t('web_assets.actions')"><a-textarea v-model:value="pageObjectForm.actionsText" class="mono" :rows="4" placeholder="[{&quot;name&quot;:&quot;submit&quot;,&quot;step&quot;:&quot;click&quot;}]" /></a-form-item>
        <a-form-item :label="t('common.description')"><a-textarea v-model:value="pageObjectForm.description" :rows="2" /></a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="visualBaselineModalOpen" :title="t('web_assets.new_visual_baseline')" :confirm-loading="saving" @ok="saveVisualBaseline">
      <a-form layout="vertical">
        <a-form-item :label="t('web_assets.name')" required><a-input v-model:value="visualBaselineForm.name" /></a-form-item>
        <a-form-item :label="t('web_assets.page_url')"><a-input v-model:value="visualBaselineForm.page_url" /></a-form-item>
        <a-form-item :label="t('web_assets.visual_threshold')"><a-input-number v-model:value="visualBaselineForm.threshold" :min="0" :max="1" :step="0.001" /></a-form-item>
        <a-form-item :label="t('web_assets.pixel_threshold')"><a-input-number v-model:value="visualBaselineForm.pixel_threshold" :min="0" :max="255" /></a-form-item>
        <a-form-item :label="t('web_assets.ignore_regions')"><a-textarea v-model:value="visualBaselineForm.ignoreText" class="mono" :rows="3" placeholder="[]" /></a-form-item>
        <a-upload :before-upload="selectVisualBaselineFile" :show-upload-list="true" :max-count="1" accept=".png">
          <a-button>{{ t('web_assets.choose_visual_baseline') }}</a-button>
        </a-upload>
      </a-form>
    </a-modal>

    <a-modal v-model:open="repairModalOpen" :title="t('web_assets.repair_title')" :confirm-loading="repairLoading" :ok-button-props="{ disabled: selectedRepairIndex == null }" @ok="applyRepair">
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
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { projectApi, webAssetsApi, webVisualApi, type ProjectItem, type WebElementAssetItem, type WebLocatorRepairCandidate, type WebPageObjectItem, type WebVisualBaselineItem } from '@/api'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const activeTab = ref('elements')
const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | undefined>()
const elements = ref<WebElementAssetItem[]>([])
const pageObjects = ref<WebPageObjectItem[]>([])
const visualBaselines = ref<WebVisualBaselineItem[]>([])
const editingElement = ref<WebElementAssetItem | null>(null)
const editingPageObject = ref<WebPageObjectItem | null>(null)
const elementModalOpen = ref(false)
const pageObjectModalOpen = ref(false)
const visualBaselineModalOpen = ref(false)
const visualBaselineFile = ref<File | null>(null)
const repairModalOpen = ref(false)
const repairLoading = ref(false)
const repairAsset = ref<WebElementAssetItem | null>(null)
const repairCandidates = ref<WebLocatorRepairCandidate[]>([])
const selectedRepairIndex = ref<number | null>(null)

const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const elementColumns = computed(() => [
  { title: t('web_assets.name'), key: 'name', dataIndex: 'name' },
  { title: t('web_assets.page_url'), key: 'page_url', dataIndex: 'page_url', ellipsis: true },
  { title: t('web_assets.locator'), key: 'locator' },
  { title: t('web_assets.version'), key: 'version', dataIndex: 'version', width: 80 },
  { title: t('web_assets.status'), key: 'status', width: 100 },
  { title: t('common.actions'), key: 'actions', width: 120 },
])
const pageObjectColumns = computed(() => [
  { title: t('web_assets.name'), key: 'name', dataIndex: 'name' },
  { title: t('web_assets.url_pattern'), key: 'url_pattern', dataIndex: 'url_pattern', ellipsis: true },
  { title: t('web_assets.counts'), key: 'counts', width: 160 },
  { title: t('web_assets.version'), key: 'version', dataIndex: 'version', width: 80 },
  { title: t('common.actions'), key: 'actions', width: 120 },
])
const visualBaselineColumns = computed(() => [
  { title: t('web_assets.name'), key: 'name', dataIndex: 'name' },
  { title: t('web_assets.page_url'), key: 'page_url', dataIndex: 'page_url', ellipsis: true },
  { title: t('web_assets.size'), key: 'size', width: 120 },
  { title: t('web_assets.visual_threshold'), key: 'threshold', dataIndex: 'threshold', width: 100 },
  { title: t('web_assets.version'), key: 'version', dataIndex: 'version', width: 80 },
  { title: t('common.actions'), key: 'actions', width: 100 },
])

const elementForm = ref({ name: '', page_url: '', locatorText: '{}', fallbackText: '[]', description: '' })
const pageObjectForm = ref({ name: '', url_pattern: '', elementRefsText: '[]', actionsText: '[]', description: '' })
const visualBaselineForm = ref({ name: '', page_url: '', threshold: 0.01, pixel_threshold: 10, ignoreText: '[]' })

const asElement = (record: unknown) => record as WebElementAssetItem
const asPageObject = (record: unknown) => record as WebPageObjectItem

function webAssetsLabel(key: 'name') {
  return t(`web_assets.${key}`)
}

function locatorLabel(locator: Record<string, unknown>) {
  return `${String(locator.strategy || 'locator')}: ${String(locator.value || '')}`
}

function parseJson<T>(text: string, label: string): T | null {
  try {
    return JSON.parse(text) as T
  } catch {
    message.warning(t('web_assets.invalid_json', { value: label }))
    return null
  }
}

async function loadAll() {
  if (!selectedProjectId.value) return
  loading.value = true
  try {
    const [elementItems, pageItems] = await Promise.all([
      webAssetsApi.listElements(selectedProjectId.value),
      webAssetsApi.listPageObjects(selectedProjectId.value),
    ])
    visualBaselines.value = await webVisualApi.listBaselines(selectedProjectId.value)
    elements.value = elementItems
    pageObjects.value = pageItems
  } catch {
    message.error(t('web_assets.load_failed'))
  } finally {
    loading.value = false
  }
}

function openVisualBaselineCreate() {
  visualBaselineForm.value = { name: '', page_url: '', threshold: 0.01, pixel_threshold: 10, ignoreText: '[]' }
  visualBaselineFile.value = null
  visualBaselineModalOpen.value = true
}

function selectVisualBaselineFile(file: File) {
  visualBaselineFile.value = file
  return false
}

async function saveVisualBaseline() {
  if (!selectedProjectId.value || !visualBaselineForm.value.name.trim() || !visualBaselineFile.value) return
  const ignoreRegions = parseJson<Array<Record<string, unknown>>>(visualBaselineForm.value.ignoreText, t('web_assets.ignore_regions'))
  if (!ignoreRegions || !Array.isArray(ignoreRegions)) return
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
    visualBaselineModalOpen.value = false
    await loadAll()
  } catch {
    message.error(t('web_assets.save_failed'))
  } finally {
    saving.value = false
  }
}

async function deleteVisualBaseline(id: number) {
  try {
    await webVisualApi.deleteBaseline(id)
    await loadAll()
  } catch {
    message.error(t('web_assets.delete_failed'))
  }
}

function openElementCreate() {
  editingElement.value = null
  elementForm.value = { name: '', page_url: '', locatorText: '{}', fallbackText: '[]', description: '' }
  elementModalOpen.value = true
}

function openElementEdit(item: WebElementAssetItem) {
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
  if (!selectedProjectId.value || !elementForm.value.name.trim()) return
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
      description: elementForm.value.description.trim() || undefined,
    }
    if (editingElement.value) await webAssetsApi.updateElement(editingElement.value.id, body)
    else await webAssetsApi.createElement(selectedProjectId.value, body)
    elementModalOpen.value = false
    await loadAll()
  } catch {
    message.error(t('web_assets.save_failed'))
  } finally {
    saving.value = false
  }
}

async function deleteElement(id: number) {
  try {
    await webAssetsApi.deleteElement(id)
    await loadAll()
  } catch {
    message.error(t('web_assets.delete_failed'))
  }
}

async function openRepair(item: WebElementAssetItem) {
  repairAsset.value = item
  repairCandidates.value = []
  selectedRepairIndex.value = null
  repairModalOpen.value = true
  repairLoading.value = true
  try {
    const result = await webAssetsApi.previewElementRepair(item.id)
    repairCandidates.value = result.candidates
    selectedRepairIndex.value = result.candidates.length ? 0 : null
  } catch {
    message.error(t('web_assets.repair_failed'))
  } finally {
    repairLoading.value = false
  }
}

async function applyRepair() {
  if (!repairAsset.value || selectedRepairIndex.value == null) return
  const candidate = repairCandidates.value[selectedRepairIndex.value]
  if (!candidate) return
  repairLoading.value = true
  try {
    await webAssetsApi.updateElement(repairAsset.value.id, {
      locator: candidate.locator,
      fallback_locators: repairAsset.value.fallback_locators,
    })
    repairModalOpen.value = false
    await loadAll()
  } catch {
    message.error(t('web_assets.repair_failed'))
  } finally {
    repairLoading.value = false
  }
}

function openPageObjectCreate() {
  editingPageObject.value = null
  pageObjectForm.value = { name: '', url_pattern: '', elementRefsText: '[]', actionsText: '[]', description: '' }
  pageObjectModalOpen.value = true
}

function openPageObjectEdit(item: WebPageObjectItem) {
  editingPageObject.value = item
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
  if (!selectedProjectId.value || !pageObjectForm.value.name.trim()) return
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
      description: pageObjectForm.value.description.trim() || undefined,
    }
    if (editingPageObject.value) await webAssetsApi.updatePageObject(editingPageObject.value.id, body)
    else await webAssetsApi.createPageObject(selectedProjectId.value, body)
    pageObjectModalOpen.value = false
    await loadAll()
  } catch {
    message.error(t('web_assets.save_failed'))
  } finally {
    saving.value = false
  }
}

async function deletePageObject(id: number) {
  try {
    await webAssetsApi.deletePageObject(id)
    await loadAll()
  } catch {
    message.error(t('web_assets.delete_failed'))
  }
}

onMounted(async () => {
  try {
    projects.value = await projectApi.list()
    selectedProjectId.value = projects.value[0]?.id
    await loadAll()
  } catch {
    message.error(t('web_assets.load_failed'))
  }
})
</script>

<style scoped>
.page-header, .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.page-header { margin-bottom: 18px; }
.page-header h2 { margin: 0; }
.subtitle { color: var(--c-text-secondary); margin-top: 4px; }
.toolbar { margin-bottom: 12px; }
.mono { font-family: var(--font-mono, monospace); }
</style>
