<template>
  <div class="page-shell system-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('user_management.title') }}</h2>
        <div class="page-subtitle">{{ t('user_management.subtitle') }}</div>
      </div>
      <a-button type="primary" @click="openCreate">
        <PlusOutlined /> {{ t('user_management.create') }}
      </a-button>
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
          <template v-if="column.key === 'role'">
            <a-tag>{{ roleLabel(record.role) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'is_active'">
            <a-tag :color="record.is_active ? 'green' : 'default'">
              {{ record.is_active ? t('common.enabled') : t('common.disabled') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(asUser(record))">
              {{ t('common.edit') }}
            </a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? t('user_management.edit') : t('user_management.create')"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('user_management.username')" required>
          <a-input v-model:value="form.username" autocomplete="username" />
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
          <a-select v-model:value="form.role" style="width: 100%">
            <a-select-option value="admin">{{ roleLabel('admin') }}</a-select-option>
            <a-select-option value="engineer">{{ roleLabel('engineer') }}</a-select-option>
            <a-select-option value="tester">{{ roleLabel('tester') }}</a-select-option>
            <a-select-option value="viewer">{{ roleLabel('viewer') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('user_management.status')">
          <a-switch v-model:checked="form.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { userApi, type AdminUserItem } from '@/api'

const { t } = useI18n()
const asUser = (record: unknown) => record as AdminUserItem
const users = ref<AdminUserItem[]>([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const editing = ref<AdminUserItem | null>(null)
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
  { title: t('common.actions'), key: 'action', width: 90 },
])

function roleLabel(role: string) {
  return t(`user_management.roles.${role}`)
}

function resetForm() {
  form.username = ''
  form.email = ''
  form.password = ''
  form.role = 'tester'
  form.is_active = true
}

function openCreate() {
  editing.value = null
  resetForm()
  modalOpen.value = true
}

function openEdit(user: AdminUserItem) {
  editing.value = user
  form.username = user.username
  form.email = user.email
  form.password = ''
  form.role = user.role
  form.is_active = user.is_active
  modalOpen.value = true
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  return typeof error === 'string' ? error : t('user_management.save_failed')
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
      await userApi.update(editing.value.id, {
        username: form.username.trim(),
        email: form.email.trim(),
        role: form.role,
        is_active: form.is_active,
        ...(form.password ? { password: form.password } : {}),
      })
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

onMounted(loadUsers)
</script>
