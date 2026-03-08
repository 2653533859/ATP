<template>
  <div class="bug-tracker-page">
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          placeholder="选择项目"
          style="width: 200px"
          allow-clear
          :options="projectOptions"
          @change="loadTrackers"
        />
      </a-space>
      <a-button type="primary" :disabled="!projectId" @click="openCreate">
        <PlusOutlined /> 添加缺陷跟踪
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="trackers"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="{ pageSize: 20 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'tracker_type'">
          <a-tag :color="typeColor(record.tracker_type)">{{ typeLabel(record.tracker_type) }}</a-tag>
        </template>
        <template v-if="column.key === 'is_enabled'">
          <a-tag :color="record.is_enabled ? 'green' : 'default'">{{ record.is_enabled ? '启用' : '禁用' }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm title="确认删除？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新建/编辑 Modal -->
    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? '编辑缺陷跟踪' : '添加缺陷跟踪'"
      :confirm-loading="saving"
      width="560px"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item label="名称">
          <a-input v-model:value="form.name" placeholder="如：项目 Jira" />
        </a-form-item>

        <a-form-item label="平台类型">
          <a-select v-model:value="form.tracker_type" :disabled="isEdit" style="width: 100%">
            <a-select-option value="jira">Jira</a-select-option>
            <a-select-option value="zentao">禅道</a-select-option>
          </a-select>
        </a-form-item>

        <!-- Jira 配置 -->
        <template v-if="form.tracker_type === 'jira'">
          <a-form-item label="Jira 地址">
            <a-input v-model:value="jiraBaseUrl" placeholder="https://xxx.atlassian.net" />
          </a-form-item>
          <a-form-item label="邮箱">
            <a-input v-model:value="jiraEmail" placeholder="user@example.com" />
          </a-form-item>
          <a-form-item label="API Token">
            <a-input-password v-model:value="jiraToken" placeholder="Jira API Token" />
          </a-form-item>
          <a-form-item label="项目 Key">
            <a-input v-model:value="jiraProjectKey" placeholder="ATP" />
          </a-form-item>
        </template>

        <!-- 禅道配置 -->
        <template v-if="form.tracker_type === 'zentao'">
          <a-form-item label="禅道地址">
            <a-input v-model:value="zentaoBaseUrl" placeholder="http://zentao.xxx.com" />
          </a-form-item>
          <a-form-item label="账号">
            <a-input v-model:value="zentaoAccount" placeholder="admin" />
          </a-form-item>
          <a-form-item label="密码">
            <a-input-password v-model:value="zentaoPassword" placeholder="密码" />
          </a-form-item>
          <a-form-item label="产品 ID">
            <a-input-number v-model:value="zentaoProductId" :min="1" style="width: 100%" placeholder="1" />
          </a-form-item>
        </template>

        <a-form-item label="启用">
          <a-switch v-model:checked="form.is_enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { bugTrackerApi, projectApi } from '@/api'

type TrackerType = 'jira' | 'zentao'

const trackers = ref<any[]>([])
const loading = ref(false)
const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const formOpen = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)

const form = ref<{ name: string; tracker_type: TrackerType; is_enabled: boolean }>({
  name: '', tracker_type: 'jira', is_enabled: true,
})

// Jira 字段
const jiraBaseUrl = ref('')
const jiraEmail = ref('')
const jiraToken = ref('')
const jiraProjectKey = ref('')

// 禅道字段
const zentaoBaseUrl = ref('')
const zentaoAccount = ref('')
const zentaoPassword = ref('')
const zentaoProductId = ref<number | undefined>(undefined)

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '平台', key: 'tracker_type', width: 100 },
  { title: '状态', key: 'is_enabled', width: 80 },
  { title: '更新时间', dataIndex: 'updated_at', width: 170,
    customRender: ({ text }: any) => text?.slice(0, 19).replace('T', ' ') },
  { title: '操作', key: 'action', width: 140, fixed: 'right' },
]

function typeLabel(t: string) {
  return { jira: 'Jira', zentao: '禅道' }[t] ?? t
}
function typeColor(t: string) {
  return { jira: 'blue', zentao: 'green' }[t] ?? 'default'
}

onMounted(async () => {
  try {
    const projects = await projectApi.list()
    projectOptions.value = projects.map((p: any) => ({ label: p.name, value: p.id }))
  } catch { /* ignore */ }
})

async function loadTrackers() {
  if (!projectId.value) { trackers.value = []; return }
  loading.value = true
  try {
    trackers.value = await bugTrackerApi.list({ project_id: projectId.value })
  } catch { message.error('加载缺陷跟踪配置失败') }
  finally { loading.value = false }
}

function resetFields() {
  jiraBaseUrl.value = ''
  jiraEmail.value = ''
  jiraToken.value = ''
  jiraProjectKey.value = ''
  zentaoBaseUrl.value = ''
  zentaoAccount.value = ''
  zentaoPassword.value = ''
  zentaoProductId.value = undefined
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  form.value = { name: '', tracker_type: 'jira', is_enabled: true }
  resetFields()
  formOpen.value = true
}

function openEdit(record: any) {
  isEdit.value = true
  editingId.value = record.id
  form.value = { name: record.name, tracker_type: record.tracker_type, is_enabled: record.is_enabled }
  resetFields()
  const cfg = record.config || {}
  if (record.tracker_type === 'jira') {
    jiraBaseUrl.value = cfg.base_url || ''
    jiraEmail.value = cfg.email || ''
    jiraToken.value = cfg.api_token || ''
    jiraProjectKey.value = cfg.project_key || ''
  } else if (record.tracker_type === 'zentao') {
    zentaoBaseUrl.value = cfg.base_url || ''
    zentaoAccount.value = cfg.account || ''
    zentaoPassword.value = cfg.password || ''
    zentaoProductId.value = cfg.product_id
  }
  formOpen.value = true
}

function buildConfig(): Record<string, unknown> {
  if (form.value.tracker_type === 'jira') {
    return {
      base_url: jiraBaseUrl.value,
      email: jiraEmail.value,
      api_token: jiraToken.value,
      project_key: jiraProjectKey.value,
    }
  } else if (form.value.tracker_type === 'zentao') {
    return {
      base_url: zentaoBaseUrl.value,
      account: zentaoAccount.value,
      password: zentaoPassword.value,
      product_id: zentaoProductId.value,
    }
  }
  return {}
}

async function handleSave() {
  if (!projectId.value && !isEdit.value) { message.warning('请先选择项目'); return }
  if (!form.value.name) { message.warning('请输入名称'); return }
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      tracker_type: form.value.tracker_type,
      config: buildConfig(),
      is_enabled: form.value.is_enabled,
    }
    if (isEdit.value) {
      await bugTrackerApi.update(editingId.value!, payload)
    } else {
      await bugTrackerApi.create({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    formOpen.value = false
    loadTrackers()
  } catch { message.error('保存失败') }
  finally { saving.value = false }
}

async function handleDelete(id: number) {
  try {
    await bugTrackerApi.delete(id)
    message.success('已删除')
    loadTrackers()
  } catch { message.error('删除失败') }
}
</script>

<style scoped>
.bug-tracker-page {
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
