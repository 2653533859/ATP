<template>
  <div class="page-shell system-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('user_management.title') }}</h2>
      </div>
      <div class="user-management-actions">
        <a-button @click="openDefaultPassword">{{ t('user_management.set_default_password') }}</a-button>
        <a-button type="primary" @click="openCreate">
          <PlusOutlined /> {{ t('user_management.create') }}
        </a-button>
      </div>
    </div>

    <div class="page-toolbar">
      <a-input-search
        v-model:value="keyword"
        allow-clear
        :placeholder="t('user_management.search_placeholder')"
        style="width: 280px"
        @search="loadUsers"
      />
      <a-button @click="loadUsers">{{ t('common.refresh') }}</a-button>
    </div>

    <a-card class="table-panel" :bordered="false">
      <a-table :data-source="users" :columns="columns" :loading="loading" row-key="id" :pagination="{ pageSize: 20 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'username'">
            <div class="username-cell">
              <span>{{ record.username }}</span>
              <a-tag v-if="isSelf(asUser(record))" color="blue">{{ t('user_management.current_account') }}</a-tag>
            </div>
          </template>
          <template v-else-if="column.key === 'role'">
            <a-tag>{{ roleLabel(record.role) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'is_active'">
            <a-tag :color="record.is_active ? 'green' : 'default'">
              {{ record.is_active ? t('common.enabled') : t('common.disabled') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space size="small">
              <a-button type="link" size="small" @click="openEdit(asUser(record))">
                {{ t('common.edit') }}
              </a-button>
              <a-tooltip v-if="deleteDisabledReason(asUser(record))" :title="deleteDisabledReason(asUser(record))">
                <a-button type="link" size="small" danger disabled>
                  {{ t('common.delete') }}
                </a-button>
              </a-tooltip>
              <a-popconfirm
                v-else
                :title="t('user_management.delete_confirm_title', { username: record.username })"
                :description="t('user_management.delete_confirm_desc')"
                :ok-text="t('common.delete')"
                :cancel-text="t('common.cancel')"
                ok-type="danger"
                @confirm="handleDelete(asUser(record))"
              >
                <a-button type="link" size="small" danger :loading="deletingId === record.id">
                  {{ t('common.delete') }}
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="defaultPasswordOpen"
      :title="t('user_management.set_default_password')"
      :confirm-loading="defaultPasswordSaving"
      @ok="saveDefaultPassword"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('user_management.new_default_password')" :help="t('user_management.default_password_hint')" required>
          <a-input-password v-model:value="defaultPassword" v-model:visible="defaultPasswordVisible" autocomplete="new-password" :minlength="8" :maxlength="128" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? t('user_management.edit') : t('user_management.create')"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-alert
        v-if="editingSelf"
        type="info"
        show-icon
        :message="t('user_management.self_edit_hint')"
        style="margin-bottom: 16px"
      />
      <a-form layout="vertical">
        <a-form-item :label="t('user_management.username')" required>
          <a-input v-model:value="form.username" autocomplete="username" :disabled="editingSelf" />
        </a-form-item>
        <a-form-item :label="t('user_management.email')" required>
          <a-input v-model:value="form.email" type="email" autocomplete="email" />
        </a-form-item>
        <a-form-item
          :label="editing ? t('user_management.password_optional') : t('user_management.password')"
          :help="t('user_management.password_hint')"
          :required="!editing"
        >
          <a-input-password
            v-model:value="form.password"
            autocomplete="new-password"
            :minlength="8"
            :maxlength="128"
          />
        </a-form-item>
        <a-form-item :label="t('user_management.role')" required>
          <a-select v-model:value="form.role" style="width: 100%" :disabled="editingSelf">
            <a-select-option value="admin">{{ roleLabel('admin') }}</a-select-option>
            <a-select-option value="engineer">{{ roleLabel('engineer') }}</a-select-option>
            <a-select-option value="tester">{{ roleLabel('tester') }}</a-select-option>
            <a-select-option value="viewer">{{ roleLabel('viewer') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('user_management.status')">
          <a-switch v-model:checked="form.is_active" :disabled="editingSelf" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="deleteConflictOpen"
      :title="t('user_management.delete_conflict_title')"
    >
      <a-alert type="warning" show-icon :message="conflictDetail" style="margin-bottom: 12px" />
      <p v-if="conflictUser && !conflictUser.is_active" class="muted-text">
        {{ t('user_management.delete_conflict_already_disabled') }}
      </p>
      <template #footer>
        <a-button @click="deleteConflictOpen = false">{{ t('common.cancel') }}</a-button>
        <a-button
          v-if="conflictUser?.is_active"
          type="primary"
          danger
          :loading="disablingConflict"
          @click="disableConflictUser"
        >
          {{ t('user_management.disable_instead') }}
        </a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { userApi, type AdminUserItem } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { extractApiError } from '@/utils/apiError'

const { t } = useI18n()
const auth = useAuthStore()
const asUser = (record: unknown) => record as AdminUserItem
const users = ref<AdminUserItem[]>([])
const loading = ref(false)
const saving = ref(false)
const deletingId = ref<number | null>(null)
const modalOpen = ref(false)
const editing = ref<AdminUserItem | null>(null)
const defaultPasswordOpen = ref(false)
const defaultPasswordSaving = ref(false)
const defaultPassword = ref('')
const defaultPasswordVisible = ref(true)
const deleteConflictOpen = ref(false)
const conflictUser = ref<AdminUserItem | null>(null)
const conflictDetail = ref('')
const disablingConflict = ref(false)
let defaultPasswordRequest = 0
let initialPasswordRequest = 0
const keyword = ref('')
const form = reactive({
  username: '',
  email: '',
  password: '',
  role: 'tester' as AdminUserItem['role'],
  is_active: true,
})

const columns = computed(() => [
  { title: t('user_management.username'), dataIndex: 'username', key: 'username' },
  { title: t('user_management.email'), dataIndex: 'email', key: 'email' },
  { title: t('user_management.role'), dataIndex: 'role', key: 'role', width: 130 },
  { title: t('user_management.status'), dataIndex: 'is_active', key: 'is_active', width: 100 },
  { title: t('common.actions'), key: 'action', width: 150 },
])

const activeAdminCount = computed(() => users.value.filter((item) => item.role === 'admin' && item.is_active).length)
const editingSelf = computed(() => Boolean(editing.value && isSelf(editing.value)))

function isSelf(user: AdminUserItem): boolean {
  return Boolean(auth.user?.id && user.id === auth.user.id)
}

function isLastActiveAdmin(user: AdminUserItem): boolean {
  return user.role === 'admin' && user.is_active && activeAdminCount.value <= 1
}

function deleteDisabledReason(user: AdminUserItem): string {
  if (isSelf(user)) return t('user_management.cannot_delete_self')
  if (isLastActiveAdmin(user)) return t('user_management.cannot_delete_last_admin')
  return ''
}

function roleLabel(role: string) {
  return t(`user_management.roles.${role}`)
}

async function openDefaultPassword() {
  const request = ++defaultPasswordRequest
  defaultPassword.value = ''
  defaultPasswordVisible.value = true
  defaultPasswordOpen.value = true
  try {
    const { password } = await userApi.initialPassword()
    if (request === defaultPasswordRequest && defaultPasswordOpen.value && !defaultPassword.value) {
      defaultPassword.value = password
    }
  } catch {
    if (request === defaultPasswordRequest && defaultPasswordOpen.value) {
      message.warning(t('user_management.default_password_unavailable'))
    }
  }
}

async function saveDefaultPassword() {
  if (defaultPassword.value.length < 8 || defaultPassword.value.length > 128) {
    message.warning(t('user_management.default_password_length'))
    return
  }
  defaultPasswordSaving.value = true
  try {
    await userApi.updateInitialPassword(defaultPassword.value)
    defaultPassword.value = ''
    defaultPasswordOpen.value = false
    message.success(t('user_management.default_password_saved'))
  } catch (error: unknown) {
    message.error(errorMessage(error))
  } finally {
    defaultPasswordSaving.value = false
  }
}

function resetForm() {
  form.username = ''
  form.email = ''
  form.password = ''
  form.role = 'tester'
  form.is_active = true
}

async function openCreate() {
  const request = ++initialPasswordRequest
  editing.value = null
  resetForm()
  modalOpen.value = true
  try {
    const { password } = await userApi.initialPassword()
    if (request === initialPasswordRequest && modalOpen.value && !editing.value && !form.password) {
      form.password = password
    }
  } catch {
    if (request === initialPasswordRequest && modalOpen.value && !editing.value) {
      message.warning(t('user_management.default_password_unavailable'))
    }
  }
}

function openEdit(user: AdminUserItem) {
  initialPasswordRequest++
  editing.value = user
  form.username = user.username
  form.email = user.email
  form.password = ''
  form.role = user.role
  form.is_active = user.is_active
  modalOpen.value = true
}

function errorMessage(error: unknown, fallback = t('user_management.save_failed')) {
  return extractApiError(error, fallback)
}

async function loadUsers() {
  loading.value = true
  try {
    users.value = await userApi.list(keyword.value.trim() || undefined)
  } catch (error: unknown) {
    message.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!form.username.trim() || !form.email.trim() || (!editing.value && !form.password)) {
    message.warning(t('user_management.required_hint'))
    return
  }
  if (form.password && form.password.length < 8) {
    message.warning(t('user_management.password_too_short'))
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      const payload = editingSelf.value
        ? {
            email: form.email.trim(),
            ...(form.password ? { password: form.password } : {}),
          }
        : {
            username: form.username.trim(),
            email: form.email.trim(),
            role: form.role,
            is_active: form.is_active,
            ...(form.password ? { password: form.password } : {}),
          }
      await userApi.update(editing.value.id, payload)
    } else {
      await userApi.create({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        is_active: form.is_active,
      })
    }
    message.success(t('user_management.saved'))
    modalOpen.value = false
    await loadUsers()
  } catch (error: unknown) {
    message.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function handleDelete(user: AdminUserItem) {
  const disabledReason = deleteDisabledReason(user)
  if (disabledReason) {
    message.warning(disabledReason)
    return
  }
  deletingId.value = user.id
  try {
    await userApi.delete(user.id)
    message.success(t('user_management.deleted'))
    await loadUsers()
  } catch (error: unknown) {
    const detail = errorMessage(error, t('user_management.delete_failed'))
    if (detail.includes('关联') || detail.includes('禁用账号')) {
      conflictUser.value = user
      conflictDetail.value = detail
      deleteConflictOpen.value = true
    } else {
      message.error(detail)
    }
  } finally {
    deletingId.value = null
  }
}

async function disableConflictUser() {
  const target = conflictUser.value
  if (!target) return
  disablingConflict.value = true
  try {
    await userApi.update(target.id, { is_active: false })
    message.success(t('user_management.disabled_success', { username: target.username }))
    deleteConflictOpen.value = false
    await loadUsers()
  } catch (error: unknown) {
    message.error(errorMessage(error))
  } finally {
    disablingConflict.value = false
  }
}

onMounted(() => {
  if (auth.user?.role && auth.user.role !== 'admin') return
  void loadUsers()
})
</script>

<style scoped>
.user-management-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.username-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
</style>
