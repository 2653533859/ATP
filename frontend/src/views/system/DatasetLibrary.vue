<template>
  <div class="dataset-library">
    <div class="header">
      <div>
        <h2>{{ t('dataset.title') }}</h2>
        <div class="subtitle">{{ t('dataset.subtitle') }}</div>
      </div>
      <a-space>
        <a-select
          v-model:value="projectId"
          :options="projectOptions"
          :placeholder="t('dataset.select_project')"
          style="width: 240px"
          allow-clear
          @change="loadList"
        />
        <a-button type="primary" :disabled="!projectId" @click="openCreate">
          + {{ t('dataset.create') }}
        </a-button>
        <a-button :disabled="!projectId" :loading="loading" @click="loadList">
          {{ t('common.refresh') }}
        </a-button>
      </a-space>
    </div>

    <a-row :gutter="12" class="summary-row">
      <a-col :span="6"><a-card size="small"><a-statistic :title="t('dataset.summary.datasets')" :value="datasets.length" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic :title="t('dataset.summary.rows')" :value="totalRows" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic :title="t('dataset.summary.schema_fields')" :value="totalSchemaFields" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic :title="t('dataset.summary.hard_block')" :value="hardBlockCount" /></a-card></a-col>
    </a-row>

    <div class="toolbar">
      <a-input-search
        v-model:value="keyword"
        :placeholder="t('dataset.search_placeholder')"
        allow-clear
        style="width: 320px"
      />
      <span class="toolbar-hint">{{ t('dataset.limit_hint') }}</span>
    </div>

    <a-table
      :columns="columns"
      :data-source="filteredDatasets"
      :loading="loading"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
      row-key="id"
      :scroll="{ x: 1120 }"
      :locale="{ emptyText: t('dataset.empty') }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'format'">
          <a-tag :color="record.format === 'csv' ? 'green' : 'blue'">{{ record.format.toUpperCase() }}</a-tag>
        </template>
        <template v-else-if="column.key === 'validation_policy'">
          <a-tag :color="record.validation_policy === 'hard' ? 'red' : 'gold'">
            {{ record.validation_policy === 'hard' ? t('dataset.validation_hard') : t('dataset.validation_soft') }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" @click="openEdit(record)">{{ t('common.edit') }}</a-button>
            <a-button size="small" @click="openImpact(record)">{{ t('dataset.impact') }}</a-button>
            <a-button size="small" @click="openVersions(record)">{{ t('dataset.versions') }}</a-button>
            <a-upload
              :show-upload-list="false"
              :before-upload="(f: File) => onUpload(record.id, f)"
            >
              <a-button size="small">{{ t('dataset.upload') }}</a-button>
            </a-upload>
            <a-popconfirm :title="t('dataset.delete_confirm')" @confirm="onDelete(record.id)">
              <a-button size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-drawer
      v-model:open="editorOpen"
      :title="editing ? t('dataset.edit_title') : t('dataset.create_title')"
      :width="860"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('dataset.name')">
          <a-input v-model:value="form.name" :placeholder="t('dataset.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('dataset.description')">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t('dataset.format')">
          <a-radio-group v-model:value="form.format" :disabled="!!editing">
            <a-radio value="json">JSON</a-radio>
            <a-radio value="csv">CSV</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('dataset.validation_policy')">
          <a-radio-group v-model:value="form.validation_policy">
            <a-radio-button value="soft">{{ t('dataset.validation_soft') }}</a-radio-button>
            <a-radio-button value="hard">{{ t('dataset.validation_hard') }}</a-radio-button>
          </a-radio-group>
          <div class="form-hint">
            {{ form.validation_policy === 'hard' ? t('dataset.validation_hard_hint') : t('dataset.validation_soft_hint') }}
          </div>
        </a-form-item>
        <a-form-item :label="t('dataset.schema_fields')">
          <a-table
            :columns="schemaColumns"
            :data-source="schemaRows"
            :pagination="false"
            size="small"
            row-key="key"
          >
            <template #bodyCell="{ column, index }">
              <template v-if="column.key === 'name'">
                <a-input v-model:value="form.schema_fields[index].name" />
              </template>
              <template v-else-if="column.key === 'type'">
                <a-select v-model:value="form.schema_fields[index].type" :options="schemaTypeOptions" style="width: 120px" />
              </template>
              <template v-else-if="column.key === 'required'">
                <a-checkbox v-model:checked="form.schema_fields[index].required" />
              </template>
              <template v-else-if="column.key === 'default'">
                <a-input v-model:value="form.schema_fields[index].defaultText" :placeholder="t('dataset.default_placeholder')" />
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-button size="small" danger @click="removeSchemaField(index)">{{ t('common.delete') }}</a-button>
              </template>
            </template>
          </a-table>
          <a-button size="small" style="margin-top: 8px" @click="addSchemaField">
            {{ t('dataset.add_schema_field') }}
          </a-button>
        </a-form-item>
        <a-form-item :label="t('dataset.rows_editor') + ` (${form.rows.length})`">
          <a-textarea
            v-model:value="rowsText"
            :rows="10"
            class="rows-editor"
            :placeholder="t('dataset.rows_editor_placeholder')"
          />
          <div v-if="rowsTextError" class="input-error">{{ rowsTextError }}</div>
          <div v-else class="form-hint">{{ t('dataset.rows_editor_hint') }}</div>
        </a-form-item>
        <a-space>
          <a-button @click="formatRowsText">{{ t('dataset.format_json') }}</a-button>
          <a-button :loading="validating" @click="validateCurrentRows">{{ t('dataset.validate_rows') }}</a-button>
        </a-space>
      </a-form>
      <template #footer>
        <div class="drawer-footer">
          <a-button @click="editorOpen = false">{{ t('common.cancel') }}</a-button>
          <a-button type="primary" @click="onSave">{{ t('common.save') }}</a-button>
        </div>
      </template>
    </a-drawer>

    <a-modal
      v-model:open="validationOpen"
      :title="t('dataset.validation_title')"
      :ok-text="pendingUpload ? t('dataset.confirm_upload') : t('common.ok')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="uploading"
      :ok-button-props="{ disabled: pendingUpload ? !!validationResult && validationResult.can_upload === false : false }"
      width="720px"
      @ok="confirmValidationAction"
    >
      <a-alert
        v-if="validationResult"
        :type="validationResult.valid ? 'success' : 'warning'"
        :message="validationResult.valid
          ? t('dataset.validation_passed', { count: validationResult.row_count })
          : t('dataset.validation_failed', { count: validationResult.issues.length })"
        show-icon
      />
      <a-alert
        v-if="pendingUpload && validationResult && !validationResult.valid && validationResult.can_upload"
        type="warning"
        :message="t('dataset.soft_policy_allows_upload')"
        show-icon
        class="validation-section"
      />
      <a-alert
        v-if="pendingUpload && validationResult?.can_upload === false"
        type="error"
        :message="t('dataset.hard_policy_blocks_upload')"
        show-icon
        class="validation-section"
      />
      <div v-if="validationResult?.issues.length" class="validation-section">
        <div class="section-label">{{ t('dataset.validation_issues') }}</div>
        <a-table
          :columns="issueColumns"
          :data-source="validationIssues"
          :pagination="{ pageSize: 5 }"
          size="small"
          row-key="key"
        />
      </div>
      <div v-if="validationResult?.normalized_rows.length" class="validation-section">
        <div class="section-label">{{ t('dataset.normalized_preview') }}</div>
        <pre class="rows-preview">{{ JSON.stringify(validationResult.normalized_rows, null, 2) }}</pre>
      </div>
    </a-modal>

    <a-modal
      v-model:open="versionOpen"
      :title="t('dataset.version_title')"
      :footer="null"
      width="760px"
    >
      <a-table
        :columns="versionColumns"
        :data-source="versions"
        :loading="versionLoading"
        :pagination="{ pageSize: 6 }"
        row-key="id"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-popconfirm :title="t('dataset.rollback_confirm', { version: record.version })" @confirm="rollbackVersion(record.version)">
              <a-button size="small">{{ t('dataset.rollback') }}</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-modal>

    <a-modal
      v-model:open="impactOpen"
      :title="t('dataset.impact_title')"
      :footer="null"
      width="760px"
    >
      <a-spin :spinning="impactLoading">
        <a-alert
          v-if="impact"
          :type="impact.total_count > 0 ? 'warning' : 'success'"
          :message="impact.total_count > 0
            ? t('dataset.impact_found', { count: impact.total_count })
            : t('dataset.impact_empty')"
          show-icon
        />
        <div v-if="impact" class="validation-section">
          <div class="section-label">{{ t('dataset.impact_cases') }}</div>
          <a-table :columns="impactColumns" :data-source="impactRows(impact.cases)" :pagination="false" size="small" row-key="key" />
        </div>
        <div v-if="impact" class="validation-section">
          <div class="section-label">{{ t('dataset.impact_suites') }}</div>
          <a-table :columns="impactColumns" :data-source="impactRows(impact.suites)" :pagination="false" size="small" row-key="key" />
        </div>
        <div v-if="impact" class="validation-section">
          <div class="section-label">{{ t('dataset.impact_plans') }}</div>
          <a-table :columns="impactColumns" :data-source="impactRows(impact.plans)" :pagination="false" size="small" row-key="key" />
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { datasetApi, projectApi, type DatasetDetail, type DatasetImpact, type DatasetImpactItem, type DatasetListItem, type DatasetFormat, type DatasetSchemaField, type DatasetSchemaFieldType, type DatasetValidationPolicy, type DatasetValidationResult, type DatasetVersionItem, type ProjectItem } from '@/api'

const { t: translate } = useI18n()

function t(key: string, params?: Record<string, string | number>) {
  return translate(key.startsWith('dataset.') ? `system_pages.${key}` : key, params ?? {})
}

const projectId = ref<number | null>(null)
const projectOptions = ref<{ label: string; value: number }[]>([])
const datasets = ref<DatasetListItem[]>([])
const loading = ref(false)
const editorOpen = ref(false)
const editing = ref<DatasetDetail | null>(null)
const validating = ref(false)
const validationOpen = ref(false)
const validationResult = ref<DatasetValidationResult | null>(null)
const pendingUpload = ref<{ id: number; file: File } | null>(null)
const uploading = ref(false)
const versionOpen = ref(false)
const versionLoading = ref(false)
const versionDatasetId = ref<number | null>(null)
const versions = ref<DatasetVersionItem[]>([])
const impactOpen = ref(false)
const impactLoading = ref(false)
const impact = ref<DatasetImpact | null>(null)
const keyword = ref('')
const rowsText = ref('[]')
const rowsTextError = ref('')

type SchemaFieldForm = {
  name: string
  type: DatasetSchemaFieldType
  required: boolean
  defaultText: string
}

const form = ref<{ name: string; description: string; format: DatasetFormat; validation_policy: DatasetValidationPolicy; rows: Record<string, unknown>[]; schema_fields: SchemaFieldForm[] }>(
  { name: '', description: '', format: 'json', validation_policy: 'soft', rows: [], schema_fields: [] },
)

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: t('dataset.name'), dataIndex: 'name', key: 'name' },
  { title: t('dataset.format'), key: 'format', width: 100 },
  { title: t('dataset.validation_policy'), dataIndex: 'validation_policy', key: 'validation_policy', width: 120 },
  { title: t('dataset.row_count'), dataIndex: 'row_count', key: 'row_count', width: 120 },
  { title: t('dataset.schema_field_count'), dataIndex: 'schema_field_count', key: 'schema_field_count', width: 120 },
  { title: t('dataset.updated_at'), dataIndex: 'updated_at', key: 'updated_at', width: 180 },
  { title: t('common.actions'), key: 'actions', width: 360 },
])

const filteredDatasets = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  if (!needle) return datasets.value
  return datasets.value.filter((item) =>
    [item.name, item.description ?? '', item.format, item.validation_policy]
      .some((value) => value.toLowerCase().includes(needle)),
  )
})

const totalRows = computed(() => datasets.value.reduce((total, item) => total + item.row_count, 0))
const totalSchemaFields = computed(() => datasets.value.reduce((total, item) => total + item.schema_field_count, 0))
const hardBlockCount = computed(() => datasets.value.filter((item) => item.validation_policy === 'hard').length)

const issueColumns = computed(() => [
  { title: t('dataset.issue_row'), dataIndex: 'row_index', key: 'row_index', width: 110 },
  { title: t('dataset.issue_field'), dataIndex: 'field', key: 'field', width: 180 },
  { title: t('dataset.issue_message'), dataIndex: 'message', key: 'message' },
])

const schemaColumns = computed(() => [
  { title: t('dataset.schema_name'), key: 'name', width: 160 },
  { title: t('dataset.schema_type'), key: 'type', width: 140 },
  { title: t('dataset.schema_required'), key: 'required', width: 90 },
  { title: t('dataset.schema_default'), key: 'default' },
  { title: t('common.actions'), key: 'actions', width: 90 },
])

const versionColumns = computed(() => [
  { title: t('dataset.version'), dataIndex: 'version', key: 'version', width: 90 },
  { title: t('dataset.change_type'), dataIndex: 'change_type', key: 'change_type', width: 140 },
  { title: t('dataset.row_count'), dataIndex: 'row_count', key: 'row_count', width: 100 },
  { title: t('dataset.validation_policy'), dataIndex: 'validation_policy', key: 'validation_policy', width: 120 },
  { title: t('dataset.created_at'), dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: t('common.actions'), key: 'action', width: 100 },
])

const impactColumns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 90 },
  { title: t('dataset.name'), dataIndex: 'name', key: 'name' },
  { title: t('dataset.impact_reason'), dataIndex: 'reason', key: 'reason', width: 220 },
])

const schemaTypeOptions = ['string', 'number', 'integer', 'boolean', 'object', 'array']
  .map((value) => ({ label: value, value }))

const schemaRows = computed(() =>
  form.value.schema_fields.map((field, index) => ({ ...field, key: `${field.name || 'field'}:${index}` })),
)

const validationIssues = computed(() =>
  (validationResult.value?.issues ?? []).map((issue, index) => ({
    ...issue,
    key: `${issue.row_index}:${issue.field}:${index}`,
  })),
)

function impactRows(items: DatasetImpactItem[]) {
  return items.map((item) => ({ ...item, key: `${item.id}:${item.reason}` }))
}

async function loadProjects() {
  const items = await projectApi.list()
  projectOptions.value = items.map((p: ProjectItem) => ({ label: p.name, value: p.id }))
  if (!projectId.value && projectOptions.value.length) {
    projectId.value = projectOptions.value[0].value
    await loadList()
  }
}

async function loadList() {
  if (!projectId.value) {
    datasets.value = []
    return
  }
  loading.value = true
  try {
    datasets.value = await datasetApi.list(projectId.value)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', description: '', format: 'json', validation_policy: 'soft', rows: [], schema_fields: [] }
  rowsText.value = '[]'
  rowsTextError.value = ''
  editorOpen.value = true
}

function schemaFieldToForm(field: DatasetSchemaField): SchemaFieldForm {
  return {
    name: field.name,
    type: field.type ?? 'string',
    required: Boolean(field.required),
    defaultText: field.default === undefined || field.default === null ? '' : JSON.stringify(field.default),
  }
}

function parseSchemaDefault(raw: string): unknown {
  const text = raw.trim()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function normalizedSchemaFields(): DatasetSchemaField[] | null {
  const fields: DatasetSchemaField[] = []
  for (const field of form.value.schema_fields) {
    const name = field.name.trim()
    if (!name) {
      message.warning(t('dataset.schema_name_required'))
      return null
    }
    fields.push({
      name,
      type: field.type,
      required: field.required,
      default: parseSchemaDefault(field.defaultText),
    })
  }
  return fields
}

function addSchemaField() {
  form.value.schema_fields.push({ name: '', type: 'string', required: false, defaultText: '' })
}

function removeSchemaField(index: number) {
  form.value.schema_fields.splice(index, 1)
}

async function openEdit(record: DatasetListItem) {
  const detail = await datasetApi.get(record.id)
  editing.value = detail
  form.value = {
    name: detail.name,
    description: detail.description || '',
    format: detail.format,
    validation_policy: detail.validation_policy ?? 'soft',
    rows: detail.rows,
    schema_fields: (detail.schema_fields ?? []).map(schemaFieldToForm),
  }
  rowsText.value = JSON.stringify(detail.rows, null, 2)
  rowsTextError.value = ''
  editorOpen.value = true
}

function applyRowsText(): boolean {
  const text = rowsText.value.trim()
  if (!text) {
    form.value.rows = []
    rowsText.value = '[]'
    rowsTextError.value = ''
    return true
  }
  try {
    const parsed: unknown = JSON.parse(text)
    if (!Array.isArray(parsed) || !parsed.every((row) => typeof row === 'object' && row !== null && !Array.isArray(row))) {
      rowsTextError.value = t('dataset.rows_array_required')
      return false
    }
    form.value.rows = parsed as Record<string, unknown>[]
    rowsTextError.value = ''
    return true
  } catch {
    rowsTextError.value = t('dataset.rows_parse_failed')
    return false
  }
}

function formatRowsText() {
  if (!applyRowsText()) return
  rowsText.value = JSON.stringify(form.value.rows, null, 2)
}

async function onSave() {
  if (!projectId.value) return
  if (!form.value.name.trim()) {
    message.warning(t('dataset.name_required'))
    return
  }
  if (!applyRowsText()) return
  const schemaFields = normalizedSchemaFields()
  if (schemaFields == null) return
  try {
    if (editing.value) {
      await datasetApi.update(editing.value.id, {
        name: form.value.name,
        description: form.value.description,
        schema_fields: schemaFields,
        validation_policy: form.value.validation_policy,
      })
    } else {
      await datasetApi.create({
        name: form.value.name,
        project_id: projectId.value,
        description: form.value.description || undefined,
        format: form.value.format,
        rows: form.value.rows,
        schema_fields: schemaFields,
        validation_policy: form.value.validation_policy,
      })
    }
    editorOpen.value = false
    await loadList()
    message.success(t('common.saved'))
  } catch {
    // axios 拦截器已弹错误
  }
}

async function validateCurrentRows() {
  validating.value = true
  pendingUpload.value = null
  try {
    if (!applyRowsText()) return
    const schemaFields = normalizedSchemaFields()
    if (schemaFields == null) return
    validationResult.value = await datasetApi.validate({
      schema_fields: schemaFields,
      rows: form.value.rows,
      preview_limit: 5,
    })
    validationOpen.value = true
  } catch {
    // axios 已处理
  } finally {
    validating.value = false
  }
}

async function onDelete(id: number) {
  try {
    await datasetApi.delete(id)
    await loadList()
    message.success(t('common.deleted'))
  } catch {
    // axios 已处理
  }
}

async function openImpact(record: DatasetListItem) {
  impact.value = null
  impactOpen.value = true
  impactLoading.value = true
  try {
    impact.value = await datasetApi.getImpact(record.id)
  } finally {
    impactLoading.value = false
  }
}

async function openVersions(record: DatasetListItem) {
  versionDatasetId.value = record.id
  versionOpen.value = true
  versionLoading.value = true
  try {
    versions.value = await datasetApi.listVersions(record.id)
  } finally {
    versionLoading.value = false
  }
}

async function rollbackVersion(version: number) {
  if (!versionDatasetId.value) return
  try {
    await datasetApi.rollback(versionDatasetId.value, version)
    versions.value = await datasetApi.listVersions(versionDatasetId.value)
    await loadList()
    message.success(t('dataset.rollback_success'))
  } catch {
    // axios 已处理
  }
}

async function onUpload(id: number, file: File) {
  pendingUpload.value = { id, file }
  uploading.value = false
  try {
    validationResult.value = await datasetApi.previewUpload(id, file)
    validationOpen.value = true
  } catch {
    // axios 已处理
  }
  return false  // 阻止默认上传行为
}

async function confirmValidationAction() {
  if (!pendingUpload.value) {
    validationOpen.value = false
    return
  }
  uploading.value = true
  try {
    await datasetApi.upload(pendingUpload.value.id, pendingUpload.value.file)
    validationOpen.value = false
    pendingUpload.value = null
    await loadList()
    message.success(t('dataset.upload_success'))
  } catch {
    // axios 已处理
  } finally {
    uploading.value = false
  }
}

onMounted(loadProjects)
</script>

<style scoped>
.dataset-library {
  padding: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.subtitle,
.toolbar-hint,
.form-hint {
  color: #8c8c8c;
  font-size: 12px;
}

.summary-row,
.toolbar {
  margin-bottom: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.rows-preview {
  margin: 0;
  padding: 8px 12px;
  background: #f6f8fa;
  border-radius: 4px;
  max-height: 240px;
  overflow: auto;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.rows-editor {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
}

.input-error {
  color: #ff4d4f;
  font-size: 12px;
  margin-top: 4px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.validation-section {
  margin-top: 12px;
}

.section-label {
  font-weight: 600;
  color: #595959;
  margin-bottom: 6px;
}
</style>
