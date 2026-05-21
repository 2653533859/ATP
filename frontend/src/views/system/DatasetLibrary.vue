<template>
  <div class="dataset-library">
    <div class="header">
      <h2>{{ t('dataset.title') }}</h2>
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
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="datasets"
      :loading="loading"
      :pagination="false"
      row-key="id"
      :locale="{ emptyText: t('dataset.empty') }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'format'">
          <a-tag :color="record.format === 'csv' ? 'green' : 'blue'">{{ record.format.toUpperCase() }}</a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" @click="openEdit(record)">{{ t('common.edit') }}</a-button>
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
      :width="640"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      @ok="onSave"
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
        <a-form-item :label="t('dataset.rows_preview') + ` (${form.rows.length})`">
          <pre class="rows-preview">{{ rowsPreview }}</pre>
        </a-form-item>
      </a-form>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { datasetApi, projectApi, type DatasetDetail, type DatasetListItem, type DatasetFormat } from '@/api'

const { t } = useI18n()

const projectId = ref<number | null>(null)
const projectOptions = ref<{ label: string; value: number }[]>([])
const datasets = ref<DatasetListItem[]>([])
const loading = ref(false)
const editorOpen = ref(false)
const editing = ref<DatasetDetail | null>(null)

const form = ref<{ name: string; description: string; format: DatasetFormat; rows: Record<string, unknown>[] }>(
  { name: '', description: '', format: 'json', rows: [] },
)

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: t('dataset.name'), dataIndex: 'name', key: 'name' },
  { title: t('dataset.format'), key: 'format', width: 100 },
  { title: t('dataset.row_count'), dataIndex: 'row_count', key: 'row_count', width: 120 },
  { title: t('dataset.updated_at'), dataIndex: 'updated_at', key: 'updated_at', width: 180 },
  { title: t('common.actions'), key: 'actions', width: 240 },
])

const rowsPreview = computed(() => {
  if (!form.value.rows.length) return t('dataset.no_rows')
  return JSON.stringify(form.value.rows.slice(0, 5), null, 2)
})

async function loadProjects() {
  const items = await projectApi.list()
  projectOptions.value = items.map((p: any) => ({ label: p.name, value: p.id }))
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
  form.value = { name: '', description: '', format: 'json', rows: [] }
  editorOpen.value = true
}

async function openEdit(record: DatasetListItem) {
  const detail = await datasetApi.get(record.id)
  editing.value = detail
  form.value = {
    name: detail.name,
    description: detail.description || '',
    format: detail.format,
    rows: detail.rows,
  }
  editorOpen.value = true
}

async function onSave() {
  if (!projectId.value) return
  if (!form.value.name.trim()) {
    message.warning(t('dataset.name_required'))
    return
  }
  try {
    if (editing.value) {
      await datasetApi.update(editing.value.id, {
        name: form.value.name,
        description: form.value.description,
      })
    } else {
      await datasetApi.create({
        name: form.value.name,
        project_id: projectId.value,
        description: form.value.description || undefined,
        format: form.value.format,
        rows: form.value.rows,
      })
    }
    editorOpen.value = false
    await loadList()
    message.success(t('common.saved'))
  } catch {
    // axios 拦截器已弹错误
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

async function onUpload(id: number, file: File) {
  try {
    await datasetApi.upload(id, file)
    await loadList()
    message.success(t('dataset.upload_success'))
  } catch {
    // axios 已处理
  }
  return false  // 阻止默认上传行为
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
</style>
