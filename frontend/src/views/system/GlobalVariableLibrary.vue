<template>
  <div style="display: flex; flex-direction: column; height: 100%">
    <!-- Header -->
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <h2 style="margin: 0">全局变量库</h2>
      <a-select
        v-model:value="selectedScope"
        style="width: 140px"
        :options="scopeOptions"
        @change="onScopeChange"
      />
      <a-select
        v-if="selectedScope === 'project'"
        v-model:value="selectedProjectId"
        placeholder="选择项目"
        style="width: 220px"
        :options="projectOptions"
        @change="loadVariables"
      />
      <a-button type="primary" :disabled="!canCreate" @click="openCreate">
        新建变量
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <a-table
        :data-source="variables"
        :columns="columns"
        :pagination="{ pageSize: 20 }"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'key'">
            <code style="font-size: 13px">{{ record.key }}</code>
          </template>
          <template v-else-if="column.key === 'value'">
            <span v-if="record.is_secret">
              <span>{{ revealedValues[record.id] ?? record.value }}</span>
              <a-button type="link" size="small" @click="toggleReveal(record)">
                {{ revealedValues[record.id] ? '隐藏' : '显示' }}
              </a-button>
            </span>
            <span v-else>{{ record.value }}</span>
          </template>
          <template v-else-if="column.key === 'is_secret'">
            <a-tag :color="record.is_secret ? 'red' : 'default'">
              {{ record.is_secret ? '是' : '否' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'scope_type'">
            <a-tag>{{ record.scope_type === 'global' ? '全局' : '项目级' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm title="确认删除此变量？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-spin>

    <!-- Create/Edit Modal -->
    <a-modal
      v-model:open="showModal"
      :title="editingVar ? '编辑变量' : '新建变量'"
      :confirm-loading="saving"
      @ok="handleSave"
      @cancel="resetForm"
    >
      <a-form :label-col="{ span: 5 }" layout="horizontal">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.key" placeholder="变量名，如 API_BASE_URL" />
        </a-form-item>
        <a-form-item label="值" required>
          <a-input-password v-model:value="form.value" placeholder="变量值" />
        </a-form-item>
        <a-form-item label="加密存储">
          <a-switch v-model:checked="form.is_secret" />
          <span style="margin-left: 8px; color: #999">加密后存储，查看时需显</span>
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="变量说明（可选）" />
        </a-form-item>
        <a-form-item v-if="selectedScope === 'project'" label="项目" required>
          <a-select
            v-model:value="form.project_id"
            placeholder="选择所属项目"
            :options="projectOptions"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { globalVariableApi, projectApi, type GlobalVariableItem, type ScopeType } from '@/api'

const loading = ref(false)
const saving = ref(false)
const variables = ref<GlobalVariableItem[]>([])
const projects = ref<any[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const selectedScope = ref<'global' | 'project'>('global')
const selectedProjectId = ref<number | null>(null)
const revealedValues = ref<Record<number, string>>({})

const scopeOptions = [
  { label: '全局', value: 'global' },
  { label: '项目级', value: 'project' },
]

const canCreate = computed(() => {
  return selectedScope.value === 'global' || selectedProjectId.value !== null
})

const columns = [
  { title: '变量名', key: 'key', dataIndex: 'key', width: '25%' },
  { title: '值', key: 'value', dataIndex: 'value', width: '30%' },
  { title: '加密', key: 'is_secret', dataIndex: 'is_secret', width: '8%' },
  { title: '类型', key: 'scope_type', dataIndex: 'scope_type', width: '10%' },
  { title: '描述', key: 'description', dataIndex: 'description', ellipsis: true },
  { title: '操作', key: 'action', width: '12%' },
]

// Form state
const showModal = ref(false)
const editingVar = ref<GlobalVariableItem | null>(null)
const form = ref({
  key: '',
  value: '',
  is_secret: false,
  description: '',
  project_id: null as number | null,
  scope_type: 'global' as ScopeType,
})

onMounted(async () => {
  try {
    const list = await projectApi.list()
    projects.value = list
    projectOptions.value = list.map((p: any) => ({ label: p.name, value: p.id }))
  } catch (e: any) {
    message.error(e?.message || '加载项目失败')
  }
  await loadVariables()
})

async function loadVariables() {
  loading.value = true
  try {
    const params: any = { scope_type: selectedScope.value }
    if (selectedScope.value === 'project' && selectedProjectId.value) {
      params.project_id = selectedProjectId.value
    }
    variables.value = await globalVariableApi.list(params)
  } catch (e: any) {
    message.error(e?.message || '加载变量失败')
  } finally {
    loading.value = false
  }
}

function onScopeChange() {
  if (selectedScope.value === 'global') {
    selectedProjectId.value = null
  }
  revealedValues.value = {}
  loadVariables()
}

async function toggleReveal(record: GlobalVariableItem) {
  if (revealedValues.value[record.id]) {
    const nextValues = { ...revealedValues.value }
    delete nextValues[record.id]
    revealedValues.value = nextValues
    return
  }
  try {
    const detail = await globalVariableApi.get(record.id, { reveal_secret: true })
    revealedValues.value = { ...revealedValues.value, [record.id]: detail.value }
  } catch (e: any) {
    message.error(e?.message || '读取变量失败')
  }
}

function openCreate() {
  editingVar.value = null
  form.value = {
    key: '',
    value: '',
    is_secret: false,
    description: '',
    project_id: selectedProjectId.value,
    scope_type: selectedScope.value,
  }
  showModal.value = true
}

function openEdit(record: GlobalVariableItem) {
  editingVar.value = record
  form.value = {
    key: record.key,
    value: '', // Don't prefill encrypted value
    is_secret: record.is_secret,
    description: record.description || '',
    project_id: record.project_id ?? null,
    scope_type: record.scope_type,
  }
  showModal.value = true
}

function resetForm() {
  editingVar.value = null
  form.value = { key: '', value: '', is_secret: false, description: '', project_id: null, scope_type: 'global' }
}

async function handleSave() {
  if (!form.value.key.trim()) {
    message.warning('请输入变量名')
    return
  }
  if (!form.value.value.trim()) {
    message.warning('请输入变量值')
    return
  }
  saving.value = true
  try {
    const data = {
      key: form.value.key.trim(),
      value_encrypted: form.value.value,
      is_secret: form.value.is_secret,
      description: form.value.description.trim() || undefined,
      scope_type: form.value.scope_type,
      project_id: form.value.project_id,
    }
    if (editingVar.value) {
      await globalVariableApi.update(editingVar.value.id, data)
      message.success('变量已更新')
    } else {
      await globalVariableApi.create(data)
      message.success('变量已创建')
    }
    showModal.value = false
    resetForm()
    await loadVariables()
  } catch (e: any) {
    message.error(e?.message || '保存变量失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await globalVariableApi.delete(id)
    message.success('变量已删除')
    await loadVariables()
  } catch (e: any) {
    message.error(e?.message || '删除变量失败')
  }
}
</script>
