<template>
  <a-drawer
    :open="open"
    :title="t('project_members.title', { name: projectName ?? '' })"
    width="640"
    :destroy-on-close="true"
    @close="emit('close')"
  >
    <a-space style="margin-bottom: 12px" wrap>
      <a-input-search
        v-model:value="newMemberQuery"
        :placeholder="t('project_members.add_placeholder')"
        style="width: 260px"
        :loading="searching"
        allow-clear
        @search="onSearchUser"
      />
      <a-select v-model:value="newMemberRole" style="width: 120px">
        <a-select-option value="viewer">viewer</a-select-option>
        <a-select-option value="editor">editor</a-select-option>
        <a-select-option value="owner">owner</a-select-option>
      </a-select>
      <a-button type="primary" :disabled="!candidateUser" :loading="adding" @click="onAddMember">
        {{ t('project_members.add_btn') }}
      </a-button>
    </a-space>
    <div v-if="candidateUser" style="margin-bottom: 8px; color: #666">
      {{ t('project_members.candidate_hint', { username: candidateUser.username, id: candidateUser.id }) }}
    </div>

    <a-table
      :columns="columns"
      :data-source="members"
      :loading="loading"
      :pagination="false"
      row-key="id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'role'">
          <a-select
            :value="record.role"
            style="width: 110px"
            :disabled="record.user_id === currentUserId && record.role === 'owner'"
            @change="(val: string) => onUpdateRole(record, val)"
          >
            <a-select-option value="viewer">viewer</a-select-option>
            <a-select-option value="editor">editor</a-select-option>
            <a-select-option value="owner">owner</a-select-option>
          </a-select>
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-popconfirm
            :title="t('project_members.remove_confirm', { username: record.username })"
            :ok-text="t('common.delete')"
            :cancel-text="t('common.cancel')"
            @confirm="onRemoveMember(record)"
          >
            <a-button size="small" type="link" danger>{{ t('common.delete') }}</a-button>
          </a-popconfirm>
        </template>
        <template v-else-if="column.dataIndex === 'created_at'">
          {{ record.created_at?.slice(0, 19).replace('T', ' ') }}
        </template>
      </template>
    </a-table>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { projectMemberApi, type ProjectMemberItem, type ProjectRoleType } from '@/api'
import { useAuthStore } from '@/stores/auth'
import http from '@/api/http'

const props = defineProps<{
  open: boolean
  projectId: number | null
  projectName?: string | null
}>()
const emit = defineEmits<{ close: []; updated: [] }>()

const { t } = useI18n()
const auth = useAuthStore()
const currentUserId = computed(() => auth.user?.id ?? -1)

const members = ref<ProjectMemberItem[]>([])
const loading = ref(false)
const adding = ref(false)
const searching = ref(false)
const newMemberQuery = ref('')
const newMemberRole = ref<ProjectRoleType>('viewer')
const candidateUser = ref<{ id: number; username: string } | null>(null)

const columns = computed(() => [
  { title: t('project_members.col.username'), dataIndex: 'username', key: 'username' },
  { title: t('project_members.col.email'), dataIndex: 'email', key: 'email' },
  { title: t('project_members.col.role'), dataIndex: 'role', key: 'role', width: 130 },
  { title: t('project_members.col.joined'), dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: t('project_members.col.actions'), dataIndex: 'actions', key: 'actions', width: 80 },
])

type ErrorLike = {
  response?: {
    data?: {
      detail?: unknown
    }
  }
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
  }
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return fallback
}

async function loadMembers() {
  if (!props.projectId) return
  loading.value = true
  try {
    members.value = await projectMemberApi.list(props.projectId)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('project_members.load_failed')))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      candidateUser.value = null
      newMemberQuery.value = ''
      newMemberRole.value = 'viewer'
      loadMembers()
    }
  },
)

async function onSearchUser(q: string) {
  if (!q.trim()) {
    candidateUser.value = null
    return
  }
  searching.value = true
  try {
    // 按 username 精确匹配（后端 GET /users?username=xxx；若没有则提示）
    const result = await http.get<unknown, { id: number; username: string }[]>('/users', {
      params: { username: q.trim() },
    })
    if (Array.isArray(result) && result.length > 0) {
      candidateUser.value = { id: result[0].id, username: result[0].username }
    } else if (/^\d+$/.test(q.trim())) {
      // 直接传 ID
      candidateUser.value = { id: Number(q.trim()), username: `#${q.trim()}` }
    } else {
      candidateUser.value = null
      message.warning(t('project_members.user_not_found'))
    }
  } catch {
    // 兼容后端无 /users 列表时：允许直接输入用户 ID
    if (/^\d+$/.test(q.trim())) {
      candidateUser.value = { id: Number(q.trim()), username: `#${q.trim()}` }
    } else {
      message.warning(t('project_members.use_user_id'))
    }
  } finally {
    searching.value = false
  }
}

async function onAddMember() {
  if (!props.projectId || !candidateUser.value) return
  adding.value = true
  try {
    await projectMemberApi.add(props.projectId, {
      user_id: candidateUser.value.id,
      role: newMemberRole.value,
    })
    message.success(t('project_members.add_success'))
    candidateUser.value = null
    newMemberQuery.value = ''
    await loadMembers()
    emit('updated')
  } catch (e: unknown) {
    message.error(errorMessage(e, t('project_members.add_failed')))
  } finally {
    adding.value = false
  }
}

async function onUpdateRole(record: ProjectMemberItem, role: string) {
  if (!props.projectId) return
  try {
    await projectMemberApi.update(props.projectId, record.user_id, role as ProjectRoleType)
    record.role = role as ProjectRoleType
    message.success(t('project_members.update_success'))
    emit('updated')
  } catch (e: unknown) {
    message.error(errorMessage(e, t('project_members.update_failed')))
  }
}

async function onRemoveMember(record: ProjectMemberItem) {
  if (!props.projectId) return
  try {
    await projectMemberApi.remove(props.projectId, record.user_id)
    message.success(t('project_members.remove_success'))
    await loadMembers()
    emit('updated')
  } catch (e: unknown) {
    message.error(errorMessage(e, t('project_members.remove_failed')))
  }
}
</script>
