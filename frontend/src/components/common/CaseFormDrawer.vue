<template>
  <a-drawer
    :open="open"
    :title="isEdit ? '编辑用例' : '新建用例'"
    width="760"
    :destroy-on-close="true"
    @close="emit('close')"
  >
    <a-form :model="form" layout="vertical" ref="formRef">
      <!-- ── 基本信息 ───────────────────────────────── -->
      <a-divider orientation="left">基本信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="16">
          <a-form-item label="用例名称" name="name" :rules="[{ required: true, message: '请输入用例名称' }]">
            <a-input v-model:value="form.name" placeholder="用例名称" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="用例类型" name="case_type">
            <a-select v-model:value="form.case_type" :disabled="isEdit">
              <a-select-option value="api">接口测试</a-select-option>
              <a-select-option value="graphql">GraphQL</a-select-option>
              <a-select-option value="websocket">WebSocket</a-select-option>
              <a-select-option value="grpc">gRPC</a-select-option>
              <a-select-option value="web">Web UI</a-select-option>
              <a-select-option value="android">Android UI</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="标签">
        <a-select
          v-model:value="form.tags"
          mode="tags"
          placeholder="输入后回车添加标签（如 smoke、p0）"
          :token-separators="[',']"
        />
      </a-form-item>
      <a-form-item label="描述">
        <a-textarea v-model:value="form.description" :rows="2" placeholder="可选" />
      </a-form-item>

      <!-- ── 接口测试配置 ────────────────────────────── -->
      <template v-if="form.case_type === 'api'">
        <a-divider orientation="left">请求配置</a-divider>

        <!-- URL + Method -->
        <a-form-item label="请求地址" :rules="[{ required: true, message: '请输入 URL' }]">
          <a-input-group compact>
            <a-select v-model:value="cfg.method" style="width: 110px">
              <a-select-option v-for="m in HTTP_METHODS" :key="m" :value="m">{{ m }}</a-select-option>
            </a-select>
            <a-input v-model:value="cfg.url" style="width: calc(100% - 110px)" placeholder="https://api.example.com/v1/..." />
          </a-input-group>
        </a-form-item>

        <!-- Tabs: Headers / Params / Body / Auth -->
        <a-tabs v-model:activeKey="activeTab" size="small">
          <!-- Headers -->
          <a-tab-pane key="headers" tab="Headers">
            <KvEditor v-model:value="cfg.headers" />
          </a-tab-pane>

          <!-- Query Params -->
          <a-tab-pane key="params" tab="Params">
            <KvEditor v-model:value="cfg.params" />
          </a-tab-pane>

          <!-- Body -->
          <a-tab-pane key="body" tab="Body">
            <a-radio-group v-model:value="cfg.body_type" size="small" style="margin-bottom: 8px">
              <a-radio-button value="none">None</a-radio-button>
              <a-radio-button value="json">JSON</a-radio-button>
              <a-radio-button value="form">Form</a-radio-button>
              <a-radio-button value="raw">Raw</a-radio-button>
            </a-radio-group>
            <KvEditor v-if="cfg.body_type === 'form'" v-model:value="formBody" />
            <a-textarea
              v-else-if="cfg.body_type !== 'none'"
              v-model:value="cfg.body"
              :rows="8"
              placeholder='{"key": "value"}'
              style="font-family: monospace; font-size: 13px"
            />
          </a-tab-pane>

          <!-- Auth -->
          <a-tab-pane key="auth" tab="Auth">
            <a-form-item label="认证方式">
              <a-select v-model:value="cfg.auth.type" style="width: 160px">
                <a-select-option value="none">无</a-select-option>
                <a-select-option value="bearer">Bearer Token</a-select-option>
                <a-select-option value="basic">Basic Auth</a-select-option>
                <a-select-option value="apikey">API Key</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="cfg.auth.type === 'bearer'">
              <a-form-item label="Token">
                <a-input v-model:value="cfg.auth.token" placeholder="支持 {{variable}} 变量" />
              </a-form-item>
            </template>
            <template v-if="cfg.auth.type === 'basic'">
              <a-form-item label="用户名">
                <a-input v-model:value="cfg.auth.username" />
              </a-form-item>
              <a-form-item label="密码">
                <a-input-password v-model:value="cfg.auth.password" />
              </a-form-item>
            </template>
            <template v-if="cfg.auth.type === 'apikey'">
              <a-form-item label="Header 名称">
                <a-input v-model:value="cfg.auth.header" placeholder="X-API-Key" />
              </a-form-item>
              <a-form-item label="Key 值">
                <a-input v-model:value="cfg.auth.value" />
              </a-form-item>
            </template>
          </a-tab-pane>
        </a-tabs>

        <!-- 超时 -->
        <a-form-item label="超时时间（秒）" style="margin-top: 16px">
          <a-input-number v-model:value="cfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <!-- ── 断言 ────────────────────────────────── -->
        <a-divider orientation="left">断言</a-divider>
        <div v-for="(a, i) in cfg.assertions" :key="i" class="assertion-row">
          <a-select v-model:value="a.target" style="width: 130px" placeholder="断言对象">
            <a-select-option value="status_code">状态码</a-select-option>
            <a-select-option value="body">响应体</a-select-option>
            <a-select-option value="header">响应头</a-select-option>
            <a-select-option value="duration">响应时间(ms)</a-select-option>
          </a-select>
          <a-input
            v-if="a.target === 'body' || a.target === 'header'"
            v-model:value="a.expression"
            placeholder="JSONPath / Header名"
            style="width: 160px"
          />
          <a-select v-model:value="a.operator" style="width: 110px" placeholder="条件">
            <a-select-option value="eq">等于</a-select-option>
            <a-select-option value="contains">包含</a-select-option>
            <a-select-option value="gt">大于</a-select-option>
            <a-select-option value="lt">小于</a-select-option>
            <a-select-option value="exists">存在</a-select-option>
          </a-select>
          <a-input
            v-if="a.operator !== 'exists'"
            v-model:value="a.expected"
            placeholder="期望值"
            style="flex: 1"
          />
          <MinusCircleOutlined class="remove-btn" @click="cfg.assertions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="addAssertion">
          <PlusOutlined /> 添加断言
        </a-button>

        <!-- ── 变量提取 ─────────────────────────────── -->
        <a-divider orientation="left">变量提取</a-divider>
        <div v-for="(e, i) in cfg.extractions" :key="i" class="assertion-row">
          <a-input v-model:value="e.variable" placeholder="变量名" style="width: 140px" />
          <span style="padding: 0 8px; color: #999">=</span>
          <a-input v-model:value="e.expression" placeholder="JSONPath（如 $.data.token）" style="flex: 1" />
          <MinusCircleOutlined class="remove-btn" @click="cfg.extractions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="cfg.extractions.push({ variable: '', expression: '' })">
          <PlusOutlined /> 添加变量提取
        </a-button>
      </template>

      <!-- ── GraphQL 测试配置 ─────────────────────────── -->
      <template v-else-if="form.case_type === 'graphql'">
        <a-divider orientation="left">GraphQL 配置</a-divider>

        <!-- Endpoint -->
        <a-form-item label="Endpoint" :rules="[{ required: true, message: '请输入 GraphQL 端点' }]">
          <a-input v-model:value="gqlCfg.endpoint" placeholder="https://api.example.com/graphql" />
        </a-form-item>

        <!-- Operation Type + Name -->
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="操作类型">
              <a-select v-model:value="gqlCfg.operation_type">
                <a-select-option value="query">Query</a-select-option>
                <a-select-option value="mutation">Mutation</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="16">
            <a-form-item label="Operation Name（可选）">
              <a-input v-model:value="gqlCfg.operation_name" placeholder="如 GetUser" />
            </a-form-item>
          </a-col>
        </a-row>

        <!-- Query -->
        <a-form-item label="Query / Mutation" :rules="[{ required: true, message: '请输入 GraphQL 查询' }]">
          <a-textarea
            v-model:value="gqlCfg.query"
            :rows="8"
            placeholder="query GetUser($id: ID!) {&#10;  user(id: $id) {&#10;    name&#10;    email&#10;  }&#10;}"
            style="font-family: monospace; font-size: 13px"
          />
        </a-form-item>

        <!-- Variables -->
        <a-form-item label="Variables（JSON）">
          <a-textarea
            v-model:value="gqlCfg.variables_text"
            :rows="4"
            placeholder='{"id": "123"}'
            style="font-family: monospace; font-size: 13px"
          />
        </a-form-item>

        <!-- Tabs: Headers / Auth -->
        <a-tabs v-model:activeKey="gqlActiveTab" size="small">
          <a-tab-pane key="headers" tab="Headers">
            <KvEditor v-model:value="gqlCfg.headers" />
          </a-tab-pane>
          <a-tab-pane key="auth" tab="Auth">
            <a-form-item label="认证方式">
              <a-select v-model:value="gqlCfg.auth.type" style="width: 160px">
                <a-select-option value="none">无</a-select-option>
                <a-select-option value="bearer">Bearer Token</a-select-option>
                <a-select-option value="basic">Basic Auth</a-select-option>
                <a-select-option value="apikey">API Key</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="gqlCfg.auth.type === 'bearer'">
              <a-form-item label="Token">
                <a-input v-model:value="gqlCfg.auth.token" placeholder="支持 {{variable}} 变量" />
              </a-form-item>
            </template>
            <template v-if="gqlCfg.auth.type === 'basic'">
              <a-form-item label="用户名">
                <a-input v-model:value="gqlCfg.auth.username" />
              </a-form-item>
              <a-form-item label="密码">
                <a-input-password v-model:value="gqlCfg.auth.password" />
              </a-form-item>
            </template>
            <template v-if="gqlCfg.auth.type === 'apikey'">
              <a-form-item label="Header 名称">
                <a-input v-model:value="gqlCfg.auth.header" placeholder="X-API-Key" />
              </a-form-item>
              <a-form-item label="Key 值">
                <a-input v-model:value="gqlCfg.auth.value" />
              </a-form-item>
            </template>
          </a-tab-pane>
        </a-tabs>

        <!-- 超时 -->
        <a-form-item label="超时时间（秒）" style="margin-top: 16px">
          <a-input-number v-model:value="gqlCfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <!-- ── 断言 ────────────────────────────────── -->
        <a-divider orientation="left">断言</a-divider>
        <div v-for="(a, i) in gqlCfg.assertions" :key="i" class="assertion-row">
          <a-select v-model:value="a.target" style="width: 150px" placeholder="断言对象">
            <a-select-option value="status_code">状态码</a-select-option>
            <a-select-option value="body">响应体(data)</a-select-option>
            <a-select-option value="header">响应头</a-select-option>
            <a-select-option value="duration">响应时间(ms)</a-select-option>
            <a-select-option value="graphql_errors">GraphQL Errors</a-select-option>
          </a-select>
          <a-input
            v-if="a.target === 'body' || a.target === 'header'"
            v-model:value="a.expression"
            placeholder="JSONPath / Header名"
            style="width: 160px"
          />
          <a-select v-model:value="a.operator" style="width: 110px" placeholder="条件">
            <a-select-option value="eq">等于</a-select-option>
            <a-select-option value="contains">包含</a-select-option>
            <a-select-option value="gt">大于</a-select-option>
            <a-select-option value="lt">小于</a-select-option>
            <a-select-option value="exists">存在</a-select-option>
            <a-select-option v-if="a.target === 'graphql_errors'" value="not_exists">不存在</a-select-option>
          </a-select>
          <a-input
            v-if="a.operator !== 'exists' && a.operator !== 'not_exists'"
            v-model:value="a.expected"
            placeholder="期望值"
            style="flex: 1"
          />
          <MinusCircleOutlined class="remove-btn" @click="gqlCfg.assertions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="addGqlAssertion">
          <PlusOutlined /> 添加断言
        </a-button>

        <!-- ── 变量提取 ─────────────────────────────── -->
        <a-divider orientation="left">变量提取</a-divider>
        <div v-for="(e, i) in gqlCfg.extractions" :key="i" class="assertion-row">
          <a-input v-model:value="e.variable" placeholder="变量名" style="width: 140px" />
          <span style="padding: 0 8px; color: #999">=</span>
          <a-input v-model:value="e.expression" placeholder="JSONPath（如 $.data.user.name）" style="flex: 1" />
          <MinusCircleOutlined class="remove-btn" @click="gqlCfg.extractions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="gqlCfg.extractions.push({ variable: '', expression: '' })">
          <PlusOutlined /> 添加变量提取
        </a-button>
      </template>

      <!-- ── WebSocket 测试配置 ────────────────────────── -->
      <template v-else-if="form.case_type === 'websocket'">
        <a-divider orientation="left">WebSocket 配置</a-divider>

        <!-- URL -->
        <a-form-item label="WebSocket 地址" :rules="[{ required: true, message: '请输入 WS 地址' }]">
          <a-input v-model:value="wsCfg.url" placeholder="wss://echo.example.com/ws" />
        </a-form-item>

        <!-- Tabs: Headers / Auth -->
        <a-tabs v-model:activeKey="wsActiveTab" size="small">
          <a-tab-pane key="headers" tab="Headers">
            <KvEditor v-model:value="wsCfg.headers" />
          </a-tab-pane>
          <a-tab-pane key="auth" tab="Auth">
            <a-form-item label="认证方式">
              <a-select v-model:value="wsCfg.auth.type" style="width: 160px">
                <a-select-option value="none">无</a-select-option>
                <a-select-option value="bearer">Bearer Token</a-select-option>
                <a-select-option value="basic">Basic Auth</a-select-option>
                <a-select-option value="apikey">API Key</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="wsCfg.auth.type === 'bearer'">
              <a-form-item label="Token">
                <a-input v-model:value="wsCfg.auth.token" placeholder="支持 {{variable}} 变量" />
              </a-form-item>
            </template>
            <template v-if="wsCfg.auth.type === 'basic'">
              <a-form-item label="用户名"><a-input v-model:value="wsCfg.auth.username" /></a-form-item>
              <a-form-item label="密码"><a-input-password v-model:value="wsCfg.auth.password" /></a-form-item>
            </template>
            <template v-if="wsCfg.auth.type === 'apikey'">
              <a-form-item label="Header 名称"><a-input v-model:value="wsCfg.auth.header" placeholder="X-API-Key" /></a-form-item>
              <a-form-item label="Key 值"><a-input v-model:value="wsCfg.auth.value" /></a-form-item>
            </template>
          </a-tab-pane>
        </a-tabs>

        <!-- 连接超时 -->
        <a-form-item label="连接超时（秒）" style="margin-top: 16px">
          <a-input-number v-model:value="wsCfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <!-- ── 消息序列 ──────────────────────────────── -->
        <a-divider orientation="left">消息序列</a-divider>
        <div v-for="(m, mi) in wsCfg.messages" :key="mi" class="ws-message-block">
          <div class="ws-message-header">
            <a-tag :color="m.action === 'send' ? 'blue' : m.action === 'receive' ? 'green' : 'default'">
              #{{ mi + 1 }}
            </a-tag>
            <a-select v-model:value="m.action" style="width: 120px" size="small">
              <a-select-option value="send">发送</a-select-option>
              <a-select-option value="receive">接收</a-select-option>
              <a-select-option value="disconnect">断开</a-select-option>
            </a-select>
            <MinusCircleOutlined class="remove-btn" @click="wsCfg.messages.splice(mi, 1)" />
          </div>

          <!-- Send 配置 -->
          <template v-if="m.action === 'send'">
            <a-row :gutter="8" style="margin-top: 8px">
              <a-col :span="6">
                <a-select v-model:value="m.data_type" size="small" style="width: 100%">
                  <a-select-option value="text">Text</a-select-option>
                  <a-select-option value="json">JSON</a-select-option>
                </a-select>
              </a-col>
              <a-col :span="18">
                <a-textarea
                  v-model:value="m.data"
                  :rows="2"
                  placeholder='发送内容，支持 {{variable}}'
                  style="font-family: monospace; font-size: 12px"
                />
              </a-col>
            </a-row>
          </template>

          <!-- Receive 配置 -->
          <template v-if="m.action === 'receive'">
            <a-form-item label="接收超时（秒）" style="margin-top: 8px; margin-bottom: 8px">
              <a-input-number v-model:value="m.timeout" :min="1" :max="120" size="small" style="width: 100px" />
            </a-form-item>

            <!-- 断言 -->
            <div style="margin-bottom: 4px; font-weight: 500; font-size: 12px; color: #666">断言</div>
            <div v-for="(a, ai) in m.assertions" :key="ai" class="assertion-row">
              <a-select v-model:value="a.target" style="width: 100px" size="small">
                <a-select-option value="body">消息体</a-select-option>
                <a-select-option value="raw">原始文本</a-select-option>
              </a-select>
              <a-input
                v-if="a.target === 'body'"
                v-model:value="a.expression"
                placeholder="JSONPath"
                size="small"
                style="width: 130px"
              />
              <a-select v-model:value="a.operator" style="width: 90px" size="small">
                <a-select-option value="eq">等于</a-select-option>
                <a-select-option value="contains">包含</a-select-option>
                <a-select-option value="exists">存在</a-select-option>
              </a-select>
              <a-input
                v-if="a.operator !== 'exists'"
                v-model:value="a.expected"
                placeholder="期望值"
                size="small"
                style="flex: 1"
              />
              <MinusCircleOutlined class="remove-btn" @click="m.assertions.splice(ai, 1)" />
            </div>
            <a-button type="dashed" size="small" @click="m.assertions.push({ target: 'body', operator: 'eq', expected: '', expression: '' })" style="margin-bottom: 8px">
              <PlusOutlined /> 断言
            </a-button>

            <!-- 变量提取 -->
            <div style="margin-bottom: 4px; font-weight: 500; font-size: 12px; color: #666">变量提取</div>
            <div v-for="(e, ei) in m.extractions" :key="ei" class="assertion-row">
              <a-input v-model:value="e.variable" placeholder="变量名" size="small" style="width: 120px" />
              <span style="padding: 0 4px; color: #999">=</span>
              <a-input v-model:value="e.expression" placeholder="JSONPath" size="small" style="flex: 1" />
              <MinusCircleOutlined class="remove-btn" @click="m.extractions.splice(ei, 1)" />
            </div>
            <a-button type="dashed" size="small" @click="m.extractions.push({ variable: '', expression: '' })">
              <PlusOutlined /> 提取
            </a-button>
          </template>
        </div>
        <a-space style="margin-top: 8px">
          <a-button type="dashed" size="small" @click="addWsMessage('send')">
            <PlusOutlined /> 添加发送
          </a-button>
          <a-button type="dashed" size="small" @click="addWsMessage('receive')">
            <PlusOutlined /> 添加接收
          </a-button>
        </a-space>
      </template>

      <!-- ── gRPC 测试配置 ─────────────────────────────── -->
      <template v-else-if="form.case_type === 'grpc'">
        <a-divider orientation="left">gRPC 配置</a-divider>

        <!-- Target + TLS -->
        <a-row :gutter="16">
          <a-col :span="16">
            <a-form-item label="Target 地址" :rules="[{ required: true, message: '请输入 gRPC 地址' }]">
              <a-input v-model:value="grpcCfg.target" placeholder="localhost:50051" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="TLS">
              <a-switch v-model:checked="grpcCfg.use_tls" checked-children="TLS" un-checked-children="明文" />
            </a-form-item>
          </a-col>
        </a-row>

        <!-- Service + Method -->
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="Service（含 package）" :rules="[{ required: true, message: '请输入 Service 名' }]">
              <a-input v-model:value="grpcCfg.service" placeholder="package.ServiceName" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Method" :rules="[{ required: true, message: '请输入 Method 名' }]">
              <a-input v-model:value="grpcCfg.method" placeholder="MethodName" />
            </a-form-item>
          </a-col>
        </a-row>

        <!-- Proto 内容 -->
        <a-form-item label="Proto 定义" :rules="[{ required: true, message: '请输入 .proto 内容' }]">
          <a-textarea
            v-model:value="grpcCfg.proto_content"
            :rows="10"
            placeholder='syntax = "proto3";&#10;package user;&#10;&#10;service UserService {&#10;  rpc GetUser(GetUserRequest) returns (GetUserResponse);&#10;}&#10;&#10;message GetUserRequest {&#10;  string user_id = 1;&#10;}&#10;&#10;message GetUserResponse {&#10;  string name = 1;&#10;  string email = 2;&#10;}'
            style="font-family: monospace; font-size: 12px"
          />
        </a-form-item>

        <!-- Request JSON -->
        <a-form-item label="Request JSON">
          <a-textarea
            v-model:value="grpcCfg.request_json"
            :rows="5"
            placeholder='{"user_id": "123"}'
            style="font-family: monospace; font-size: 13px"
          />
        </a-form-item>

        <!-- Metadata -->
        <a-form-item label="Metadata（gRPC 头部）">
          <KvEditor v-model:value="grpcCfg.metadata" />
        </a-form-item>

        <!-- 超时 -->
        <a-form-item label="超时时间（秒）">
          <a-input-number v-model:value="grpcCfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <!-- ── 断言 ────────────────────────────────── -->
        <a-divider orientation="left">断言</a-divider>
        <div v-for="(a, i) in grpcCfg.assertions" :key="i" class="assertion-row">
          <a-select v-model:value="a.target" style="width: 140px" placeholder="断言对象">
            <a-select-option value="body">响应体</a-select-option>
            <a-select-option value="grpc_status">gRPC 状态</a-select-option>
            <a-select-option value="duration">响应时间(ms)</a-select-option>
          </a-select>
          <a-input
            v-if="a.target === 'body'"
            v-model:value="a.expression"
            placeholder="JSONPath"
            style="width: 150px"
          />
          <a-select v-model:value="a.operator" style="width: 110px" placeholder="条件">
            <a-select-option value="eq">等于</a-select-option>
            <a-select-option value="contains">包含</a-select-option>
            <a-select-option value="gt">大于</a-select-option>
            <a-select-option value="lt">小于</a-select-option>
            <a-select-option value="exists">存在</a-select-option>
          </a-select>
          <a-input
            v-if="a.operator !== 'exists'"
            v-model:value="a.expected"
            :placeholder="a.target === 'grpc_status' ? 'OK / NOT_FOUND / ...' : '期望值'"
            style="flex: 1"
          />
          <MinusCircleOutlined class="remove-btn" @click="grpcCfg.assertions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="addGrpcAssertion">
          <PlusOutlined /> 添加断言
        </a-button>

        <!-- ── 变量提取 ─────────────────────────────── -->
        <a-divider orientation="left">变量提取</a-divider>
        <div v-for="(e, i) in grpcCfg.extractions" :key="i" class="assertion-row">
          <a-input v-model:value="e.variable" placeholder="变量名" style="width: 140px" />
          <span style="padding: 0 8px; color: #999">=</span>
          <a-input v-model:value="e.expression" placeholder="JSONPath（如 $.name）" style="flex: 1" />
          <MinusCircleOutlined class="remove-btn" @click="grpcCfg.extractions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="grpcCfg.extractions.push({ variable: '', expression: '' })">
          <PlusOutlined /> 添加变量提取
        </a-button>
      </template>

      <!-- ── Web / Android 占位 ────────────────────── -->
      <template v-else-if="form.case_type === 'web' || form.case_type === 'android'">
        <a-alert
          :message="`${form.case_type === 'web' ? 'Web UI' : 'Android UI'} 用例配置将在后续阶段实现`"
          type="info"
          show-icon
          style="margin-top: 16px"
        />
      </template>
    </a-form>

    <template #footer>
      <a-space style="float: right">
        <a-button @click="emit('close')">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
      </a-space>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons-vue'
import { caseApi } from '@/api'
import KvEditor from '@/components/common/KvEditor.vue'

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']

const props = defineProps<{
  open: boolean
  moduleId: number | null
  editCase?: any
  defaultCaseType?: string
}>()
const emit = defineEmits<{ close: []; saved: [] }>()

const isEdit = ref(false)
const saving = ref(false)
const activeTab = ref('headers')
const gqlActiveTab = ref('headers')
const wsActiveTab = ref('headers')
const formRef = ref()

// 基本信息
const form = reactive({
  name: '',
  description: '',
  case_type: 'api',
  tags: [] as string[],
})

// 接口测试配置
const cfg = reactive({
  url: '',
  method: 'GET',
  headers: {} as Record<string, string>,
  params: {} as Record<string, string>,
  body_type: 'none' as 'none' | 'json' | 'form' | 'raw',
  body: '',
  auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
  timeout: 30,
  assertions: [] as any[],
  extractions: [] as any[],
})
const formBody = ref<Record<string, string>>({})

// GraphQL 测试配置
const gqlCfg = reactive({
  endpoint: '',
  operation_type: 'query' as 'query' | 'mutation',
  query: '',
  variables_text: '',
  operation_name: '',
  headers: {} as Record<string, string>,
  auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
  timeout: 30,
  assertions: [] as any[],
  extractions: [] as any[],
})

// WebSocket 测试配置
const wsCfg = reactive({
  url: '',
  headers: {} as Record<string, string>,
  auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
  timeout: 30,
  messages: [] as any[],
})

// gRPC 测试配置
const grpcCfg = reactive({
  target: '',
  use_tls: false,
  proto_content: '',
  service: '',
  method: '',
  request_json: '',
  metadata: {} as Record<string, string>,
  timeout: 30,
  assertions: [] as any[],
  extractions: [] as any[],
})

watch(() => props.open, (v) => {
  if (!v) return
  if (props.editCase) {
    isEdit.value = true
    const c = props.editCase
    form.name = c.name
    form.description = c.description ?? ''
    form.case_type = c.case_type
    form.tags = c.tags ?? []
    const step = c.config?.steps?.[0] ?? c.config ?? {}
    const bodyType = step.body_type ?? 'none'
    if (bodyType === 'form') {
      if (step.body && typeof step.body === 'object' && !Array.isArray(step.body)) {
        formBody.value = { ...step.body }
      } else if (typeof step.body === 'string' && step.body.trim()) {
        try {
          const parsed = JSON.parse(step.body)
          formBody.value = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
        } catch {
          formBody.value = {}
        }
      } else {
        formBody.value = {}
      }
    } else {
      formBody.value = {}
    }

    Object.assign(cfg, {
      url: step.url ?? '',
      method: step.method ?? 'GET',
      headers: step.headers ?? {},
      params: step.params ?? {},
      body_type: bodyType,
      body: typeof step.body === 'string' ? step.body : JSON.stringify(step.body ?? '', null, 2),
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', ...step.auth },
      timeout: step.timeout ?? 30,
      assertions: step.assertions ? [...step.assertions] : [],
      extractions: step.extractions ? [...step.extractions] : [],
    })

    // GraphQL 编辑回填
    if (c.case_type === 'graphql') {
      const vars = step.variables
      Object.assign(gqlCfg, {
        endpoint: step.endpoint ?? '',
        operation_type: step.operation_type ?? 'query',
        query: step.query ?? '',
        variables_text: vars ? JSON.stringify(vars, null, 2) : '',
        operation_name: step.operation_name ?? '',
        headers: step.headers ?? {},
        auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', ...step.auth },
        timeout: step.timeout ?? 30,
        assertions: step.assertions ? [...step.assertions] : [],
        extractions: step.extractions ? [...step.extractions] : [],
      })
    }

    // WebSocket 编辑回填
    if (c.case_type === 'websocket') {
      Object.assign(wsCfg, {
        url: step.url ?? '',
        headers: step.headers ?? {},
        auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', ...step.auth },
        timeout: step.timeout ?? 30,
        messages: (step.messages ?? []).map((m: any) => ({
          action: m.action ?? 'send',
          data: m.data ?? '',
          data_type: m.data_type ?? 'text',
          timeout: m.timeout ?? 10,
          assertions: m.assertions ? [...m.assertions] : [],
          extractions: m.extractions ? [...m.extractions] : [],
        })),
      })
    }

    // gRPC 编辑回填
    if (c.case_type === 'grpc') {
      Object.assign(grpcCfg, {
        target: step.target ?? '',
        use_tls: step.use_tls ?? false,
        proto_content: step.proto_content ?? '',
        service: step.service ?? '',
        method: step.method ?? '',
        request_json: step.request_json ?? '',
        metadata: step.metadata ?? {},
        timeout: step.timeout ?? 30,
        assertions: step.assertions ? [...step.assertions] : [],
        extractions: step.extractions ? [...step.extractions] : [],
      })
    }
  } else {
    isEdit.value = false
    form.name = ''
    form.description = ''
    form.case_type = props.defaultCaseType ?? 'api'
    form.tags = []
    Object.assign(cfg, {
      url: '', method: 'GET', headers: {}, params: {},
      body_type: 'none', body: '',
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
      timeout: 30, assertions: [], extractions: [],
    })
    formBody.value = {}
    Object.assign(gqlCfg, {
      endpoint: '', operation_type: 'query', query: '', variables_text: '',
      operation_name: '', headers: {},
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
      timeout: 30, assertions: [], extractions: [],
    })
    Object.assign(wsCfg, {
      url: '', headers: {},
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
      timeout: 30, messages: [],
    })
    Object.assign(grpcCfg, {
      target: '', use_tls: false, proto_content: '', service: '', method: '',
      request_json: '', metadata: {}, timeout: 30, assertions: [], extractions: [],
    })
  }
})

function addAssertion() {
  cfg.assertions.push({ target: 'status_code', operator: 'eq', expected: '200', expression: '' })
}

function addGqlAssertion() {
  gqlCfg.assertions.push({ target: 'status_code', operator: 'eq', expected: '200', expression: '' })
}

function addWsMessage(action: 'send' | 'receive') {
  if (action === 'send') {
    wsCfg.messages.push({ action: 'send', data: '', data_type: 'text' })
  } else {
    wsCfg.messages.push({ action: 'receive', timeout: 10, assertions: [], extractions: [] })
  }
}

function buildWebsocketConfig() {
  return {
    steps: [{
      name: form.name,
      url: wsCfg.url,
      headers: wsCfg.headers,
      auth: wsCfg.auth,
      timeout: wsCfg.timeout,
      messages: wsCfg.messages.map((m: any) => {
        if (m.action === 'send') {
          return { action: 'send', data: m.data, data_type: m.data_type }
        } else if (m.action === 'receive') {
          return { action: 'receive', timeout: m.timeout, assertions: m.assertions, extractions: m.extractions }
        }
        return { action: m.action }
      }),
    }],
  }
}

function addGrpcAssertion() {
  grpcCfg.assertions.push({ target: 'grpc_status', operator: 'eq', expected: 'OK', expression: '' })
}

function buildGrpcConfig() {
  return {
    steps: [{
      name: form.name,
      target: grpcCfg.target,
      use_tls: grpcCfg.use_tls,
      proto_content: grpcCfg.proto_content,
      service: grpcCfg.service,
      method: grpcCfg.method,
      request_json: grpcCfg.request_json,
      metadata: grpcCfg.metadata,
      timeout: grpcCfg.timeout,
      assertions: grpcCfg.assertions,
      extractions: grpcCfg.extractions,
    }],
  }
}

function buildGraphqlConfig() {
  let variables: any = {}
  if (gqlCfg.variables_text.trim()) {
    try { variables = JSON.parse(gqlCfg.variables_text) } catch { /* 保持空对象 */ }
  }
  return {
    steps: [{
      name: form.name,
      endpoint: gqlCfg.endpoint,
      operation_type: gqlCfg.operation_type,
      query: gqlCfg.query,
      variables,
      operation_name: gqlCfg.operation_name || null,
      headers: gqlCfg.headers,
      auth: gqlCfg.auth,
      timeout: gqlCfg.timeout,
      assertions: gqlCfg.assertions,
      extractions: gqlCfg.extractions,
    }],
  }
}

function buildConfig() {
  if (form.case_type === 'graphql') {
    return buildGraphqlConfig()
  }
  if (form.case_type === 'websocket') {
    return buildWebsocketConfig()
  }
  if (form.case_type === 'grpc') {
    return buildGrpcConfig()
  }
  let body: any = cfg.body_type === 'form' ? { ...formBody.value } : cfg.body
  if (cfg.body_type === 'json' && typeof body === 'string') {
    try { body = JSON.parse(body) } catch { /* 保持字符串 */ }
  }
  return {
    steps: [{
      name: form.name,
      url: cfg.url,
      method: cfg.method,
      headers: cfg.headers,
      params: cfg.params,
      body_type: cfg.body_type,
      body: cfg.body_type === 'none' ? null : body,
      auth: cfg.auth,
      timeout: cfg.timeout,
      assertions: cfg.assertions,
      extractions: cfg.extractions,
    }],
  }
}

async function handleSave() {
  try { await formRef.value?.validate() } catch { return }
  if (form.case_type === 'api' && !cfg.url) {
    message.warning('请输入请求地址')
    return
  }
  if (form.case_type === 'graphql') {
    if (!gqlCfg.endpoint) { message.warning('请输入 GraphQL 端点'); return }
    if (!gqlCfg.query.trim()) { message.warning('请输入 GraphQL Query'); return }
  }
  if (form.case_type === 'websocket') {
    if (!wsCfg.url) { message.warning('请输入 WebSocket 地址'); return }
    if (wsCfg.messages.length === 0) { message.warning('请添加至少一条消息'); return }
  }
  if (form.case_type === 'grpc') {
    if (!grpcCfg.target) { message.warning('请输入 gRPC Target 地址'); return }
    if (!grpcCfg.proto_content.trim()) { message.warning('请输入 Proto 定义'); return }
    if (!grpcCfg.service) { message.warning('请输入 Service 名称'); return }
    if (!grpcCfg.method) { message.warning('请输入 Method 名称'); return }
  }
  saving.value = true
  try {
    const payload = {
      name: form.name,
      description: form.description,
      case_type: form.case_type,
      tags: form.tags,
      module_id: props.moduleId!,
      config: buildConfig(),
    }
    if (isEdit.value) {
      await caseApi.update(props.editCase.id, { name: payload.name, description: payload.description, tags: payload.tags, config: payload.config })
    } else {
      await caseApi.create(payload)
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    emit('saved')
    emit('close')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.assertion-row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: center;
}
.remove-btn {
  color: #ff4d4f;
  cursor: pointer;
  flex-shrink: 0;
}
.ws-message-block {
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 10px;
  background: #fafafa;
}
.ws-message-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
