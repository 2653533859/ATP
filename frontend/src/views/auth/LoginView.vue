<template>
  <div class="login-wrapper">
    <a-card class="login-card" :title="t('login.title')">
      <a-form :model="form" @finish="onFinish" layout="vertical">
        <a-form-item name="username" :rules="[{ required: true, message: t('login.required_username') }]">
          <a-input v-model:value="form.username" :placeholder="t('login.username')" size="large">
            <template #prefix><UserOutlined /></template>
          </a-input>
        </a-form-item>
        <a-form-item name="password" :rules="[{ required: true, message: t('login.required_password') }]">
          <a-input-password v-model:value="form.password" :placeholder="t('login.password')" size="large">
            <template #prefix><LockOutlined /></template>
          </a-input-password>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="loading" block size="large">
            {{ t('login.submit') }}
          </a-button>
        </a-form-item>
      </a-form>
      <div class="lang-switch">
        <a-radio-group
          :value="currentLocale"
          size="small"
          button-style="solid"
          @change="onLocaleRadioChange"
        >
          <a-radio-button value="zh-CN">{{ t('lang.zh') }}</a-radio-button>
          <a-radio-button value="en-US">{{ t('lang.en') }}</a-radio-button>
        </a-radio-group>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { UserOutlined, LockOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { getLocale, setLocale, type SupportedLocale } from '@/locales'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()

const loading = ref(false)
const form = reactive({ username: '', password: '' })

const currentLocale = computed<SupportedLocale>(() => getLocale())

function onLocaleChange(value: SupportedLocale) {
  setLocale(value)
}

function onLocaleRadioChange(event: Event) {
  const target = event.target as HTMLInputElement | null
  if (target?.value === 'zh-CN' || target?.value === 'en-US') {
    onLocaleChange(target.value)
  }
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

async function onFinish() {
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    const redirect = (route.query.redirect as string) || '/'
    await router.push(redirect)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('login.failed')))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f0f2f5;
}
.login-card {
  width: 400px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
}
.lang-switch {
  margin-top: 8px;
  text-align: center;
}
</style>
