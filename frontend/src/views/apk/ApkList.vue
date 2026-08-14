<template>
  <div class="page-shell apk-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('apk.title') }}</h2>
        <div class="page-subtitle">{{ t('apk.subtitle') }}</div>
      </div>
      <a-button type="primary" @click="uploadOpen = true">
        <UploadOutlined /> {{ t('apk.upload') }}
      </a-button>
    </div>

    <a-row :gutter="12" class="page-summary">
      <a-col :span="8"><a-card size="small"><a-statistic :title="t('apk.summary.total')" :value="apks.length" /></a-card></a-col>
      <a-col :span="8"><a-card size="small"><a-statistic :title="t('apk.summary.projects')" :value="apkProjectCount" /></a-card></a-col>
      <a-col :span="8"><a-card size="small"><a-statistic :title="t('apk.summary.size')" :value="totalSizeLabel" /></a-card></a-col>
    </a-row>

    <div class="page-toolbar">
      <div class="page-toolbar-main">
        <a-select
          v-model:value="projectFilter"
          :placeholder="t('apk.select_project')"
          allow-clear
          style="width: 200px"
          @change="loadApks"
        >
          <a-select-option v-for="p in projects" :key="p.id" :value="p.id">
            {{ p.name }}
          </a-select-option>
        </a-select>
        <a-input-search
          v-model:value="keyword"
          :placeholder="t('apk.search_placeholder')"
          allow-clear
          style="width: 300px"
        />
      </div>
      <span class="muted-text">{{ t('apk.upload_hint') }}</span>
    </div>

    <a-table
      :columns="columns"
      :data-source="filteredApks"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="false"
      :locale="{ emptyText: t('apk.empty') }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'filename'">
          <div>{{ record.filename }}</div>
          <div v-if="record.package_name" style="color: var(--c-text-tertiary); font-size: 12px">
            {{ record.package_name }}
          </div>
        </template>

        <template v-if="column.key === 'version'">
          <span v-if="record.version_name">{{ record.version_name }}</span>
          <span v-if="record.version_code" style="color: var(--c-text-tertiary)">
            ({{ record.version_code }})
          </span>
          <span v-if="!record.version_name && !record.version_code">-</span>
        </template>

        <template v-if="column.key === 'size'">
          {{ formatSize(record.file_size) }}
        </template>

        <template v-if="column.key === 'project'">
          {{ getProjectName(record.project_id) }}
        </template>

        <template v-if="column.key === 'created'">
          {{ formatTime(record.created_at) }}
        </template>

        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleDownload(asApk(record))">{{ t('apk.download') }}</a-button>
            <a-button type="link" size="small" @click="openEdit(asApk(record))">{{ t('common.edit') }}</a-button>
            <a-popconfirm :title="t('apk.confirm_delete')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="uploadOpen"
      :title="t('apk.upload')"
      :ok-text="t('apk.upload_action')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="uploading"
      :ok-button-props="{ disabled: !uploadForm.file || !uploadForm.project_id }"
      @ok="handleUpload"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('apk.fields.project')" required>
          <a-select
            v-model:value="uploadForm.project_id"
            :placeholder="t('apk.select_project')"
            style="width: 100%"
          >
            <a-select-option v-for="p in projects" :key="p.id" :value="p.id">
              {{ p.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('apk.fields.file')" required>
          <a-upload
            :before-upload="beforeUpload"
            :max-count="1"
            accept=".apk"
            :file-list="fileList"
            @remove="handleRemoveFile"
          >
            <a-button><UploadOutlined /> {{ t('apk.select_file') }}</a-button>
          </a-upload>
        </a-form-item>
        <a-form-item :label="t('apk.fields.package_name')">
          <a-input v-model:value="uploadForm.package_name" placeholder="com.example.app" />
          <div class="form-hint">{{ t('apk.metadata_hint') }}</div>
        </a-form-item>
        <a-form-item :label="t('apk.fields.version')">
          <a-space>
            <a-input v-model:value="uploadForm.version_name" :placeholder="t('apk.placeholders.version_name')" style="width: 160px" />
            <a-input-number v-model:value="uploadForm.version_code" :placeholder="t('apk.placeholders.version_code')" style="width: 140px" />
          </a-space>
        </a-form-item>
        <a-form-item :label="t('apk.fields.description')">
          <a-textarea v-model:value="uploadForm.description" :placeholder="t('apk.placeholders.description')" :rows="2" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="editOpen"
      :title="t('apk.edit')"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('apk.fields.package_name')">
          <a-input v-model:value="editForm.package_name" placeholder="com.example.app" />
        </a-form-item>
        <a-form-item :label="t('apk.fields.version')">
          <a-space>
            <a-input v-model:value="editForm.version_name" :placeholder="t('apk.placeholders.version_name_short')" style="width: 160px" />
            <a-input-number v-model:value="editForm.version_code" :placeholder="t('apk.placeholders.version_code')" style="width: 140px" />
          </a-space>
        </a-form-item>
        <a-form-item :label="t('apk.fields.description')">
          <a-textarea v-model:value="editForm.description" :placeholder="t('apk.placeholders.description')" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import type { UploadFile } from 'ant-design-vue'
import { apkApi, projectApi } from '@/api'
import type { ApkItem, ProjectItem } from '@/api'
// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asApk = (record: unknown) => record as ApkItem

const { t } = useI18n()
const apks = ref<ApkItem[]>([])
const projects = ref<ProjectItem[]>([])
const loading = ref(false)
const projectFilter = ref<number | undefined>(undefined)
const keyword = ref('')

const uploadOpen = ref(false)
const uploading = ref(false)
const fileList = ref<UploadFile[]>([])
const uploadForm = ref({
  project_id: undefined as number | undefined,
  file: null as File | null,
  package_name: '',
  version_name: '',
  version_code: undefined as number | undefined,
  description: '',
})

const editOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const editForm = ref({
  package_name: '',
  version_name: '',
  version_code: undefined as number | undefined,
  description: '',
})

const columns = computed(() => [
  { title: t('apk.columns.filename'), key: 'filename', width: 260 },
  { title: t('apk.columns.project'), key: 'project', width: 150 },
  { title: t('apk.columns.version'), key: 'version', width: 160 },
  { title: t('apk.columns.size'), key: 'size', width: 100 },
  { title: t('apk.columns.created'), key: 'created', width: 170 },
  { title: t('apk.columns.action'), key: 'action', width: 180, fixed: 'right' as const },
])

const filteredApks = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  if (!needle) return apks.value
  return apks.value.filter((apk) =>
    [apk.filename, apk.package_name ?? '', apk.version_name ?? '', String(apk.version_code ?? ''), getProjectName(apk.project_id)]
      .some((value) => value.toLowerCase().includes(needle)),
  )
})

const apkProjectCount = computed(() => new Set(apks.value.map((apk) => apk.project_id)).size)
const totalSizeLabel = computed(() => formatSize(apks.value.reduce((total, apk) => total + apk.file_size, 0)))

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ')
}

function getProjectName(projectId: number) {
  return projects.value.find(p => p.id === projectId)?.name ?? '-'
}

function beforeUpload(file: File) {
  uploadForm.value.file = file
  fileList.value = [{ uid: '-1', name: file.name, status: 'done' } as UploadFile]
  return false
}

function handleRemoveFile() {
  uploadForm.value.file = null
  fileList.value = []
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('apk.msg.load_projects_failed')))
  }
}

async function loadApks() {
  loading.value = true
  try {
    apks.value = await apkApi.list(
      projectFilter.value ? { project_id: projectFilter.value } : undefined,
    )
  } catch (e: unknown) {
    message.error(errorMessage(e, t('apk.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

async function handleUpload() {
  const { file, project_id, package_name, version_name, version_code, description } = uploadForm.value
  if (!file || !project_id) return

  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    form.append('project_id', String(project_id))
    if (package_name) form.append('package_name', package_name)
    if (version_name) form.append('version_name', version_name)
    if (version_code !== undefined && version_code !== null) form.append('version_code', String(version_code))
    if (description) form.append('description', description)

    await apkApi.upload(form)
    message.success(t('apk.msg.upload_success'))
    uploadOpen.value = false
    resetUploadForm()
    loadApks()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('apk.msg.upload_failed')))
  } finally {
    uploading.value = false
  }
}

function resetUploadForm() {
  uploadForm.value = {
    project_id: undefined,
    file: null,
    package_name: '',
    version_name: '',
    version_code: undefined,
    description: '',
  }
  fileList.value = []
}

function openEdit(record: ApkItem) {
  editingId.value = record.id
  editForm.value = {
    package_name: record.package_name ?? '',
    version_name: record.version_name ?? '',
    version_code: record.version_code ?? undefined,
    description: record.description ?? '',
  }
  editOpen.value = true
}

async function handleSave() {
  if (!editingId.value) return
  saving.value = true
  try {
    await apkApi.update(editingId.value, editForm.value)
    message.success(t('apk.msg.save_success'))
    editOpen.value = false
    loadApks()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('apk.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await apkApi.delete(id)
    message.success(t('apk.msg.delete_success'))
    loadApks()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('apk.msg.delete_failed')))
  }
}

async function handleDownload(record: ApkItem) {
  try {
    const { url } = await apkApi.download(record.id)
    window.open(url, '_blank')
  } catch (e: unknown) {
    message.error(errorMessage(e, t('apk.msg.download_failed')))
  }
}

onMounted(() => {
  loadProjects()
  loadApks()
})
</script>

<style scoped>
.apk-page {
  display: flex;
  flex-direction: column;
}
</style>
