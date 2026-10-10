<template>
  <section class="request-console" aria-label="HTTP request console">
    <header class="console-heading">
      <div class="request-identity">
        <h2>{{ caseDetail?.name || t('api_workbench.console.untitled') }}</h2>
        <span v-if="caseDetail" class="request-code">{{ caseDetail.case_code }}</span>
      </div>
      <div class="heading-actions">
        <a-button v-if="caseDetail" @click="emit('detail')">{{ t('common.view_detail') }}</a-button>
        <a-button v-if="caseDetail" :disabled="!canModify" @click="emit('edit')">{{ t('api_workbench.console.advanced_edit') }}</a-button>
        <a-button v-if="caseDetail" :disabled="!canModify || !caseDetail.is_ready_for_execution" @click="emit('run')">{{ t('api_workbench.console.run_case') }}</a-button>
        <a-button :disabled="!canModify" :title="!moduleId ? t('api_workbench.select_module_first') : undefined" @click="saveDraft">
          {{ t('api_workbench.console.save_as_case') }}
        </a-button>
      </div>
    </header>

    <div class="request-line">
      <a-select v-model:value="draft.method" class="method-select" :aria-label="t('api_workbench.console.method')">
        <a-select-option v-for="method in methods" :key="method" :value="method">{{ method }}</a-select-option>
      </a-select>
      <a-input v-model:value="draft.url" class="url-input" :placeholder="t('api_workbench.console.url_placeholder')" @pressEnter="sendRequest" />
      <a-dropdown :trigger="['click']">
        <template #overlay>
          <a-menu @click="handleApplyRequestTemplate">
            <a-menu-item key="rest_json_get">
              <div class="preset-menu-item">
                <span class="preset-label">📋 标准 REST 查询 (GET + Accept JSON)</span>
                <small class="preset-code">仅配置 GET 方式、Accept 请求头与分页参数</small>
              </div>
            </a-menu-item>
            <a-menu-item key="jwt_form_login">
              <div class="preset-menu-item">
                <span class="preset-label">🔑 表单登录获取 Token (POST + urlencoded)</span>
                <small class="preset-code">仅配置 POST、urlencoded 头与表单凭据</small>
              </div>
            </a-menu-item>
            <a-menu-item key="auth_json_post">
              <div class="preset-menu-item">
                <span class="preset-label">🛡️ 鉴权业务调用 (POST + Bearer Token)</span>
                <small class="preset-code">仅配置 POST、JSON 头、Authorization 头与 Body</small>
              </div>
            </a-menu-item>
            <a-menu-item key="healthcheck_get">
              <div class="preset-menu-item">
                <span class="preset-label">🩺 服务探活配置 (GET)</span>
                <small class="preset-code">仅配置 GET 方式</small>
              </div>
            </a-menu-item>
          </a-menu>
        </template>
        <a-button class="template-quick-btn" :title="t('api_scenario.request_template_label')">
          <ThunderboltOutlined />
        </a-button>
      </a-dropdown>
      <a-button v-if="sending" class="cancel-button" @click="cancelRequest">{{ t('api_workbench.console.cancel') }}</a-button>
      <a-button type="primary" class="send-button" :loading="sending" :disabled="!canModify || !draft.url.trim()" @click="sendRequest">
        {{ t('api_workbench.console.send') }}
      </a-button>
    </div>

    <div class="request-section-heading">
      <span>{{ t('api_workbench.console.request_options') }}</span>
    </div>
    <a-tabs v-model:activeKey="requestTab" class="request-tabs" size="small">
      <a-tab-pane key="params" :tab="t('api_workbench.console.params')"><KvEditor v-model:value="draft.params" preset-kind="params" /></a-tab-pane>
      <a-tab-pane key="headers" :tab="t('api_workbench.console.headers')"><KvEditor v-model:value="draft.headers" preset-kind="headers" /></a-tab-pane>
      <a-tab-pane key="body" :tab="t('api_workbench.console.body')">
        <div class="body-header-row">
          <a-radio-group v-model:value="draft.body_type" size="small" class="body-kind">
            <a-radio-button value="none">{{ t('case_form.body_types.none') }}</a-radio-button>
            <a-radio-button value="json">JSON</a-radio-button>
            <a-radio-button value="form">Form</a-radio-button>
            <a-radio-button value="raw">Raw</a-radio-button>
            <a-radio-button value="xml">XML</a-radio-button>
            <a-radio-button value="multipart">Multipart</a-radio-button>
          </a-radio-group>
          <div v-if="draft.body_type === 'json' || draft.body_type === 'raw'" class="body-format-actions">
            <a-dropdown :trigger="['click']">
              <template #overlay>
                <a-menu @click="handleApplyBodyTemplate">
                  <a-menu-item key="empty_object">
                    <div class="preset-menu-item">
                      <span class="preset-label">空 JSON 对象</span>
                      <code class="preset-code">{}</code>
                    </div>
                  </a-menu-item>
                  <a-menu-item key="pagination">
                    <div class="preset-menu-item">
                      <span class="preset-label">分页检索参数</span>
                      <code class="preset-code">{"page": 1, "page_size": 20, "keyword": ""}</code>
                    </div>
                  </a-menu-item>
                  <a-menu-item key="login_credentials">
                    <div class="preset-menu-item">
                      <span class="preset-label">登录凭证结构</span>
                      <code class="preset-code">{"username": "admin", "password": "password"}</code>
                    </div>
                  </a-menu-item>
                  <a-menu-item key="id_update">
                    <div class="preset-menu-item">
                      <span class="preset-label">状态更新模板</span>
                      <code class="preset-code">&#123;&quot;id&quot;: &quot;&#123;&#123;id&#125;&#125;&quot;, &quot;status&quot;: &quot;active&quot;&#125;</code>
                    </div>
                  </a-menu-item>
                  <a-menu-item key="object_array">
                    <div class="preset-menu-item">
                      <span class="preset-label">对象数组结构</span>
                      <code class="preset-code">[{"name": "item1"}]</code>
                    </div>
                  </a-menu-item>
                </a-menu>
              </template>
              <a-button size="small">
                <ThunderboltOutlined /> {{ t('api_scenario.body_template_label') }} <DownOutlined style="font-size: 9px" />
              </a-button>
            </a-dropdown>
            <a-space size="small">
              <a-button size="small" @click="handleFormatBody">
                <FormatPainterOutlined /> 格式化 JSON
              </a-button>
              <a-button size="small" @click="handleCompressBody">
                压缩
              </a-button>
            </a-space>
          </div>
        </div>
        <KvEditor v-if="draft.body_type === 'form'" v-model:value="formBody" />
        <a-textarea
          v-else-if="draft.body_type !== 'none' && draft.body_type !== 'multipart'"
          v-model:value="bodyText"
          class="body-editor"
          :rows="8"
          :placeholder="draft.body_type === 'json' ? jsonBodyPlaceholder : t('api_workbench.console.body_placeholder')"
        />
        <a-alert v-else-if="draft.body_type === 'multipart'" type="info" :message="t('api_workbench.console.multipart_hint')" />
        <div v-else class="option-empty">{{ t('api_workbench.console.no_body') }}</div>
      </a-tab-pane>
      <a-tab-pane key="auth" :tab="t('api_workbench.console.auth')">
        <div class="auth-grid">
          <label>{{ t('case_form.auth.label') }}</label>
          <a-select v-model:value="authType" :options="authOptions" />
          <template v-if="authType === 'bearer'">
            <label>{{ t('case_form.auth.token_label') }}</label>
            <a-input-password v-model:value="authToken" autocomplete="off" />
          </template>
          <template v-if="authType === 'basic' || authType === 'digest'">
            <label>{{ t('case_form.auth.username_label') }}</label>
            <a-input v-model:value="authUsername" autocomplete="off" />
            <label>{{ t('case_form.auth.password_label') }}</label>
            <a-input-password v-model:value="authPassword" autocomplete="off" />
          </template>
          <template v-if="authType === 'apikey'">
            <label>{{ t('case_form.auth.header_label') }}</label>
            <a-input v-model:value="authHeader" placeholder="X-API-Key" />
            <label>{{ t('case_form.auth.value_label') }}</label>
            <a-input-password v-model:value="authValue" autocomplete="off" />
          </template>
          <a-alert v-if="authType === 'oauth2_client_credentials'" type="info" :message="t('api_workbench.console.advanced_auth_hint')" />
        </div>
      </a-tab-pane>
      <a-tab-pane key="cookies" :tab="t('api_workbench.console.cookies')"><KvEditor v-model:value="draft.cookies" /></a-tab-pane>
    </a-tabs>

    <div class="response-divider">
      <div style="font-weight: 700; font-size: 13px; color: var(--c-text)">
        {{ t('api_workbench.console.response') }}
      </div>
      <div v-if="result" class="response-metrics">
        <span class="status-pill" :class="result.status_code < 400 ? 'status-ok' : 'status-error'">{{ result.status_code }} {{ result.reason }}</span>
        <span>{{ result.duration_ms }} ms</span>
        <span>{{ formatSize(result.size_bytes) }}</span>
        <span v-if="result.truncated">{{ t('api_workbench.console.truncated') }}</span>
      </div>
    </div>
    <a-alert v-if="errorText" type="error" show-icon class="request-error" :message="errorText" />
    <div v-if="lastRequest && (result || errorText)" class="response-context">
      <div class="context-row">
        <span class="context-label">{{ t('api_workbench.console.sent_request') }}</span>
        <code class="context-url"><strong>{{ lastRequest.method }}</strong> {{ lastRequest.url }}</code>
      </div>
      <template v-if="result">
        <div class="context-row">
          <span class="context-label">{{ t('api_workbench.console.server_result') }}</span>
          <span>{{ result.status_code }} {{ result.reason || '' }} · {{ result.size_bytes === 0 ? t('api_workbench.console.no_response_body') : formatSize(result.size_bytes) }}</span>
        </div>
        <div v-if="responseContentType" class="context-row">
          <span class="context-label">Content-Type</span>
          <span>{{ responseContentType }}</span>
        </div>
        <div v-if="responseRequestId" class="context-row">
          <span class="context-label">Request ID</span>
          <code>{{ responseRequestId }}</code>
        </div>
        <div v-if="responseLocation" class="context-row">
          <span class="context-label">Location</span>
          <code class="context-url">{{ responseLocation }}</code>
        </div>
        <div v-if="responseAllow" class="context-row">
          <span class="context-label">Allow</span>
          <span>{{ responseAllow }}</span>
        </div>
        <div v-if="responseDiagnosis" class="diagnosis" :class="result.status_code >= 400 ? 'diagnosis-error' : 'diagnosis-notice'">
          <strong>{{ responseDiagnosis.title }}</strong>
          <span>{{ responseDiagnosis.description }}</span>
        </div>
        <div v-if="modelListPathSuggestion" class="path-suggestion">
          <div>
            <strong>{{ t('api_workbench.console.model_path.title') }}</strong>
            <span>{{ t('api_workbench.console.model_path.description') }}</span>
            <code>{{ modelListPathSuggestion }}</code>
            <small>{{ t('api_workbench.console.model_path.auth_hint') }}</small>
          </div>
          <a-button size="small" type="primary" @click="applyModelListPathSuggestion">
            {{ t('api_workbench.console.model_path.apply') }}
          </a-button>
        </div>
      </template>
    </div>
    <div v-if="result" class="response-content">
      <a-tabs v-model:activeKey="responseTab" size="small">
        <a-tab-pane key="body" :tab="t('api_workbench.console.response_body')">
          <ResponseBodyViewer :body="result.body" :content-type="responseContentType" :size-bytes="result.size_bytes" />
        </a-tab-pane>
        <a-tab-pane key="headers" :tab="t('api_workbench.console.response_headers')">
          <pre class="response-code">{{ formattedHeaders }}</pre>
        </a-tab-pane>
      </a-tabs>
    </div>
    <div v-else-if="!errorText" class="response-empty">
      <span class="response-empty-icon">↳</span>
      <strong>{{ t('api_workbench.console.empty_response_title') }}</strong>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { FormatPainterOutlined, ThunderboltOutlined, DownOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { caseApi, type ApiRequestPreviewPayload, type ApiRequestPreviewResult, type CaseDetailItem } from '@/api'
import { tryFormatJson, tryCompressJson } from '@/utils/jsonFormat'
import KvEditor from '@/components/common/KvEditor.vue'
import ResponseBodyViewer from './ResponseBodyViewer.vue'

const props = defineProps<{
  projectId: number | null
  moduleId: number | null
  canModify: boolean
  caseDetail: CaseDetailItem | null
  resetKey: number
}>()
const emit = defineEmits<{
  'save-draft': [value: ApiRequestPreviewPayload]
  edit: []
  detail: []
  run: []
}>()
const { t } = useI18n()
const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
const jsonBodyPlaceholder = JSON.stringify({ key: 'value' }, null, 2)
const requestTab = ref('params')
const responseTab = ref('body')
const sending = ref(false)
const errorText = ref('')
const result = ref<ApiRequestPreviewResult | null>(null)
const lastRequest = ref<{ method: string; url: string } | null>(null)
const bodyText = ref('')
const formBody = ref<Record<string, string>>({})
const draft = reactive<ApiRequestPreviewPayload>({
  method: 'GET', url: '', headers: {}, params: {}, cookies: {}, body_type: 'none', body: null,
  multipart: [], auth: { type: 'none' }, timeout: 30,
})
let controller: AbortController | null = null

function handleApplyRequestTemplate({ key }: { key: string | number }) {
  if (key === 'rest_json_get') {
    draft.method = 'GET'
    draft.headers = { ...draft.headers, Accept: 'application/json' }
    draft.params = { ...draft.params, page: '1', page_size: '20' }
    message.success(t('api_scenario.template_applied', { name: '标准 REST 查询' }))
  } else if (key === 'jwt_form_login') {
    draft.method = 'POST'
    draft.headers = { ...draft.headers, 'Content-Type': 'application/x-www-form-urlencoded' }
    draft.body_type = 'form'
    formBody.value = { username: 'admin', password: 'password' }
    message.success(t('api_scenario.template_applied', { name: '表单登录获取 Token' }))
  } else if (key === 'auth_json_post') {
    draft.method = 'POST'
    draft.headers = {
      ...draft.headers,
      'Content-Type': 'application/json',
      Authorization: 'Bearer {{token}}',
    }
    draft.body_type = 'json'
    bodyText.value = JSON.stringify({ name: 'demo', status: 'active' }, null, 2)
    message.success(t('api_scenario.template_applied', { name: '鉴权业务调用' }))
  } else if (key === 'healthcheck_get') {
    draft.method = 'GET'
    message.success(t('api_scenario.template_applied', { name: '服务探活心跳' }))
  }
}

function handleApplyBodyTemplate({ key }: { key: string | number }) {
  draft.body_type = 'json'
  if (key === 'empty_object') {
    bodyText.value = '{\n  \n}'
  } else if (key === 'pagination') {
    bodyText.value = JSON.stringify({ page: 1, page_size: 20, keyword: '' }, null, 2)
  } else if (key === 'login_credentials') {
    bodyText.value = JSON.stringify({ username: 'admin', password: 'password' }, null, 2)
  } else if (key === 'id_update') {
    bodyText.value = JSON.stringify({ id: '{{id}}', status: 'active' }, null, 2)
  } else if (key === 'object_array') {
    bodyText.value = JSON.stringify([{ name: 'item1' }], null, 2)
  }
  message.success(t('api_scenario.template_applied', { name: 'Body 结构' }))
}

const authType = computed({
  get: () => String(draft.auth.type || 'none'),
  set: (value: string) => { draft.auth = { ...draft.auth, type: value } },
})
function authField(key: string) {
  return computed({
    get: () => String(draft.auth[key] || ''),
    set: (value: string) => { draft.auth = { ...draft.auth, [key]: value } },
  })
}
const authToken = authField('token')
const authUsername = authField('username')
const authPassword = authField('password')
const authHeader = authField('header')
const authValue = authField('value')
const authOptions = computed(() => [
  { value: 'none', label: t('case_form.auth.none') },
  { value: 'bearer', label: t('case_form.auth.bearer') },
  { value: 'basic', label: t('case_form.auth.basic') },
  { value: 'apikey', label: t('case_form.auth.apikey') },
  { value: 'digest', label: t('case_form.auth.digest') },
  { value: 'oauth2_client_credentials', label: t('case_form.auth.oauth2_client_credentials') },
])

function cancelRequest() {
  controller?.abort()
  controller = null
  sending.value = false
}

function clearResult() {
  cancelRequest()
  result.value = null
  errorText.value = ''
  lastRequest.value = null
}

function resetDraft() {
  clearResult()
  Object.assign(draft, {
    method: 'GET', url: '', headers: {}, params: {}, cookies: {}, body_type: 'none', body: null,
    multipart: [], auth: { type: 'none' }, timeout: 30,
  })
  bodyText.value = ''
  formBody.value = {}
  requestTab.value = 'params'
}

watch(() => props.resetKey, resetDraft)
watch(() => props.caseDetail, (detail) => {
  if (!detail || detail.case_type !== 'api') return
  const config = detail.config as Record<string, unknown>
  const step = (Array.isArray(config.steps) ? config.steps[0] : config) as Record<string, unknown> | undefined
  if (!step) return
  clearResult()
  Object.assign(draft, {
    method: String(step.method || 'GET'),
    url: String(step.url || ''),
    headers: { ...((step.headers || {}) as Record<string, string>) },
    params: { ...((step.params || {}) as Record<string, string>) },
    cookies: { ...((step.cookies || {}) as Record<string, string>) },
    body_type: String(step.body_type || 'none'),
    body: step.body ?? null,
    multipart: Array.isArray(step.multipart) ? step.multipart.map((part) => ({ ...part })) : [],
    auth: { ...((step.auth || { type: 'none' }) as Record<string, unknown>) },
    timeout: Number(step.timeout || 30),
  })
  bodyText.value = typeof step.body === 'string' ? step.body : step.body == null ? '' : JSON.stringify(step.body, null, 2)
  formBody.value = draft.body_type === 'form' && step.body && typeof step.body === 'object'
    ? { ...(step.body as Record<string, string>) }
    : {}
}, { immediate: true })
watch(draft, clearResult, { deep: true })
watch(bodyText, clearResult)
watch(formBody, clearResult, { deep: true })
onBeforeUnmount(cancelRequest)

function payload(): ApiRequestPreviewPayload {
  let body: unknown = null
  if (draft.body_type === 'form') body = { ...formBody.value }
  else if (draft.body_type === 'json') body = bodyText.value.trim() ? JSON.parse(bodyText.value) : null
  else if (draft.body_type !== 'none') body = bodyText.value
  return {
    method: draft.method, url: draft.url.trim(), headers: { ...draft.headers }, params: { ...draft.params },
    cookies: { ...draft.cookies }, body_type: draft.body_type, body,
    multipart: draft.multipart.map((part) => ({ ...part })), auth: { ...draft.auth },
    timeout: Math.min(Math.max(draft.timeout || 30, 1), 60),
  }
}

function saveDraft() {
  if (!props.moduleId) {
    errorText.value = t('api_workbench.select_module_first')
    return
  }
  try {
    const draftPayload = payload()
    if (result.value) {
      draftPayload.status_code = result.value.status_code
      draftPayload.response_body = result.value.body
      draftPayload.response_headers = result.value.headers
    }
    emit('save-draft', draftPayload)
  } catch {
    errorText.value = t('case_form.preview.invalid_json')
  }
}

async function sendRequest() {
  if (!props.projectId || !props.canModify || sending.value) return
  let request: ApiRequestPreviewPayload
  try {
    request = payload()
  } catch {
    errorText.value = t('case_form.preview.invalid_json')
    return
  }
  if (!request.url) return
  clearResult()
  lastRequest.value = { method: request.method, url: requestUrl(request) }
  const activeController = new AbortController()
  controller = activeController
  sending.value = true
  try {
    result.value = await caseApi.previewRequest(props.projectId, request, activeController.signal)
    responseTab.value = 'body'
  } catch (error) {
    if (!activeController.signal.aborted) {
      const responseError = error as { response?: { data?: { detail?: unknown } }; message?: unknown }
      const detail = responseError?.response?.data?.detail
      errorText.value = typeof detail === 'string'
        ? detail
        : typeof responseError?.message === 'string'
          ? responseError.message
          : t('common.failed')
    }
  } finally {
    if (controller === activeController) {
      controller = null
      sending.value = false
    }
  }
}

function formatSize(bytes: number) {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`
}
function requestUrl(request: ApiRequestPreviewPayload) {
  try {
    const url = new URL(request.url)
    Object.entries(request.params).forEach(([key, value]) => url.searchParams.set(key, value))
    return url.toString()
  } catch {
    return request.url
  }
}
function responseHeader(name: string) {
  const entry = Object.entries(result.value?.headers || {}).find(([key]) => key.toLowerCase() === name)
  return entry?.[1] || ''
}
const responseContentType = computed(() => responseHeader('content-type'))
const responseRequestId = computed(() => responseHeader('x-request-id') || responseHeader('x-correlation-id') || responseHeader('trace-id'))
const responseLocation = computed(() => responseHeader('location'))
const responseAllow = computed(() => responseHeader('allow'))
const responseDiagnosis = computed(() => {
  const status = result.value?.status_code
  if (!status) return null
  let key = ''
  if (status === 404) key = 'not_found'
  else if (status === 405) key = 'method_not_allowed'
  else if (status === 401) key = 'unauthorized'
  else if (status === 403) key = 'forbidden'
  else if (status === 400 || status === 422) key = 'bad_request'
  else if (status === 429) key = 'rate_limited'
  else if (status >= 500) key = 'server_error'
  else if (status >= 300) key = 'redirect'
  if (!key) return null
  return {
    title: t(`api_workbench.console.diagnosis.${key}.title`),
    description: t(`api_workbench.console.diagnosis.${key}.description`),
  }
})
const modelListPathSuggestion = computed(() => {
  if (result.value?.status_code !== 404 || lastRequest.value?.method !== 'GET') return ''
  try {
    const url = new URL(lastRequest.value.url)
    if (!/\/v1\/model\/?$/i.test(url.pathname)) return ''
    url.pathname = url.pathname.replace(/\/model\/?$/i, '/models')
    return url.toString()
  } catch {
    return ''
  }
})
function applyModelListPathSuggestion() {
  if (!modelListPathSuggestion.value) return
  draft.url = modelListPathSuggestion.value
}

function handleFormatBody() {
  bodyText.value = tryFormatJson(bodyText.value)
}

function handleCompressBody() {
  bodyText.value = tryCompressJson(bodyText.value)
}
const formattedHeaders = computed(() =>
  Object.entries(result.value?.headers || {}).map(([key, value]) => `${key}: ${value}`).join('\n'),
)
</script>

<style scoped>
.request-console { min-width: 0; display: flex; flex-direction: column; background: var(--c-bg-elevated); color: var(--c-text); }
.console-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 20px 14px; border-bottom: 1px solid var(--c-border); }
.request-identity { min-width: 0; }
.request-identity h2 { display: inline-block; margin: 0 9px 0 0; color: var(--c-text); font-size: 16px; font-weight: 700; }
.request-code { color: var(--c-text-tertiary); font-size: 11px; font-family: 'JetBrains Mono', Consolas, monospace; }
.heading-actions { display: flex; flex-wrap: wrap; gap: 8px; flex-shrink: 0; }
.request-line { display: flex; gap: 0; padding: 16px 20px; }
.method-select { width: 120px; flex-shrink: 0; }
.method-select :deep(.ant-select-selector) { height: 38px !important; align-items: center; border-radius: var(--radius-sm) 0 0 var(--radius-sm) !important; background: var(--c-bg-subtle) !important; color: var(--c-text) !important; border-color: var(--c-border) !important; font-family: 'JetBrains Mono', Consolas, monospace; font-weight: 700; }
.url-input { min-width: 0; height: 38px; border-radius: 0; background: var(--c-bg-elevated); color: var(--c-text); border-color: var(--c-border); font-family: 'JetBrains Mono', Consolas, monospace; font-size: 13px; }
.send-button { width: 100px; height: 38px; flex-shrink: 0; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; font-weight: 700; }
.cancel-button { height: 38px; border-radius: 0; }
.request-section-heading { display: flex; justify-content: space-between; gap: 12px; padding: 0 20px; color: var(--c-text); font-size: 12px; font-weight: 650; }
.request-tabs { min-height: 195px; padding: 0 20px 14px; }
.request-tabs :deep(.ant-tabs-content-holder) { min-height: 126px; }
.body-header-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.body-kind { margin-bottom: 0; }
.body-format-actions { display: flex; align-items: center; gap: 8px; }
.body-editor :deep(textarea) { font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; background: var(--c-bg-subtle); color: var(--c-text); border-color: var(--c-border); }
.option-empty { padding: 16px 0; color: var(--c-text-tertiary); font-size: 12px; }
.auth-grid { display: grid; grid-template-columns: 132px minmax(0, 360px); align-items: center; gap: 11px 14px; max-width: 550px; color: var(--c-text-secondary); font-size: 12px; }
.auth-grid :deep(.ant-alert) { grid-column: 1 / -1; }
.response-divider { display: flex; align-items: center; justify-content: space-between; gap: 15px; padding: 14px 20px 10px; border-top: 1px solid var(--c-border); }
.response-metrics { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; color: var(--c-text-secondary); font-size: 12px; font-family: 'JetBrains Mono', Consolas, monospace; }
.status-pill { padding: 2px 8px; border-radius: var(--radius-xs); font-weight: 700; }
.status-ok { background: var(--c-success-soft); color: var(--c-success); }
.status-error { background: var(--c-error-soft); color: var(--c-error); }
.request-error { margin: 0 20px 16px; }
.response-context { display: grid; gap: 8px; margin: 0 20px 14px; padding: 12px 14px; border: 1px solid var(--c-border); border-radius: var(--radius-sm); background: var(--c-bg-subtle); color: var(--c-text); font-size: 12px; }
.context-row { display: grid; grid-template-columns: 104px minmax(0, 1fr); gap: 12px; align-items: start; }
.context-label { color: var(--c-text-tertiary); }
.context-url { min-width: 0; overflow-wrap: anywhere; color: var(--c-text); font: 12px/1.5 'JetBrains Mono', Consolas, monospace; }
.context-url strong { color: var(--c-primary); }
.diagnosis { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; padding: 10px 12px; border-radius: var(--radius-xs); line-height: 1.55; }
.diagnosis-error { background: var(--c-error-soft); color: var(--c-error); }
.diagnosis-notice { background: var(--c-primary-soft); color: var(--c-primary); }
.path-suggestion { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 12px; border: 1px solid var(--c-primary-glow); border-radius: var(--radius-sm); background: var(--c-primary-soft); color: var(--c-text); }
.path-suggestion > div { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.path-suggestion code { overflow-wrap: anywhere; font: 12px/1.5 'JetBrains Mono', Consolas, monospace; }
.path-suggestion small { color: var(--c-text-secondary); line-height: 1.5; }
.path-suggestion :deep(.ant-btn) { flex-shrink: 0; }
.response-content { padding: 0 20px 20px; }
.response-code { min-height: 210px; max-height: 460px; margin: 0; padding: 14px 16px; overflow: auto; border: 1px solid var(--c-border); border-radius: var(--radius-sm); background: var(--c-bg-subtle); color: var(--c-text); font: 12px/1.65 'JetBrains Mono', Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.response-empty { min-height: 220px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; margin: 0 20px 20px; border: 1px dashed var(--c-border); border-radius: var(--radius-md); color: var(--c-text-tertiary); font-size: 12px; }
.response-empty strong { color: var(--c-text); font-size: 13px; }
.response-empty-icon { color: var(--c-primary); font: 36px/1 Georgia, serif; }
@media (max-width: 800px) { .console-heading, .response-divider { align-items: flex-start; flex-direction: column; } }
@media (max-width: 560px) { .console-heading, .request-line, .request-section-heading, .request-tabs, .response-divider, .response-content { padding-left: 14px; padding-right: 14px; } .response-context { margin-left: 14px; margin-right: 14px; } .context-row { grid-template-columns: 1fr; gap: 2px; } .path-suggestion { align-items: stretch; flex-direction: column; } .request-line { flex-wrap: wrap; gap: 8px; } .method-select { width: 100px; } .url-input { flex: 1; border-radius: 0 7px 7px 0; } .send-button { width: 100%; border-radius: 7px; } .auth-grid { grid-template-columns: 1fr; } }
.template-quick-btn {
  height: 38px;
  border-radius: 0;
  border-left: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--c-primary, #1677ff);
  background: var(--c-primary-soft, #f0f7ff);
}

.preset-menu-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
}

.preset-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text, #1e293b);
}

.preset-code {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  font-family: monospace;
}
</style>
