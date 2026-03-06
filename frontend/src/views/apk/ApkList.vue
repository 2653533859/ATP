<template>
  <div class="apk-page">
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectFilter"
          placeholder="选择项目"
          allow-clear
          style="width: 200px"
          @change="loadApks"
        >
          <a-select-option v-for="p in projects" :key="p.id" :value="p.id">
            {{ p.name }}
          </a-select-option>
        </a-select>
      </a-space>
      <a-button type="primary" @click="uploadOpen = true">
        <UploadOutlined /> 上传 APK
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="apks"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="false"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'filename'">
          <div>{{ record.filename }}</div>
          <div v-if="record.package_name" style="color: #999; font-size: 12px">
            {{ record.package_name }}
          </div>
        </template>

        <template v-if="column.key === 'version'">
          <span v-if="record.version_name">{{ record.version_name }}</span>
          <span v-if="record.version_code" style="color: #999">
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
            <a-button type="link" size="small" @click="handleDownload(record)">下载</a-button>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm title="确认删除该 APK？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 上传 Modal -->
    <a-modal
      v-model:open="uploadOpen"
      title="上传 APK"
      ok-text="上传"
      cancel-text="取消"
      :confirm-loading="uploading"
      :ok-button-props="{ disabled: !uploadForm.file || !uploadForm.project_id }"
      @ok="handleUpload"
    >
      <a-form layout="vertical">
        <a-form-item label="所属项目" required>
          <a-select
            v-model:value="uploadForm.project_id"
            placeholder="选择项目"
            style="width: 100%"
          >
            <a-select-option v-for="p in projects" :key="p.id" :value="p.id">
              {{ p.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="APK 文件" required>
          <a-upload
            :before-upload="beforeUpload"
            :max-count="1"
            accept=".apk"
            :file-list="fileList"
            @remove="handleRemoveFile"
          >
            <a-button><UploadOutlined /> 选择文件</a-button>
          </a-upload>
        </a-form-item>
        <a-form-item label="包名">
          <a-input v-model:value="uploadForm.package_name" placeholder="com.example.app" />
        </a-form-item>
        <a-form-item label="版本号">
          <a-space>
            <a-input v-model:value="uploadForm.version_name" placeholder="版本名称 (如 1.0.0)" style="width: 160px" />
            <a-input-number v-model:value="uploadForm.version_code" placeholder="版本代码" style="width: 140px" />
          </a-space>
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="uploadForm.description" placeholder="APK 备注信息" :rows="2" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 编辑 Modal -->
    <a-modal
      v-model:open="editOpen"
      title="编辑 APK 信息"
      ok-text="保存"
      cancel-text="取消"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item label="包名">
          <a-input v-model:value="editForm.package_name" placeholder="com.example.app" />
        </a-form-item>
        <a-form-item label="版本号">
          <a-space>
            <a-input v-model:value="editForm.version_name" placeholder="版本名称" style="width: 160px" />
            <a-input-number v-model:value="editForm.version_code" placeholder="版本代码" style="width: 140px" />
          </a-space>
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="editForm.description" placeholder="APK 备注信息" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import type { UploadFile } from 'ant-design-vue'
import { apkApi, projectApi } from '@/api'

const apks = ref<any[]>([])
const projects = ref<any[]>([])
const loading = ref(false)
const projectFilter = ref<number | undefined>(undefined)

// 上传
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

// 编辑
const editOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const editForm = ref({
  package_name: '',
  version_name: '',
  version_code: undefined as number | undefined,
  description: '',
})

const columns = [
  { title: '文件名', key: 'filename', width: 260 },
  { title: '项目', key: 'project', width: 150 },
  { title: '版本', key: 'version', width: 160 },
  { title: '大小', key: 'size', width: 100 },
  { title: '上传时间', key: 'created', width: 170 },
  { title: '操作', key: 'action', width: 180, fixed: 'right' as const },
]

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
  } catch (e: any) {
    message.error(e ?? '加载项目列表失败')
  }
}

async function loadApks() {
  loading.value = true
  try {
    apks.value = await apkApi.list(
      projectFilter.value ? { project_id: projectFilter.value } : undefined,
    )
  } catch (e: any) {
    message.error(e ?? '加载 APK 列表失败')
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
    message.success('上传成功')
    uploadOpen.value = false
    resetUploadForm()
    loadApks()
  } catch (e: any) {
    message.error(e ?? '上传失败')
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

function openEdit(record: any) {
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
    message.success('保存成功')
    editOpen.value = false
    loadApks()
  } catch (e: any) {
    message.error(e ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await apkApi.delete(id)
    message.success('已删除')
    loadApks()
  } catch (e: any) {
    message.error(e ?? '删除失败')
  }
}

async function handleDownload(record: any) {
  try {
    const { url } = await apkApi.download(record.id)
    window.open(url, '_blank')
  } catch (e: any) {
    message.error(e ?? '获取下载链接失败')
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
  gap: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
