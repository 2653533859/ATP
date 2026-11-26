<template>
  <div class="page-shell account-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('account.title') }}</h2>
      </div>
      <div v-if="auth.user" class="account-badges">
        <a-tag color="blue">{{ t('account.role') }}：{{ t(`user_management.roles.${auth.user.role || 'tester'}`) }}</a-tag>
        <a-tag :color="auth.user.is_active === false ? 'default' : 'green'">
          {{ t('account.status') }}：{{ auth.user.is_active === false ? t('common.disabled') : t('common.enabled') }}
        </a-tag>
      </div>
    </div>

    <a-alert
      class="account-hint"
      type="info"
      show-icon
      :message="t('account.self_manage_hint')"
    />

    <a-card class="account-card" :bordered="false">
      <a-form :model="form" layout="vertical" @finish="handleSave">
        <a-form-item :label="t('account.username')" required>
          <a-input v-model:value="form.username" autocomplete="username" />
        </a-form-item>
        <a-form-item :label="t('account.email')" required>
          <a-input v-model:value="form.email" type="email" autocomplete="email" />
        </a-form-item>

        <a-divider orientation="left">{{ t('account.password_section') }}</a-divider>
        <a-form-item :label="t('account.current_password')" required>
          <a-input-password v-model:value="form.current_password" autocomplete="current-password" />
        </a-form-item>
        <a-form-item :label="t('account.new_password')">
          <a-input-password
            v-model:value="form.new_password"
            :placeholder="t('account.new_password_placeholder')"
            autocomplete="new-password"
          />
        </a-form-item>
        <a-form-item v-if="form.new_password" :label="t('account.confirm_password')" required>
          <a-input-password v-model:value="form.confirm_password" autocomplete="new-password" />
        </a-form-item>

        <div class="account-actions">
          <a-button type="primary" html-type="submit" :loading="saving">
            {{ t('common.save') }}
          </a-button>
        </div>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { authApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const saving = ref(false)
const form = reactive({
  username: '',
  email: '',
  current_password: '',
  new_password: '',
  confirm_password: '',
})

watch(
  () => auth.user,
  (user) => {
    if (user) {
      form.username = user.username
      form.email = user.email
    }
  },
  { immediate: true },
)

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  return typeof error === 'string' ? error : t('account.save_failed')
}

async function handleSave() {
  if (!form.username.trim() || !form.email.trim() || !form.current_password) {
    message.warning(t('account.required_hint'))
    return
  }
  if (form.new_password && form.new_password !== form.confirm_password) {
    message.warning(t('account.password_mismatch'))
    return
  }

  saving.value = true
  try {
    await authApi.updateMe({
      current_password: form.current_password,
      username: form.username.trim(),
      email: form.email.trim(),
      ...(form.new_password ? { new_password: form.new_password } : {}),
    })
    await auth.fetchMe()
    form.current_password = ''
    form.new_password = ''
    form.confirm_password = ''
    message.success(t('account.saved'))
  } catch (error: unknown) {
    message.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.account-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.account-hint {
  max-width: 640px;
  margin-bottom: 16px;
}

.account-card {
  max-width: 640px;
}

.account-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
