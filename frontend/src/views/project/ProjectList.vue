<template>
  <div>
    <div class="page-header">
      <h2>项目列表</h2>
      <a-button type="primary" @click="showCreate = true">新建项目</a-button>
    </div>

    <a-spin :spinning="loading">
      <a-row :gutter="[16, 16]">
        <a-col v-for="p in projects" :key="p.id" :span="8">
          <a-card hoverable :title="p.name" @click="router.push({ name: 'cases', query: { project_id: String(p.id) } })">
            <p>{{ p.description || '暂无描述' }}</p>
            <template #extra>
              <a-button type="link" danger @click.stop="handleDelete(p.id)">删除</a-button>
            </template>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>

    <a-modal v-model:open="showCreate" title="新建项目" @ok="handleCreate">
      <a-form :model="form" layout="vertical">
        <a-form-item label="项目名称" required>
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { projectApi } from '@/api'

const router = useRouter()
const projects = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const form = reactive({ name: '', description: '' })

async function loadProjects() {
  loading.value = true
  try {
    projects.value = await projectApi.list()
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.name.trim()) { message.warning('请输入项目名称'); return }
  await projectApi.create({ name: form.name, description: form.description })
  message.success('创建成功')
  showCreate.value = false
  form.name = ''
  form.description = ''
  await loadProjects()
}

async function handleDelete(id: number) {
  await projectApi.delete(id)
  message.success('已删除')
  await loadProjects()
}

onMounted(loadProjects)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
</style>
