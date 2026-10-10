<template>
  <a-drawer
    :open="open"
    :title="isEdit ? t('case_form.title_edit') : t('case_form.title_create')"
    :width="880"
    :body-style="{ overflowX: 'hidden' }"
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
              <a-select-option v-if="!localMode" value="ios">{{ t('case_form.case_types.ios') }}</a-select-option>
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
          <template #extra>
            <a-button size="small" type="link" style="padding: 0" @click="form.dataset_prepare_actions_text = tryFormatJson(form.dataset_prepare_actions_text)">
              <FormatPainterOutlined /> 格式化 JSON
            </a-button>
          </template>
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
        <a-tabs v-model:activeKey="apiConfigTab" class="api-case-main-tabs" size="small">
          <a-tab-pane key="request" :tab="t('case_form.sections.request_config')">
        <div class="url-config-section">
          <div class="url-label-row">
            <span class="url-label-title"><span class="required-star">*</span> {{ t('case_form.api.url_label') }}</span>
            <a-dropdown :trigger="['click']">
              <template #overlay>
                <a-menu @click="handleApplyRequestTemplate">
                  <a-menu-item key="rest_json_get">
                    <div class="preset-menu-item">
                      <span class="preset-label">📋 标准 REST 查询 (GET + Accept JSON)</span>
                      <small class="preset-code">配置 GET 方式、Accept 请求头与分页参数</small>
                    </div>
                  </a-menu-item>
                  <a-menu-item key="jwt_form_login">
                    <div class="preset-menu-item">
                      <span class="preset-label">🔑 表单登录获取 Token (POST + urlencoded)</span>
                      <small class="preset-code">配置 POST、urlencoded 头与表单凭据</small>
                    </div>
                  </a-menu-item>
                  <a-menu-item key="auth_json_post">
                    <div class="preset-menu-item">
                      <span class="preset-label">🛡️ 鉴权业务调用 (POST + Bearer Token)</span>
                      <small class="preset-code">配置 POST、JSON 头、Authorization 头与 Body</small>
                    </div>
                  </a-menu-item>
                  <a-menu-item key="healthcheck_get">
                    <div class="preset-menu-item">
                      <span class="preset-label">🩺 服务探活配置 (GET)</span>
                      <small class="preset-code">配置 GET 方式</small>
                    </div>
                  </a-menu-item>
                </a-menu>
              </template>
              <a-button size="small" class="request-template-pill-btn">
                <ThunderboltOutlined /> {{ t('api_scenario.request_template_label') }} <DownOutlined style="font-size: 9px" />
              </a-button>
            </a-dropdown>
          </div>

          <a-form-item :rules="[{ required: true, message: t('case_form.api.url_required') }]" style="margin-bottom: 14px">
            <a-input-group compact style="display: flex; width: 100%">
              <a-select v-model:value="cfg.method" style="width: 110px; flex-shrink: 0">
                <a-select-option v-for="m in HTTP_METHODS" :key="m" :value="m">{{ m }}</a-select-option>
              </a-select>
              <a-input v-model:value="cfg.url" style="flex: 1" placeholder="https://api.example.com/v1/..." />
            </a-input-group>
          </a-form-item>
        </div>

        <a-tabs v-model:activeKey="activeTab" size="small">
          <a-tab-pane key="headers" :tab="t('case_form.tabs.headers')">
            <KvEditor v-model:value="cfg.headers" preset-kind="headers" />
          </a-tab-pane>

          <a-tab-pane key="params" :tab="t('case_form.tabs.params')">
            <KvEditor v-model:value="cfg.params" preset-kind="params" />
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
            <template v-else-if="cfg.body_type !== 'none'">
              <div v-if="cfg.body_type === 'json' || cfg.body_type === 'raw'" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
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
                  <a-button size="small" @click="cfg.body = tryFormatJson(cfg.body)">
                    <FormatPainterOutlined /> 格式化 JSON
                  </a-button>
                  <a-button size="small" @click="cfg.body = tryCompressJson(cfg.body)">
                    压缩
                  </a-button>
                </a-space>
              </div>
              <a-textarea
                v-model:value="cfg.body"
                :rows="8"
                :placeholder="cfg.body_type === 'xml' ? '<request><id>{{id}}</id></request>' : 'JSON body'"
                style="font-family: monospace; font-size: 13px"
              />
            </template>
          </a-tab-pane>

          <a-tab-pane key="cookies" :tab="t('case_form.tabs.cookies')">
            <KvEditor v-model:value="cfg.cookies" preset-kind="cookies" />
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

        <section class="request-preview" aria-label="API request preview">
          <div class="request-preview-toolbar">
            <div>
              <strong>{{ t('case_form.preview.title') }}</strong>
              <div class="form-hint">{{ t('case_form.preview.hint') }}</div>
            </div>
            <a-space>
              <a-button v-if="previewLoading" @click="cancelPreview">{{ t('case_form.preview.cancel') }}</a-button>
              <a-button type="primary" :loading="previewLoading" :disabled="!cfg.url.trim() || !props.projectId" @click="sendPreview">
                {{ t('case_form.preview.send') }}
              </a-button>
            </a-space>
          </div>
          <a-alert v-if="previewError" type="error" show-icon :message="previewError" style="margin-top: 12px" />
          <div v-if="previewResult" class="request-preview-result">
            <div class="request-preview-metrics">
              <a-tag :color="previewResult.status_code < 400 ? 'green' : 'red'">
                {{ previewResult.status_code }} {{ previewResult.reason }}
              </a-tag>
              <span>{{ previewResult.duration_ms }} ms</span>
              <span>{{ formatPreviewSize(previewResult.size_bytes) }}</span>
              <a-tag v-if="previewResult.truncated" color="orange">{{ t('case_form.preview.truncated') }}</a-tag>
            </div>
            <a-tabs v-model:activeKey="previewTab" size="small">
              <a-tab-pane key="body" :tab="t('case_form.preview.response_body')">
                <pre class="request-preview-content">{{ formattedPreviewBody }}</pre>
              </a-tab-pane>
              <a-tab-pane key="headers" :tab="t('case_form.preview.response_headers')">
                <pre class="request-preview-content">{{ formattedPreviewHeaders }}</pre>
              </a-tab-pane>
            </a-tabs>
          </div>
        </section>

        <div class="scenario-pipeline-quick-banner">
          <div class="banner-text">
            <strong>🔗 {{ t('api_scenario.pipeline_title') }} ({{ apiScenarioSteps.length }})</strong>
            <span>{{ t('api_scenario.pipeline_desc') }}</span>
          </div>
          <a-space>
            <a-button type="primary" ghost size="small" @click="libraryPickerOpen = true">
              <ApiOutlined /> {{ t('api_scenario.import_from_library') }}
            </a-button>
            <a-button size="small" @click="apiConfigTab = 'scenario'">
              查看场景流水线 ({{ apiScenarioSteps.length }})
            </a-button>
          </a-space>
        </div>
      </a-tab-pane>

      <!-- Tab 2: 场景自动化流水线 -->
      <a-tab-pane key="scenario" :tab="`⚡ 场景流水线 (${apiScenarioSteps.length})`">
        <ApiScenarioPipeline
          v-model:steps="apiScenarioSteps"
          :project-id="projectId"
          :can-modify="true"
          @open-library-picker="libraryPickerOpen = true"
        />
      </a-tab-pane>

      <!-- Tab 2: 断言与变量提取 -->
      <a-tab-pane key="validations" :tab="t('case_form.tab_validations')">
        <div class="section-header-bar">
          <div class="section-header-left">
            <span class="section-header-title">{{ t('case_form.sections.assertions') }}</span>
            <span class="section-header-line" />
          </div>
          <a-button
            type="primary"
            ghost
            size="small"
            class="ai-suggest-btn"
            :loading="aiSuggesting"
            @click="openAiSuggestModal"
          >
            <ThunderboltOutlined /> {{ t('case_form.ai_suggest_action') }}
          </a-button>
        </div>
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

        <div class="section-header-bar">
          <div class="section-header-left">
            <span class="section-header-title">{{ t('case_form.sections.extractions') }}</span>
            <span class="section-header-line" />
          </div>
        </div>
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
      </a-tab-pane>

      <!-- Tab 3: 执行策略与高级 -->
      <a-tab-pane key="strategy" :tab="t('case_form.tab_strategy')">
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

        <a-form-item :label="t('case_form.hooks.pre_label')">
          <template #extra>
            <a-button size="small" type="link" style="padding: 0" @click="cfg.pre_actions_text = tryFormatJson(cfg.pre_actions_text)">
              <FormatPainterOutlined /> 格式化 JSON
            </a-button>
          </template>
          <a-textarea
            v-model:value="cfg.pre_actions_text"
            :rows="3"
            :placeholder="hookActionPlaceholder"
            style="font-family: monospace; font-size: 12px"
          />
          <div class="form-hint">{{ t('case_form.hooks.hint') }}</div>
        </a-form-item>
        <a-form-item :label="t('case_form.hooks.post_label')">
          <template #extra>
            <a-button size="small" type="link" style="padding: 0" @click="cfg.post_actions_text = tryFormatJson(cfg.post_actions_text)">
              <FormatPainterOutlined /> 格式化 JSON
            </a-button>
          </template>
          <a-textarea
            v-model:value="cfg.post_actions_text"
            :rows="3"
            :placeholder="hookActionPlaceholder"
            style="font-family: monospace; font-size: 12px"
          />
        </a-form-item>
        </a-tab-pane>
      </a-tabs>
    </template>

      <template v-else-if="form.case_type === 'graphql'">
        <a-divider orientation="left">{{ t('case_form.sections.graphql_config') }}</a-divider>

        <a-form-item :label="t('case_form.graphql.endpoint_label')" :rules="[{ required: true, message: t('case_form.graphql.endpoint_required') }]">
          <a-input-group compact>
            <a-input v-model:value="gqlCfg.endpoint" placeholder="https://api.example.com/graphql" style="width: calc(100% - 132px)" />
            <a-button :loading="gqlIntrospectionLoading" @click="loadGraphqlSchema">{{ t('case_form.graphql.introspect') }}</a-button>
          </a-input-group>
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item :label="t('case_form.graphql.operation_type_label')">
              <a-select v-model:value="gqlCfg.operation_type">
                <a-select-option value="query">{{ t('case_form.graphql.operation_types.query') }}</a-select-option>
                <a-select-option value="mutation">{{ t('case_form.graphql.operation_types.mutation') }}</a-select-option>
                <a-select-option value="subscription">{{ t('case_form.graphql.operation_types.subscription') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="16">
            <a-form-item :label="t('case_form.graphql.operation_name_label')">
              <a-input v-model:value="gqlCfg.operation_name" :placeholder="t('case_form.graphql.operation_name_placeholder')" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item v-if="gqlSchemaFieldOptions.length" :label="t('case_form.graphql.schema_field_label')">
          <a-select
            show-search
            :options="gqlSchemaFieldOptions"
            :placeholder="t('case_form.graphql.schema_field_placeholder')"
            @select="applyGraphqlField"
          />
        </a-form-item>

        <a-form-item :label="t('case_form.graphql.query_label')" :rules="[{ required: true, message: t('case_form.graphql.query_required') }]">
          <a-textarea
            v-model:value="gqlCfg.query"
            :rows="8"
            placeholder="query GetUser($id: ID!) {&#10;  user(id: $id) {&#10;    name&#10;    email&#10;  }&#10;}"
            style="font-family: monospace; font-size: 13px"
          />
        </a-form-item>

        <a-form-item :label="t('case_form.graphql.variables_label')">
          <template #extra>
            <a-button size="small" type="link" style="padding: 0" @click="gqlCfg.variables_text = tryFormatJson(gqlCfg.variables_text)">
              <FormatPainterOutlined /> 格式化 JSON
            </a-button>
          </template>
          <a-textarea
            v-model:value="gqlCfg.variables_text"
            :rows="4"
            placeholder='{"id": "123"}'
            style="font-family: monospace; font-size: 13px"
          />
        </a-form-item>

        <template v-if="gqlCfg.operation_type === 'subscription'">
          <a-form-item :label="t('case_form.graphql.subscription_url_label')">
            <a-input v-model:value="gqlCfg.subscription_url" placeholder="wss://api.example.com/graphql" />
          </a-form-item>
          <a-form-item :label="t('case_form.graphql.connection_payload_label')">
            <template #extra>
              <a-button size="small" type="link" style="padding: 0" @click="gqlCfg.connection_payload_text = tryFormatJson(gqlCfg.connection_payload_text)">
                <FormatPainterOutlined /> 格式化 JSON
              </a-button>
            </template>
            <a-textarea v-model:value="gqlCfg.connection_payload_text" :rows="3" placeholder='{"authToken":"{{token}}"}' />
          </a-form-item>
          <a-row :gutter="16">
            <a-col :span="8"><a-form-item :label="t('case_form.graphql.max_messages_label')"><a-input-number v-model:value="gqlCfg.max_messages" :min="1" :max="100" /></a-form-item></a-col>
            <a-col :span="8"><a-form-item :label="t('case_form.websocket.reconnect_attempts_label')"><a-input-number v-model:value="gqlCfg.reconnect_attempts" :min="0" :max="5" /></a-form-item></a-col>
            <a-col :span="8"><a-form-item :label="t('case_form.websocket.reconnect_delay_label')"><a-input-number v-model:value="gqlCfg.reconnect_delay_ms" :min="0" :max="30000" /></a-form-item></a-col>
          </a-row>
        </template>

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
        <a-row :gutter="16">
          <a-col :span="12"><a-form-item :label="t('case_form.websocket.reconnect_attempts_label')"><a-input-number v-model:value="wsCfg.reconnect_attempts" :min="0" :max="5" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item :label="t('case_form.websocket.reconnect_delay_label')"><a-input-number v-model:value="wsCfg.reconnect_delay_ms" :min="0" :max="30000" /></a-form-item></a-col>
        </a-row>

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
          <template #extra>
            <a-button size="small" type="link" style="padding: 0" @click="grpcCfg.request_json = tryFormatJson(grpcCfg.request_json)">
              <FormatPainterOutlined /> 格式化 JSON
            </a-button>
          </template>
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

  <!-- AI 智能推荐断言与变量提取弹窗 -->
  <a-modal
    v-model:open="aiSuggestModalOpen"
    :title="t('case_form.ai_suggest_modal_title')"
    width="720px"
    :ok-text="t('case_form.ai_suggest_apply')"
    :ok-button-props="{ disabled: selectedAssertIndexes.length === 0 && selectedExtractIndexes.length === 0 }"
    @ok="applyAiSuggestions"
  >
    <a-alert
      type="info"
      show-icon
      :message="t('case_form.ai_suggest_modal_desc')"
      style="margin-bottom: 16px"
    />

    <div class="ai-suggest-sample-box">
      <div class="sample-label-row">
        <label>{{ t('case_form.ai_suggest_paste_resp') }}</label>
        <a-button size="small" type="link" :loading="aiSuggesting" @click="fetchAiSuggestions">
          <ReloadOutlined /> 重新推荐
        </a-button>
      </div>
      <a-textarea
        v-model:value="customResponseSampleText"
        :rows="3"
        placeholder='例如: {"code": 0, "message": "success", "data": {"token": "eyJ...", "user_id": 10086}}'
        style="font-family: monospace; font-size: 12px; margin-bottom: 16px"
      />
    </div>

    <div v-if="aiSuggesting" class="ai-suggest-loading">
      <a-spin />
      <span style="margin-left: 8px">AI 正在深度解析接口数据并生成推荐规则...</span>
    </div>

    <div v-else>
      <!-- 推荐断言 -->
      <div class="suggest-section">
        <div class="suggest-section-head">
          <strong>推荐断言 ({{ selectedAssertIndexes.length }}/{{ suggestedAssertions.length }})</strong>
          <a-button type="link" size="small" @click="toggleAllAsserts">
            {{ selectedAssertIndexes.length === suggestedAssertions.length ? '全部取消' : '全选' }}
          </a-button>
        </div>
        <div v-if="suggestedAssertions.length === 0" class="suggest-empty-tip">未生成断言建议</div>
        <div v-else class="suggest-items-grid">
          <div
            v-for="(item, idx) in suggestedAssertions"
            :key="`assert-${idx}`"
            class="suggest-card"
            :class="{ 'is-selected': selectedAssertIndexes.includes(idx) }"
            @click="toggleAssertIndex(idx)"
          >
            <a-checkbox
              :checked="selectedAssertIndexes.includes(idx)"
              @click.stop="toggleAssertIndex(idx)"
            />
            <div class="suggest-card-body">
              <div class="suggest-card-top">
                <a-tag color="blue">{{ item.target }}</a-tag>
                <code class="suggest-card-code">{{ item.expression || item.target }} {{ item.operator }} {{ item.expected || 'exists' }}</code>
              </div>
              <small class="suggest-card-desc">{{ item.description }}</small>
            </div>
          </div>
        </div>
      </div>

      <!-- 推荐变量提取 -->
      <div class="suggest-section" style="margin-top: 16px">
        <div class="suggest-section-head">
          <strong>推荐变量提取 ({{ selectedExtractIndexes.length }}/{{ suggestedExtractions.length }})</strong>
          <a-button type="link" size="small" @click="toggleAllExtracts">
            {{ selectedExtractIndexes.length === suggestedExtractions.length ? '全部取消' : '全选' }}
          </a-button>
        </div>
        <div v-if="suggestedExtractions.length === 0" class="suggest-empty-tip">未生成变量提取建议</div>
        <div v-else class="suggest-items-grid">
          <div
            v-for="(item, idx) in suggestedExtractions"
            :key="`extract-${idx}`"
            class="suggest-card"
            :class="{ 'is-selected': selectedExtractIndexes.includes(idx) }"
            @click="toggleExtractIndex(idx)"
          >
            <a-checkbox
              :checked="selectedExtractIndexes.includes(idx)"
              @click.stop="toggleExtractIndex(idx)"
            />
            <div class="suggest-card-body">
              <div class="suggest-card-top">
                <span class="suggest-var-badge">${{ item.variable }}</span>
                <span style="color: var(--c-text-tertiary); margin: 0 4px">=</span>
                <code class="suggest-card-code">{{ item.expression }}</code>
              </div>
              <small class="suggest-card-desc">{{ item.description }}</small>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>

  <ApiLibraryPickerDrawer
    v-model:open="libraryPickerOpen"
    :project-id="projectId"
    :current-step-count="apiScenarioSteps.length"
    @import="handleImportLibrarySteps"
  />
</template>


<script setup lang="ts">
import { getRuntimeMode } from '@/runtimeMode'
import { computed, onBeforeUnmount, ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined, MinusCircleOutlined, FormatPainterOutlined, ThunderboltOutlined, ReloadOutlined, ApiOutlined, DownOutlined } from '@ant-design/icons-vue'
import ApiLibraryPickerDrawer from '@/components/common/ApiLibraryPickerDrawer.vue'
import ApiScenarioPipeline from '@/components/common/ApiScenarioPipeline.vue'
import type { ApiScenarioStep } from '@/types/apiScenario'
import { tryFormatJson, tryCompressJson } from '@/utils/jsonFormat'
import { apiSchemaAssetApi, caseApi, projectApi, datasetApi, type AIAssertionSuggestion, type AIExtractionSuggestion, type ApiRequestPreviewPayload, type ApiRequestPreviewResult, type ApiSchemaAssetItem, type GraphqlIntrospectionField } from '@/api'
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

const localMode = getRuntimeMode()?.mode === 'local'
const { t } = useI18n()
const hookActionPlaceholder = JSON.stringify([{ action: 'set_variable', variable: 'request_id', value: 'demo' }])
const apiConfigTab = ref('request')

const libraryPickerOpen = ref(false)

function handleImportLibrarySteps(importedSteps: ApiScenarioStep[]) {
  if (!importedSteps.length) return
  if (!apiScenarioSteps.value.length) {
    const first = importedSteps[0]
    if (first.url) cfg.url = first.url
    if (first.method) cfg.method = first.method
    if (first.headers) cfg.headers = { ...first.headers }
    if (first.params) cfg.params = { ...first.params }
    if (first.cookies) cfg.cookies = { ...first.cookies }
    if (first.body_type) cfg.body_type = first.body_type as typeof cfg.body_type
    if (first.body != null) cfg.body = typeof first.body === 'string' ? first.body : JSON.stringify(first.body, null, 2)
    if (first.assertions) {
      cfg.assertions = first.assertions.map((a) => ({
        target: a.target,
        operator: a.operator,
        expected: a.expected,
        expression: a.expression,
        schema_asset_id: a.schema_asset_id,
      }))
    }
    if (first.extractions) {
      cfg.extractions = first.extractions.map((e) => ({
        variable: e.variable,
        expression: e.expression,
        type: e.type,
      }))
    }
    if (!form.name && first.name) form.name = first.name
    apiScenarioSteps.value = [...importedSteps]
  } else {
    const offset = apiScenarioSteps.value.length
    const withDeps = importedSteps.map((step, idx) => ({
      ...step,
      depends_on: [offset + idx - 1],
    }))
    apiScenarioSteps.value.push(...withDeps)
  }
  apiConfigTab.value = 'scenario'
}
function handleApplyRequestTemplate({ key }: { key: string | number }) {
  if (key === 'rest_json_get') {
    cfg.method = 'GET'
    cfg.headers = { ...cfg.headers, Accept: 'application/json' }
    cfg.params = { ...cfg.params, page: '1', page_size: '20' }
    message.success(t('api_scenario.template_applied', { name: '标准 REST 查询' }))
  } else if (key === 'jwt_form_login') {
    cfg.method = 'POST'
    cfg.headers = { ...cfg.headers, 'Content-Type': 'application/x-www-form-urlencoded' }
    cfg.body_type = 'form'
    formBody.value = { username: 'admin', password: 'password' }
    message.success(t('api_scenario.template_applied', { name: '表单登录获取 Token' }))
  } else if (key === 'auth_json_post') {
    cfg.method = 'POST'
    cfg.headers = {
      ...cfg.headers,
      'Content-Type': 'application/json',
      Authorization: 'Bearer {{token}}',
    }
    cfg.body_type = 'json'
    if (!cfg.body) cfg.body = JSON.stringify({ name: 'demo', status: 'active' }, null, 2)
    message.success(t('api_scenario.template_applied', { name: '鉴权业务调用' }))
  } else if (key === 'healthcheck_get') {
    cfg.method = 'GET'
    message.success(t('api_scenario.template_applied', { name: '服务探活心跳' }))
  }
}
function handleApplyBodyTemplate({ key }: { key: string | number }) {
  if (key === 'empty_object') {
    cfg.body = '{\n  \n}'
  } else if (key === 'pagination') {
    cfg.body = JSON.stringify({ page: 1, page_size: 20, keyword: '' }, null, 2)
  } else if (key === 'login_credentials') {
    cfg.body = JSON.stringify({ username: 'admin', password: 'password' }, null, 2)
  } else if (key === 'id_update') {
    cfg.body = JSON.stringify({ id: '{{id}}', status: 'active' }, null, 2)
  } else if (key === 'object_array') {
    cfg.body = JSON.stringify([{ name: 'item1' }], null, 2)
  }
  message.success(t('api_scenario.template_applied', { name: 'Body 结构' }))
}


const aiSuggestModalOpen = ref(false)
const aiSuggesting = ref(false)
const customResponseSampleText = ref('')
const cachedResponseSample = ref<unknown>(null)
const cachedStatusCode = ref<number | null>(null)
const suggestedAssertions = ref<AIAssertionSuggestion[]>([])
const suggestedExtractions = ref<AIExtractionSuggestion[]>([])
const selectedAssertIndexes = ref<number[]>([])
const selectedExtractIndexes = ref<number[]>([])

async function openAiSuggestModal() {
  aiSuggestModalOpen.value = true
  if (suggestedAssertions.value.length === 0 && suggestedExtractions.value.length === 0) {
    await fetchAiSuggestions()
  }
}

async function fetchAiSuggestions() {
  aiSuggesting.value = true
  try {
    let parsedBody: unknown = undefined
    const text = customResponseSampleText.value.trim()
    if (text) {
      try {
        parsedBody = JSON.parse(text)
      } catch {
        parsedBody = text
      }
    } else if (cachedResponseSample.value !== null) {
      parsedBody = cachedResponseSample.value
    } else if (cfg.body) {
      try {
        parsedBody = JSON.parse(cfg.body)
      } catch {
        parsedBody = cfg.body
      }
    }

    const res = await caseApi.suggestAssertions({
      project_id: props.projectId,
      method: cfg.method || 'GET',
      url: cfg.url || '',
      status_code: cachedStatusCode.value ?? 200,
      response_body: parsedBody,
      request_body: cfg.body || undefined,
    })

    suggestedAssertions.value = res.assertions
    suggestedExtractions.value = res.extractions
    selectedAssertIndexes.value = res.assertions.map((_, i) => i)
    selectedExtractIndexes.value = res.extractions.map((_, i) => i)
  } catch (err: unknown) {
    message.error(err instanceof Error ? err.message : '获取 AI 建议失败')
  } finally {
    aiSuggesting.value = false
  }
}

function toggleAllAsserts() {
  if (selectedAssertIndexes.value.length === suggestedAssertions.value.length) {
    selectedAssertIndexes.value = []
  } else {
    selectedAssertIndexes.value = suggestedAssertions.value.map((_, i) => i)
  }
}

function toggleAssertIndex(idx: number) {
  const i = selectedAssertIndexes.value.indexOf(idx)
  if (i >= 0) {
    selectedAssertIndexes.value.splice(i, 1)
  } else {
    selectedAssertIndexes.value.push(idx)
  }
}

function toggleAllExtracts() {
  if (selectedExtractIndexes.value.length === suggestedExtractions.value.length) {
    selectedExtractIndexes.value = []
  } else {
    selectedExtractIndexes.value = suggestedExtractions.value.map((_, i) => i)
  }
}

function toggleExtractIndex(idx: number) {
  const i = selectedExtractIndexes.value.indexOf(idx)
  if (i >= 0) {
    selectedExtractIndexes.value.splice(i, 1)
  } else {
    selectedExtractIndexes.value.push(idx)
  }
}

function applyAiSuggestions() {
  const addedAsserts: AssertionItem[] = selectedAssertIndexes.value.map((idx) => {
    const s = suggestedAssertions.value[idx]
    return {
      target: s.target,
      operator: s.operator,
      expected: s.expected,
      expression: s.expression,
      expression_type: 'jsonpath' as const,
    }
  })

  const addedExtracts: ExtractionItem[] = selectedExtractIndexes.value.map((idx) => {
    const s = suggestedExtractions.value[idx]
    return {
      variable: s.variable,
      type: 'jsonpath' as const,
      expression: s.expression,
    }
  })

  cfg.assertions.push(...addedAsserts)
  cfg.extractions.push(...addedExtracts)

  aiSuggestModalOpen.value = false
  message.success(
    t('case_form.ai_suggest_applied', {
      assertions: addedAsserts.length,
      extractions: addedExtracts.length,
    })
  )
}

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
  type?: 'jsonpath' | 'xpath' | 'regex' | 'header'
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

type CaseConfigStep = ApiScenarioStep & {
  multipart?: MultipartPart[]
  auth?: Partial<AuthConfig>
  messages?: WsMessage[]
  assertions?: AssertionItem[]
  extractions?: ExtractionItem[]
  pre_actions?: HookAction[]
  post_actions?: HookAction[]
}
type EditableCase = Pick<CaseSummaryItem, 'id' | 'name' | 'description' | 'case_type' | 'tags' | 'dataset_id' | 'dataset_version' | 'priority' | 'case_level'> &
  Partial<Pick<CaseDetailItem, 'config'>>

const props = defineProps<{
  open: boolean
  moduleId: number | null
  projectId?: number | null
  editCase?: EditableCase | null
  defaultCaseType?: CaseType
  draftRequest?: ApiRequestPreviewPayload | null
  initialScenarioSteps?: ApiScenarioStep[] | null
}>()
const emit = defineEmits<{ close: []; saved: [] }>()

const isEdit = ref(false)
const saving = ref(false)
const activeTab = ref('headers')
const gqlActiveTab = ref('headers')
const gqlIntrospectionLoading = ref(false)
const gqlSchemaFields = ref<GraphqlIntrospectionField[]>([])
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
const apiScenarioSteps = ref<ApiScenarioStep[]>([])

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
const previewLoading = ref(false)
const previewError = ref('')
const previewResult = ref<ApiRequestPreviewResult | null>(null)
const previewTab = ref('body')
let previewController: AbortController | null = null

const formattedPreviewBody = computed(() => {
  const result = previewResult.value
  if (!result?.body) return t('case_form.preview.empty_body')
  if (!result.headers['content-type']?.toLowerCase().includes('json')) return result.body
  try {
    return JSON.stringify(JSON.parse(result.body), null, 2)
  } catch {
    return result.body
  }
})
const formattedPreviewHeaders = computed(() =>
  Object.entries(previewResult.value?.headers ?? {}).map(([key, value]) => `${key}: ${value}`).join('\n'),
)

function formatPreviewSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`
}

function cancelPreview() {
  previewController?.abort()
  previewController = null
  previewLoading.value = false
}

function resetPreview() {
  cancelPreview()
  previewResult.value = null
  previewError.value = ''
}

watch(cfg, resetPreview, { deep: true })
watch(formBody, resetPreview, { deep: true })
onBeforeUnmount(cancelPreview)

async function sendPreview() {
  if (!props.projectId || previewLoading.value) return
  const url = cfg.url.trim()
  if (!url) {
    previewError.value = t('case_form.msg.url_required')
    return
  }
  if (cfg.body_type === 'json' && cfg.body.trim()) {
    try {
      JSON.parse(cfg.body)
    } catch {
      previewError.value = t('case_form.preview.invalid_json')
      return
    }
  }
  const controller = new AbortController()
  previewController = controller
  previewLoading.value = true
  previewError.value = ''
  previewResult.value = null
  try {
    previewResult.value = await caseApi.previewRequest(props.projectId, {
      method: cfg.method,
      url,
      headers: { ...cfg.headers },
      params: { ...cfg.params },
      cookies: { ...cfg.cookies },
      body_type: cfg.body_type,
      body: resolveRequestBody(cfg.body_type, cfg.body, formBody.value),
      multipart: cfg.multipart.map((part) => ({ ...part })),
      auth: { ...cfg.auth },
      timeout: Math.min(Math.max(cfg.timeout || 30, 1), 60),
    }, controller.signal)
    previewTab.value = 'body'
  } catch (error) {
    if (!controller.signal.aborted) {
      previewError.value = typeof error === 'string' ? error : error instanceof Error ? error.message : JSON.stringify(error)
    }
  } finally {
    if (previewController === controller) {
      previewController = null
      previewLoading.value = false
    }
  }
}

const gqlCfg = reactive({
  endpoint: '',
  operation_type: 'query' as 'query' | 'mutation' | 'subscription',
  subscription_url: '',
  connection_payload_text: '',
  max_messages: 1,
  reconnect_attempts: 0,
  reconnect_delay_ms: 500,
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
  reconnect_attempts: 0,
  reconnect_delay_ms: 500,
  messages: [] as WsMessage[],
})

const gqlSchemaFieldOptions = computed(() => gqlSchemaFields.value
  .filter((item) => item.operation_type === gqlCfg.operation_type)
  .map((item) => ({ label: `${item.name}${item.arguments.length ? `(${item.arguments.join(', ')})` : ''}`, value: item.name })))

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

async function loadGraphqlSchema() {
  if (!props.projectId || !gqlCfg.endpoint.trim()) {
    message.warning(t('case_form.graphql.introspect_endpoint_required'))
    return
  }
  gqlIntrospectionLoading.value = true
  try {
    const result = await apiSchemaAssetApi.introspectGraphql(props.projectId, {
      endpoint: gqlCfg.endpoint.trim(),
      headers: gqlCfg.headers,
      timeout: gqlCfg.timeout,
    })
    gqlSchemaFields.value = result.fields
    message.success(t('case_form.graphql.introspect_success', { count: result.fields.length }))
  } catch (error: any) {
    message.error(error?.response?.data?.detail || t('case_form.graphql.introspect_failed'))
  } finally {
    gqlIntrospectionLoading.value = false
  }
}

function applyGraphqlField(selected: unknown) {
  const fieldName = String(selected)
  const field = gqlSchemaFields.value.find((item) => item.operation_type === gqlCfg.operation_type && item.name === fieldName)
  if (!field) return
  const operationName = gqlCfg.operation_name.trim() ? ` ${gqlCfg.operation_name.trim()}` : ''
  const argumentHint = field.arguments.length ? `(${field.arguments.map((name) => `${name}: $${name}`).join(', ')})` : ''
  gqlCfg.query = `${gqlCfg.operation_type}${operationName} {\n  ${field.name}${argumentHint}\n}`
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

watch(() => props.open, async (v) => {
  resetPreview()
  if (!v) return
  loadDatasetOptions()
  loadSchemaAssetOptions()
  if (props.editCase) {
    isEdit.value = true
    let c = props.editCase
    if (c.id && (!c.config || Object.keys(c.config).length === 0)) {
      try {
        const full = await caseApi.get(c.id)
        if (full) c = full
      } catch {
        // keep c
      }
    }
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
      ? (c.config.steps as ApiScenarioStep[]).map((item) => ({ ...item, depends_on: Array.isArray(item.depends_on) ? [...item.depends_on] : [] }))
      : []
    if (apiScenarioSteps.value.length > 1) {
      apiConfigTab.value = 'scenario'
    } else {
      apiConfigTab.value = 'request'
    }
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
        subscription_url: step.subscription_url ?? '',
        connection_payload_text: step.connection_payload ? JSON.stringify(step.connection_payload, null, 2) : '',
        max_messages: step.max_messages ?? 1,
        reconnect_attempts: step.reconnect_attempts ?? 0,
        reconnect_delay_ms: step.reconnect_delay_ms ?? 500,
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
        reconnect_attempts: step.reconnect_attempts ?? 0,
        reconnect_delay_ms: step.reconnect_delay_ms ?? 500,
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
    if (props.draftRequest) {
      const draft = props.draftRequest
      Object.assign(cfg, {
        method: draft.method,
        url: draft.url,
        headers: { ...draft.headers },
        params: { ...draft.params },
        cookies: { ...draft.cookies },
        body_type: draft.body_type,
        body: draft.body == null ? '' : typeof draft.body === 'string' ? draft.body : JSON.stringify(draft.body, null, 2),
        multipart: draft.multipart.map((part) => ({ ...part })),
        auth: { ...cfg.auth, ...draft.auth },
        timeout: draft.timeout,
      })
      if (draft.body_type === 'form' && draft.body && typeof draft.body === 'object' && !Array.isArray(draft.body)) {
        formBody.value = { ...(draft.body as Record<string, string>) }
      }
      if (draft.response_body !== undefined) {
        cachedResponseSample.value = draft.response_body
        customResponseSampleText.value = typeof draft.response_body === 'string'
          ? draft.response_body
          : JSON.stringify(draft.response_body, null, 2)
      } else {
        cachedResponseSample.value = null
        customResponseSampleText.value = ''
      }
      if (draft.status_code !== undefined) {
        cachedStatusCode.value = draft.status_code
      } else {
        cachedStatusCode.value = null
      }
    } else {
      cachedResponseSample.value = null
      customResponseSampleText.value = ''
      cachedStatusCode.value = null
      suggestedAssertions.value = []
      suggestedExtractions.value = []
    }
    apiScenarioSteps.value = []
    if (props.initialScenarioSteps && props.initialScenarioSteps.length) {
      handleImportLibrarySteps(props.initialScenarioSteps)
      apiConfigTab.value = 'scenario'
      if (!form.name.trim()) {
        const stepNames = props.initialScenarioSteps.map((s) => s.name || 'API').filter(Boolean)
        form.name = `自动化场景 - ${stepNames.slice(0, 2).join(' + ')}${stepNames.length > 2 ? ` 等${stepNames.length}个接口` : ''}`
      }
      if (apiScenarioSteps.value[0]?.url) {
        cfg.url = apiScenarioSteps.value[0].url
        cfg.method = apiScenarioSteps.value[0].method || 'GET'
      }
    }
    Object.assign(gqlCfg, {
      endpoint: '', operation_type: 'query', query: '', variables_text: '',
      subscription_url: '', connection_payload_text: '', max_messages: 1, reconnect_attempts: 0, reconnect_delay_ms: 500,
      operation_name: '', headers: {},
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', token_url: '', client_id: '', client_secret: '', scope: '', audience: '', token_endpoint_auth_method: 'client_secret_basic' },
      timeout: 30, assertions: [], extractions: [],
    })
    Object.assign(wsCfg, {
      url: '', headers: {},
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', token_url: '', client_id: '', client_secret: '', scope: '', audience: '', token_endpoint_auth_method: 'client_secret_basic' },
      timeout: 30, reconnect_attempts: 0, reconnect_delay_ms: 500, messages: [],
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
      reconnect_attempts: wsCfg.reconnect_attempts,
      reconnect_delay_ms: wsCfg.reconnect_delay_ms,
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
  const connectionPayload = parseGraphqlVariables(gqlCfg.connection_payload_text)
  return {
    steps: [{
      name: form.name,
      endpoint: gqlCfg.endpoint,
      operation_type: gqlCfg.operation_type,
      subscription_url: gqlCfg.operation_type === 'subscription' ? gqlCfg.subscription_url.trim() || undefined : undefined,
      connection_payload: gqlCfg.operation_type === 'subscription' ? connectionPayload : undefined,
      max_messages: gqlCfg.operation_type === 'subscription' ? gqlCfg.max_messages : undefined,
      reconnect_attempts: gqlCfg.operation_type === 'subscription' ? gqlCfg.reconnect_attempts : undefined,
      reconnect_delay_ms: gqlCfg.operation_type === 'subscription' ? gqlCfg.reconnect_delay_ms : undefined,
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
  let steps: CaseConfigStep[]
  if (apiScenarioSteps.value.length > 0) {
    steps = apiScenarioSteps.value.map((step) => ({
      name: step.name || form.name || 'API 步骤',
      method: (step.method || 'GET').toUpperCase(),
      url: step.url || '',
      headers: step.headers ?? {},
      params: step.params ?? {},
      cookies: step.cookies ?? {},
      body_type: step.body_type ?? 'none',
      body: step.body ?? '',
      assertions: (step.assertions as any) ?? [],
      extractions: (step.extractions as any) ?? [],
      depends_on: step.depends_on ?? [],
      timeout: step.timeout ?? 30,
      pre_actions: Array.isArray(step.pre_actions) ? (step.pre_actions as any) : [],
      post_actions: Array.isArray(step.post_actions) ? (step.post_actions as any) : [],
    }))
  } else {
    steps = [buildCurrentApiStep()]
  }
  return withDatasetStrictFlag({
    reuse_api_session: cfg.session_lifecycle === 'reuse' || cfg.reuse_api_session,
    failure_strategy: cfg.failure_strategy,
    context_scope: cfg.context_scope,
    session_lifecycle: cfg.session_lifecycle,
    steps,
  })
}

async function handleSave() {
  try {
    await formRef.value?.validate()
  } catch {
    message.warning(t('case_form.basic.name_required') || '请先填写用例名称')
    return
  }
  if (!form.name.trim()) {
    message.warning(t('case_form.basic.name_required') || '请先填写用例名称')
    return
  }
  if (localMode && form.case_type === 'ios') {
    message.warning(t('case_form.case_types.ios') + ' 在本地单机模式下不受支持')
    return
  }
  if (form.case_type === 'api') {
    if (apiScenarioSteps.value.length > 0) {
      const emptyUrlStep = apiScenarioSteps.value.find((s) => !s.url?.trim())
      if (emptyUrlStep) {
        message.warning(`场景步骤【${emptyUrlStep.name || '未命名'}】缺少请求 URL`)
        return
      }
    } else if (!cfg.url?.trim()) {
      message.warning(t('case_form.msg.url_required') || '请输入请求 URL')
      return
    }
  }

  let targetModuleId = props.moduleId || (props.editCase as any)?.module_id || null
  if (!targetModuleId && props.projectId) {
    try {
      const modules = await projectApi.getModules(props.projectId)
      const findFirst = (list: any[]): number | null => {
        for (const m of list) {
          if (m.id) return m.id
          if (m.children?.length) {
            const cId = findFirst(m.children)
            if (cId) return cId
          }
        }
        return null
      }
      targetModuleId = findFirst(modules)
    } catch { /* ignore */ }
  }
  if (!targetModuleId) {
    message.warning('请选择用例所属模块')
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
      module_id: targetModuleId,
      config,
      dataset_id: form.dataset_id,
      dataset_version: form.dataset_version,
      auto_approve: true,
    }
    if (isEdit.value && props.editCase) {
      await caseApi.update(props.editCase.id, payload)
    } else {
      await caseApi.create(payload)
    }
    message.success(isEdit.value ? t('case_form.msg.updated') : t('case_form.msg.created'))
    emit('saved')
    emit('close')
  } catch (err: unknown) {
    const msg = (err as any)?.response?.data?.detail || (err instanceof Error ? err.message : '')
    message.error(msg ? `保存用例失败: ${msg}` : '保存用例失败，请检查填写内容')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.section-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 16px 0 12px;
  width: 100%;
}

.section-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.section-header-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text);
  white-space: nowrap;
}

.section-header-line {
  flex: 1;
  height: 1px;
  background: var(--c-border);
}

.ai-suggest-btn {
  flex-shrink: 0;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.ai-suggest-sample-box {
  background: var(--c-bg-subtle, #f8fafc);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.sample-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text, #1e293b);
}

.ai-suggest-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 36px 0;
  color: var(--c-text-secondary, #64748b);
  font-size: 13px;
}

.suggest-section {
  background: var(--c-bg-elevated, #fff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 12px;
}

.suggest-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--c-text, #1e293b);
}

.suggest-items-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
}

.suggest-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 12px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  background: var(--c-bg-subtle, #f8fafc);
  cursor: pointer;
  transition: all 0.15s ease;
}

.suggest-card:hover {
  border-color: var(--c-primary, #1677ff);
  background: var(--c-primary-soft, #f0f7ff);
}

.suggest-card.is-selected {
  border-color: var(--c-primary, #1677ff);
  background: var(--c-primary-soft, #f0f7ff);
}

.suggest-card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.suggest-card-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.suggest-card-code {
  font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
  font-size: 12px;
  color: var(--c-text, #1e293b);
  background: transparent;
}

.suggest-card-desc {
  color: var(--c-text-secondary, #64748b);
  font-size: 11px;
}

.suggest-var-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--c-primary-soft, #f0f7ff);
  color: var(--c-primary, #1677ff);
  font-weight: 700;
  font-size: 11px;
}

.suggest-empty-tip {
  color: var(--c-text-tertiary, #94a3b8);
  font-size: 12px;
  text-align: center;
  padding: 14px 0;
}
.request-preview {
  margin: 18px 0 24px;
  padding: 16px;
  border: 1px solid #d9e3ee;
  border-radius: 10px;
  background: #f8fbff;
}
.request-preview-toolbar,
.request-preview-metrics {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.request-preview-metrics {
  justify-content: flex-start;
  margin-top: 14px;
  color: #475569;
  font-size: 12px;
}
.request-preview-content {
  min-height: 72px;
  max-height: 320px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #1e293b;
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.api-case-main-tabs {
  margin-top: 10px;
}

.api-case-main-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 18px;
}

.sub-tab-heading {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text);
}

.assertion-row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.assertion-row > * {
  min-width: 0;
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
.scenario-pipeline-quick-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  margin-top: 16px;
  background: var(--c-primary-soft, #f0f7ff);
  border: 1px solid var(--c-primary-soft, #bae0ff);
  border-radius: 8px;
}

.scenario-pipeline-quick-banner .banner-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 12px;
}

.scenario-pipeline-quick-banner .banner-text strong {
  font-size: 13px;
  color: var(--c-primary, #1677ff);
}

.scenario-pipeline-quick-banner .banner-text span {
  color: var(--c-text-secondary, #64748b);
}
.url-config-section {
  margin-bottom: 14px;
}

.url-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.url-label-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text, #1e293b);
}

.required-star {
  color: #ff4d4f;
  margin-right: 4px;
}

.request-template-pill-btn {
  height: 26px;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-weight: 600;
  color: var(--c-primary, #1677ff);
  background: var(--c-primary-soft, #f0f7ff);
  border: 1px solid var(--c-primary-soft, #bae0ff);
  border-radius: 4px;
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
