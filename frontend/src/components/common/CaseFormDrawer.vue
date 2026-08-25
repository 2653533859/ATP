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
              <a-select-option value="ios">{{ t('case_form.case_types.ios') }}</a-select-option>
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
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('case.filters.priority')">
            <a-select v-model:value="form.priority">
              <a-select-option value="P0">P0</a-select-option>
              <a-select-option value="P1">P1</a-select-option>
              <a-select-option value="P2">P2</a-select-option>
              <a-select-option value="P3">P3</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('case.filters.level')">
            <a-select v-model:value="form.case_level">
              <a-select-option value="smoke">{{ t('case.levels.smoke') }}</a-select-option>
              <a-select-option value="core">{{ t('case.levels.core') }}</a-select-option>
              <a-select-option value="regression">{{ t('case.levels.regression') }}</a-select-option>
              <a-select-option value="extended">{{ t('case.levels.extended') }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item :label="t('case_form.basic.dataset_label')">
        <a-select
          v-model:value="(form.dataset_id as number | undefined)"
          :placeholder="t('case_form.basic.dataset_placeholder')"
          allow-clear
          :options="datasetOptions"
          @change="handleDatasetChange"
        />
        <div v-if="form.dataset_id" style="color:#999;font-size:12px;margin-top:4px">
          {{ t('case_form.basic.dataset_hint') }}
        </div>
      </a-form-item>
      <a-form-item v-if="form.dataset_id" :label="t('case_form.basic.dataset_version_label')">
        <a-select
          v-model:value="(form.dataset_version as number | undefined)"
          :placeholder="t('case_form.basic.dataset_version_placeholder')"
          allow-clear
          :loading="datasetVersionsLoading"
          :options="datasetVersionOptions"
        />
        <div style="color:#999;font-size:12px;margin-top:4px">
          {{ t('case_form.basic.dataset_version_hint') }}
        </div>
      </a-form-item>
      <a-form-item v-if="form.dataset_id">
        <a-checkbox v-model:checked="form.dataset_strict_schema">
          {{ t('case_form.basic.dataset_strict_schema') }}
        </a-checkbox>
        <div style="color:#999;font-size:12px;margin-top:4px">
          {{ t('case_form.basic.dataset_strict_schema_hint') }}
        </div>
        <a-row :gutter="12" style="margin-top:12px">
          <a-col :span="8">
            <a-form-item :label="t('case_form.basic.dataset_strategy')">
              <a-select v-model:value="form.dataset_strategy">
                <a-select-option value="sequential">{{ t('case_form.basic.dataset_strategy_sequential') }}</a-select-option>
                <a-select-option value="random">{{ t('case_form.basic.dataset_strategy_random') }}</a-select-option>
                <a-select-option value="fixed_count">{{ t('case_form.basic.dataset_strategy_fixed') }}</a-select-option>
                <a-select-option value="cartesian">{{ t('case_form.basic.dataset_strategy_cartesian') }}</a-select-option>
                <a-select-option value="pairwise">{{ t('case_form.basic.dataset_strategy_pairwise') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8" v-if="['fixed_count', 'random', 'cartesian', 'pairwise'].includes(form.dataset_strategy)">
            <a-form-item :label="t('case_form.basic.dataset_fixed_count')">
              <a-input-number v-model:value="(form.dataset_fixed_count as number | undefined)" :min="1" style="width:100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('case_form.basic.dataset_max_iterations')">
              <a-input-number v-model:value="form.dataset_max_iterations" :min="1" :max="1000" style="width:100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item v-if="['cartesian', 'pairwise'].includes(form.dataset_strategy)" :label="t('case_form.basic.dataset_combination_fields')">
          <a-select v-model:value="form.dataset_combination_fields" mode="tags" :placeholder="t('case_form.basic.dataset_combination_fields_placeholder')" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item :label="t('case_form.basic.dataset_seed')">
              <a-input-number v-model:value="(form.dataset_seed as number | undefined)" style="width:100%" />
            </a-form-item>
          </a-col>
          <a-col :span="16">
            <a-form-item :label="t('case_form.basic.dataset_redact_fields')">
              <a-select v-model:value="form.dataset_redact_fields" mode="tags" :placeholder="t('case_form.basic.dataset_redact_fields_placeholder')" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item v-if="form.case_type === 'api'" :label="t('case_form.basic.dataset_prepare_actions')">
          <a-textarea
            v-model:value="form.dataset_prepare_actions_text"
            :rows="5"
            :placeholder="t('case_form.basic.dataset_prepare_actions_placeholder')"
            style="font-family: monospace; font-size: 12px"
          />
          <div class="form-hint">{{ t('case_form.basic.dataset_prepare_actions_hint') }}</div>
        </a-form-item>
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
          <a-tab-pane key="headers" :tab="t('case_form.tabs.headers')">
            <KvEditor v-model:value="cfg.headers" />
          </a-tab-pane>

          <a-tab-pane key="params" :tab="t('case_form.tabs.params')">
            <KvEditor v-model:value="cfg.params" />
          </a-tab-pane>

          <a-tab-pane key="body" :tab="t('case_form.tabs.body')">
            <a-radio-group v-model:value="cfg.body_type" size="small" style="margin-bottom: 8px">
              <a-radio-button value="none">{{ t('case_form.body_types.none') }}</a-radio-button>
              <a-radio-button value="json">JSON</a-radio-button>
              <a-radio-button value="form">{{ t('case_form.body_types.form') }}</a-radio-button>
              <a-radio-button value="multipart">{{ t('case_form.body_types.multipart') }}</a-radio-button>
              <a-radio-button value="xml">XML</a-radio-button>
              <a-radio-button value="raw">{{ t('case_form.body_types.raw') }}</a-radio-button>
            </a-radio-group>
            <KvEditor v-if="cfg.body_type === 'form'" v-model:value="formBody" />
            <template v-else-if="cfg.body_type === 'multipart'">
              <div v-for="(part, i) in cfg.multipart" :key="i" class="assertion-row">
                <a-input v-model:value="part.name" :placeholder="t('case_form.multipart.name_placeholder')" style="width: 150px" />
                <a-select v-model:value="part.type" style="width: 100px">
                  <a-select-option value="text">{{ t('case_form.multipart.text') }}</a-select-option>
                  <a-select-option value="file">{{ t('case_form.multipart.file') }}</a-select-option>
                </a-select>
                <a-input
                  v-if="part.type === 'text'"
                  v-model:value="part.value"
                  :placeholder="t('case_form.multipart.value_placeholder')"
                  style="flex: 1"
                />
                <template v-else>
                  <a-upload :show-upload-list="false" :before-upload="(file: File) => uploadMultipartFile(file, i)">
                    <a-button size="small">{{ part.filename ? t('case_form.multipart.replace') : t('case_form.multipart.choose') }}</a-button>
                  </a-upload>
                  <span class="file-name">{{ part.filename || t('case_form.multipart.not_selected') }}</span>
                </template>
                <MinusCircleOutlined class="remove-btn" @click="cfg.multipart.splice(i, 1)" />
              </div>
              <a-button type="dashed" size="small" @click="addMultipartPart">
                <PlusOutlined /> {{ t('case_form.multipart.add') }}
              </a-button>
              <div class="form-hint">{{ t('case_form.multipart.hint') }}</div>
            </template>
            <a-textarea
              v-else-if="cfg.body_type !== 'none'"
              v-model:value="cfg.body"
              :rows="8"
              :placeholder="cfg.body_type === 'xml' ? '<request><id>{{id}}</id></request>' : 'JSON body'"
              style="font-family: monospace; font-size: 13px"
            />
          </a-tab-pane>

          <a-tab-pane key="cookies" :tab="t('case_form.tabs.cookies')">
            <KvEditor v-model:value="cfg.cookies" />
            <div class="form-hint">{{ t('case_form.api.cookies_hint') }}</div>
          </a-tab-pane>

          <a-tab-pane key="auth" :tab="t('case_form.tabs.auth')">
            <a-form-item :label="t('case_form.auth.label')">
              <a-select v-model:value="cfg.auth.type" style="width: 160px">
                <a-select-option value="none">{{ t('case_form.auth.none') }}</a-select-option>
                <a-select-option value="bearer">{{ t('case_form.auth.bearer') }}</a-select-option>
                <a-select-option value="basic">{{ t('case_form.auth.basic') }}</a-select-option>
                <a-select-option value="apikey">{{ t('case_form.auth.apikey') }}</a-select-option>
                <a-select-option value="digest">{{ t('case_form.auth.digest') }}</a-select-option>
                <a-select-option value="oauth2_client_credentials">{{ t('case_form.auth.oauth2_client_credentials') }}</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="cfg.auth.type === 'bearer'">
              <a-form-item :label="t('case_form.auth.token_label')">
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
            <template v-if="cfg.auth.type === 'digest'">
              <a-form-item :label="t('case_form.auth.username_label')">
                <a-input v-model:value="cfg.auth.username" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.password_label')">
                <a-input-password v-model:value="cfg.auth.password" />
              </a-form-item>
            </template>
            <template v-if="cfg.auth.type === 'oauth2_client_credentials'">
              <a-form-item :label="t('case_form.auth.token_url_label')">
                <a-input v-model:value="cfg.auth.token_url" :placeholder="t('case_form.auth.token_url_placeholder')" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.client_id_label')">
                <a-input v-model:value="cfg.auth.client_id" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.client_secret_label')">
                <a-input-password v-model:value="cfg.auth.client_secret" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.token_endpoint_auth_method_label')">
                <a-select v-model:value="cfg.auth.token_endpoint_auth_method" style="width: 220px">
                  <a-select-option value="client_secret_basic">{{ t('case_form.auth.client_secret_basic') }}</a-select-option>
                  <a-select-option value="client_secret_post">{{ t('case_form.auth.client_secret_post') }}</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item :label="t('case_form.auth.scope_label')">
                <a-input v-model:value="cfg.auth.scope" :placeholder="t('case_form.auth.scope_placeholder')" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.audience_label')">
                <a-input v-model:value="cfg.auth.audience" :placeholder="t('case_form.auth.audience_placeholder')" />
              </a-form-item>
            </template>
          </a-tab-pane>
        </a-tabs>

        <a-divider orientation="left">{{ t('case_form.api.orchestration_title') }}</a-divider>
        <a-alert
          v-if="apiScenarioSteps.length <= 1"
          type="info"
          show-icon
          :message="t('case_form.api.orchestration_single_step')"
          style="margin-bottom: 12px"
        />
        <a-list v-else size="small" bordered :data-source="apiScenarioSteps">
          <template #renderItem="{ item, index }">
            <a-list-item>
              <div style="display: flex; width: 100%; align-items: center; gap: 12px; flex-wrap: wrap">
                <a-tag color="blue">{{ index + 1 }}</a-tag>
                <span style="min-width: 150px; flex: 1">{{ item.name || t('case_form.api.orchestration_step_fallback', { index: index + 1 }) }}</span>
                <a-select
                  v-if="index > 0"
                  v-model:value="item.depends_on"
                  mode="multiple"
                  allow-clear
                  :options="scenarioDependencyOptions(index)"
                  :placeholder="t('case_form.api.depends_on_placeholder')"
                  style="min-width: 260px"
                />
                <span v-else class="form-hint">{{ t('case_form.api.orchestration_entry_step') }}</span>
              </div>
            </a-list-item>
          </template>
        </a-list>
        <a-button type="dashed" size="small" style="margin: 10px 0 4px" @click="addScenarioStep">
          <PlusOutlined /> {{ t('case_form.api.add_scenario_step') }}
        </a-button>
        <div class="form-hint">{{ t('case_form.api.orchestration_steps_hint') }}</div>

        <a-form-item style="margin-top: 16px; margin-bottom: 0">
          <a-checkbox v-model:checked="cfg.reuse_api_session">
            {{ t('case_form.api.reuse_session_label') }}
          </a-checkbox>
          <div style="color: #999; font-size: 12px; margin-top: 4px">
            {{ t('case_form.api.reuse_session_hint') }}
          </div>
        </a-form-item>

        <a-row :gutter="12" style="margin-top: 16px">
          <a-col :span="8">
            <a-form-item :label="t('case_form.api.failure_strategy_label')">
              <a-select v-model:value="cfg.failure_strategy">
                <a-select-option value="continue">{{ t('case_form.api.failure_strategies.continue') }}</a-select-option>
                <a-select-option value="stop">{{ t('case_form.api.failure_strategies.stop') }}</a-select-option>
                <a-select-option value="skip_dependents">{{ t('case_form.api.failure_strategies.skip_dependents') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('case_form.api.context_scope_label')">
              <a-select v-model:value="cfg.context_scope">
                <a-select-option value="scenario">{{ t('case_form.api.context_scopes.scenario') }}</a-select-option>
                <a-select-option value="step">{{ t('case_form.api.context_scopes.step') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('case_form.api.session_lifecycle_label')">
              <a-select v-model:value="cfg.session_lifecycle">
                <a-select-option value="isolated">{{ t('case_form.api.session_lifecycles.isolated') }}</a-select-option>
                <a-select-option value="reuse">{{ t('case_form.api.session_lifecycles.reuse') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <div class="form-hint">{{ t('case_form.api.orchestration_hint') }}</div>

        <a-form-item :label="t('case_form.api.timeout_label')" style="margin-top: 16px">
          <a-input-number v-model:value="cfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('case_form.api.response_type_label')">
              <a-select v-model:value="cfg.response_type" style="width: 180px">
                <a-select-option value="auto">{{ t('case_form.api.response_types.auto') }}</a-select-option>
                <a-select-option value="json">JSON</a-select-option>
                <a-select-option value="xml">XML</a-select-option>
                <a-select-option value="sse">SSE</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col v-if="cfg.response_type === 'sse'" :span="12">
            <a-form-item :label="t('case_form.api.sse_max_events_label')">
              <a-input-number v-model:value="cfg.sse_max_events" :min="1" :max="1000" style="width: 120px" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">{{ t('case_form.sections.assertions') }}</a-divider>
        <div v-for="(a, i) in cfg.assertions" :key="i" class="assertion-row">
          <a-select v-model:value="a.target" style="width: 130px" :placeholder="t('case_form.assertion.target_placeholder')">
            <a-select-option value="status_code">{{ t('case_form.assertion.targets.status_code') }}</a-select-option>
            <a-select-option value="body">{{ t('case_form.assertion.targets.body') }}</a-select-option>
            <a-select-option value="header">{{ t('case_form.assertion.targets.header') }}</a-select-option>
            <a-select-option value="duration">{{ t('case_form.assertion.targets.duration') }}</a-select-option>
            <a-select-option value="json_schema">{{ t('case_form.assertion.targets.json_schema') }}</a-select-option>
          </a-select>
          <a-select
            v-if="a.target === 'body'"
            v-model:value="a.expression_type"
            style="width: 105px"
          >
            <a-select-option value="jsonpath">JSONPath</a-select-option>
            <a-select-option value="xpath">XPath</a-select-option>
          </a-select>
          <a-input
            v-if="a.target === 'body' || a.target === 'header'"
            v-model:value="a.expression"
            :placeholder="a.target === 'body' && a.expression_type === 'xpath' ? t('case_form.assertion.xpath_placeholder') : t('case_form.assertion.expression_placeholder')"
            style="width: 160px"
          />
          <template v-if="a.target === 'json_schema'">
            <a-textarea
              v-model:value="a.expected"
              :rows="2"
              :placeholder="t('case_form.assertion.schema_placeholder')"
              style="width: 230px; font-family: monospace"
            />
            <a-select
              v-model:value="a.schema_asset_id"
              allow-clear
              :options="schemaAssetOptions"
              :placeholder="t('case_form.assertion.schema_asset_placeholder')"
              style="width: 150px"
              @change="(id: unknown) => applySchemaAsset(a, typeof id === 'number' ? id : undefined)"
            />
            <a-input v-model:value="a.schema_asset_name" :placeholder="t('case_form.assertion.schema_asset_name_placeholder')" style="width: 135px" />
            <a-button size="small" :loading="savingSchemaAssetIndex === i" @click="saveSchemaAsset(a, i)">
              {{ t('case_form.assertion.schema_asset_save') }}
            </a-button>
          </template>
          <a-select v-model:value="a.operator" style="width: 110px" :placeholder="t('case_form.assertion.operator_placeholder')">
            <a-select-option value="eq">{{ t('case_form.assertion.operators.eq') }}</a-select-option>
            <a-select-option value="contains">{{ t('case_form.assertion.operators.contains') }}</a-select-option>
            <a-select-option value="gt">{{ t('case_form.assertion.operators.gt') }}</a-select-option>
            <a-select-option value="lt">{{ t('case_form.assertion.operators.lt') }}</a-select-option>
            <a-select-option value="exists">{{ t('case_form.assertion.operators.exists') }}</a-select-option>
            <a-select-option v-if="a.target === 'json_schema'" value="valid">{{ t('case_form.assertion.operators.valid') }}</a-select-option>
            <a-select-option v-if="a.target === 'json_schema'" value="invalid">{{ t('case_form.assertion.operators.invalid') }}</a-select-option>
          </a-select>
          <a-input
            v-if="a.operator !== 'exists' && a.target !== 'json_schema'"
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
          <a-select v-model:value="e.type" style="width: 105px">
            <a-select-option value="jsonpath">JSONPath</a-select-option>
            <a-select-option value="xpath">XPath</a-select-option>
          </a-select>
          <a-input v-model:value="e.expression" :placeholder="e.type === 'xpath' ? t('case_form.extraction.xpath_placeholder') : t('case_form.extraction.expression_placeholder_token')" style="flex: 1" />
          <MinusCircleOutlined class="remove-btn" @click="cfg.extractions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="cfg.extractions.push({ variable: '', expression: '' })">
          <PlusOutlined /> {{ t('case_form.extraction.add') }}
        </a-button>

        <a-divider orientation="left">{{ t('case_form.sections.hooks') }}</a-divider>
        <a-form-item :label="t('case_form.hooks.pre_label')">
          <a-textarea
            v-model:value="cfg.pre_actions_text"
            :rows="3"
            :placeholder="t('case_form.hooks.placeholder')"
            style="font-family: monospace; font-size: 12px"
          />
          <div class="form-hint">{{ t('case_form.hooks.hint') }}</div>
        </a-form-item>
        <a-form-item :label="t('case_form.hooks.post_label')">
          <a-textarea
            v-model:value="cfg.post_actions_text"
            :rows="3"
            :placeholder="t('case_form.hooks.placeholder')"
            style="font-family: monospace; font-size: 12px"
          />
        </a-form-item>
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
                <a-select-option value="query">{{ t('case_form.graphql.operation_types.query') }}</a-select-option>
                <a-select-option value="mutation">{{ t('case_form.graphql.operation_types.mutation') }}</a-select-option>
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
          <a-tab-pane key="headers" :tab="t('case_form.tabs.headers')">
            <KvEditor v-model:value="gqlCfg.headers" />
          </a-tab-pane>
          <a-tab-pane key="auth" :tab="t('case_form.tabs.auth')">
            <a-form-item :label="t('case_form.auth.label')">
              <a-select v-model:value="gqlCfg.auth.type" style="width: 160px">
                <a-select-option value="none">{{ t('case_form.auth.none') }}</a-select-option>
                <a-select-option value="bearer">{{ t('case_form.auth.bearer') }}</a-select-option>
                <a-select-option value="basic">{{ t('case_form.auth.basic') }}</a-select-option>
                <a-select-option value="apikey">{{ t('case_form.auth.apikey') }}</a-select-option>
                <a-select-option value="digest">{{ t('case_form.auth.digest') }}</a-select-option>
                <a-select-option value="oauth2_client_credentials">{{ t('case_form.auth.oauth2_client_credentials') }}</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="gqlCfg.auth.type === 'bearer'">
              <a-form-item :label="t('case_form.auth.token_label')">
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
            <template v-if="gqlCfg.auth.type === 'digest'">
              <a-form-item :label="t('case_form.auth.username_label')">
                <a-input v-model:value="gqlCfg.auth.username" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.password_label')">
                <a-input-password v-model:value="gqlCfg.auth.password" />
              </a-form-item>
            </template>
            <template v-if="gqlCfg.auth.type === 'oauth2_client_credentials'">
              <a-form-item :label="t('case_form.auth.token_url_label')">
                <a-input v-model:value="gqlCfg.auth.token_url" :placeholder="t('case_form.auth.token_url_placeholder')" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.client_id_label')">
                <a-input v-model:value="gqlCfg.auth.client_id" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.client_secret_label')">
                <a-input-password v-model:value="gqlCfg.auth.client_secret" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.token_endpoint_auth_method_label')">
                <a-select v-model:value="gqlCfg.auth.token_endpoint_auth_method" style="width: 220px">
                  <a-select-option value="client_secret_basic">{{ t('case_form.auth.client_secret_basic') }}</a-select-option>
                  <a-select-option value="client_secret_post">{{ t('case_form.auth.client_secret_post') }}</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item :label="t('case_form.auth.scope_label')">
                <a-input v-model:value="gqlCfg.auth.scope" :placeholder="t('case_form.auth.scope_placeholder')" />
              </a-form-item>
              <a-form-item :label="t('case_form.auth.audience_label')">
                <a-input v-model:value="gqlCfg.auth.audience" :placeholder="t('case_form.auth.audience_placeholder')" />
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
          <a-tab-pane key="headers" :tab="t('case_form.tabs.headers')">
            <KvEditor v-model:value="wsCfg.headers" />
          </a-tab-pane>
          <a-tab-pane key="auth" :tab="t('case_form.tabs.auth')">
            <a-form-item :label="t('case_form.auth.label')">
              <a-select v-model:value="wsCfg.auth.type" style="width: 160px">
                <a-select-option value="none">{{ t('case_form.auth.none') }}</a-select-option>
                <a-select-option value="bearer">{{ t('case_form.auth.bearer') }}</a-select-option>
                <a-select-option value="basic">{{ t('case_form.auth.basic') }}</a-select-option>
                <a-select-option value="apikey">{{ t('case_form.auth.apikey') }}</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="wsCfg.auth.type === 'bearer'">
              <a-form-item :label="t('case_form.auth.token_label')">
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
                  <a-select-option value="text">{{ t('case_form.websocket.data_types.text') }}</a-select-option>
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

        <div v-if="grpcCfg.use_tls" class="tls-options-panel">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item :label="t('case_form.grpc.tls_server_name_label')">
                <a-input v-model:value="grpcCfg.tls_server_name" placeholder="grpc.example.com" />
                <div class="field-hint">{{ t('case_form.grpc.tls_server_name_hint') }}</div>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item :label="t('case_form.grpc.tls_root_certificates_label')">
                <a-textarea
                  v-model:value="grpcCfg.tls_root_certificates"
                  :rows="4"
                  :placeholder="t('case_form.grpc.tls_root_certificates_placeholder')"
                  style="font-family: monospace; font-size: 12px"
                />
                <div class="field-hint">{{ t('case_form.grpc.tls_root_certificates_hint') }}</div>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

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
          <a-space>
            <a-upload
              :show-upload-list="false"
              accept=".proto,text/plain"
              :before-upload="(file: File) => loadGrpcProtoFile(file, true)"
            >
              <a-button size="small">{{ t('case_form.grpc.choose_main_proto') }}</a-button>
            </a-upload>
            <a-upload
              :show-upload-list="false"
              :multiple="true"
              accept=".proto,text/plain"
              :before-upload="(file: File) => loadGrpcProtoFile(file, false)"
            >
              <a-button size="small">{{ t('case_form.grpc.add_import_proto') }}</a-button>
            </a-upload>
            <span v-if="grpcProtoMainFileName" class="file-name">
              {{ t('case_form.grpc.main_proto_selected', { name: grpcProtoMainFileName }) }}
            </span>
          </a-space>
          <div v-if="grpcProtoImportFileNames.length" class="field-hint">
            {{ t('case_form.grpc.import_proto_selected', { count: grpcProtoImportFileNames.length, names: grpcProtoImportFileNames.join(', ') }) }}
          </div>
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
          <div class="field-hint">{{ t('case_form.grpc.request_json_hint') }}</div>
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

      <template v-else-if="form.case_type === 'ios'">
        <a-alert
          :message="t('case_form.ios.hint')"
          :description="t('case_form.ios.steps_hint')"
          type="info"
          show-icon
          style="margin-top: 16px"
        />
        <a-row :gutter="12" style="margin-top: 16px">
          <a-col :span="12">
            <a-form-item :label="t('case_form.ios.appium_server_url')">
              <a-input v-model:value="iosCfg.appium_server_url" placeholder="http://mac-worker:4723" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('case_form.ios.udid')">
              <a-input v-model:value="iosCfg.udid" placeholder="00008110-..." />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="8"><a-form-item :label="t('case_form.ios.device_name')"><a-input v-model:value="iosCfg.device_name" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item :label="t('case_form.ios.platform_version')"><a-input v-model:value="iosCfg.platform_version" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item :label="t('case_form.ios.bundle_id')"><a-input v-model:value="iosCfg.bundle_id" /></a-form-item></a-col>
        </a-row>
        <a-form-item :label="t('case_form.ios.steps_label')">
          <a-textarea v-model:value="iosCfg.steps_text" :rows="12" :placeholder="t('case_form.ios.steps_placeholder')" />
        </a-form-item>
        <a-space>
          <a-checkbox v-model:checked="iosCfg.record_video">{{ t('case_form.ios.record_video') }}</a-checkbox>
          <a-checkbox v-model:checked="iosCfg.capture_screenshot">{{ t('case_form.ios.capture_screenshot') }}</a-checkbox>
        </a-space>
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
import { computed, ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons-vue'
import { apiSchemaAssetApi, caseApi, datasetApi, type ApiSchemaAssetItem } from '@/api'
import type { CaseDetailItem, CaseLevel, CasePriority, CaseSavePayload, CaseSummaryItem, CaseType } from '@/api'
import {
  getFirstStep,
  getProtocolConfigError,
  normalizeWsMessage,
  parseFormBody,
  parseGraphqlVariables,
  resolveRequestBody,
} from '@/utils/caseFormConfig'
import { GrpcProtoFileError, readGrpcProtoFile, validateGrpcProtoBundle } from '@/utils/grpcProtoFile'
import KvEditor from '@/components/common/KvEditor.vue'

const { t } = useI18n()

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']

type AuthConfig = {
  type: 'none' | 'bearer' | 'basic' | 'apikey' | 'digest' | 'oauth2_client_credentials'
  token: string
  username: string
  password: string
  header: string
  value: string
  token_url: string
  client_id: string
  client_secret: string
  scope: string
  audience: string
  token_endpoint_auth_method: 'client_secret_basic' | 'client_secret_post'
}

type AssertionItem = {
  target: string
  operator: string
  expected?: string
  expression?: string
  expression_type?: 'jsonpath' | 'xpath'
  schema_asset_id?: number
  schema_asset_name?: string
}

type ExtractionItem = {
  variable: string
  expression: string
  type?: 'jsonpath' | 'xpath'
}

type HookAction = Record<string, unknown> & { action: string; variable?: string }

type MultipartPart = {
  name: string
  type: 'text' | 'file'
  value: string
  filename?: string
  object_name?: string
  content_type?: string
  size?: number
}

type WsMessage = {
  action: 'send' | 'receive' | 'disconnect' | string
  data?: string
  data_type?: 'text' | 'json' | string
  timeout?: number
  assertions: AssertionItem[]
  extractions: ExtractionItem[]
}

type CaseConfigStep = Record<string, unknown> & {
  url?: string
  method?: string
  headers?: Record<string, string>
  params?: Record<string, string>
  body_type?: 'none' | 'json' | 'form' | 'multipart' | 'xml' | 'raw'
  body?: unknown
  multipart?: MultipartPart[]
  cookies?: Record<string, string>
  auth?: Partial<AuthConfig>
  timeout?: number
  assertions?: AssertionItem[]
  extractions?: ExtractionItem[]
  pre_actions?: HookAction[]
  post_actions?: HookAction[]
  endpoint?: string
  operation_type?: 'query' | 'mutation'
  query?: string
  variables?: unknown
  operation_name?: string
  messages?: WsMessage[]
  target?: string
  use_tls?: boolean
  tls_server_name?: string
  tls_root_certificates?: string
  proto_content?: string
  proto_files?: Record<string, string>
  service?: string
  request_json?: string
  metadata?: Record<string, string>
  depends_on?: number[]
}

type EditableCase = Pick<CaseSummaryItem, 'id' | 'name' | 'description' | 'case_type' | 'tags' | 'dataset_id' | 'dataset_version' | 'priority' | 'case_level'> &
  Partial<Pick<CaseDetailItem, 'config'>>

const props = defineProps<{
  open: boolean
  moduleId: number | null
  projectId?: number | null
  editCase?: EditableCase | null
  defaultCaseType?: CaseType
}>()
const emit = defineEmits<{ close: []; saved: [] }>()

const isEdit = ref(false)
const saving = ref(false)
const activeTab = ref('headers')
const gqlActiveTab = ref('headers')
const wsActiveTab = ref('headers')
const formRef = ref()

const form = reactive<{
  name: string
  description: string
  case_type: CaseType
  tags: string[]
  priority: CasePriority
  case_level: CaseLevel
  dataset_id: number | null
  dataset_version: number | null
  dataset_strict_schema: boolean
  dataset_strategy: string
  dataset_fixed_count: number | null
  dataset_seed: number | null
  dataset_max_iterations: number
  dataset_combination_fields: string[]
  dataset_redact_fields: string[]
  dataset_prepare_actions_text: string
}>({
  name: '',
  description: '',
  case_type: 'api',
  tags: [],
  priority: 'P2',
  case_level: 'regression',
  dataset_id: null,
  dataset_version: null,
  dataset_strict_schema: false,
  dataset_strategy: 'sequential',
  dataset_fixed_count: null,
  dataset_seed: null,
  dataset_max_iterations: 1000,
  dataset_combination_fields: [],
  dataset_redact_fields: [],
  dataset_prepare_actions_text: '[]',
})

const datasetOptions = ref<{ label: string; value: number }[]>([])
const datasetVersionOptions = ref<{ label: string; value: number }[]>([])
const datasetVersionsLoading = ref(false)
const datasetVersionLoadSeq = ref(0)
const schemaAssets = ref<ApiSchemaAssetItem[]>([])
const savingSchemaAssetIndex = ref<number | null>(null)
const schemaAssetOptions = computed(() => schemaAssets.value.map((item) => ({ label: `${item.name} v${item.version}`, value: item.id })))
const apiScenarioSteps = ref<CaseConfigStep[]>([])

const cfg = reactive({
  url: '',
  method: 'GET',
  headers: {} as Record<string, string>,
  params: {} as Record<string, string>,
  cookies: {} as Record<string, string>,
  body_type: 'none' as 'none' | 'json' | 'form' | 'multipart' | 'xml' | 'raw',
  body: '',
  multipart: [] as MultipartPart[],
  auth: {
    type: 'none',
    token: '',
    username: '',
    password: '',
    header: '',
    value: '',
    token_url: '',
    client_id: '',
    client_secret: '',
    scope: '',
    audience: '',
    token_endpoint_auth_method: 'client_secret_basic',
  },
  reuse_api_session: false,
  failure_strategy: 'continue' as 'continue' | 'stop' | 'skip_dependents',
  context_scope: 'scenario' as 'scenario' | 'step',
  session_lifecycle: 'isolated' as 'isolated' | 'reuse',
  timeout: 30,
  response_type: 'auto' as 'auto' | 'json' | 'xml' | 'sse',
  sse_max_events: 100,
  assertions: [] as AssertionItem[],
  extractions: [] as ExtractionItem[],
  pre_actions_text: '[]',
  post_actions_text: '[]',
})
const formBody = ref<Record<string, string>>({})

const gqlCfg = reactive({
  endpoint: '',
  operation_type: 'query' as 'query' | 'mutation',
  query: '',
  variables_text: '',
  operation_name: '',
  headers: {} as Record<string, string>,
  auth: {
    type: 'none',
    token: '',
    username: '',
    password: '',
    header: '',
    value: '',
    token_url: '',
    client_id: '',
    client_secret: '',
    scope: '',
    audience: '',
    token_endpoint_auth_method: 'client_secret_basic',
  },
  timeout: 30,
  assertions: [] as AssertionItem[],
  extractions: [] as ExtractionItem[],
})

const wsCfg = reactive({
  url: '',
  headers: {} as Record<string, string>,
  auth: {
    type: 'none',
    token: '',
    username: '',
    password: '',
    header: '',
    value: '',
    token_url: '',
    client_id: '',
    client_secret: '',
    scope: '',
    audience: '',
    token_endpoint_auth_method: 'client_secret_basic',
  },
  timeout: 30,
  messages: [] as WsMessage[],
})

const grpcCfg = reactive({
  target: '',
  use_tls: false,
  tls_server_name: '',
  tls_root_certificates: '',
  proto_content: '',
  proto_files: {} as Record<string, string>,
  service: '',
  method: '',
  request_json: '',
  metadata: {} as Record<string, string>,
  timeout: 30,
  assertions: [] as AssertionItem[],
  extractions: [] as ExtractionItem[],
})
const grpcProtoMainFileName = ref('')
const grpcProtoImportFileNames = computed(() => Object.keys(grpcCfg.proto_files).filter((name) => name !== grpcProtoMainFileName.value))

const iosCfg = reactive({
  appium_server_url: '',
  udid: '',
  device_name: '',
  platform_version: '',
  bundle_id: '',
  steps_text: '[\n  {"action":"click","name":"点击登录","params":{"strategy":"accessibility_id","value":"登录"}}\n]',
  record_video: false,
  capture_screenshot: true,
})

async function loadDatasetOptions() {
  if (!props.projectId) {
    datasetOptions.value = []
    datasetVersionOptions.value = []
    return
  }
  try {
    const items = await datasetApi.list(props.projectId)
    datasetOptions.value = items.map((d) => ({ label: `${d.name} (${d.row_count} 行)`, value: d.id }))
  } catch {
    datasetOptions.value = []
  }
}

async function loadDatasetVersions(datasetId: number | null) {
  const seq = ++datasetVersionLoadSeq.value
  if (datasetId == null) {
    datasetVersionOptions.value = []
    datasetVersionsLoading.value = false
    return
  }
  datasetVersionsLoading.value = true
  try {
    const versions = await datasetApi.listVersions(datasetId)
    if (seq !== datasetVersionLoadSeq.value) return
    datasetVersionOptions.value = versions.map((item) => ({
      label: `v${item.version} (${item.row_count} ${t('case_form.basic.dataset_rows_suffix')})`,
      value: item.version,
    }))
    if (form.dataset_version != null && !versions.some((item) => item.version === form.dataset_version)) {
      form.dataset_version = null
    }
  } catch {
    if (seq === datasetVersionLoadSeq.value) datasetVersionOptions.value = []
  } finally {
    if (seq === datasetVersionLoadSeq.value) datasetVersionsLoading.value = false
  }
}

function handleDatasetChange(value: unknown) {
  const datasetId = value == null || value === '' ? null : Number(value)
  form.dataset_id = Number.isFinite(datasetId) ? datasetId : null
  form.dataset_version = null
  void loadDatasetVersions(form.dataset_id)
}

async function loadSchemaAssetOptions() {
  if (!props.projectId) {
    schemaAssets.value = []
    return
  }
  try {
    schemaAssets.value = await apiSchemaAssetApi.list(props.projectId)
  } catch {
    schemaAssets.value = []
  }
}

watch(() => props.open, (v) => {
  if (!v) return
  loadDatasetOptions()
  loadSchemaAssetOptions()
  if (props.editCase) {
    isEdit.value = true
    const c = props.editCase
    form.name = c.name
    form.description = c.description ?? ''
    form.case_type = c.case_type
    form.tags = c.tags ?? []
    form.priority = c.priority ?? 'P2'
    form.case_level = c.case_level ?? 'regression'
    form.dataset_id = c.dataset_id ?? null
    form.dataset_version = c.dataset_version ?? null
    void loadDatasetVersions(form.dataset_id)
    form.dataset_strict_schema = Boolean(c.config?.dataset_strict_schema)
    form.dataset_strategy = String(c.config?.dataset_strategy ?? 'sequential')
    form.dataset_fixed_count = c.config?.dataset_fixed_count == null ? null : Number(c.config.dataset_fixed_count)
    form.dataset_seed = c.config?.dataset_seed == null ? null : Number(c.config.dataset_seed)
    form.dataset_max_iterations = Number(c.config?.dataset_max_iterations ?? 1000)
    form.dataset_combination_fields = Array.isArray(c.config?.dataset_combination_fields) ? [...c.config.dataset_combination_fields] : []
    form.dataset_redact_fields = Array.isArray(c.config?.dataset_redact_fields) ? [...c.config.dataset_redact_fields] : []
    form.dataset_prepare_actions_text = JSON.stringify(c.config?.dataset_prepare_actions ?? [], null, 2)
    const step = getFirstStep(c.config) as CaseConfigStep
    apiScenarioSteps.value = Array.isArray(c.config?.steps)
      ? c.config.steps.map((item) => ({ ...item, depends_on: Array.isArray(item.depends_on) ? [...item.depends_on] : [] }))
      : []
    const bodyType = step.body_type ?? 'none'
    formBody.value = bodyType === 'form' ? parseFormBody(step.body) : {}

    Object.assign(cfg, {
      url: step.url ?? '',
      method: step.method ?? 'GET',
      headers: step.headers ?? {},
      params: step.params ?? {},
      cookies: step.cookies ?? {},
      body_type: bodyType,
      body: typeof step.body === 'string' ? step.body : JSON.stringify(step.body ?? '', null, 2),
      multipart: step.multipart ? [...step.multipart] : [],
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', token_url: '', client_id: '', client_secret: '', scope: '', audience: '', token_endpoint_auth_method: 'client_secret_basic', ...step.auth },
      reuse_api_session: Boolean(c.config?.reuse_api_session),
      failure_strategy: c.config?.failure_strategy ?? 'continue',
      context_scope: c.config?.context_scope ?? 'scenario',
      session_lifecycle: c.config?.session_lifecycle ?? (c.config?.reuse_api_session ? 'reuse' : 'isolated'),
      timeout: step.timeout ?? 30,
      response_type: step.response_type ?? 'auto',
      sse_max_events: step.sse_max_events ?? 100,
      assertions: step.assertions ? [...step.assertions] : [],
      extractions: step.extractions ? step.extractions.map((item) => ({ type: 'jsonpath', ...item })) : [],
      pre_actions_text: JSON.stringify(step.pre_actions ?? [], null, 2),
      post_actions_text: JSON.stringify(step.post_actions ?? [], null, 2),
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
        auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', token_url: '', client_id: '', client_secret: '', scope: '', audience: '', token_endpoint_auth_method: 'client_secret_basic', ...step.auth },
        timeout: step.timeout ?? 30,
        assertions: step.assertions ? [...step.assertions] : [],
        extractions: step.extractions ? [...step.extractions] : [],
      })
    }

    if (c.case_type === 'websocket') {
      Object.assign(wsCfg, {
        url: step.url ?? '',
        headers: step.headers ?? {},
        auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', token_url: '', client_id: '', client_secret: '', scope: '', audience: '', token_endpoint_auth_method: 'client_secret_basic', ...step.auth },
        timeout: step.timeout ?? 30,
        messages: (step.messages ?? []).map((m) => ({
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
        tls_server_name: step.tls_server_name ?? '',
        tls_root_certificates: step.tls_root_certificates ?? '',
        proto_content: step.proto_content ?? '',
        proto_files: step.proto_files ?? {},
        service: step.service ?? '',
        method: step.method ?? '',
        request_json: step.request_json ?? '',
        metadata: step.metadata ?? {},
        timeout: step.timeout ?? 30,
        assertions: step.assertions ? [...step.assertions] : [],
        extractions: step.extractions ? [...step.extractions] : [],
      })
      grpcProtoMainFileName.value = step.proto_content ? 'service.proto' : ''
    }
    if (c.case_type === 'ios') {
      Object.assign(iosCfg, {
        appium_server_url: c.config?.appium_server_url ?? '',
        udid: c.config?.udid ?? '',
        device_name: c.config?.device_name ?? '',
        platform_version: c.config?.platform_version ?? '',
        bundle_id: c.config?.bundle_id ?? '',
        steps_text: JSON.stringify(c.config?.steps ?? [], null, 2),
        record_video: Boolean(c.config?.record_video),
        capture_screenshot: c.config?.capture_screenshot !== false,
      })
    }
  } else {
    isEdit.value = false
    form.name = ''
    form.description = ''
    form.case_type = props.defaultCaseType ?? 'api'
    form.tags = []
    form.priority = 'P2'
    form.case_level = 'regression'
    form.dataset_id = null
    form.dataset_version = null
    datasetVersionOptions.value = []
    form.dataset_strict_schema = false
    form.dataset_strategy = 'sequential'
    form.dataset_fixed_count = null
    form.dataset_seed = null
    form.dataset_max_iterations = 1000
    form.dataset_combination_fields = []
    form.dataset_redact_fields = []
    form.dataset_prepare_actions_text = '[]'
    Object.assign(cfg, {
      url: '', method: 'GET', headers: {}, params: {}, cookies: {},
      body_type: 'none', body: '', multipart: [],
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', token_url: '', client_id: '', client_secret: '', scope: '', audience: '', token_endpoint_auth_method: 'client_secret_basic' },
      reuse_api_session: false,
      failure_strategy: 'continue',
      context_scope: 'scenario',
      session_lifecycle: 'isolated',
      timeout: 30, response_type: 'auto', sse_max_events: 100, assertions: [], extractions: [],
      pre_actions_text: '[]', post_actions_text: '[]',
    })
    formBody.value = {}
    apiScenarioSteps.value = []
    Object.assign(gqlCfg, {
      endpoint: '', operation_type: 'query', query: '', variables_text: '',
      operation_name: '', headers: {},
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', token_url: '', client_id: '', client_secret: '', scope: '', audience: '', token_endpoint_auth_method: 'client_secret_basic' },
      timeout: 30, assertions: [], extractions: [],
    })
    Object.assign(wsCfg, {
      url: '', headers: {},
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', token_url: '', client_id: '', client_secret: '', scope: '', audience: '', token_endpoint_auth_method: 'client_secret_basic' },
      timeout: 30, messages: [],
    })
    Object.assign(grpcCfg, {
      target: '', use_tls: false, tls_server_name: '', tls_root_certificates: '', proto_content: '', proto_files: {}, service: '', method: '',
      request_json: '', metadata: {}, timeout: 30, assertions: [], extractions: [],
    })
    grpcProtoMainFileName.value = ''
    Object.assign(iosCfg, {
      appium_server_url: '', udid: '', device_name: '', platform_version: '', bundle_id: '',
      steps_text: '[\n  {"action":"click","name":"点击登录","params":{"strategy":"accessibility_id","value":"登录"}}\n]',
      record_video: false, capture_screenshot: true,
    })
  }
})

function addAssertion() {
  cfg.assertions.push({ target: 'status_code', operator: 'eq', expected: '200', expression: '', expression_type: 'jsonpath' })
}

function scenarioDependencyOptions(index: number) {
  return apiScenarioSteps.value.slice(0, index).map((step, stepIndex) => ({
    label: `${stepIndex + 1}. ${step.name || t('case_form.api.orchestration_step_fallback', { index: stepIndex + 1 })}`,
    value: stepIndex,
  }))
}

function buildCurrentApiStep(): CaseConfigStep {
  const body = resolveRequestBody(cfg.body_type, cfg.body, formBody.value)
  return {
    name: form.name,
    url: cfg.url,
    method: cfg.method,
    headers: cfg.headers,
    params: cfg.params,
    cookies: cfg.cookies,
    body_type: cfg.body_type,
    body,
    multipart: cfg.body_type === 'multipart' ? cfg.multipart : undefined,
    auth: cfg.auth as Partial<AuthConfig>,
    timeout: cfg.timeout,
    response_type: cfg.response_type,
    sse_max_events: cfg.sse_max_events,
    assertions: cfg.assertions.map(({ schema_asset_name: _schemaAssetName, ...assertion }) => assertion),
    extractions: cfg.extractions,
    pre_actions: parseHookActions(cfg.pre_actions_text),
    post_actions: parseHookActions(cfg.post_actions_text),
    depends_on: apiScenarioSteps.value[0]?.depends_on ?? [],
  }
}

function addScenarioStep() {
  const current = buildCurrentApiStep()
  if (!apiScenarioSteps.value.length) {
    apiScenarioSteps.value.push(current)
  } else {
    apiScenarioSteps.value[0] = { ...apiScenarioSteps.value[0], ...current }
  }
  const nextIndex = apiScenarioSteps.value.length
  apiScenarioSteps.value.push({
    ...JSON.parse(JSON.stringify(current)) as CaseConfigStep,
    name: `${form.name || t('case_form.api.orchestration_step_fallback', { index: 1 })} ${nextIndex + 1}`,
    depends_on: [nextIndex - 1],
  })
}

function applySchemaAsset(assertion: AssertionItem, assetId?: number) {
  if (assetId == null) {
    assertion.schema_asset_id = undefined
    return
  }
  const asset = schemaAssets.value.find((item) => item.id === assetId)
  if (!asset) return
  assertion.expected = JSON.stringify(asset.definition, null, 2)
  assertion.schema_asset_id = asset.id
}

async function saveSchemaAsset(assertion: AssertionItem, index: number) {
  if (!props.projectId) {
    message.warning(t('case_form.assertion.schema_asset_project_required'))
    return
  }
  const name = assertion.schema_asset_name?.trim()
  if (!name) {
    message.warning(t('case_form.assertion.schema_asset_name_required'))
    return
  }
  let definition: Record<string, unknown>
  try {
    const parsed = JSON.parse(assertion.expected || '')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('not-object')
    definition = parsed as Record<string, unknown>
  } catch {
    message.warning(t('case_form.assertion.schema_asset_invalid'))
    return
  }
  savingSchemaAssetIndex.value = index
  try {
    const asset = await apiSchemaAssetApi.create(props.projectId, { name, definition })
    schemaAssets.value = [...schemaAssets.value, asset]
    assertion.schema_asset_id = asset.id
    message.success(t('case_form.assertion.schema_asset_saved'))
  } catch (error: unknown) {
    message.error(error instanceof Error ? error.message : t('case_form.assertion.schema_asset_save_failed'))
  } finally {
    savingSchemaAssetIndex.value = null
  }
}

function parseHookActions(text: string): HookAction[] {
  if (!text.trim()) return []
  const parsed = JSON.parse(text)
  if (!Array.isArray(parsed)) throw new Error(t('case_form.hooks.invalid'))
  return parsed as HookAction[]
}

function parseDatasetPreparationActions(text: string): HookAction[] {
  if (!text.trim()) return []
  const parsed = JSON.parse(text)
  if (!Array.isArray(parsed)) throw new Error(t('case_form.basic.dataset_prepare_actions_invalid'))
  return parsed as HookAction[]
}

function addMultipartPart() {
  cfg.multipart.push({ name: '', type: 'text', value: '' })
}

async function uploadMultipartFile(file: File, index: number) {
  if (!props.projectId) {
    message.warning(t('case_form.msg.project_required_for_file'))
    return false
  }
  try {
    const result = await caseApi.uploadRequestFile(props.projectId, file)
    const part = cfg.multipart[index]
    if (part) {
      part.filename = result.filename
      part.object_name = result.object_name
      part.content_type = result.content_type
      part.size = result.size
    }
    message.success(t('case_form.msg.file_uploaded'))
  } catch {
    message.error(t('case_form.msg.file_upload_failed'))
  }
  return false
}

async function loadGrpcProtoFile(file: File, asMain: boolean) {
  try {
    if (!asMain && !grpcCfg.proto_content.trim()) {
      message.warning(t('case_form.grpc.main_proto_required'))
      return false
    }
    const content = await readGrpcProtoFile(file)
    const nextFiles = asMain ? { ...grpcCfg.proto_files } : { ...grpcCfg.proto_files, [file.name]: content }
    validateGrpcProtoBundle(nextFiles, asMain ? content : grpcCfg.proto_content)
    grpcCfg.proto_files = nextFiles
    if (asMain) {
      grpcCfg.proto_content = content
      grpcProtoMainFileName.value = file.name
    }
    message.success(t(asMain ? 'case_form.grpc.proto_file_loaded' : 'case_form.grpc.import_proto_file_loaded'))
  } catch (error) {
    if (error instanceof GrpcProtoFileError) {
      const key = {
        extension: 'case_form.grpc.proto_file_extension',
        size: 'case_form.grpc.proto_file_too_large',
        empty: 'case_form.grpc.proto_file_empty',
        bundle_size: 'case_form.grpc.proto_bundle_too_large',
      }[error.reason]
      message.warning(t(key))
    } else {
      message.error(t('case_form.grpc.proto_file_read_failed'))
    }
  }
  return false
}

function addGqlAssertion() {
  gqlCfg.assertions.push({ target: 'status_code', operator: 'eq', expected: '200', expression: '' })
}

function addWsMessage(action: 'send' | 'receive') {
  if (action === 'send') {
    wsCfg.messages.push({ action: 'send', data: '', data_type: 'text', assertions: [], extractions: [] })
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
      messages: wsCfg.messages.map(normalizeWsMessage),
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
      tls_server_name: grpcCfg.tls_server_name.trim() || undefined,
      tls_root_certificates: grpcCfg.tls_root_certificates.trim() || undefined,
      proto_content: grpcCfg.proto_content,
      proto_files: Object.keys(grpcCfg.proto_files).length ? { ...grpcCfg.proto_files } : undefined,
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

function buildIosConfig() {
  let steps: unknown
  try {
    steps = JSON.parse(iosCfg.steps_text)
  } catch {
    throw new Error(t('case_form.ios.steps_invalid'))
  }
  if (!Array.isArray(steps) || !steps.length) throw new Error(t('case_form.ios.steps_required'))
  if (!iosCfg.appium_server_url.trim() || !iosCfg.udid.trim()) throw new Error(t('case_form.ios.connection_required'))
  return {
    appium_server_url: iosCfg.appium_server_url.trim(),
    udid: iosCfg.udid.trim(),
    device_name: iosCfg.device_name.trim() || undefined,
    platform_version: iosCfg.platform_version.trim() || undefined,
    bundle_id: iosCfg.bundle_id.trim() || undefined,
    steps,
    record_video: iosCfg.record_video,
    capture_screenshot: iosCfg.capture_screenshot,
  }
}

function buildGraphqlConfig() {
  const variables = parseGraphqlVariables(gqlCfg.variables_text)
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
  const withDatasetStrictFlag = (config: Record<string, unknown>) => {
    if (form.dataset_id == null) return config
    return {
      ...config,
      dataset_strict_schema: form.dataset_strict_schema,
      dataset_strategy: form.dataset_strategy,
      dataset_fixed_count: form.dataset_fixed_count,
      dataset_seed: form.dataset_seed,
      dataset_max_iterations: form.dataset_max_iterations,
      dataset_combination_fields: form.dataset_combination_fields,
      dataset_redact_fields: form.dataset_redact_fields,
      dataset_prepare_actions: form.case_type === 'api'
        ? parseDatasetPreparationActions(form.dataset_prepare_actions_text)
        : [],
    }
  }
  if (form.case_type === 'graphql') {
    return withDatasetStrictFlag(buildGraphqlConfig())
  }
  if (form.case_type === 'websocket') {
    return withDatasetStrictFlag(buildWebsocketConfig())
  }
  if (form.case_type === 'grpc') {
    return withDatasetStrictFlag(buildGrpcConfig())
  }
  if (form.case_type === 'ios') {
    return withDatasetStrictFlag(buildIosConfig())
  }
  const currentStep = buildCurrentApiStep()
  const steps = apiScenarioSteps.value.length > 1
    ? apiScenarioSteps.value.map((step, index) => index === 0 ? { ...step, ...currentStep } : { ...step, depends_on: step.depends_on ?? [] })
    : [currentStep]
  return withDatasetStrictFlag({
    reuse_api_session: cfg.session_lifecycle === 'reuse' || cfg.reuse_api_session,
    failure_strategy: cfg.failure_strategy,
    context_scope: cfg.context_scope,
    session_lifecycle: cfg.session_lifecycle,
    steps,
  })
}

async function handleSave() {
  try { await formRef.value?.validate() } catch { return }
  if (form.case_type === 'api' && !cfg.url) {
    message.warning(t('case_form.msg.url_required'))
    return
  }
  if (form.case_type === 'api' && cfg.body_type === 'multipart') {
    const invalidFile = cfg.multipart.some((part) => part.type === 'file' && !part.object_name)
    if (invalidFile) {
      message.warning(t('case_form.msg.multipart_file_required'))
      return
    }
  }
  const protocolError = getProtocolConfigError(form.case_type, {
    endpoint: gqlCfg.endpoint,
    query: gqlCfg.query,
    url: wsCfg.url,
    messages: wsCfg.messages,
    target: grpcCfg.target,
    proto_content: grpcCfg.proto_content,
    service: grpcCfg.service,
    method: grpcCfg.method,
  })
  if (protocolError) {
    message.warning(t(`case_form.msg.${protocolError}`))
    return
  }
  let config: Record<string, unknown>
  try {
    config = buildConfig()
  } catch (error) {
    message.warning(error instanceof Error ? error.message : t('case_form.hooks.invalid'))
    return
  }
  saving.value = true
  try {
    const payload: CaseSavePayload = {
      name: form.name,
      description: form.description,
      case_type: form.case_type,
      tags: form.tags,
      priority: form.priority,
      case_level: form.case_level,
      module_id: props.moduleId!,
      config,
      dataset_id: form.dataset_id,
      dataset_version: form.dataset_version,
    }
    if (isEdit.value && props.editCase) {
      await caseApi.update(props.editCase.id, {
        name: payload.name,
        description: payload.description,
        tags: payload.tags,
        priority: payload.priority,
        case_level: payload.case_level,
        config: payload.config,
        dataset_id: form.dataset_id,
        dataset_version: form.dataset_version,
      })
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
.file-name {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #666;
  font-size: 12px;
}
.form-hint {
  margin-top: 6px;
  color: #999;
  font-size: 12px;
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
