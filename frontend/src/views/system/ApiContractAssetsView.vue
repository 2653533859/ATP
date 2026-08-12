<template>
  <div class="contract-page">
    <section class="contract-hero">
      <div class="hero-copy">
        <div class="eyebrow">{{ t('api_contract_assets.eyebrow') }}</div>
        <h2>{{ t('api_contract_assets.title') }}</h2>
        <p>{{ t('api_contract_assets.subtitle') }}</p>
      </div>
      <div class="hero-actions">
        <a-select
          v-model:value="projectId"
          :options="projectOptions"
          :placeholder="t('api_contract_assets.select_project')"
          class="project-select"
          @change="loadAssets"
        />
        <a-button ghost :loading="loading" :disabled="!projectId" @click="loadAssets">
          {{ t('common.refresh') }}
        </a-button>
        <a-button type="primary" class="new-button" :disabled="!projectId" @click="openCreate">
          + {{ t('api_contract_assets.new_asset') }}
        </a-button>
      </div>
    </section>

    <a-alert
      v-if="!projectId"
      type="info"
      show-icon
      :message="t('api_contract_assets.select_project_hint')"
      class="page-notice"
    />

    <template v-else>
      <a-row :gutter="[16, 16]" class="summary-row">
        <a-col :xs="24" :sm="8">
          <div class="summary-card provider-summary">
            <span class="summary-label">{{ t('api_contract_assets.provider_assets') }}</span>
            <strong>{{ providerCount }}</strong>
            <span class="summary-foot">{{ t('api_contract_assets.provider_hint') }}</span>
          </div>
        </a-col>
        <a-col :xs="24" :sm="8">
          <div class="summary-card consumer-summary">
            <span class="summary-label">{{ t('api_contract_assets.consumer_assets') }}</span>
            <strong>{{ consumerCount }}</strong>
            <span class="summary-foot">{{ t('api_contract_assets.consumer_hint') }}</span>
          </div>
        </a-col>
        <a-col :xs="24" :sm="8">
          <div class="summary-card neutral-summary">
            <span class="summary-label">{{ t('api_contract_assets.latest_version') }}</span>
            <strong>v{{ latestVersion }}</strong>
            <span class="summary-foot">{{ t('api_contract_assets.version_hint') }}</span>
          </div>
        </a-col>
      </a-row>

      <a-row :gutter="[16, 16]" align="top">
        <a-col :xs="24" :xl="15">
          <a-card class="registry-card" :bordered="false">
            <template #title>
              <div class="card-heading">
                <div>
                  <span class="card-kicker">{{ t('api_contract_assets.registry_kicker') }}</span>
                  <strong>{{ t('api_contract_assets.registry_title') }}</strong>
                </div>
                <a-radio-group v-model:value="roleFilter" button-style="solid" size="small">
                  <a-radio-button value="all">{{ t('api_contract_assets.all_roles') }}</a-radio-button>
                  <a-radio-button value="provider">{{ t('api_contract_assets.provider') }}</a-radio-button>
                  <a-radio-button value="consumer">{{ t('api_contract_assets.consumer') }}</a-radio-button>
                </a-radio-group>
              </div>
            </template>
            <a-table
              :data-source="filteredAssets"
              :columns="assetColumns"
              :loading="loading"
              row-key="id"
              :pagination="{ pageSize: 8, showSizeChanger: false }"
              :locale="{ emptyText: t('api_contract_assets.empty') }"
              :scroll="{ x: 620 }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'name'">
                  <div class="asset-name-cell">
                    <strong>{{ asAsset(record).name }}</strong>
                    <span>{{ asAsset(record).description || t('api_contract_assets.no_description') }}</span>
                  </div>
                </template>
                <template v-else-if="column.key === 'role'">
                  <a-tag :color="asAsset(record).role === 'provider' ? 'cyan' : 'purple'">
                    {{ roleLabel(asAsset(record).role) }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'format'">
                  <span class="format-mark">{{ formatLabel(asAsset(record).format) }}</span>
                </template>
                <template v-else-if="column.key === 'actions'">
                  <a-space>
                    <a-button type="link" size="small" @click="openEdit(asAsset(record))">
                      {{ t('common.edit') }}
                    </a-button>
                    <a-popconfirm :title="t('api_contract_assets.delete_confirm')" @confirm="deleteAsset(asAsset(record).id)">
                      <a-button type="link" danger size="small">{{ t('common.delete') }}</a-button>
                    </a-popconfirm>
                  </a-space>
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>

        <a-col :xs="24" :xl="9">
          <a-card class="compare-card" :bordered="false">
            <template #title>
              <div class="compare-heading">
                <span class="delta-mark">Δ</span>
                <div>
                  <span class="card-kicker">{{ t('api_contract_assets.compare_kicker') }}</span>
                  <strong>{{ t('api_contract_assets.compare_title') }}</strong>
                </div>
              </div>
            </template>
            <div class="compare-flow">
              <div class="compare-side baseline-side">
                <span class="compare-step">01 · {{ t('api_contract_assets.baseline') }}</span>
                <a-select
                  v-model:value="baselineAssetId"
                  :options="assetOptions"
                  allow-clear
                  :placeholder="t('api_contract_assets.choose_baseline')"
                  style="width: 100%"
                />
              </div>
              <div class="compare-connector"><span>→</span></div>
              <div class="compare-side current-side">
                <span class="compare-step">02 · {{ t('api_contract_assets.current') }}</span>
                <a-select
                  v-model:value="currentAssetId"
                  :options="assetOptions"
                  allow-clear
                  :placeholder="t('api_contract_assets.choose_current')"
                  style="width: 100%"
                />
              </div>
            </div>
            <a-button
              type="primary"
              block
              :loading="comparing"
              :disabled="!baselineAssetId || !currentAssetId"
              class="compare-button"
              @click="compareAssets"
            >
              {{ t('api_contract_assets.compare_action') }}
            </a-button>

            <div v-if="comparison" class="comparison-result">
              <div class="compatibility-banner" :class="comparison.compatible ? 'compatible' : 'breaking'">
                <span class="compatibility-dot" />
                <div>
                  <strong>{{ comparison.compatible ? t('api_contract_assets.compatible') : t('api_contract_assets.breaking') }}</strong>
                  <span>{{ comparison.summary }}</span>
                </div>
              </div>
              <a-collapse v-if="comparison.breaking_changes.length || comparison.warnings.length" ghost>
                <a-collapse-panel v-if="comparison.breaking_changes.length" key="breaking" :header="t('api_contract_assets.breaking_changes', { count: comparison.breaking_changes.length })">
                  <ul class="change-list breaking-list">
                    <li v-for="change in comparison.breaking_changes" :key="`${change.location}:${change.message}`">
                      <code>{{ change.location }}</code>
                      <span>{{ change.message }}</span>
                    </li>
                  </ul>
                </a-collapse-panel>
                <a-collapse-panel v-if="comparison.warnings.length" key="warnings" :header="t('api_contract_assets.warnings', { count: comparison.warnings.length })">
                  <ul class="change-list warning-list">
                    <li v-for="change in comparison.warnings" :key="`${change.location}:${change.message}`">
                      <code>{{ change.location }}</code>
                      <span>{{ change.message }}</span>
                    </li>
                  </ul>
                </a-collapse-panel>
              </a-collapse>
              <div v-else class="no-diff">{{ t('api_contract_assets.no_changes') }}</div>
            </div>
            <div v-else class="compare-empty">
              <span class="empty-glyph">⌁</span>
              <strong>{{ t('api_contract_assets.compare_empty_title') }}</strong>
              <span>{{ t('api_contract_assets.compare_empty_hint') }}</span>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </template>

    <a-drawer v-model:open="editorOpen" :title="editing ? t('api_contract_assets.edit_title') : t('api_contract_assets.create_title')" :width="720">
      <a-alert
        type="info"
        show-icon
        :message="t('api_contract_assets.editor_hint')"
        :description="t('api_contract_assets.editor_description')"
        class="editor-notice"
      />
      <a-form layout="vertical">
        <a-form-item :label="t('api_contract_assets.name')" required>
          <a-input v-model:value="form.name" :placeholder="t('api_contract_assets.name_placeholder')" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('api_contract_assets.role')" required>
              <a-radio-group v-model:value="form.role" button-style="solid">
                <a-radio-button value="provider">{{ t('api_contract_assets.provider') }}</a-radio-button>
                <a-radio-button value="consumer">{{ t('api_contract_assets.consumer') }}</a-radio-button>
              </a-radio-group>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('api_contract_assets.format')" required>
              <a-select v-model:value="form.format" :options="formatOptions" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="t('api_contract_assets.description')">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t('api_contract_assets.definition')" required>
          <a-textarea v-model:value="form.definitionText" class="json-editor" :rows="18" :placeholder="t('api_contract_assets.definition_placeholder')" />
          <div v-if="definitionError" class="input-error">{{ definitionError }}</div>
          <div v-else class="form-hint">{{ t('api_contract_assets.definition_hint') }}</div>
        </a-form-item>
      </a-form>
      <template #footer>
        <div class="drawer-footer">
          <a-button @click="editorOpen = false">{{ t('common.cancel') }}</a-button>
          <a-button type="primary" :loading="saving" @click="saveAsset">{{ t('common.save') }}</a-button>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import {
  apiContractApi,
  apiContractAssetApi,
  projectApi,
  type ApiContractAssetItem,
  type ApiContractCompareResult,
  type ProjectItem,
} from '@/api'
import { projectIdFromQuery, selectAvailableProjectId } from '@/utils/projectContext'

const { t } = useI18n()
const route = useRoute()

const projects = ref<ProjectItem[]>([])
const projectId = ref<number | undefined>()
const assets = ref<ApiContractAssetItem[]>([])
const loading = ref(false)
const saving = ref(false)
const comparing = ref(false)
const editorOpen = ref(false)
const editing = ref<ApiContractAssetItem | null>(null)
const roleFilter = ref<'all' | 'provider' | 'consumer'>('all')
const baselineAssetId = ref<number | undefined>()
const currentAssetId = ref<number | undefined>()
const comparison = ref<ApiContractCompareResult | null>(null)
const definitionError = ref('')

type AssetRole = 'provider' | 'consumer'
type AssetFormat = 'openapi' | 'swagger' | 'json_schema'

const form = ref<{
  name: string
  role: AssetRole
  format: AssetFormat
  description: string
  definitionText: string
}>({ name: '', role: 'provider', format: 'openapi', description: '', definitionText: '{\n  "openapi": "3.0.0",\n  "paths": {}\n}' })

const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const providerCount = computed(() => assets.value.filter((asset) => asset.role === 'provider').length)
const consumerCount = computed(() => assets.value.filter((asset) => asset.role === 'consumer').length)
const latestVersion = computed(() => assets.value.reduce((max, asset) => Math.max(max, asset.version), 0))
const filteredAssets = computed(() => roleFilter.value === 'all' ? assets.value : assets.value.filter((asset) => asset.role === roleFilter.value))
const assetOptions = computed(() => assets.value.map((asset) => ({
  label: `${asset.name} · v${asset.version} · ${roleLabel(asset.role)}`,
  value: asset.id,
})) )
const formatOptions = computed(() => (['openapi', 'swagger', 'json_schema'] as AssetFormat[]).map((format) => ({
  label: formatLabel(format),
  value: format,
})))
const assetColumns = computed(() => [
  { title: t('api_contract_assets.name'), key: 'name', dataIndex: 'name' },
  { title: t('api_contract_assets.role'), key: 'role', width: 110 },
  { title: t('api_contract_assets.format'), key: 'format', width: 110 },
  { title: t('api_contract_assets.version'), key: 'version', dataIndex: 'version', width: 90 },
  { title: t('common.actions'), key: 'actions', width: 130 },
])

const asAsset = (record: unknown) => record as ApiContractAssetItem

function roleLabel(role: AssetRole) {
  return t(`api_contract_assets.${role}`)
}

function formatLabel(format: AssetFormat) {
  return t(`api_contract_assets.formats.${format}`)
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string' && error.trim()) return error
  if (error && typeof error === 'object' && 'message' in error) {
    const detail = (error as { message?: unknown }).message
    if (typeof detail === 'string' && detail.trim()) return detail
  }
  return fallback
}

function syncCompareSelection() {
  const ids = assets.value.map((asset) => asset.id)
  if (!baselineAssetId.value || !ids.includes(baselineAssetId.value)) baselineAssetId.value = ids[0]
  if (!currentAssetId.value || !ids.includes(currentAssetId.value)) currentAssetId.value = ids[1] ?? ids[0]
  if (baselineAssetId.value === currentAssetId.value && ids.length > 1) currentAssetId.value = ids[1]
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    projectId.value = selectAvailableProjectId(projectIdFromQuery(route.query.project_id), projects.value)
    await loadAssets()
  } catch (error) {
    message.error(errorMessage(error, t('api_contract_assets.load_failed')))
  }
}

async function loadAssets() {
  if (!projectId.value) {
    assets.value = []
    return
  }
  loading.value = true
  comparison.value = null
  try {
    assets.value = await apiContractAssetApi.list(projectId.value)
    syncCompareSelection()
  } catch (error) {
    assets.value = []
    message.error(errorMessage(error, t('api_contract_assets.load_failed')))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', role: 'provider', format: 'openapi', description: '', definitionText: '{\n  "openapi": "3.0.0",\n  "paths": {}\n}' }
  definitionError.value = ''
  editorOpen.value = true
}

function openEdit(asset: ApiContractAssetItem) {
  editing.value = asset
  form.value = {
    name: asset.name,
    role: asset.role,
    format: asset.format,
    description: asset.description || '',
    definitionText: JSON.stringify(asset.definition, null, 2),
  }
  definitionError.value = ''
  editorOpen.value = true
}

function parseDefinition(): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(form.value.definitionText)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed) || !Object.keys(parsed).length) {
      definitionError.value = t('api_contract_assets.definition_object_required')
      return null
    }
    definitionError.value = ''
    return parsed as Record<string, unknown>
  } catch {
    definitionError.value = t('api_contract_assets.definition_invalid')
    return null
  }
}

async function saveAsset() {
  if (!projectId.value) return
  if (!form.value.name.trim()) {
    message.warning(t('api_contract_assets.name_required'))
    return
  }
  const definition = parseDefinition()
  if (!definition) return
  saving.value = true
  try {
    if (editing.value) {
      await apiContractAssetApi.update(editing.value.id, {
        name: form.value.name.trim(),
        role: form.value.role,
        format: form.value.format,
        description: form.value.description.trim() || null,
        definition,
      })
    } else {
      await apiContractAssetApi.create(projectId.value, {
        name: form.value.name.trim(),
        role: form.value.role,
        format: form.value.format,
        description: form.value.description.trim() || undefined,
        definition,
      })
    }
    editorOpen.value = false
    await loadAssets()
    message.success(t('api_contract_assets.saved'))
  } catch (error) {
    message.error(errorMessage(error, t('api_contract_assets.save_failed')))
  } finally {
    saving.value = false
  }
}

async function deleteAsset(id: number) {
  try {
    await apiContractAssetApi.delete(id)
    await loadAssets()
    message.success(t('api_contract_assets.deleted'))
  } catch (error) {
    message.error(errorMessage(error, t('api_contract_assets.delete_failed')))
  }
}

async function compareAssets() {
  if (!projectId.value || !baselineAssetId.value || !currentAssetId.value) return
  comparing.value = true
  try {
    comparison.value = await apiContractApi.compareAssets(projectId.value, baselineAssetId.value, currentAssetId.value)
  } catch (error) {
    message.error(errorMessage(error, t('api_contract_assets.compare_failed')))
  } finally {
    comparing.value = false
  }
}

onMounted(loadProjects)
</script>

<style scoped>
.contract-page { padding: 18px; }
.contract-hero { display: flex; justify-content: space-between; gap: 24px; align-items: flex-end; padding: 28px 30px; color: #fff; background: linear-gradient(118deg, #12233f 0%, #1c4566 64%, #237c88 100%); border-radius: 16px; box-shadow: 0 14px 34px rgba(18, 35, 63, 0.18); }
.eyebrow, .card-kicker { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 700; }
.eyebrow { color: #8ed8d4; margin-bottom: 8px; }
.hero-copy h2 { margin: 0; color: #fff; font-size: 28px; letter-spacing: -0.02em; }
.hero-copy p { max-width: 650px; margin: 8px 0 0; color: rgba(255, 255, 255, 0.74); }
.hero-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.project-select { min-width: 210px; }
.new-button { color: #12233f; background: #8ed8d4; border-color: #8ed8d4; }
.page-notice { margin: 18px 0; }
.summary-row { margin: 18px 0; }
.summary-card { min-height: 116px; padding: 18px 20px; border: 1px solid #e8edf1; border-radius: 12px; background: #fff; box-shadow: 0 6px 18px rgba(28, 51, 77, 0.06); display: flex; flex-direction: column; }
.summary-card strong { margin: 4px 0; color: #12233f; font-size: 30px; line-height: 1; }
.summary-label { color: #34445b; font-size: 13px; font-weight: 700; }
.summary-foot { color: #8a96a6; font-size: 12px; }
.provider-summary { border-top: 3px solid #42c6be; }
.consumer-summary { border-top: 3px solid #9672d8; }
.neutral-summary { border-top: 3px solid #5c7ca5; }
.registry-card, .compare-card { border-radius: 12px; box-shadow: 0 6px 18px rgba(28, 51, 77, 0.06); }
.card-heading, .compare-heading { display: flex; justify-content: space-between; gap: 16px; align-items: center; }
.card-heading > div, .compare-heading > div { display: flex; flex-direction: column; gap: 3px; }
.card-kicker { color: #8a96a6; }
.compare-heading { justify-content: flex-start; }
.delta-mark { width: 40px; height: 40px; display: grid; place-items: center; color: #12233f; background: #8ed8d4; border-radius: 10px; font-size: 24px; font-weight: 800; }
.asset-name-cell { display: flex; flex-direction: column; gap: 2px; }
.asset-name-cell span { color: #8a96a6; font-size: 12px; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.format-mark { color: #536b89; font-family: var(--font-mono, Consolas, monospace); font-size: 12px; }
.compare-flow { display: grid; grid-template-columns: 1fr 26px 1fr; gap: 7px; align-items: end; margin-bottom: 14px; }
.compare-side { padding: 12px; border-radius: 10px; }
.baseline-side { background: #f2f7fb; }
.current-side { background: #f6f2fb; }
.compare-step { display: block; margin-bottom: 7px; color: #68798d; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.compare-connector { display: grid; place-items: center; height: 38px; color: #7991aa; font-size: 20px; }
.compare-button { height: 40px; margin-bottom: 18px; }
.comparison-result { border-top: 1px solid #edf0f3; padding-top: 16px; }
.compatibility-banner { display: flex; gap: 10px; align-items: flex-start; padding: 12px; border-radius: 10px; }
.compatibility-banner.compatible { color: #166534; background: #edf9f0; }
.compatibility-banner.breaking { color: #a32929; background: #fff1f0; }
.compatibility-banner strong, .compatibility-banner span { display: block; }
.compatibility-banner span { margin-top: 3px; font-size: 12px; opacity: 0.82; }
.compatibility-dot { width: 9px; height: 9px; margin-top: 5px; border-radius: 50%; background: currentColor; }
.change-list { margin: 0; padding-left: 18px; font-size: 12px; }
.change-list li { margin-bottom: 8px; }
.change-list code { display: block; color: #536b89; }
.change-list span { display: block; margin-top: 2px; color: #6e7887; }
.no-diff, .compare-empty { color: #8a96a6; font-size: 12px; text-align: center; }
.compare-empty { display: flex; flex-direction: column; align-items: center; gap: 7px; padding: 34px 16px 22px; }
.empty-glyph { color: #8ed8d4; font-size: 34px; line-height: 1; }
.editor-notice { margin-bottom: 18px; }
.json-editor { font-family: var(--font-mono, Consolas, monospace); font-size: 12px; line-height: 1.55; }
.form-hint { color: #8a96a6; font-size: 12px; margin-top: 5px; }
.input-error { color: #d4380d; font-size: 12px; margin-top: 5px; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 900px) {
  .contract-hero { align-items: stretch; flex-direction: column; padding: 22px; }
  .hero-actions { justify-content: flex-start; }
  .project-select { flex: 1; }
  .card-heading { align-items: flex-start; flex-direction: column; }
}
@media (prefers-reduced-motion: reduce) {
  .contract-page * { transition: none !important; animation: none !important; }
}
</style>
