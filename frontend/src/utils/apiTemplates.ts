export interface DynamicVariablePreset {
  id: string
  token: string
  label: string
  category: 'id' | 'time' | 'random'
  example: string
  suggestedKey: string
}

export interface KvPresetOption {
  id: string
  label: string
  preview: string
  entries: Record<string, string>
}

export interface ApiRequestTemplate {
  id: string
  label: string
  description: string
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS'
  url?: string
  headers?: Record<string, string>
  params?: Record<string, string>
  cookies?: Record<string, string>
  bodyType?: 'none' | 'json' | 'form' | 'xml' | 'raw'
  jsonBody?: Record<string, unknown> | unknown[]
  formBody?: Record<string, string>
  rawBody?: string
}

export interface AssertionPreset {
  id: string
  label: string
  preview: string
  target: 'status_code' | 'jsonpath' | 'header' | 'body_contains' | 'response_time'
  expression?: string
  operator: string
  expected: string
}

export interface ExtractionPreset {
  id: string
  label: string
  preview: string
  variable: string
  type: 'jsonpath' | 'xpath' | 'header'
  expression: string
}

export interface ScenarioStepTemplate {
  name: string
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  url: string
  headers?: Record<string, string>
  params?: Record<string, string>
  cookies?: Record<string, string>
  body_type?: 'none' | 'json' | 'form' | 'raw'
  body?: unknown
  assertions?: Array<{ target: string; expression?: string; operator: string; expected: string }>
  extractions?: Array<{ variable: string; type: string; expression: string }>
}

export interface ScenarioTemplate {
  id: string
  label: string
  description: string
  steps: ScenarioStepTemplate[]
}

export const DYNAMIC_VARIABLE_PRESETS: readonly DynamicVariablePreset[] = [
  { id: 'uuid', token: '{{$uuid}}', label: 'UUID v4', category: 'id', example: '550e8400-e29b-41d4-a716-446655440000', suggestedKey: 'request_id' },
  { id: 'uuid_hex', token: '{{$uuid_hex}}', label: '32位无横杠 UUID', category: 'id', example: '550e8400e29b41d4a716446655440000', suggestedKey: 'trace_id' },
  { id: 'timestamp', token: '{{$timestamp}}', label: '秒级时间戳', category: 'time', example: '1764000000', suggestedKey: 'timestamp' },
  { id: 'timestamp_ms', token: '{{$timestamp_ms}}', label: '毫秒时间戳', category: 'time', example: '1764000000123', suggestedKey: 'ts' },
  { id: 'iso_now', token: '{{$iso_now}}', label: 'UTC ISO 时间', category: 'time', example: '2026-11-26T04:00:00Z', suggestedKey: 'created_at' },
  { id: 'date', token: '{{$date}}', label: '当前日期 YYYY-MM-DD', category: 'time', example: '2026-11-26', suggestedKey: 'biz_date' },
  { id: 'random_int', token: '{{$random_int}}', label: '随机整数', category: 'random', example: '482910', suggestedKey: 'random_num' },
  { id: 'random_int_range', token: '{{$random_int(1, 100)}}', label: '区间整数 (1-100)', category: 'random', example: '42', suggestedKey: 'score' },
  { id: 'random_str', token: '{{$random_str}}', label: '8位随机字符串', category: 'random', example: 'aB9kP2xQ', suggestedKey: 'nonce' },
  { id: 'random_str_16', token: '{{$random_str(16)}}', label: '16位随机字符串', category: 'random', example: 'aB9kP2xQm7Tr4LwZ', suggestedKey: 'request_nonce' },
  { id: 'random_email', token: '{{$random_email}}', label: '随机邮箱', category: 'random', example: 'user_a1b2c3d4@example.com', suggestedKey: 'email' },
  { id: 'random_phone', token: '{{$random_phone}}', label: '随机手机号', category: 'random', example: '13800138000', suggestedKey: 'phone' },
  { id: 'random_name', token: '{{$random_name}}', label: '随机姓名', category: 'random', example: 'Alice Chen', suggestedKey: 'username' },
  { id: 'random_bool', token: '{{$random_bool}}', label: '随机布尔值', category: 'random', example: 'true', suggestedKey: 'enabled' },
]

export const HEADER_KEY_SUGGESTIONS: readonly string[] = [
  'Content-Type',
  'Authorization',
  'Accept',
  'X-Request-Id',
  'X-Trace-Id',
  'X-Env',
  'X-API-Key',
  'User-Agent',
  'Cache-Control',
  'Accept-Language',
]

export const HEADER_VALUE_SUGGESTIONS: readonly string[] = [
  'application/json',
  'application/x-www-form-urlencoded',
  'Bearer {{token}}',
  '{{$uuid}}',
  '{{$timestamp}}',
  'zh-CN',
  'no-cache',
]

export const HEADER_PRESETS: readonly KvPresetOption[] = [
  { id: 'json', label: 'JSON 内容头', preview: 'Content-Type: application/json', entries: { 'Content-Type': 'application/json' } },
  { id: 'form', label: '表单提交头', preview: 'Content-Type: application/x-www-form-urlencoded', entries: { 'Content-Type': 'application/x-www-form-urlencoded' } },
  { id: 'text_plain', label: '纯文本头', preview: 'Content-Type: text/plain; charset=utf-8', entries: { 'Content-Type': 'text/plain; charset=utf-8' } },
  { id: 'xml', label: 'XML 内容头', preview: 'Content-Type: application/xml', entries: { 'Content-Type': 'application/xml' } },
  { id: 'accept_json', label: 'Accept JSON', preview: 'Accept: application/json', entries: { Accept: 'application/json' } },
  { id: 'bearer', label: 'Bearer 鉴权', preview: 'Authorization: Bearer {{token}}', entries: { Authorization: 'Bearer {{token}}' } },
  { id: 'basic_auth', label: 'Basic 鉴权', preview: 'Authorization: Basic {{basic_token}}', entries: { Authorization: 'Basic {{basic_token}}' } },
  { id: 'api_key', label: 'API Key 请求头', preview: 'X-API-Key: {{api_key}}', entries: { 'X-API-Key': '{{api_key}}' } },
  { id: 'trace', label: '动态链路追踪头', preview: 'X-Request-Id: {{$uuid}}', entries: { 'X-Request-Id': '{{$uuid}}' } },
  { id: 'idempotency', label: '幂等请求头', preview: 'Idempotency-Key: {{$uuid}}', entries: { 'Idempotency-Key': '{{$uuid}}' } },
  { id: 'no_cache', label: '禁用缓存', preview: 'Cache-Control: no-cache', entries: { 'Cache-Control': 'no-cache' } },
  { id: 'user_agent', label: '模拟浏览器 UA', preview: 'User-Agent: ATP-Runner/2.0', entries: { 'User-Agent': 'ATP-Runner/2.0' } },
  {
    id: 'auth_json_bundle',
    label: '鉴权 + JSON 组合头',
    preview: 'Content-Type + Accept + Bearer {{token}}',
    entries: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: 'Bearer {{token}}',
    },
  },
  {
    id: 'canary_trace_bundle',
    label: '灰度路由 + 链路组合头',
    preview: 'X-Env + X-Request-Id + X-Timestamp',
    entries: {
      'X-Env': 'staging',
      'X-Request-Id': '{{$uuid}}',
      'X-Timestamp': '{{$timestamp}}',
    },
  },
]

export const PARAM_KEY_SUGGESTIONS: readonly string[] = [
  'page',
  'page_size',
  'keyword',
  'status',
  'sort_by',
  'order',
  'id',
  'cursor',
  'limit',
  'start_date',
  'end_date',
  'include',
  'locale',
]

export const PARAM_PRESETS: readonly KvPresetOption[] = [
  { id: 'pagination', label: '分页参数', preview: 'page=1 & page_size=20', entries: { page: '1', page_size: '20' } },
  { id: 'search', label: '关键字检索', preview: 'keyword=demo & page=1 & page_size=20', entries: { keyword: 'demo', page: '1', page_size: '20' } },
  { id: 'status', label: '状态过滤', preview: 'status=active', entries: { status: 'active' } },
  { id: 'sort', label: '排序参数', preview: 'sort_by=created_at & order=desc', entries: { sort_by: 'created_at', order: 'desc' } },
  { id: 'time_range', label: '日期区间（动态今日）', preview: 'start_date={{$date}} & end_date={{$date}}', entries: { start_date: '{{$date}}', end_date: '{{$date}}' } },
  { id: 'cursor', label: '游标分页', preview: 'cursor= & limit=50', entries: { cursor: '', limit: '50' } },
  { id: 'include', label: '关联资源展开', preview: 'include=details,owner', entries: { include: 'details,owner' } },
  { id: 'fields', label: '返回字段裁剪', preview: 'fields=id,name,status', entries: { fields: 'id,name,status' } },
  { id: 'locale', label: '语言地区', preview: 'locale=zh-CN', entries: { locale: 'zh-CN' } },
  { id: 'debug', label: '调试开关', preview: 'debug=true', entries: { debug: 'true' } },
  { id: 'replay_guard', label: '防重放时间戳与随机串', preview: 'timestamp={{$timestamp}} & nonce={{$random_str}}', entries: { timestamp: '{{$timestamp}}', nonce: '{{$random_str}}' } },
  { id: 'id_filter', label: '资源 ID 参数', preview: 'id={{id}}', entries: { id: '{{id}}' } },
]

export const COOKIE_KEY_SUGGESTIONS: readonly string[] = [
  'session_id',
  'csrf_token',
  'auth_token',
  'locale',
  'gray_env',
  'debug_trace',
]

export const COOKIE_PRESETS: readonly KvPresetOption[] = [
  { id: 'session_id', label: '会话 ID Cookie', preview: 'session_id={{session_id}}', entries: { session_id: '{{session_id}}' } },
  { id: 'csrf_token', label: 'CSRF 防护令牌', preview: 'csrf_token={{csrf_token}}', entries: { csrf_token: '{{csrf_token}}' } },
  { id: 'auth_token', label: '认证令牌 Cookie', preview: 'auth_token={{token}}', entries: { auth_token: '{{token}}' } },
  { id: 'locale', label: '语言偏好 Cookie', preview: 'locale=zh-CN', entries: { locale: 'zh-CN' } },
  { id: 'canary', label: '灰度路由标记', preview: 'gray_env=canary', entries: { gray_env: 'canary' } },
  { id: 'trace_cookie', label: '动态链路追踪 Cookie', preview: 'debug_trace={{$uuid_hex}}', entries: { debug_trace: '{{$uuid_hex}}' } },
]

export const API_REQUEST_TEMPLATES: readonly ApiRequestTemplate[] = [
  {
    id: 'rest_json_get',
    label: '标准 REST 查询 (GET + Accept JSON)',
    description: '配置 GET 方式、Accept 请求头与分页参数',
    method: 'GET',
    headers: { Accept: 'application/json' },
    params: { page: '1', page_size: '20' },
  },
  {
    id: 'jwt_form_login',
    label: '表单登录获取 Token (POST + urlencoded)',
    description: '配置 POST、urlencoded 头与表单凭据',
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    bodyType: 'form',
    formBody: { username: 'admin', password: 'password' },
  },
  {
    id: 'auth_json_post',
    label: '鉴权业务调用 (POST + Bearer Token)',
    description: '配置 POST、JSON 头、Authorization 头与 Body',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer {{token}}',
    },
    bodyType: 'json',
    jsonBody: { name: 'demo', status: 'active' },
  },
  {
    id: 'rest_json_put',
    label: '资源更新调用 (PUT + Bearer Token)',
    description: '配置 PUT 方式、JSON 鉴权头与局部更新 Body',
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer {{token}}',
    },
    bodyType: 'json',
    jsonBody: { id: '{{id}}', status: 'active', updated_at: '{{$iso_now}}' },
  },
  {
    id: 'rest_delete',
    label: '资源删除调用 (DELETE + Bearer Token)',
    description: '配置 DELETE 方式与 Authorization 鉴权头',
    method: 'DELETE',
    headers: { Authorization: 'Bearer {{token}}' },
    bodyType: 'none',
  },
  {
    id: 'webhook_callback_post',
    label: 'Webhook 回调通知 (POST + 动态事件)',
    description: '自动注入动态事件 ID 与时间戳',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-Id': '{{$uuid}}',
    },
    bodyType: 'json',
    jsonBody: {
      event_id: '{{$uuid}}',
      event_type: 'order.paid',
      timestamp: '{{$timestamp}}',
      payload: { order_no: 'ORD_{{$random_str(8)}}', verified: true },
    },
  },
  {
    id: 'graphql_query_post',
    label: 'GraphQL HTTP POST 查询',
    description: '标准 query + variables GraphQL 载荷结构',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer {{token}}',
    },
    bodyType: 'json',
    jsonBody: {
      query: 'query GetItem($id: ID!) { item(id: $id) { id name } }',
      variables: { id: '{{id}}' },
    },
  },
  {
    id: 'healthcheck_get',
    label: '服务探活配置 (GET)',
    description: '配置 GET 方式与超时兜底检查',
    method: 'GET',
  },
]

export const ASSERTION_PRESETS: readonly AssertionPreset[] = [
  { id: 'status_200', label: '状态码 = 200', preview: 'status_code eq 200', target: 'status_code', operator: 'eq', expected: '200' },
  { id: 'status_201', label: '状态码 = 201', preview: 'status_code eq 201', target: 'status_code', operator: 'eq', expected: '201' },
  { id: 'json_code_zero', label: '业务码 $.code = 0', preview: 'jsonpath $.code eq 0', target: 'jsonpath', expression: '$.code', operator: 'eq', expected: '0' },
  { id: 'json_data_exists', label: '响应包含 $.data', preview: 'jsonpath $.data exists', target: 'jsonpath', expression: '$.data', operator: 'exists', expected: '' },
  { id: 'response_time_1s', label: '耗时 < 1000ms', preview: 'response_time lt 1000', target: 'response_time', operator: 'lt', expected: '1000' },
]

export const EXTRACTION_PRESETS: readonly ExtractionPreset[] = [
  { id: 'extract_token', label: '提取认证 Token', preview: 'token <- $.data.token', variable: 'token', type: 'jsonpath', expression: '$.data.token' },
  { id: 'extract_id', label: '提取创建 ID', preview: 'created_id <- $.data.id', variable: 'created_id', type: 'jsonpath', expression: '$.data.id' },
  { id: 'extract_total', label: '提取分页总数', preview: 'total <- $.data.total', variable: 'total', type: 'jsonpath', expression: '$.data.total' },
]

export const SCENARIO_TEMPLATES: readonly ScenarioTemplate[] = [
  {
    id: 'login_and_fetch',
    label: '登录鉴权 -> 业务查询 (2步)',
    description: '先登录提取 token，再携带 Bearer Token 请求业务接口',
    steps: [
      {
        name: '1. 登录获取 Token',
        method: 'POST',
        url: '{{base_url}}/api/v1/auth/login',
        headers: { 'Content-Type': 'application/json' },
        body_type: 'json',
        body: { username: 'admin', password: 'password' },
        assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
        extractions: [{ variable: 'token', type: 'jsonpath', expression: '$.access_token' }],
      },
      {
        name: '2. 鉴权查询列表',
        method: 'GET',
        url: '{{base_url}}/api/v1/items',
        headers: { Accept: 'application/json', Authorization: 'Bearer {{token}}' },
        params: { page: '1', page_size: '20' },
        body_type: 'none',
        assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
      },
    ],
  },
  {
    id: 'crud_lifecycle',
    label: '创建 -> 查询 -> 更新 -> 删除 (4步 CRUD 闭环)',
    description: '使用动态随机值创建资源并验证完整生命周期',
    steps: [
      {
        name: '1. 创建测试资源',
        method: 'POST',
        url: '{{base_url}}/api/v1/items',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer {{token}}', 'X-Request-Id': '{{$uuid}}' },
        body_type: 'json',
        body: { name: 'auto_{{$random_str(6)}}', status: 'active' },
        assertions: [{ target: 'status_code', operator: 'eq', expected: '201' }],
        extractions: [{ variable: 'created_id', type: 'jsonpath', expression: '$.data.id' }],
      },
      {
        name: '2. 查询详情校验',
        method: 'GET',
        url: '{{base_url}}/api/v1/items/{{created_id}}',
        headers: { Accept: 'application/json', Authorization: 'Bearer {{token}}' },
        body_type: 'none',
        assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
      },
      {
        name: '3. 更新状态',
        method: 'PUT',
        url: '{{base_url}}/api/v1/items/{{created_id}}',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer {{token}}' },
        body_type: 'json',
        body: { status: 'archived', updated_at: '{{$iso_now}}' },
        assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
      },
      {
        name: '4. 清理测试资源',
        method: 'DELETE',
        url: '{{base_url}}/api/v1/items/{{created_id}}',
        headers: { Authorization: 'Bearer {{token}}' },
        body_type: 'none',
        assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
      },
    ],
  },
  {
    id: 'pagination_search',
    label: '分页边界 + 关键字过滤对比 (2步)',
    description: '分别验证首页列表结构与关键字搜索响应',
    steps: [
      {
        name: '1. 首页默认分页',
        method: 'GET',
        url: '{{base_url}}/api/v1/items',
        headers: { Accept: 'application/json' },
        params: { page: '1', page_size: '20' },
        body_type: 'none',
        assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
      },
      {
        name: '2. 关键字过滤检索',
        method: 'GET',
        url: '{{base_url}}/api/v1/items',
        headers: { Accept: 'application/json' },
        params: { page: '1', page_size: '10', keyword: '{{$random_str(4)}}' },
        body_type: 'none',
        assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
      },
    ],
  },
]

export interface EnvVariablePresetItem {
  key: string
  value: string
  is_secret: boolean
}

export interface EnvironmentVariablePreset {
  id: string
  label: string
  description: string
  variables: readonly EnvVariablePresetItem[]
}

export const ENVIRONMENT_VARIABLE_PRESETS: readonly EnvironmentVariablePreset[] = [
  {
    id: 'rest_basic',
    label: '基础 REST API 环境',
    description: '包含 base_url、api_prefix、timeout 等基础调试变量',
    variables: [
      { key: 'base_url', value: 'https://api-staging.example.com', is_secret: false },
      { key: 'api_prefix', value: '/api/v1', is_secret: false },
      { key: 'timeout', value: '30', is_secret: false },
      { key: 'trace_prefix', value: 'atp-{{$date}}', is_secret: false },
    ],
  },
  {
    id: 'jwt_auth',
    label: 'JWT / 登录鉴权环境',
    description: '包含登录账号、密文密码与运行时 token 占位',
    variables: [
      { key: 'base_url', value: 'https://api-staging.example.com', is_secret: false },
      { key: 'auth_username', value: 'qa_tester', is_secret: false },
      { key: 'auth_password', value: 'ChangeMe123!', is_secret: true },
      { key: 'token', value: 'replace_after_login', is_secret: true },
    ],
  },
  {
    id: 'oauth2_client',
    label: 'OAuth2 Client Credentials 环境',
    description: '包含 token_url、client_id、client_secret 与 scope',
    variables: [
      { key: 'base_url', value: 'https://api-staging.example.com', is_secret: false },
      { key: 'token_url', value: 'https://auth-staging.example.com/oauth/token', is_secret: false },
      { key: 'client_id', value: 'atp-service-client', is_secret: false },
      { key: 'client_secret', value: 'replace_with_client_secret', is_secret: true },
      { key: 'oauth_scope', value: 'read write', is_secret: false },
    ],
  },
  {
    id: 'api_key_gateway',
    label: 'API 网关 / 签名鉴权环境',
    description: '包含网关 api_key、api_secret、租户 ID 与环境标识',
    variables: [
      { key: 'base_url', value: 'https://gateway-staging.example.com', is_secret: false },
      { key: 'api_key', value: 'ak_staging_demo', is_secret: true },
      { key: 'api_secret', value: 'sk_staging_demo', is_secret: true },
      { key: 'tenant_id', value: 'tenant_qa_01', is_secret: false },
      { key: 'env_tag', value: 'staging', is_secret: false },
    ],
  },
  {
    id: 'microservice_gray',
    label: '微服务灰度与多端环境',
    description: '包含灰度路由、区域、国际化与链路追踪变量',
    variables: [
      { key: 'base_url', value: 'https://mesh-staging.example.com', is_secret: false },
      { key: 'gray_env', value: 'canary', is_secret: false },
      { key: 'region', value: 'cn-east-1', is_secret: false },
      { key: 'locale', value: 'zh-CN', is_secret: false },
      { key: 'debug_trace', value: '{{$uuid_hex}}', is_secret: false },
    ],
  },
]
