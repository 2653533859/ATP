<template>
  <a-drawer
    :open="open"
    :title="isEdit ? t('case_form.title_edit') : t('case_form.title_create')"
    width="760"
    :destroy-on-close="true"
    @close="emit('close')"
  >
    <a-form :model="form" layout="vertical" ref="formRef">
      <a-divider orientation="left">{{ t('case_form.sections.basic_info') }}</a-divider>
      <a-row :gutter="16">
        <a-col :span="16">
          <a-form-item :label="t('case_form.basic.name_label')" name="name" :rules="[{ required: true, message: t('case_form.basic.name_required') }]">
            <a-input v-model:value="form.name" :placeholder="t('case_form.basic.name_placeholder')" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case_form.basic.type_label')" name="case_type">
            <a-select v-model:value="form.case_type" :disabled="isEdit">
              <a-select-option value="api">{{ t('case_form.case_types.api') }}</a-select-option>
              <a-select-option value="graphql">{{ t('case_form.case_types.graphql') }}</a-select-option>
              <a-select-option value="websocket">{{ t('case_form.case_types.websocket') }}</a-select-option>
              <a-select-option value="grpc">{{ t('case_form.case_types.grpc') }}</a-select-option>
              <a-select-option value="web">{{ t('case_form.case_types.web') }}</a-select-option>
              <a-select-option value="android">{{ t('case_form.case_types.android') }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item :label="t('case_form.basic.tags_label')">
        <a-select
          v-model:value="form.tags"
          mode="tags"
          :placeholder="t('case_form.basic.tags_placeholder')"
          :token-separators="[',']"
        />
      </a-form-item>
      <a-form-item :label="t('case_form.basic.description_label')">
        <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('case_form.basic.description_placeholder')" />
      </a-form-item>
      <a-form-item :label="t('case_form.basic.dataset_label')">
        <a-select
          v-model:value="form.dataset_id"
          :placeholder="t('case_form.basic.dataset_placeholder')"
          allow-clear
          :options="datasetOptions"
        />
        <div v-if="form.dataset_id" style="color:#999;font-size:12px;margin-top:4px">
          {{ t('case_form.basic.dataset_hint') }}
        </div>
      </a-form-item>

      <template v-if="form.case_type === 'api'">
        <a-divider orientation="left">{{ t('case_form.sections.request_config') }}</a-divider>

        <a-form-item :label="t('case_form.api.url_label')" :rules="[{ required: true, message: t('case_form.api.url_required') }]">
          <a-input-group compact>
            <a-select v-model:value="cfg.method" style="width: 110px">
              <a-select-option v-for="m in HTTP_METHODS" :key="m" :value="m">{{ m }}</a-select-option>
            </a-select>
            <a-input v-model:value="cfg.url" style="width: calc(100% - 110px)" placeholder="https://api.example.com/v1/..." />
          </a-input-group>
        </a-form-item>

        <a-tabs v-model:activeKey="activeTab" size="small">
          <a-tab-pane key="headers" tab="Headers">
            <KvEditor v-model:value="cfg.headers" />
          </a-tab-pane>

          <a-tab-pane key="params" tab="Params">
            <KvEditor v-model:value="cfg.params" />
          </a-tab-pane>

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

          <a-tab-pane key="auth" tab="Auth">
            <a-form-item :label="t('case_form.auth.label')">
              <a-select v-model:value="cfg.auth.type" style="width: 160px">
                <a-select-option value="none">{{ t('case_form.auth.none') }}</a-select-option>
                <a-select-option value="bearer">{{ t('case_form.auth.bearer') }}</a-select-option>
                <a-select-option value="basic">{{ t('case_form.auth.basic') }}</a-select-option>
                <a-select-option value="apikey">{{ t('case_form.auth.apikey') }}</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="cfg.auth.type === 'bearer'">
              <a-form-item label="Token">
                <a-input v-model:value="cfg.auth.token" :placeholder="t('case_form.auth.token_placeholder', { variable: '{{variable}}' })" />
              </a-form-item>
            </template>
            <template v-if="cfg.auth.type === 'basic'">
              <a-form-item :label="t('case_form.auth.username_label')">
                <a-input v-model:value="cfg.auth.username" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.password_label')">
                <a-input-password v-model:value="cfg.auth.password" />
              </a-form-item>
            </template>
            <template v-if="cfg.auth.type === 'apikey'">
              <a-form-item :label="t('case_form.auth.header_label')">
                <a-input v-model:value="cfg.auth.header" placeholder="X-API-Key" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.value_label')">
                <a-input v-model:value="cfg.auth.value" />
              </a-form-item>
            </template>
          </a-tab-pane>
        </a-tabs>

        <a-form-item :label="t('case_form.api.timeout_label')" style="margin-top: 16px">
          <a-input-number v-model:value="cfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <a-divider orientation="left">{{ t('case_form.sections.assertions') }}</a-divider>
        <div v-for="(a, i) in cfg.assertions" :key="i" class="assertion-row">
          <a-select v-model:value="a.target" style="width: 130px" :placeholder="t('case_form.assertion.target_placeholder')">
            <a-select-option value="status_code">{{ t('case_form.assertion.targets.status_code') }}</a-select-option>
            <a-select-option value="body">{{ t('case_form.assertion.targets.body') }}</a-select-option>
            <a-select-option value="header">{{ t('case_form.assertion.targets.header') }}</a-select-option>
            <a-select-option value="duration">{{ t('case_form.assertion.targets.duration') }}</a-select-option>
          </a-select>
          <a-input
            v-if="a.target === 'body' || a.target === 'header'"
            v-model:value="a.expression"
            :placeholder="t('case_form.assertion.expression_placeholder')"
            style="width: 160px"
          />
          <a-select v-model:value="a.operator" style="width: 110px" :placeholder="t('case_form.assertion.operator_placeholder')">
            <a-select-option value="eq">{{ t('case_form.assertion.operators.eq') }}</a-select-option>
            <a-select-option value="contains">{{ t('case_form.assertion.operators.contains') }}</a-select-option>
            <a-select-option value="gt">{{ t('case_form.assertion.operators.gt') }}</a-select-option>
            <a-select-option value="lt">{{ t('case_form.assertion.operators.lt') }}</a-select-option>
            <a-select-option value="exists">{{ t('case_form.assertion.operators.exists') }}</a-select-option>
          </a-select>
          <a-input
            v-if="a.operator !== 'exists'"
            v-model:value="a.expected"
            :placeholder="t('case_form.assertion.expected_placeholder')"
            style="flex: 1"
          />
          <MinusCircleOutlined class="remove-btn" @click="cfg.assertions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="addAssertion">
          <PlusOutlined /> {{ t('case_form.assertion.add') }}
        </a-button>

        <a-divider orientation="left">{{ t('case_form.sections.extractions') }}</a-divider>
        <div v-for="(e, i) in cfg.extractions" :key="i" class="assertion-row">
          <a-input v-model:value="e.variable" :placeholder="t('case_form.extraction.variable_placeholder')" style="width: 140px" />
          <span style="padding: 0 8px; color: #999">=</span>
          <a-input v-model:value="e.expression" :placeholder="t('case_form.extraction.expression_placeholder_token')" style="flex: 1" />
          <MinusCircleOutlined class="remove-btn" @click="cfg.extractions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="cfg.extractions.push({ variable: '', expression: '' })">
          <PlusOutlined /> {{ t('case_form.extraction.add') }}
        </a-button>
      </template>

      <template v-else-if="form.case_type === 'graphql'">
        <a-divider orientation="left">{{ t('case_form.sections.graphql_config') }}</a-divider>

        <a-form-item :label="t('case_form.graphql.endpoint_label')" :rules="[{ required: true, message: t('case_form.graphql.endpoint_required') }]">
          <a-input v-model:value="gqlCfg.endpoint" placeholder="https://api.example.com/graphql" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item :label="t('case_form.graphql.operation_type_label')">
              <a-select v-model:value="gqlCfg.operation_type">
                <a-select-option value="query">Query</a-select-option>
                <a-select-option value="mutation">Mutation</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="16">
            <a-form-item :label="t('case_form.graphql.operation_name_label')">
              <a-input v-model:value="gqlCfg.operation_name" :placeholder="t('case_form.graphql.operation_name_placeholder')" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item :label="t('case_form.graphql.query_label')" :rules="[{ required: true, message: t('case_form.graphql.query_required') }]">
          <a-textarea
            v-model:value="gqlCfg.query"
            :rows="8"
            placeholder="query GetUser($id: ID!) {&#10;  user(id: $id) {&#10;    name&#10;    email&#10;  }&#10;}"
            style="font-family: monospace; font-size: 13px"
          />
        </a-form-item>

        <a-form-item :label="t('case_form.graphql.variables_label')">
          <a-textarea
            v-model:value="gqlCfg.variables_text"
            :rows="4"
            placeholder='{"id": "123"}'
            style="font-family: monospace; font-size: 13px"
          />
        </a-form-item>

        <a-tabs v-model:activeKey="gqlActiveTab" size="small">
          <a-tab-pane key="headers" tab="Headers">
            <KvEditor v-model:value="gqlCfg.headers" />
          </a-tab-pane>
          <a-tab-pane key="auth" tab="Auth">
            <a-form-item :label="t('case_form.auth.label')">
              <a-select v-model:value="gqlCfg.auth.type" style="width: 160px">
                <a-select-option value="none">{{ t('case_form.auth.none') }}</a-select-option>
                <a-select-option value="bearer">{{ t('case_form.auth.bearer') }}</a-select-option>
                <a-select-option value="basic">{{ t('case_form.auth.basic') }}</a-select-option>
                <a-select-option value="apikey">{{ t('case_form.auth.apikey') }}</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="gqlCfg.auth.type === 'bearer'">
              <a-form-item label="Token">
                <a-input v-model:value="gqlCfg.auth.token" :placeholder="t('case_form.auth.token_placeholder', { variable: '{{variable}}' })" />
              </a-form-item>
            </template>
            <template v-if="gqlCfg.auth.type === 'basic'">
              <a-form-item :label="t('case_form.auth.username_label')">
                <a-input v-model:value="gqlCfg.auth.username" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.password_label')">
                <a-input-password v-model:value="gqlCfg.auth.password" />
              </a-form-item>
            </template>
            <template v-if="gqlCfg.auth.type === 'apikey'">
              <a-form-item :label="t('case_form.auth.header_label')">
                <a-input v-model:value="gqlCfg.auth.header" placeholder="X-API-Key" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.value_label')">
                <a-input v-model:value="gqlCfg.auth.value" />
              </a-form-item>
            </template>
          </a-tab-pane>
        </a-tabs>

        <a-form-item :label="t('case_form.api.timeout_label')" style="margin-top: 16px">
          <a-input-number v-model:value="gqlCfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <a-divider orientation="left">{{ t('case_form.sections.assertions') }}</a-divider>
        <div v-for="(a, i) in gqlCfg.assertions" :key="i" class="assertion-row">
          <a-select v-model:value="a.target" style="width: 150px" :placeholder="t('case_form.assertion.target_placeholder')">
            <a-select-option value="status_code">{{ t('case_form.assertion.targets.status_code') }}</a-select-option>
            <a-select-option value="body">{{ t('case_form.assertion.targets.body_data') }}</a-select-option>
            <a-select-option value="header">{{ t('case_form.assertion.targets.header') }}</a-select-option>
            <a-select-option value="duration">{{ t('case_form.assertion.targets.duration') }}</a-select-option>
            <a-select-option value="graphql_errors">{{ t('case_form.assertion.targets.graphql_errors') }}</a-select-option>
          </a-select>
          <a-input
            v-if="a.target === 'body' || a.target === 'header'"
            v-model:value="a.expression"
            :placeholder="t('case_form.assertion.expression_placeholder')"
            style="width: 160px"
          />
          <a-select v-model:value="a.operator" style="width: 110px" :placeholder="t('case_form.assertion.operator_placeholder')">
            <a-select-option value="eq">{{ t('case_form.assertion.operators.eq') }}</a-select-option>
            <a-select-option value="contains">{{ t('case_form.assertion.operators.contains') }}</a-select-option>
            <a-select-option value="gt">{{ t('case_form.assertion.operators.gt') }}</a-select-option>
            <a-select-option value="lt">{{ t('case_form.assertion.operators.lt') }}</a-select-option>
            <a-select-option value="exists">{{ t('case_form.assertion.operators.exists') }}</a-select-option>
            <a-select-option v-if="a.target === 'graphql_errors'" value="not_exists">{{ t('case_form.assertion.operators.not_exists') }}</a-select-option>
          </a-select>
          <a-input
            v-if="a.operator !== 'exists' && a.operator !== 'not_exists'"
            v-model:value="a.expected"
            :placeholder="t('case_form.assertion.expected_placeholder')"
            style="flex: 1"
          />
          <MinusCircleOutlined class="remove-btn" @click="gqlCfg.assertions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="addGqlAssertion">
          <PlusOutlined /> {{ t('case_form.assertion.add') }}
        </a-button>

        <a-divider orientation="left">{{ t('case_form.sections.extractions') }}</a-divider>
        <div v-for="(e, i) in gqlCfg.extractions" :key="i" class="assertion-row">
          <a-input v-model:value="e.variable" :placeholder="t('case_form.extraction.variable_placeholder')" style="width: 140px" />
          <span style="padding: 0 8px; color: #999">=</span>
          <a-input v-model:value="e.expression" :placeholder="t('case_form.extraction.expression_placeholder_user')" style="flex: 1" />
          <MinusCircleOutlined class="remove-btn" @click="gqlCfg.extractions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="gqlCfg.extractions.push({ variable: '', expression: '' })">
          <PlusOutlined /> {{ t('case_form.extraction.add') }}
        </a-button>
      </template>

      <template v-else-if="form.case_type === 'websocket'">
        <a-divider orientation="left">{{ t('case_form.sections.websocket_config') }}</a-divider>

        <a-form-item :label="t('case_form.websocket.url_label')" :rules="[{ required: true, message: t('case_form.websocket.url_required') }]">
          <a-input v-model:value="wsCfg.url" placeholder="wss://echo.example.com/ws" />
        </a-form-item>

        <a-tabs v-model:activeKey="wsActiveTab" size="small">
          <a-tab-pane key="headers" tab="Headers">
            <KvEditor v-model:value="wsCfg.headers" />
          </a-tab-pane>
          <a-tab-pane key="auth" tab="Auth">
            <a-form-item :label="t('case_form.auth.label')">
              <a-select v-model:value="wsCfg.auth.type" style="width: 160px">
                <a-select-option value="none">{{ t('case_form.auth.none') }}</a-select-option>
                <a-select-option value="bearer">{{ t('case_form.auth.bearer') }}</a-select-option>
                <a-select-option value="basic">{{ t('case_form.auth.basic') }}</a-select-option>
                <a-select-option value="apikey">{{ t('case_form.auth.apikey') }}</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="wsCfg.auth.type === 'bearer'">
              <a-form-item label="Token">
                <a-input v-model:value="wsCfg.auth.token" :placeholder="t('case_form.auth.token_placeholder', { variable: '{{variable}}' })" />
              </a-form-item>
            </template>
            <template v-if="wsCfg.auth.type === 'basic'">
              <a-form-item :label="t('case_form.auth.username_label')"><a-input v-model:value="wsCfg.auth.username" /></a-form-item>
              <a-form-item :label="t('case_form.auth.password_label')"><a-input-password v-model:value="wsCfg.auth.password" /></a-form-item>
            </template>
            <template v-if="wsCfg.auth.type === 'apikey'">
              <a-form-item :label="t('case_form.auth.header_label')"><a-input v-model:value="wsCfg.auth.header" placeholder="X-API-Key" /></a-form-item>
              <a-form-item :label="t('case_form.auth.value_label')"><a-input v-model:value="wsCfg.auth.value" /></a-form-item>
            </template>
          </a-tab-pane>
        </a-tabs>

        <a-form-item :label="t('case_form.websocket.timeout_label')" style="margin-top: 16px">
          <a-input-number v-model:value="wsCfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <a-divider orientation="left">{{ t('case_form.sections.message_sequence') }}</a-divider>
        <div v-for="(m, mi) in wsCfg.messages" :key="mi" class="ws-message-block">
          <div class="ws-message-header">
            <a-tag :color="m.action === 'send' ? 'blue' : m.action === 'receive' ? 'green' : 'default'">
              #{{ mi + 1 }}
            </a-tag>
            <a-select v-model:value="m.action" style="width: 120px" size="small">
              <a-select-option value="send">{{ t('case_form.websocket.actions.send') }}</a-select-option>
              <a-select-option value="receive">{{ t('case_form.websocket.actions.receive') }}</a-select-option>
              <a-select-option value="disconnect">{{ t('case_form.websocket.actions.disconnect') }}</a-select-option>
            </a-select>
            <MinusCircleOutlined class="remove-btn" @click="wsCfg.messages.splice(mi, 1)" />
          </div>

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
                  :placeholder="t('case_form.websocket.data_placeholder', { variable: '{{variable}}' })"
                  style="font-family: monospace; font-size: 12px"
                />
              </a-col>
            </a-row>
          </template>

          <template v-if="m.action === 'receive'">
            <a-form-item :label="t('case_form.websocket.receive_timeout_label')" style="margin-top: 8px; margin-bottom: 8px">
              <a-input-number v-model:value="m.timeout" :min="1" :max="120" size="small" style="width: 100px" />
            </a-form-item>

            <div style="margin-bottom: 4px; font-weight: 500; font-size: 12px; color: #666">{{ t('case_form.sections.assertions') }}</div>
            <div v-for="(a, ai) in m.assertions" :key="ai" class="assertion-row">
              <a-select v-model:value="a.target" style="width: 100px" size="small">
                <a-select-option value="body">{{ t('case_form.assertion.targets.message_body') }}</a-select-option>
                <a-select-option value="raw">{{ t('case_form.assertion.targets.raw_text') }}</a-select-option>
              </a-select>
              <a-input
                v-if="a.target === 'body'"
                v-model:value="a.expression"
                :placeholder="t('case_form.assertion.expression_jsonpath')"
                size="small"
                style="width: 130px"
              />
              <a-select v-model:value="a.operator" style="width: 90px" size="small">
                <a-select-option value="eq">{{ t('case_form.assertion.operators.eq') }}</a-select-option>
                <a-select-option value="contains">{{ t('case_form.assertion.operators.contains') }}</a-select-option>
                <a-select-option value="exists">{{ t('case_form.assertion.operators.exists') }}</a-select-option>
              </a-select>
              <a-input
                v-if="a.operator !== 'exists'"
                v-model:value="a.expected"
                :placeholder="t('case_form.assertion.expected_placeholder')"
                size="small"
                style="flex: 1"
              />
              <MinusCircleOutlined class="remove-btn" @click="m.assertions.splice(ai, 1)" />
            </div>
            <a-button type="dashed" size="small" @click="m.assertions.push({ target: 'body', operator: 'eq', expected: '', expression: '' })" style="margin-bottom: 8px">
              <PlusOutlined /> {{ t('case_form.assertion.add_short') }}
            </a-button>

            <div style="margin-bottom: 4px; font-weight: 500; font-size: 12px; color: #666">{{ t('case_form.sections.extractions') }}</div>
            <div v-for="(e, ei) in m.extractions" :key="ei" class="assertion-row">
              <a-input v-model:value="e.variable" :placeholder="t('case_form.extraction.variable_placeholder')" size="small" style="width: 120px" />
              <span style="padding: 0 4px; color: #999">=</span>
              <a-input v-model:value="e.expression" :placeholder="t('case_form.extraction.expression_placeholder_jsonpath')" size="small" style="flex: 1" />
              <MinusCircleOutlined class="remove-btn" @click="m.extractions.splice(ei, 1)" />
            </div>
            <a-button type="dashed" size="small" @click="m.extractions.push({ variable: '', expression: '' })">
              <PlusOutlined /> {{ t('case_form.extraction.add_short') }}
            </a-button>
          </template>
        </div>
        <a-space style="margin-top: 8px">
          <a-button type="dashed" size="small" @click="addWsMessage('send')">
            <PlusOutlined /> {{ t('case_form.websocket.add_send') }}
          </a-button>
          <a-button type="dashed" size="small" @click="addWsMessage('receive')">
            <PlusOutlined /> {{ t('case_form.websocket.add_receive') }}
          </a-button>
        </a-space>
      </template>

      <template v-else-if="form.case_type === 'grpc'">
        <a-divider orientation="left">{{ t('case_form.sections.grpc_config') }}</a-divider>

        <a-row :gutter="16">
          <a-col :span="16">
            <a-form-item :label="t('case_form.grpc.target_label')" :rules="[{ required: true, message: t('case_form.grpc.target_required') }]">
              <a-input v-model:value="grpcCfg.target" placeholder="localhost:50051" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('case_form.grpc.tls_label')">
              <a-switch v-model:checked="grpcCfg.use_tls" :checked-children="t('case_form.grpc.tls_on')" :un-checked-children="t('case_form.grpc.tls_off')" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('case_form.grpc.service_label')" :rules="[{ required: true, message: t('case_form.grpc.service_required') }]">
              <a-input v-model:value="grpcCfg.service" placeholder="package.ServiceName" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('case_form.grpc.method_label')" :rules="[{ required: true, message: t('case_form.grpc.method_required') }]">
              <a-input v-model:value="grpcCfg.method" placeholder="MethodName" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item :label="t('case_form.grpc.proto_label')" :rules="[{ required: true, message: t('case_form.grpc.proto_required') }]">
          <a-textarea
            v-model:value="grpcCfg.proto_content"
            :rows="10"
            placeholder='syntax = "proto3";&#10;package user;&#10;&#10;service UserService {&#10;  rpc GetUser(GetUserRequest) returns (GetUserResponse);&#10;}&#10;&#10;message GetUserRequest {&#10;  string user_id = 1;&#10;}&#10;&#10;message GetUserResponse {&#10;  string name = 1;&#10;  string email = 2;&#10;}'
            style="font-family: monospace; font-size: 12px"
          />
        </a-form-item>

        <a-form-item :label="t('case_form.grpc.request_json_label')">
          <a-textarea
            v-model:value="grpcCfg.request_json"
            :rows="5"
            placeholder='{"user_id": "123"}'
            style="font-family: monospace; font-size: 13px"
          />
        </a-form-item>

        <a-form-item :label="t('case_form.grpc.metadata_label')">
          <KvEditor v-model:value="grpcCfg.metadata" />
        </a-form-item>

        <a-form-item :label="t('case_form.api.timeout_label')">
          <a-input-number v-model:value="grpcCfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <a-divider orientation="left">{{ t('case_form.sections.assertions') }}</a-divider>
        <div v-for="(a, i) in grpcCfg.assertions" :key="i" class="assertion-row">
          <a-select v-model:value="a.target" style="width: 140px" :placeholder="t('case_form.assertion.target_placeholder')">
            <a-select-option value="body">{{ t('case_form.assertion.targets.body') }}</a-select-option>
            <a-select-option value="grpc_status">{{ t('case_form.assertion.targets.grpc_status') }}</a-select-option>
            <a-select-option value="duration">{{ t('case_form.assertion.targets.duration') }}</a-select-option>
          </a-select>
          <a-input
            v-if="a.target === 'body'"
            v-model:value="a.expression"
            :placeholder="t('case_form.assertion.expression_jsonpath')"
            style="width: 150px"
          />
          <a-select v-model:value="a.operator" style="width: 110px" :placeholder="t('case_form.assertion.operator_placeholder')">
            <a-select-option value="eq">{{ t('case_form.assertion.operators.eq') }}</a-select-option>
            <a-select-option value="contains">{{ t('case_form.assertion.operators.contains') }}</a-select-option>
            <a-select-option value="gt">{{ t('case_form.assertion.operators.gt') }}</a-select-option>
            <a-select-option value="lt">{{ t('case_form.assertion.operators.lt') }}</a-select-option>
            <a-select-option value="exists">{{ t('case_form.assertion.operators.exists') }}</a-select-option>
          </a-select>
          <a-input
            v-if="a.operator !== 'exists'"
            v-model:value="a.expected"
            :placeholder="a.target === 'grpc_status' ? t('case_form.assertion.grpc_status_placeholder') : t('case_form.assertion.expected_placeholder')"
            style="flex: 1"
          />
          <MinusCircleOutlined class="remove-btn" @click="grpcCfg.assertions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="addGrpcAssertion">
          <PlusOutlined /> {{ t('case_form.assertion.add') }}
        </a-button>

        <a-divider orientation="left">{{ t('case_form.sections.extractions') }}</a-divider>
        <div v-for="(e, i) in grpcCfg.extractions" :key="i" class="assertion-row">
          <a-input v-model:value="e.variable" :placeholder="t('case_form.extraction.variable_placeholder')" style="width: 140px" />
          <span style="padding: 0 8px; color: #999">=</span>
          <a-input v-model:value="e.expression" :placeholder="t('case_form.extraction.expression_placeholder_name')" style="flex: 1" />
          <MinusCircleOutlined class="remove-btn" @click="grpcCfg.extractions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="grpcCfg.extractions.push({ variable: '', expression: '' })">
          <PlusOutlined /> {{ t('case_form.extraction.add') }}
        </a-button>
      </template>

      <template v-else-if="form.case_type === 'web' || form.case_type === 'android'">
        <a-alert
          :message="t('case_form.placeholder_alert', { type: form.case_type === 'web' ? t('case_form.case_types.web') : t('case_form.case_types.android') })"
          type="info"
          show-icon
          style="margin-top: 16px"
        />
      </template>
    </a-form>

    <template #footer>
      <a-space style="float: right">
        <a-button @click="emit('close')">{{ t('case_form.buttons.cancel') }}</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">{{ t('case_form.buttons.save') }}</a-button>
      </a-space>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons-vue'
import { caseApi, datasetApi } from '@/api'
import type { CaseSavePayload, CaseType } from '@/api'
import KvEditor from '@/components/common/KvEditor.vue'

const { t } = useI18n()

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']

const props = defineProps<{
  open: boolean
  moduleId: number | null
  projectId?: number | null
  editCase?: any
  defaultCaseType?: CaseType
}>()
const emit = defineEmits<{ close: []; saved: [] }>()

const isEdit = ref(false)
const saving = ref(false)
const activeTab = ref('headers')
const gqlActiveTab = ref('headers')
const wsActiveTab = ref('headers')
const formRef = ref()

const form = reactive<{ name: string; description: string; case_type: CaseType; tags: string[]; dataset_id: number | null }>({
  name: '',
  description: '',
  case_type: 'api',
  tags: [],
  dataset_id: null,
})

const datasetOptions = ref<{ label: string; value: number }[]>([])

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

const wsCfg = reactive({
  url: '',
  headers: {} as Record<string, string>,
  auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
  timeout: 30,
  messages: [] as any[],
})

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

async function loadDatasetOptions() {
  if (!props.projectId) {
    datasetOptions.value = []
    return
  }
  try {
    const items = await datasetApi.list(props.projectId)
    datasetOptions.value = items.map((d) => ({ label: `${d.name} (${d.row_count} 行)`, value: d.id }))
  } catch {
    datasetOptions.value = []
  }
}

watch(() => props.open, (v) => {
  if (!v) return
  loadDatasetOptions()
  if (props.editCase) {
    isEdit.value = true
    const c = props.editCase
    form.name = c.name
    form.description = c.description ?? ''
    form.case_type = c.case_type
    form.tags = c.tags ?? []
    form.dataset_id = c.dataset_id ?? null
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
    form.dataset_id = null
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
    try { variables = JSON.parse(gqlCfg.variables_text) } catch { /* keep empty */ }
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
    try { body = JSON.parse(body) } catch { /* keep string */ }
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
    message.warning(t('case_form.msg.url_required'))
    return
  }
  if (form.case_type === 'graphql') {
    if (!gqlCfg.endpoint) { message.warning(t('case_form.msg.graphql_endpoint_required')); return }
    if (!gqlCfg.query.trim()) { message.warning(t('case_form.msg.graphql_query_required')); return }
  }
  if (form.case_type === 'websocket') {
    if (!wsCfg.url) { message.warning(t('case_form.msg.ws_url_required')); return }
    if (wsCfg.messages.length === 0) { message.warning(t('case_form.msg.ws_messages_required')); return }
  }
  if (form.case_type === 'grpc') {
    if (!grpcCfg.target) { message.warning(t('case_form.msg.grpc_target_required')); return }
    if (!grpcCfg.proto_content.trim()) { message.warning(t('case_form.msg.grpc_proto_required')); return }
    if (!grpcCfg.service) { message.warning(t('case_form.msg.grpc_service_required')); return }
    if (!grpcCfg.method) { message.warning(t('case_form.msg.grpc_method_required')); return }
  }
  saving.value = true
  try {
    const payload: CaseSavePayload = {
      name: form.name,
      description: form.description,
      case_type: form.case_type,
      tags: form.tags,
      module_id: props.moduleId!,
      config: buildConfig(),
      dataset_id: form.dataset_id,
    }
    if (isEdit.value) {
      await caseApi.update(props.editCase.id, { name: payload.name, description: payload.description, tags: payload.tags, config: payload.config, dataset_id: form.dataset_id })
    } else {
      await caseApi.create(payload)
    }
    message.success(isEdit.value ? t('case_form.msg.updated') : t('case_form.msg.created'))
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
