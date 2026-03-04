<template>
  <div style="display: flex; flex-direction: column; height: 100%">
    <!-- Header -->
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <h2 style="margin: 0">环境管理</h2>
      <a-select
        v-model:value="selectedProjectId"
        placeholder="选择项目"
        style="width: 220px"
        :options="projectOptions"
        @change="onProjectChange"
      />
      <a-button type="primary" :disabled="!selectedProjectId" @click="showCreateModal = true">
        新建环境
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <div v-if="!selectedProjectId">
        <a-empty description="请先选择项目" />
      </div>

      <div v-else style="display: flex; gap: 16px; min-height: 400px">
        <!-- Left: environment list -->
        <a-card title="环境列表" style="width: 280px; flex-shrink: 0">
          <a-empty v-if="environments.length === 0" description="暂无环境" />
          <a-list v-else :data-source="environments" size="small">
            <template #renderItem="{ item }">
              <a-list-item
                style="cursor: pointer; padding: 8px 12px"
                :style="{ background: selectedEnvId === item.id ? '#e6f4ff' : 'transparent' }"
                @click="selectEnv(item)"
              >
                <a-list-item-meta :title="item.name" :description="item.description || '无描述'" />
                <template #actions>
                  <a-button type="link" size="small" @click.stop="openEditModal(item)">编辑</a-button>
                  <a-popconfirm
                    title="确认删除此环境？变量将一并删除"
                    @confirm="handleDeleteEnv(item.id)"
                  >
                    <a-button type="link" size="small" danger @click.stop>删除</a-button>
                  </a-popconfirm>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-card>

        <!-- Right: variable editor -->
        <a-card
          style="flex: 1"
          :title="selectedEnv ? `变量 - ${selectedEnv.name}` : '环境变量'"
        >
          <template v-if="!selectedEnvId">
            <a-empty description="请在左侧选择环境" />
          </template>
          <template v-else>
            <a-spin :spinning="varsLoading">
              <div style="margin-bottom: 12px">
                <a-button type="dashed" @click="addVariable">添加变量</a-button>
              </div>
              <a-table
                :data-source="editingVars"
                :columns="varColumns"
                :pagination="false"
                row-key="_idx"
                size="small"
              >
                <template #bodyCell="{ column, record, index }">
                  <template v-if="column.key === 'key'">
                    <a-input v-model:value="record.key" placeholder="变量名" />
                  </template>
                  <template v-else-if="column.key === 'value'">
                    <a-input-password
                      v-if="record.is_secret"
                      v-model:value="record.value"
                      :placeholder="record._wasSecret ? '留空则保留原值' : '变量值'"
                    />
                    <a-input v-else v-model:value="record.value" placeholder="变量值" />
                  </template>
                  <template v-else-if="column.key === 'is_secret'">
                    <a-switch v-model:checked="record.is_secret" />
                  </template>
                  <template v-else-if="column.key === 'action'">
                    <a-button type="link" danger size="small" @click="removeVariable(index)">
                      删除
                    </a-button>
                  </template>
                </template>
              </a-table>
              <div style="margin-top: 12px; text-align: right">
                <a-button type="primary" :loading="saving" @click="handleSaveVars">
                  保存变量
                </a-button>
              </div>
            </a-spin>
          </template>
        </a-card>
      </div>
    </a-spin>

    <!-- Create/Edit modal -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingEnv ? '编辑环境' : '新建环境'"
      :confirm-loading="envSaving"
      @ok="handleSaveEnv"
      @cancel="resetEnvForm"
    >
      <a-form :label-col="{ span: 5 }">
        <a-form-item label="名称">
          <a-input v-model:value="envForm.name" placeholder="如：开发环境、测试环境" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="envForm.description" :rows="3" placeholder="环境说明（可选）" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { projectApi, environmentApi } from '@/api'

// -- Project selection --
const projects = ref<any[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const selectedProjectId = ref<number | null>(null)

// -- Environment list --
const environments = ref<any[]>([])
const selectedEnvId = ref<number | null>(null)
const selectedEnv = ref<any>(null)
const loading = ref(false)

// -- Variable editor --
const editingVars = ref<Array<{ key: string; value: string; is_secret: boolean; _idx: number; _wasSecret: boolean }>>([])
const varsLoading = ref(false)
const saving = ref(false)
const envSaving = ref(false)
let varIdx = 0

const varColumns = [
  { title: '变量名', key: 'key', dataIndex: 'key', width: '30%' },
  { title: '变量值', key: 'value', dataIndex: 'value', width: '35%' },
  { title: '加密', key: 'is_secret', dataIndex: 'is_secret', width: '15%' },
  { title: '操作', key: 'action', width: '20%' },
]

// -- Create/Edit env form --
const showCreateModal = ref(false)
const editingEnv = ref<any>(null)
const envForm = ref({ name: '', description: '' })

onMounted(async () => {
  try {
    const list = await projectApi.list()
    projects.value = list
    projectOptions.value = list.map((p: any) => ({ label: p.name, value: p.id }))
  } catch (e: any) {
    message.error(e ?? '加载项目失败')
  }
})

async function onProjectChange() {
  selectedEnvId.value = null
  selectedEnv.value = null
  editingVars.value = []
  await loadEnvironments()
}

async function loadEnvironments() {
  if (!selectedProjectId.value) return
  loading.value = true
  try {
    environments.value = await environmentApi.list(selectedProjectId.value)
  } catch (e: any) {
    message.error(e ?? '加载环境列表失败')
  } finally {
    loading.value = false
  }
}

async function selectEnv(env: any) {
  selectedEnvId.value = env.id
  selectedEnv.value = env
  await loadVariables()
}

async function loadVariables() {
  if (!selectedEnvId.value) return
  varsLoading.value = true
  try {
    const vars = await environmentApi.getVariables(selectedEnvId.value)
    editingVars.value = vars.map((v: any) => ({
      key: v.key,
      value: v.is_secret ? '' : v.value,
      is_secret: v.is_secret,
      _idx: varIdx++,
      _wasSecret: v.is_secret,
    }))
  } catch (e: any) {
    message.error(e ?? '加载变量失败')
  } finally {
    varsLoading.value = false
  }
}

function addVariable() {
  editingVars.value = [
    ...editingVars.value,
    { key: '', value: '', is_secret: false, _idx: varIdx++, _wasSecret: false },
  ]
}

function removeVariable(index: number) {
  editingVars.value = editingVars.value.filter((_, i) => i !== index)
}

async function handleSaveVars() {
  if (!selectedEnvId.value) return
  const variables = editingVars.value
    .filter((v) => v.key.trim() !== '')
    .map((v) => ({ key: v.key.trim(), value: v.value, is_secret: v.is_secret }))

  // Check duplicate keys
  const keys = variables.map((v) => v.key)
  const duplicates = keys.filter((k, i) => keys.indexOf(k) !== i)
  if (duplicates.length > 0) {
    message.warning(`存在重复的变量名: ${[...new Set(duplicates)].join(', ')}`)
    return
  }

  // Warn about empty secret values
  const emptySecrets = editingVars.value.filter(
    (v) => v.is_secret && v._wasSecret && v.value.trim() === '' && v.key.trim() !== ''
  )
  if (emptySecrets.length > 0) {
    message.warning(`${emptySecrets.length} 个密钥变量值为空，请重新输入密钥值后再保存`)
    return
  }

  saving.value = true
  try {
    await environmentApi.saveVariables(selectedEnvId.value, { variables })
    message.success('变量已保存')
    await loadVariables()
  } catch (e: any) {
    message.error(e ?? '保存变量失败')
  } finally {
    saving.value = false
  }
}

// -- Environment CRUD --
function openEditModal(env: any) {
  editingEnv.value = env
  envForm.value = { name: env.name, description: env.description || '' }
  showCreateModal.value = true
}

function resetEnvForm() {
  editingEnv.value = null
  envForm.value = { name: '', description: '' }
}

async function handleSaveEnv() {
  if (!envForm.value.name.trim()) {
    message.warning('请输入环境名称')
    return
  }

  envSaving.value = true
  try {
    if (editingEnv.value) {
      await environmentApi.update(editingEnv.value.id, {
        name: envForm.value.name.trim(),
        description: envForm.value.description.trim() || undefined,
      })
      message.success('环境已更新')
    } else {
      await environmentApi.create({
        name: envForm.value.name.trim(),
        description: envForm.value.description.trim() || undefined,
        project_id: selectedProjectId.value!,
      })
      message.success('环境已创建')
    }
    showCreateModal.value = false
    resetEnvForm()
    await loadEnvironments()
    // Refresh selectedEnv if it was the one being edited
    if (selectedEnvId.value) {
      const updated = environments.value.find((e: any) => e.id === selectedEnvId.value)
      if (updated) {
        selectedEnv.value = updated
      }
    }
  } catch (e: any) {
    message.error(e ?? '保存环境失败')
  } finally {
    envSaving.value = false
  }
}

async function handleDeleteEnv(id: number) {
  try {
    await environmentApi.delete(id)
    message.success('环境已删除')
    if (selectedEnvId.value === id) {
      selectedEnvId.value = null
      selectedEnv.value = null
      editingVars.value = []
    }
    await loadEnvironments()
  } catch (e: any) {
    message.error(e ?? '删除环境失败')
  }
}
</script>
