<template>
  <div>
    <div class="page-header">
      <h2>项目列表</h2>
      <a-button type="primary" @click="openCreate">新建项目</a-button>
    </div>

    <a-spin :spinning="loading">
      <a-row :gutter="[16, 16]">
        <a-col v-for="p in projects" :key="p.id" :span="8">
          <a-card hoverable :title="p.name" @click="router.push({ name: 'cases', query: { project_id: String(p.id) } })">
            <p>{{ p.description || '暂无描述' }}</p>
            <p style="color: #888; font-size: 12px">
              AI 模型：{{ llmConfigLabel(p.ai_llm_config_id) }}
            </p>
            <template #extra>
              <a-button type="link" @click.stop="openEdit(p)">编辑</a-button>
              <a-button type="link" danger @click.stop="handleDelete(p.id)">删除</a-button>
            </template>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>

    <a-modal
      v-model:open="showModal"
      :title="editingId ? '编辑项目' : '新建项目'"
      :confirm-loading="saving"
      :mask-closable="!saving"
      :keyboard="!saving"
      @ok="handleSave"
      @cancel="handleCancel"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item label="项目名称" required>
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="3" />
        </a-form-item>
        <a-form-item label="AI 模型配置">
          <a-select
            v-model:value="form.ai_llm_config_id"
            placeholder="不绑定 AI 模型"
            allow-clear
            :options="llmOptions"
          />
          <span style="color: #888; font-size: 12px">
            选择后，本项目可使用 AI 用例生成（在系统管理 → AI 模型配置中维护）
          </span>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { aiLLMConfigApi, projectApi, type AILLMConfigItem, type ProjectItem } from '@/api'
import { getProjectErrorMessage } from './project-errors'

const router = useRouter()
const projects = ref<ProjectItem[]>([])
const llmConfigs = ref<AILLMConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)
const showModal = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<{
  name: string
  description: string
  ai_llm_config_id: number | null
}>({ name: '', description: '', ai_llm_config_id: null })

const llmOptions = computed(() =>
  llmConfigs.value
    .filter((c) => c.enabled)
    .map((c) => ({ label: `${c.name} (${c.provider}/${c.model_name})`, value: c.id })),
)

const llmNameMap = computed(() => {
  const map = new Map<number, string>()
  llmConfigs.value.forEach((c) => map.set(c.id, c.name))
  return map
})

function llmConfigLabel(id?: number | null): string {
  if (id == null) return '未绑定'
  return llmNameMap.value.get(id) ?? `#${id}`
}

async function loadProjects() {
  loading.value = true
  try {
    projects.value = await projectApi.list()
  } catch (error) {
    message.error(getProjectErrorMessage(error, '加载项目列表失败'))
  } finally {
    loading.value = false
  }
}

async function loadLLMConfigs() {
  try {
    llmConfigs.value = await aiLLMConfigApi.list()
  } catch (error: any) {
    // 非管理员调用会 403，静默处理：编辑表单仍能保存（仅看不到下拉）
    if (error?.response?.status !== 403) {
      message.error('加载 AI 模型配置失败')
    }
  }
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.description = ''
  form.ai_llm_config_id = null
}

function openCreate() {
  resetForm()
  showModal.value = true
}

function openEdit(project: ProjectItem) {
  editingId.value = project.id
  form.name = project.name
  form.description = project.description ?? ''
  form.ai_llm_config_id = project.ai_llm_config_id ?? null
  showModal.value = true
}

function handleCancel() {
  if (saving.value) return
  showModal.value = false
  resetForm()
}

async function handleSave() {
  if (saving.value) return
  if (!form.name.trim()) {
    message.warning('请输入项目名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await projectApi.update(editingId.value, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        ai_llm_config_id: form.ai_llm_config_id,
      })
      message.success('已更新')
    } else {
      await projectApi.create({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        ai_llm_config_id: form.ai_llm_config_id,
      })
      message.success('创建成功')
    }
    showModal.value = false
    resetForm()
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, '保存项目失败'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await projectApi.delete(id)
    message.success('已删除')
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, '删除项目失败'))
  }
}

onMounted(() => {
  loadProjects()
  loadLLMConfigs()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
</style>
