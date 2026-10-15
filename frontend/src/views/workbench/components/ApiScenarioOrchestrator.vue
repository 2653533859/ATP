<template>
  <div class="scenario-orchestrator">
    <!-- 顶部场景控制栏 (参考 AutoDroid ScenarioEditor Header) -->
    <header class="scenario-header">
      <div class="scenario-header-left">
        <a-button type="text" size="small" class="back-btn" @click="emit('exit')">
          ‹ 返回
        </a-button>
        <a-input
          v-model:value="scenarioName"
          class="scenario-name-input"
          placeholder="输入场景名称（如：登录场景回归）"
          :maxlength="160"
        />
        <span class="save-state-badge" :class="{ 'is-dirty': isDirty }">
          {{ saving ? '保存中…' : isDirty ? '未保存' : editingCaseId ? '已保存' : '新场景' }}
        </span>
        <a-select
          v-model:value="selectedEnvId"
          allow-clear
          size="small"
          placeholder="默认环境"
          class="env-select"
          :options="envOptions"
        />
        <a-button type="link" size="small" class="env-var-btn" @click="envModalOpen = true">
          环境变量
        </a-button>
      </div>

      <div class="scenario-header-right">
        <a-button size="small" :disabled="!canModify" :loading="saving" @click="handleSaveScenario(false)">
          保存
        </a-button>
        <a-button
          type="primary"
          size="small"
          :disabled="!steps.length"
          :loading="runningScenario"
          @click="handleRunScenario"
        >
          <PlayCircleOutlined /> 运行场景
        </a-button>
        <a-dropdown :trigger="['click']">
          <a-button size="small">
            更多 <DownOutlined />
          </a-button>
          <template #overlay>
            <a-menu @click="handleMoreMenu">
              <a-menu-item key="load_scenario">打开已有场景用例</a-menu-item>
              <a-menu-item key="new_scenario">新建空白场景</a-menu-item>
              <a-menu-divider />
              <a-menu-item key="clear_debug">清空调试结果</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </header>

    <!-- 场景说明栏 -->
    <div class="scenario-note-bar">
      <input
        v-model="scenarioDescription"
        type="text"
        class="scenario-note-input"
        placeholder="添加说明，帮助接手的人理解这个场景在测什么"
      />
    </div>

    <!-- 三栏核心工作区：左(步骤流) + 中(请求与校验配置) + 右(响应与字段点选) -->
    <div class="scenario-workspace">
      <!-- 第一栏：步骤流 (Steps Flow) -->
      <aside class="steps-flow-pane">
        <div class="flow-heading">
          <span class="flow-title">步骤 ({{ steps.length }})</span>
          <a-button type="link" size="small" class="add-step-btn" @click="openAddStepDrawer">
            <PlusOutlined /> 添加步骤
          </a-button>
        </div>

        <draggable
          v-model="steps"
          item-key="uid"
          handle=".step-drag-handle"
          :animation="160"
          class="steps-list"
          @end="markDirty"
        >
          <template #item="{ element: step, index }">
            <article
              class="step-card"
              :class="{ 'is-selected': selectedStepUid === step.uid }"
              tabindex="0"
              role="button"
              @click="selectStep(step.uid)"
            >
              <div class="step-card-top">
                <span class="step-drag-handle" title="拖拽调整顺序">⋮⋮</span>
                <span class="step-card-title" :title="step.name">
                  {{ index + 1 }}. {{ step.name || '未命名步骤' }}
                </span>
                <a-dropdown :trigger="['click']" @click.stop>
                  <button type="button" class="step-more-btn" @click.stop>···</button>
                  <template #overlay>
                    <a-menu @click="({ key }) => handleStepAction(String(key), index)">
                      <a-menu-item key="duplicate">复制步骤</a-menu-item>
                      <a-menu-item key="up" :disabled="index === 0">上移一步</a-menu-item>
                      <a-menu-item key="down" :disabled="index === steps.length - 1">下移一步</a-menu-item>
                      <a-menu-divider />
                      <a-menu-item key="remove" danger>删除步骤</a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </div>
              <div class="step-card-meta">
                <span>{{ (step.method || 'GET').toUpperCase() }} · {{ (step.assertions || []).length }} 条校验</span>
                <span v-if="(step.extractions || []).length" class="meta-extract">
                  · {{ step.extractions.length }} 项取值
                </span>
              </div>
              <div v-if="stepDebugResults[step.uid]" class="step-card-status">
                <a-tag
                  :color="stepDebugResults[step.uid]?.passed ? 'success' : 'error'"
                  size="small"
                >
                  {{ stepDebugResults[step.uid]?.status_code || 'ERR' }}
                  · {{ stepDebugResults[step.uid]?.passed ? '校验通过' : '校验未通过' }}
                </a-tag>
              </div>
            </article>
          </template>
        </draggable>

        <div v-if="!steps.length" class="steps-empty">
          <p>按业务操作顺序添加接口步骤</p>
          <a-space direction="vertical" style="width: 100%">
            <a-button type="primary" size="small" block @click="openAddStepDrawer">
              <PlusOutlined /> 从接口库选择
            </a-button>
            <a-button size="small" block @click="addBlankStep">
              新建空白请求
            </a-button>
          </a-space>
        </div>
      </aside>

      <!-- 第二栏：当前步骤配置器 (Step Request & Assertion Inspector) -->
      <section v-if="currentStep" class="step-inspector-pane">
        <div class="inspector-scroll">
          <!-- 步骤名称行 -->
          <div class="step-title-bar">
            <a-input
              v-model:value="currentStep.name"
              placeholder="输入步骤名称"
              class="step-name-input"
              @change="markDirty"
            />
            <span class="step-origin-tag">
              {{ currentStep.sourceCaseId ? '来自接口库' : '场景内步骤' }}
            </span>
          </div>

          <!-- 请求方法 + 请求地址 + 取值 + 调试本步 -->
          <div class="request-address-grid">
            <div class="addr-col-method">
              <label class="field-label">请求方法</label>
              <a-select
                v-model:value="currentStep.method"
                class="method-select"
                @change="markDirty"
              >
                <a-select-option v-for="m in HTTP_METHODS" :key="m" :value="m">{{ m }}</a-select-option>
              </a-select>
            </div>

            <div class="addr-col-url">
              <label class="field-label">请求地址</label>
              <div class="url-input-group">
                <a-input
                  v-model:value="currentStep.url"
                  placeholder="https://example.com/api/v1/resource 或 /api/path"
                  class="url-input"
                  @change="markDirty"
                />
                <a-dropdown :trigger="['click']">
                  <a-button class="var-picker-btn">
                    取值 <DownOutlined />
                  </a-button>
                  <template #overlay>
                    <a-menu @click="({ key }) => insertVariableIntoUrl(String(key))">
                      <a-menu-item-group v-if="availableUpstreamVars.length" title="前序步骤提取变量">
                        <a-menu-item v-for="v in availableUpstreamVars" :key="v.name">
                          <code>{{ formatVarToken(v.name) }}</code>
                          <span class="var-menu-sub">（来自：{{ v.stepName }}）</span>
                        </a-menu-item>
                      </a-menu-item-group>
                      <a-menu-item-group v-if="currentEnvVariables.length" title="当前环境变量">
                        <a-menu-item v-for="ev in currentEnvVariables" :key="ev.key">
                          <code>{{ formatVarToken(ev.key) }}</code>
                          <span class="var-menu-sub">={{ ev.value }}</span>
                        </a-menu-item>
                      </a-menu-item-group>
                      <a-menu-item v-if="!availableUpstreamVars.length && !currentEnvVariables.length" key="__none" disabled>
                        暂无可用变量（可在前序步骤「提取变量」或环境变量中添加）
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>

                <a-dropdown-button
                  type="primary"
                  :loading="debugging"
                  @click="debugCurrentStep('single')"
                >
                  调试本步
                  <template #overlay>
                    <a-menu @click="({ key }) => debugCurrentStep(key as 'single' | 'through')">
                      <a-menu-item key="single">仅调试当前步骤</a-menu-item>
                      <a-menu-item key="through">从第 1 步连续执行到此步</a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown-button>
              </div>
            </div>
          </div>

          <!-- 一级 Tab：请求 | 校验 (N) | 提取变量 (N) -->
          <a-tabs v-model:activeKey="inspectorMainTab" class="inspector-main-tabs" size="small">
            <a-tab-pane key="request" tab="请求">
              <!-- 二级 Tab：参数 | 请求体 | 请求头 | 鉴权 | 高级 -->
              <a-tabs v-model:activeKey="requestSubTab" class="inspector-sub-tabs" size="small">
                <a-tab-pane key="params" :tab="`参数 (${queryParamRows.length})`">
                  <div class="kv-section">
                    <div class="kv-header">
                      <span>查询参数 (Query Params)</span>
                      <a-button type="link" size="small" @click="addQueryParamRow">+ 添加参数</a-button>
                    </div>
                    <div v-if="!queryParamRows.length" class="kv-empty">暂无查询参数</div>
                    <div v-for="(row, idx) in queryParamRows" :key="idx" class="kv-row">
                      <a-input v-model:value="row.key" placeholder="参数名" size="small" @change="syncQueryParamsToStep" />
                      <a-input v-model:value="row.value" placeholder="参数值（支持 {{变量}}）" size="small" @change="syncQueryParamsToStep" />
                      <a-button type="text" danger size="small" @click="removeQueryParamRow(idx)">
                        <MinusCircleOutlined />
                      </a-button>
                    </div>
                  </div>
                </a-tab-pane>

                <a-tab-pane key="body" tab="请求体">
                  <div class="body-type-bar">
                    <a-radio-group
                      v-model:value="currentBodyType"
                      size="small"
                      button-style="solid"
                      @change="handleBodyTypeChange"
                    >
                      <a-radio-button value="none">无</a-radio-button>
                      <a-radio-button value="json">JSON</a-radio-button>
                      <a-radio-button value="form">表单</a-radio-button>
                      <a-radio-button value="raw">文本</a-radio-button>
                    </a-radio-group>
                  </div>

                  <div v-if="currentBodyType === 'json'" class="json-body-box">
                    <div class="json-sub-toolbar">
                      <div class="json-mode-pills">
                        <button
                          type="button"
                          class="sub-pill"
                          :class="{ active: jsonEditMode === 'raw' }"
                          @click="jsonEditMode = 'raw'"
                        >
                          JSON
                        </button>
                        <button
                          type="button"
                          class="sub-pill"
                          :class="{ active: jsonEditMode === 'fields' }"
                          @click="switchToJsonFieldsMode"
                        >
                          字段与引用
                        </button>
                        <button
                          type="button"
                          class="sub-pill"
                          :class="{ active: jsonEditMode === 'preview' }"
                          @click="jsonEditMode = 'preview'"
                        >
                          请求预览
                        </button>
                      </div>
                      <a-button type="link" size="small" @click="formatCurrentJsonBody">格式化</a-button>
                    </div>

                    <template v-if="jsonEditMode === 'raw'">
                      <a-textarea
                        v-model:value="jsonBodyText"
                        :rows="10"
                        class="json-textarea"
                        placeholder='{\n  "key": "value"\n}'
                        @change="syncJsonTextToStep"
                      />
                      <div v-if="jsonError" class="json-error-tip">{{ jsonError }}</div>
                      <div class="json-helper-note">
                        直接粘贴 JSON，保留数字、布尔、空值、对象和数组类型。支持使用 {{ formatVarToken('变量名') }} 引用前序步骤返回值。
                      </div>
                    </template>

                    <template v-else-if="jsonEditMode === 'fields'">
                      <div class="json-fields-table">
                        <div v-for="(fRow, fIdx) in jsonFieldRows" :key="fIdx" class="json-field-row">
                          <a-input v-model:value="fRow.key" placeholder="字段名" size="small" @change="syncJsonFieldsToStep" />
                          <a-input v-model:value="fRow.value" placeholder="字段值或 {{变量}}" size="small" @change="syncJsonFieldsToStep" />
                          <a-dropdown :trigger="['click']">
                            <a-button size="small">取值 <DownOutlined /></a-button>
                            <template #overlay>
                              <a-menu @click="({ key }) => setJsonFieldVar(fIdx, String(key))">
                                <a-menu-item v-for="v in availableUpstreamVars" :key="v.name">
                                  {{ formatVarToken(v.name) }}（{{ v.stepName }}）
                                </a-menu-item>
                                <a-menu-item v-for="ev in currentEnvVariables" :key="ev.key">
                                  {{ formatVarToken(ev.key) }}
                                </a-menu-item>
                                <a-menu-item v-if="!availableUpstreamVars.length && !currentEnvVariables.length" key="__empty" disabled>
                                  暂无可用变量
                                </a-menu-item>
                              </a-menu>
                            </template>
                          </a-dropdown>
                          <a-button type="text" danger size="small" @click="removeJsonFieldRow(fIdx)">
                            <MinusCircleOutlined />
                          </a-button>
                        </div>
                        <a-button type="dashed" size="small" block style="margin-top: 8px" @click="addJsonFieldRow">
                          + 添加 JSON 字段
                        </a-button>
                      </div>
                    </template>

                    <template v-else>
                      <pre class="json-preview-box">{{ previewInterpolatedBody }}</pre>
                    </template>
                  </div>

                  <div v-else-if="currentBodyType === 'form'" class="kv-section">
                    <div class="kv-header">
                      <span>表单字段 (application/x-www-form-urlencoded)</span>
                      <a-button type="link" size="small" @click="addFormBodyRow">+ 添加字段</a-button>
                    </div>
                    <div v-for="(row, idx) in formBodyRows" :key="idx" class="kv-row">
                      <a-input v-model:value="row.key" placeholder="字段名" size="small" @change="syncFormBodyToStep" />
                      <a-input v-model:value="row.value" placeholder="字段值" size="small" @change="syncFormBodyToStep" />
                      <a-button type="text" danger size="small" @click="removeFormBodyRow(idx)">
                        <MinusCircleOutlined />
                      </a-button>
                    </div>
                  </div>

                  <div v-else-if="currentBodyType === 'raw'" class="json-body-box">
                    <a-textarea
                      v-model:value="rawBodyText"
                      :rows="8"
                      class="json-textarea"
                      placeholder="输入原始文本请求体"
                      @change="syncRawBodyToStep"
                    />
                  </div>

                  <div v-else class="kv-empty">该请求不携带请求体 (None)</div>
                </a-tab-pane>

                <a-tab-pane key="headers" :tab="`请求头 (${headerRows.length})`">
                  <div class="kv-section">
                    <div class="kv-header">
                      <span>HTTP 请求头 (Headers)</span>
                      <a-button type="link" size="small" @click="addHeaderRow">+ 添加请求头</a-button>
                    </div>
                    <div v-if="!headerRows.length" class="kv-empty">暂无自定义请求头</div>
                    <div v-for="(row, idx) in headerRows" :key="idx" class="kv-row">
                      <a-input v-model:value="row.key" placeholder="Header 名称 (如 Authorization)" size="small" @change="syncHeadersToStep" />
                      <a-input v-model:value="row.value" placeholder="Header 值（支持 {{token}}）" size="small" @change="syncHeadersToStep" />
                      <a-button type="text" danger size="small" @click="removeHeaderRow(idx)">
                        <MinusCircleOutlined />
                      </a-button>
                    </div>
                  </div>
                </a-tab-pane>

                <a-tab-pane key="auth" tab="鉴权">
                  <div class="auth-section">
                    <label class="field-label">快捷注入 Bearer Token 请求头</label>
                    <div class="url-input-group">
                      <a-input
                        v-model:value="bearerTokenInput"
                        placeholder="输入 Token 或 {{token}} 引用变量"
                        size="small"
                      />
                      <a-button size="small" type="primary" @click="applyBearerTokenToHeader">
                        应用到 Authorization 头
                      </a-button>
                    </div>
                    <p class="json-helper-note" style="margin-top: 8px">
                      可使用敏感环境变量或前序登录步骤提取的输出（如 <code>Bearer {{ formatVarToken('token') }}</code>）。
                    </p>
                  </div>
                </a-tab-pane>

                <a-tab-pane key="advanced" tab="高级">
                  <div class="auth-section">
                    <label class="field-label">超时时间（秒）</label>
                    <a-input-number v-model:value="currentStep.timeout" :min="1" :max="120" size="small" @change="markDirty" />
                  </div>
                </a-tab-pane>
              </a-tabs>
            </a-tab-pane>

            <!-- 校验 (Assertions) Tab -->
            <a-tab-pane key="assertions" :tab="`校验 (${(currentStep.assertions || []).length})`">
              <div class="assertions-section">
                <div class="kv-header">
                  <span>响应断言校验规则</span>
                  <a-space size="small">
                    <a-button size="small" @click="addStatus200Assertion">+ 状态码 200</a-button>
                    <a-button type="primary" size="small" @click="addAssertionRow">+ 添加校验</a-button>
                  </a-space>
                </div>

                <div v-if="!(currentStep.assertions || []).length" class="kv-empty">
                  暂无校验规则，可点击上方按钮或在右侧响应面板中点选字段快速生成。
                </div>

                <div
                  v-for="(assertItem, aIdx) in currentStep.assertions"
                  :key="aIdx"
                  class="assertion-row"
                >
                  <a-select v-model:value="assertItem.target" size="small" style="width: 120px" @change="markDirty">
                    <a-select-option value="status_code">状态码</a-select-option>
                    <a-select-option value="jsonpath">JSONPath</a-select-option>
                    <a-select-option value="body_contains">响应体文本</a-select-option>
                    <a-select-option value="response_header">响应头</a-select-option>
                  </a-select>
                  <a-input
                    v-if="assertItem.target === 'jsonpath' || assertItem.target === 'response_header'"
                    v-model:value="assertItem.expression"
                    :placeholder="assertItem.target === 'jsonpath' ? '$.code 或 $.data.id' : 'Content-Type'"
                    size="small"
                    style="width: 160px"
                    @change="markDirty"
                  />
                  <a-select v-model:value="assertItem.operator" size="small" style="width: 110px" @change="markDirty">
                    <a-select-option value="eq">等于</a-select-option>
                    <a-select-option value="ne">不等于</a-select-option>
                    <a-select-option value="contains">包含</a-select-option>
                    <a-select-option value="not_empty">不为空</a-select-option>
                  </a-select>
                  <a-input
                    v-if="assertItem.operator !== 'not_empty'"
                    v-model:value="assertItem.expected"
                    placeholder="期望值"
                    size="small"
                    style="flex: 1"
                    @change="markDirty"
                  />
                  <a-button type="text" danger size="small" @click="removeAssertionRow(aIdx)">
                    <MinusCircleOutlined />
                  </a-button>
                </div>
              </div>
            </a-tab-pane>

            <!-- 提取变量 (Extractions) Tab -->
            <a-tab-pane key="extractions" :tab="`提取变量 (${(currentStep.extractions || []).length})`">
              <div class="assertions-section">
                <div class="kv-header">
                  <span>提取响应字段供后续步骤引用</span>
                  <a-button type="primary" size="small" @click="addExtractionRow">+ 添加提取变量</a-button>
                </div>
                <div v-if="!(currentStep.extractions || []).length" class="kv-empty">
                  暂无提取变量。可在右侧调试响应中一键点选字段提取为变量。
                </div>
                <div
                  v-for="(extItem, eIdx) in currentStep.extractions"
                  :key="eIdx"
                  class="assertion-row"
                >
                  <a-input
                    v-model:value="extItem.variable"
                    placeholder="变量名 (如 token)"
                    size="small"
                    style="width: 140px"
                    @change="markDirty"
                  />
                  <a-select v-model:value="extItem.type" size="small" style="width: 110px" @change="markDirty">
                    <a-select-option value="jsonpath">JSONPath</a-select-option>
                    <a-select-option value="header">响应头</a-select-option>
                    <a-select-option value="regex">正则</a-select-option>
                  </a-select>
                  <a-input
                    v-model:value="extItem.expression"
                    placeholder="表达式 (如 $.data.token)"
                    size="small"
                    style="flex: 1"
                    @change="markDirty"
                  />
                  <a-button type="text" danger size="small" @click="removeExtractionRow(eIdx)">
                    <MinusCircleOutlined />
                  </a-button>
                </div>
              </div>
            </a-tab-pane>
          </a-tabs>

          <!-- 底部环境说明与配置统计 -->
          <div class="inspector-footer-meta">
            <div class="config-override-note">
              ▸ 本步骤配置了 {{ Object.keys(currentStep.headers || {}).length }} 项请求头 · {{ (currentStep.assertions || []).length }} 条校验
            </div>
            <div class="env-execution-note">
              {{ currentEnvName || '未选择环境' }} · 调试将发送真实请求
            </div>
          </div>
        </div>
      </section>

      <section v-else class="step-inspector-empty">
        <h3>从第一个接口步骤开始</h3>
        <p>从接口库选择已有接口或新建请求，按顺序编排业务链路并串联参数与断言。</p>
        <a-space>
          <a-button type="primary" @click="openAddStepDrawer">从接口库选择</a-button>
          <a-button @click="addBlankStep">新建空白请求</a-button>
        </a-space>
      </section>

      <!-- 第三栏：实时响应与字段快速点选面板 (Response & Field Picker) -->
      <aside class="step-response-pane">
        <template v-if="currentStep && stepDebugResults[currentStep.uid]">
          <div class="response-status-header">
            <div class="status-badges">
              <a-tag :color="currentDebugResult?.status_code && currentDebugResult.status_code < 400 ? 'success' : 'error'">
                HTTP {{ currentDebugResult?.status_code || 'ERR' }}
              </a-tag>
              <span class="elapsed-tag">{{ currentDebugResult?.elapsed_ms ?? 0 }} ms</span>
              <a-tag :color="currentDebugResult?.passed ? 'green' : 'red'">
                {{ currentDebugResult?.passed ? '校验通过' : '存在失败校验' }}
              </a-tag>
            </div>
          </div>

          <a-tabs v-model:activeKey="responseTab" size="small" class="response-tabs">
            <a-tab-pane key="fields" tab="点选字段 (快速校验/取值)">
              <div v-if="flattenedResponseFields.length" class="response-fields-list">
                <div
                  v-for="field in flattenedResponseFields"
                  :key="field.path"
                  class="response-field-item"
                >
                  <div class="field-main">
                    <code class="field-path">{{ field.path }}</code>
                    <span class="field-val" :title="field.displayValue">{{ field.displayValue }}</span>
                  </div>
                  <div class="field-actions">
                    <a-button type="link" size="small" @click="quickAddAssertionFromField(field)">
                      + 校验
                    </a-button>
                    <a-button type="link" size="small" @click="quickAddExtractionFromField(field)">
                      + 取值
                    </a-button>
                  </div>
                </div>
              </div>
              <pre v-else class="response-raw-pre">{{ currentDebugResult?.body || '（空响应体）' }}</pre>
            </a-tab-pane>

            <a-tab-pane key="raw" tab="原始响应体">
              <pre class="response-raw-pre">{{ formattedResponseBody }}</pre>
            </a-tab-pane>

            <a-tab-pane key="assertions" :tab="`校验结果 (${(currentDebugResult?.assertionDetails || []).length})`">
              <div v-if="!(currentDebugResult?.assertionDetails || []).length" class="kv-empty">
                当前步骤未配置校验规则
              </div>
              <div
                v-for="(ar, idx) in currentDebugResult?.assertionDetails || []"
                :key="idx"
                class="assertion-result-item"
                :class="ar.passed ? 'is-pass' : 'is-fail'"
              >
                <span class="ar-badge">{{ ar.passed ? 'PASS' : 'FAIL' }}</span>
                <span class="ar-text">{{ ar.label }}（实际值: <code>{{ ar.actual }}</code>）</span>
              </div>
            </a-tab-pane>
          </a-tabs>
        </template>

        <div v-else class="response-empty-hint">
          发送请求后，在这里查看响应，选择字段并添加校验。
        </div>
      </aside>
    </div>

    <!-- 添加步骤抽屉 (从接口库选择 / 新建空白请求) -->
    <a-drawer
      v-model:open="addStepDrawerOpen"
      title="添加步骤"
      :width="620"
    >
      <div class="add-step-toolbar">
        <a-input-search
          v-model:value="librarySearchKeyword"
          placeholder="搜索接口名称或编号"
          allow-clear
          style="flex: 1"
        />
        <a-button @click="addBlankStepFromDrawer">+ 新建空白请求</a-button>
      </div>

      <a-table
        :data-source="filteredLibraryCases"
        :columns="libraryColumns"
        row-key="id"
        size="small"
        :pagination="{ pageSize: 12 }"
        :row-selection="{
          selectedRowKeys: selectedLibraryIds,
          onChange: (keys: (string | number)[]) => (selectedLibraryIds = keys as number[]),
        }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <div>
              <strong>{{ record.name }}</strong>
              <div class="library-sub-meta">
                <code>{{ record.case_code }}</code>
              </div>
            </div>
          </template>
        </template>
      </a-table>

      <template #footer>
        <div class="drawer-footer-bar">
          <span>已选 {{ selectedLibraryIds.length }} 个接口</span>
          <a-space>
            <a-button @click="addStepDrawerOpen = false">取消</a-button>
            <a-button
              type="primary"
              :disabled="!selectedLibraryIds.length"
              :loading="addingLibrarySteps"
              @click="confirmAddSelectedLibraryCases"
            >
              添加 {{ selectedLibraryIds.length || '' }} 个接口步骤
            </a-button>
          </a-space>
        </div>
      </template>
    </a-drawer>

    <!-- 打开已有场景用例弹窗 -->
    <a-modal
      v-model:open="loadScenarioModalOpen"
      title="选择已有场景用例"
      :footer="null"
      :width="560"
    >
      <div v-if="!scenarioRecordsList.length" class="kv-empty">
        当前项目暂无已保存的自动化场景
      </div>
      <div v-else class="scenario-Load-list">
        <div
          v-for="sc in scenarioRecordsList"
          :key="sc.id"
          class="scenario-load-row"
          @click="loadScenarioRecord(sc)"
        >
          <div>
            <strong>{{ sc.name }}</strong>
            <small style="margin-left: 8px; color: var(--c-text-tertiary)">{{ sc.scenario_code }} · {{ sc.step_count }} 步</small>
          </div>
          <a-button type="link" size="small">加载编排</a-button>
        </div>
      </div>
    </a-modal>

    <!-- 环境变量预览弹窗 -->
    <a-modal
      v-model:open="envModalOpen"
      :title="`环境变量 - ${currentEnvName || '未选择环境'}`"
      :footer="null"
      :width="520"
    >
      <div v-if="!selectedEnv" class="kv-empty">
        请先在顶部下拉框中选择一个运行环境
      </div>
      <div v-else class="env-vars-preview">
        <div class="env-base-url">
          <strong>前置地址 (Base URL)：</strong>
          <code>{{ selectedEnvBaseUrl || '未设置' }}</code>
        </div>
        <div v-if="!currentEnvVariables.length" class="kv-empty">该环境未配置自定义变量</div>
        <div v-for="ev in currentEnvVariables" :key="ev.key" class="env-var-row">
          <code>{{ formatVarToken(ev.key) }}</code>
          <span>{{ ev.value }}</span>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import draggable from 'vuedraggable'
import { message } from 'ant-design-vue'
import {
  DownOutlined,
  MinusCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons-vue'
import {
  apiScenarioApi,
  caseApi,
  type ApiScenarioRecord,
  type CaseDetailItem,
  type CaseSummaryItem,
  type EnvironmentItem,
} from '@/api'
import {
  parseStepFromCase,
  type ApiScenarioStep,
} from '@/types/apiScenario'

export interface OrchestratorStep extends ApiScenarioStep {
  uid: string
  sourceCaseId?: number
}

interface StepDebugResult {
  status_code: number
  elapsed_ms: number
  body: string
  body_json: unknown
  headers: Record<string, string>
  passed: boolean
  assertionDetails: Array<{ label: string; passed: boolean; actual: string }>
}

const props = defineProps<{
  projectId: number | null
  moduleId: number | null
  canModify: boolean
  cases: CaseSummaryItem[]
  scenarios?: ApiScenarioRecord[]
  environments: EnvironmentItem[]
  initialSteps?: ApiScenarioStep[] | null
  initialScenario?: ApiScenarioRecord | null
  initialCase?: CaseDetailItem | null
}>()

const emit = defineEmits<{
  exit: []
  saved: [caseId: number]
  runCreated: [runId: number]
}>()

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']

let uidCounter = 1
function nextUid() {
  return `step_${Date.now()}_${uidCounter++}`
}

function formatVarToken(name: string) {
  return `{{${name}}}`
}

const scenarioName = ref('登录场景回归')
const scenarioDescription = ref('')
const editingCaseId = ref<number | null>(null)
const selectedEnvId = ref<number | undefined>(undefined)
const isDirty = ref(false)
const saving = ref(false)
const runningScenario = ref(false)
const debugging = ref(false)

const steps = ref<OrchestratorStep[]>([])
const selectedStepUid = ref<string | null>(null)
const inspectorMainTab = ref<'request' | 'assertions' | 'extractions'>('request')
const requestSubTab = ref<'params' | 'body' | 'headers' | 'auth' | 'advanced'>('body')
const jsonEditMode = ref<'raw' | 'fields' | 'preview'>('raw')
const responseTab = ref<'fields' | 'raw' | 'assertions'>('fields')

const queryParamRows = ref<Array<{ key: string; value: string }>>([])
const headerRows = ref<Array<{ key: string; value: string }>>([])
const formBodyRows = ref<Array<{ key: string; value: string }>>([])
const jsonFieldRows = ref<Array<{ key: string; value: string }>>([])
const currentBodyType = ref<'none' | 'json' | 'form' | 'raw'>('json')
const jsonBodyText = ref('{\n  \n}')
const rawBodyText = ref('')
const jsonError = ref('')
const bearerTokenInput = ref('{{token}}')

const stepDebugResults = ref<Record<string, StepDebugResult>>({})
const runtimeVariables = ref<Record<string, string>>({})

const addStepDrawerOpen = ref(false)
const librarySearchKeyword = ref('')
const selectedLibraryIds = ref<number[]>([])
const addingLibrarySteps = ref(false)
const loadScenarioModalOpen = ref(false)
const envModalOpen = ref(false)

const envOptions = computed(() =>
  props.environments.map((env) => ({ label: env.name, value: env.id })),
)

const selectedEnv = computed(() =>
  props.environments.find((env) => env.id === selectedEnvId.value) ?? null,
)

const currentEnvName = computed(() => selectedEnv.value?.name ?? '')

const selectedEnvBaseUrl = computed(() => {
  const raw = (selectedEnv.value as Record<string, unknown> | null)?.base_url
  return typeof raw === 'string' ? raw : ''
})

const currentEnvVariables = computed(() => {
  const vars = (selectedEnv.value as Record<string, unknown> | null)?.variables
  if (!vars || typeof vars !== 'object') return []
  return Object.entries(vars as Record<string, unknown>).map(([key, value]) => ({
    key,
    value: String(value ?? ''),
  }))
})

const currentStepIndex = computed(() =>
  steps.value.findIndex((s) => s.uid === selectedStepUid.value),
)

const currentStep = computed<OrchestratorStep | null>(() =>
  currentStepIndex.value >= 0 ? steps.value[currentStepIndex.value] : null,
)

const currentDebugResult = computed<StepDebugResult | null>(() =>
  currentStep.value ? stepDebugResults.value[currentStep.value.uid] ?? null : null,
)

const availableUpstreamVars = computed(() => {
  const list: Array<{ name: string; stepName: string }> = []
  const idx = currentStepIndex.value
  if (idx <= 0) return list
  for (let i = 0; i < idx; i++) {
    const s = steps.value[i]
    for (const ext of s.extractions || []) {
      if (ext.variable?.trim()) {
        list.push({ name: ext.variable.trim(), stepName: s.name || `步骤 ${i + 1}` })
      }
    }
  }
  return list
})

const filteredLibraryCases = computed(() => {
  const kw = librarySearchKeyword.value.trim().toLowerCase()
  return props.cases.filter((c) => {
    if (c.case_type !== 'api') return false
    if (!kw) return true
    return c.name.toLowerCase().includes(kw) || c.case_code.toLowerCase().includes(kw)
  })
})

const scenarioRecordsList = computed(() => props.scenarios || [])

const libraryColumns = [
  { title: '接口名称', key: 'name', dataIndex: 'name' },
]

function draftStorageKey() {
  return `atp_api_scenario_draft_${props.projectId || 'default'}`
}

function saveDraftToStorage() {
  try {
    const snapshot = {
      editingCaseId: editingCaseId.value,
      scenarioName: scenarioName.value,
      scenarioDescription: scenarioDescription.value,
      selectedEnvId: selectedEnvId.value,
      selectedStepUid: selectedStepUid.value,
      isDirty: isDirty.value,
      steps: steps.value,
    }
    window.localStorage.setItem(draftStorageKey(), JSON.stringify(snapshot))
  } catch {}
}

function restoreDraftFromStorage(): boolean {
  try {
    const raw = window.localStorage.getItem(draftStorageKey())
    if (!raw) return false
    const parsed = JSON.parse(raw)
    if (!parsed || !Array.isArray(parsed.steps) || !parsed.steps.length) return false
    editingCaseId.value = parsed.editingCaseId ?? null
    scenarioName.value = parsed.scenarioName || '登录场景回归'
    scenarioDescription.value = parsed.scenarioDescription || ''
    if (parsed.selectedEnvId) selectedEnvId.value = parsed.selectedEnvId
    steps.value = parsed.steps
    const targetUid = parsed.selectedStepUid && steps.value.some((s) => s.uid === parsed.selectedStepUid)
      ? parsed.selectedStepUid
      : steps.value[0]?.uid ?? null
    selectedStepUid.value = targetUid
    loadStepIntoEditor(steps.value.find((s) => s.uid === targetUid) ?? null)
    isDirty.value = Boolean(parsed.isDirty)
    return true
  } catch {
    return false
  }
}

function markDirty() {
  isDirty.value = true
  saveDraftToStorage()
}

function toOrchestratorStep(raw: ApiScenarioStep, sourceCaseId?: number): OrchestratorStep {
  return {
    uid: nextUid(),
    sourceCaseId,
    name: raw.name || '未命名步骤',
    method: (raw.method || 'GET').toUpperCase(),
    url: raw.url || '',
    headers: { ...(raw.headers || {}) },
    params: { ...(raw.params || {}) },
    cookies: { ...(raw.cookies || {}) },
    body_type: (raw.body_type as any) || 'none',
    body: raw.body ?? '',
    assertions: Array.isArray(raw.assertions) && raw.assertions.length
      ? raw.assertions.map((a) => ({ ...a }))
      : [{ target: 'status_code', operator: 'eq', expected: '200' }],
    extractions: Array.isArray(raw.extractions) ? raw.extractions.map((e) => ({ ...e })) : [],
    timeout: raw.timeout || 30,
  }
}

function loadStepIntoEditor(step: OrchestratorStep | null) {
  if (!step) return
  queryParamRows.value = Object.entries(step.params || {}).map(([key, value]) => ({
    key,
    value: String(value ?? ''),
  }))
  headerRows.value = Object.entries(step.headers || {}).map(([key, value]) => ({
    key,
    value: String(value ?? ''),
  }))
  const bt = step.body_type || 'none'
  currentBodyType.value = bt === 'json' || bt === 'form' || bt === 'raw' ? bt : 'none'
  jsonError.value = ''

  if (bt === 'json') {
    if (typeof step.body === 'string') {
      jsonBodyText.value = step.body || '{\n  \n}'
    } else if (step.body && typeof step.body === 'object') {
      jsonBodyText.value = JSON.stringify(step.body, null, 2)
    } else {
      jsonBodyText.value = '{\n  \n}'
    }
    requestSubTab.value = 'body'
  } else if (bt === 'form') {
    const obj = typeof step.body === 'object' && step.body ? (step.body as Record<string, unknown>) : {}
    formBodyRows.value = Object.entries(obj).map(([key, value]) => ({ key, value: String(value ?? '') }))
    requestSubTab.value = 'body'
  } else if (bt === 'raw') {
    rawBodyText.value = typeof step.body === 'string' ? step.body : JSON.stringify(step.body ?? '')
    requestSubTab.value = 'body'
  } else {
    requestSubTab.value = queryParamRows.value.length ? 'params' : 'body'
  }
}

function selectStep(uid: string) {
  selectedStepUid.value = uid
  loadStepIntoEditor(steps.value.find((s) => s.uid === uid) ?? null)
}

function loadScenarioRecord(sc: ApiScenarioRecord) {
  editingCaseId.value = sc.id
  scenarioName.value = sc.name
  scenarioDescription.value = sc.description || ''
  if (sc.env_id) selectedEnvId.value = sc.env_id
  const rawSteps = Array.isArray(sc.steps) ? (sc.steps as unknown as ApiScenarioStep[]) : []
  steps.value = rawSteps.map((s) => toOrchestratorStep(s))
  selectedStepUid.value = steps.value[0]?.uid ?? null
  loadStepIntoEditor(steps.value[0] ?? null)
  isDirty.value = false
  loadScenarioModalOpen.value = false
  saveDraftToStorage()
}

watch(
  () => [props.initialSteps, props.initialScenario, props.initialCase] as const,
  ([initSteps, initScenario, initCase]) => {
    if (initScenario) {
      loadScenarioRecord(initScenario)
      return
    }
    if (initCase) {
      editingCaseId.value = null
      scenarioName.value = initCase.name
      scenarioDescription.value = initCase.description || ''
      const rawSteps = Array.isArray((initCase.config as any)?.steps)
        ? ((initCase.config as any).steps as ApiScenarioStep[])
        : [parseStepFromCase(initCase)]
      steps.value = rawSteps.map((s) => toOrchestratorStep(s, initCase.id))
      selectedStepUid.value = steps.value[0]?.uid ?? null
      loadStepIntoEditor(steps.value[0] ?? null)
      isDirty.value = true
      saveDraftToStorage()
      return
    }
    if (initSteps && initSteps.length) {
      editingCaseId.value = null
      steps.value = initSteps.map((s) => toOrchestratorStep(s))
      const names = steps.value.map((s) => s.name).filter(Boolean)
      scenarioName.value = `场景编排 - ${names.slice(0, 2).join(' → ')}${names.length > 2 ? ` 等${names.length}步` : ''}`
      selectedStepUid.value = steps.value[0]?.uid ?? null
      loadStepIntoEditor(steps.value[0] ?? null)
      isDirty.value = true
      saveDraftToStorage()
    } else if (!steps.value.length) {
      if (restoreDraftFromStorage()) {
        return
      }
      if (props.scenarios && props.scenarios.length) {
        loadScenarioRecord(props.scenarios[0])
      } else {
        addBlankStep()
        isDirty.value = false
        saveDraftToStorage()
      }
    }
  },
  { immediate: true },
)

watch(
  () => [scenarioName.value, scenarioDescription.value, selectedStepUid.value],
  () => {
    if (steps.value.length) {
      saveDraftToStorage()
    }
  },
)

watch(
  () => props.environments,
  (envs) => {
    if (!selectedEnvId.value && envs.length) {
      selectedEnvId.value = envs[0].id
    }
  },
  { immediate: true },
)

function addBlankStep() {
  const newStep = toOrchestratorStep({
    name: `请求步骤 ${steps.value.length + 1}`,
    method: 'POST',
    url: '',
    headers: { 'Content-Type': 'application/json' },
    params: {},
    body_type: 'json',
    body: { pageNo: 1, pageSize: 10 },
    assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
    extractions: [],
  })
  steps.value.push(newStep)
  selectStep(newStep.uid)
  markDirty()
}

function addBlankStepFromDrawer() {
  addStepDrawerOpen.value = false
  addBlankStep()
}

function openAddStepDrawer() {
  selectedLibraryIds.value = []
  librarySearchKeyword.value = ''
  addStepDrawerOpen.value = true
}

async function confirmAddSelectedLibraryCases() {
  if (!selectedLibraryIds.value.length) return
  addingLibrarySteps.value = true
  try {
    let lastUid: string | null = null
    for (const id of selectedLibraryIds.value) {
      try {
        const detail = await caseApi.get(id)
        const parsed = parseStepFromCase(detail)
        const step = toOrchestratorStep(parsed, id)
        steps.value.push(step)
        lastUid = step.uid
      } catch {
        const summary = props.cases.find((c) => c.id === id)
        if (summary) {
          const step = toOrchestratorStep({ name: summary.name, method: 'GET', url: '' }, id)
          steps.value.push(step)
          lastUid = step.uid
        }
      }
    }
    if (lastUid) {
      selectStep(lastUid)
    }
    addStepDrawerOpen.value = false
    markDirty()
  } finally {
    addingLibrarySteps.value = false
  }
}

function handleStepAction(action: string, index: number) {
  const target = steps.value[index]
  if (!target) return
  if (action === 'duplicate') {
    const clone: OrchestratorStep = JSON.parse(JSON.stringify(target))
    clone.uid = nextUid()
    clone.name = `${target.name} (副本)`
    steps.value.splice(index + 1, 0, clone)
    selectStep(clone.uid)
    markDirty()
  } else if (action === 'up' && index > 0) {
    const tmp = steps.value[index - 1]
    steps.value[index - 1] = target
    steps.value[index] = tmp
    markDirty()
  } else if (action === 'down' && index < steps.value.length - 1) {
    const tmp = steps.value[index + 1]
    steps.value[index + 1] = target
    steps.value[index] = tmp
    markDirty()
  } else if (action === 'remove') {
    steps.value.splice(index, 1)
    if (selectedStepUid.value === target.uid) {
      selectStep(steps.value[0]?.uid ?? '')
    }
    markDirty()
  }
}

function addQueryParamRow() {
  queryParamRows.value.push({ key: '', value: '' })
}
function removeQueryParamRow(idx: number) {
  queryParamRows.value.splice(idx, 1)
  syncQueryParamsToStep()
}
function syncQueryParamsToStep() {
  if (!currentStep.value) return
  const map: Record<string, string> = {}
  for (const r of queryParamRows.value) {
    if (r.key.trim()) map[r.key.trim()] = r.value
  }
  currentStep.value.params = map
  markDirty()
}

function addHeaderRow() {
  headerRows.value.push({ key: '', value: '' })
}
function removeHeaderRow(idx: number) {
  headerRows.value.splice(idx, 1)
  syncHeadersToStep()
}
function syncHeadersToStep() {
  if (!currentStep.value) return
  const map: Record<string, string> = {}
  for (const r of headerRows.value) {
    if (r.key.trim()) map[r.key.trim()] = r.value
  }
  currentStep.value.headers = map
  markDirty()
}

function handleBodyTypeChange() {
  if (!currentStep.value) return
  currentStep.value.body_type = currentBodyType.value
  if (currentBodyType.value === 'none') {
    currentStep.value.body = ''
  } else if (currentBodyType.value === 'json') {
    syncJsonTextToStep()
  } else if (currentBodyType.value === 'form') {
    syncFormBodyToStep()
  } else {
    syncRawBodyToStep()
  }
  markDirty()
}

function syncJsonTextToStep() {
  if (!currentStep.value) return
  try {
    const parsed = JSON.parse(jsonBodyText.value)
    jsonError.value = ''
    currentStep.value.body = parsed
  } catch (e: any) {
    jsonError.value = `JSON 格式有误: ${e?.message || '请检查括号或引号'}`
    currentStep.value.body = jsonBodyText.value
  }
  markDirty()
}

function formatCurrentJsonBody() {
  try {
    const parsed = JSON.parse(jsonBodyText.value)
    jsonBodyText.value = JSON.stringify(parsed, null, 2)
    jsonError.value = ''
    if (currentStep.value) currentStep.value.body = parsed
  } catch {
    message.warning('当前 JSON 格式有误，无法格式化')
  }
}

function switchToJsonFieldsMode() {
  try {
    const parsed = JSON.parse(jsonBodyText.value)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      jsonFieldRows.value = Object.entries(parsed).map(([key, value]) => ({
        key,
        value: typeof value === 'string' ? value : JSON.stringify(value),
      }))
    }
  } catch {
    // keep existing rows
  }
  jsonEditMode.value = 'fields'
}

function addJsonFieldRow() {
  jsonFieldRows.value.push({ key: '', value: '' })
}
function removeJsonFieldRow(idx: number) {
  jsonFieldRows.value.splice(idx, 1)
  syncJsonFieldsToStep()
}
function setJsonFieldVar(idx: number, varName: string) {
  if (varName === '__empty') return
  if (jsonFieldRows.value[idx]) {
    jsonFieldRows.value[idx].value = `{{${varName}}}`
    syncJsonFieldsToStep()
  }
}
function syncJsonFieldsToStep() {
  if (!currentStep.value) return
  const obj: Record<string, unknown> = {}
  for (const r of jsonFieldRows.value) {
    if (!r.key.trim()) continue
    const raw = r.value.trim()
    if (raw === 'true') obj[r.key.trim()] = true
    else if (raw === 'false') obj[r.key.trim()] = false
    else if (raw === 'null') obj[r.key.trim()] = null
    else if (/^-?\d+(\.\d+)?$/.test(raw)) obj[r.key.trim()] = Number(raw)
    else obj[r.key.trim()] = r.value
  }
  jsonBodyText.value = JSON.stringify(obj, null, 2)
  currentStep.value.body = obj
  markDirty()
}

function addFormBodyRow() {
  formBodyRows.value.push({ key: '', value: '' })
}
function removeFormBodyRow(idx: number) {
  formBodyRows.value.splice(idx, 1)
  syncFormBodyToStep()
}
function syncFormBodyToStep() {
  if (!currentStep.value) return
  const map: Record<string, string> = {}
  for (const r of formBodyRows.value) {
    if (r.key.trim()) map[r.key.trim()] = r.value
  }
  currentStep.value.body = map
  markDirty()
}

function syncRawBodyToStep() {
  if (!currentStep.value) return
  currentStep.value.body = rawBodyText.value
  markDirty()
}

function applyBearerTokenToHeader() {
  if (!currentStep.value) return
  const tokenVal = bearerTokenInput.value.trim()
  if (!tokenVal) return
  const fullVal = tokenVal.toLowerCase().startsWith('bearer ') ? tokenVal : `Bearer ${tokenVal}`
  const existing = headerRows.value.find((r) => r.key.toLowerCase() === 'authorization')
  if (existing) {
    existing.value = fullVal
  } else {
    headerRows.value.push({ key: 'Authorization', value: fullVal })
  }
  syncHeadersToStep()
  requestSubTab.value = 'headers'
  message.success('已写入 Authorization 请求头')
}

function insertVariableIntoUrl(varName: string) {
  if (varName === '__none' || !currentStep.value) return
  currentStep.value.url = `${currentStep.value.url || ''}{{${varName}}}`
  markDirty()
}

function addStatus200Assertion() {
  if (!currentStep.value) return
  if (!currentStep.value.assertions) currentStep.value.assertions = []
  currentStep.value.assertions.push({ target: 'status_code', operator: 'eq', expected: '200' })
  markDirty()
}

function addAssertionRow() {
  if (!currentStep.value) return
  if (!currentStep.value.assertions) currentStep.value.assertions = []
  currentStep.value.assertions.push({
    target: 'jsonpath',
    expression: '$.code',
    operator: 'eq',
    expected: '200',
  })
  markDirty()
}

function removeAssertionRow(idx: number) {
  currentStep.value?.assertions?.splice(idx, 1)
  markDirty()
}

function addExtractionRow() {
  if (!currentStep.value) return
  if (!currentStep.value.extractions) currentStep.value.extractions = []
  currentStep.value.extractions.push({
    variable: '',
    type: 'jsonpath',
    expression: '$.data.token',
  })
  markDirty()
}

function removeExtractionRow(idx: number) {
  currentStep.value?.extractions?.splice(idx, 1)
  markDirty()
}

function interpolateString(input: string, vars: Record<string, string>): string {
  return input.replace(/\{\{([a-zA-Z0-9_\-\.]+)\}\}/g, (_match, key) => {
    if (key in vars) return vars[key]
    return _match
  })
}

function buildEffectiveVarMap(): Record<string, string> {
  const map: Record<string, string> = {}
  for (const ev of currentEnvVariables.value) {
    map[ev.key] = ev.value
  }
  Object.assign(map, runtimeVariables.value)
  return map
}

const previewInterpolatedBody = computed(() => {
  const vars = buildEffectiveVarMap()
  return interpolateString(jsonBodyText.value, vars)
})

function resolveJsonPathValue(obj: unknown, expr: string): unknown {
  if (!obj || typeof obj !== 'object') return undefined
  const clean = expr.replace(/^\$\.?/, '')
  if (!clean) return obj
  const parts = clean.split('.')
  let cur: any = obj
  for (const p of parts) {
    if (cur == null) return undefined
    const arrMatch = p.match(/^([^\[]+)\[(\d+)\]$/)
    const rootArrMatch = p.match(/^\[(\d+)\]$/)
    if (arrMatch) {
      cur = cur[arrMatch[1]]?.[Number(arrMatch[2])]
    } else if (rootArrMatch) {
      cur = cur[Number(rootArrMatch[1])]
    } else {
      cur = cur[p]
    }
  }
  return cur
}

function evaluateStepAssertions(
  step: OrchestratorStep,
  res: { status_code: number; body: string; body_json: unknown; headers: Record<string, string> },
) {
  const details: Array<{ label: string; passed: boolean; actual: string }> = []
  let allPassed = true
  for (const a of step.assertions || []) {
    let actualVal = ''
    let passed = false
    const expected = String(a.expected ?? '')
    if (a.target === 'status_code') {
      actualVal = String(res.status_code)
    } else if (a.target === 'jsonpath') {
      const v = resolveJsonPathValue(res.body_json, a.expression || '')
      actualVal = v === undefined ? 'undefined' : typeof v === 'object' ? JSON.stringify(v) : String(v)
    } else if (a.target === 'response_header') {
      const hk = (a.expression || '').toLowerCase()
      const found = Object.entries(res.headers || {}).find(([k]) => k.toLowerCase() === hk)
      actualVal = found ? String(found[1]) : ''
    } else {
      actualVal = res.body?.slice(0, 120) || ''
    }

    if (a.operator === 'eq') passed = actualVal === expected
    else if (a.operator === 'ne') passed = actualVal !== expected
    else if (a.operator === 'contains') passed = actualVal.includes(expected)
    else if (a.operator === 'not_empty') passed = actualVal !== '' && actualVal !== 'undefined' && actualVal !== 'null'
    else passed = actualVal === expected

    if (!passed) allPassed = false
    details.push({
      label: `${a.target}${a.expression ? ` (${a.expression})` : ''} ${a.operator} ${expected}`,
      passed,
      actual: actualVal,
    })
  }
  return { allPassed, details }
}

function extractStepVariables(
  step: OrchestratorStep,
  res: { body_json: unknown; headers: Record<string, string> },
) {
  for (const ext of step.extractions || []) {
    const varName = ext.variable?.trim()
    if (!varName || !ext.expression?.trim()) continue
    if (ext.type === 'header') {
      const hk = ext.expression.trim().toLowerCase()
      const found = Object.entries(res.headers || {}).find(([k]) => k.toLowerCase() === hk)
      if (found) runtimeVariables.value[varName] = String(found[1])
    } else {
      const val = resolveJsonPathValue(res.body_json, ext.expression.trim())
      if (val !== undefined && val !== null) {
        runtimeVariables.value[varName] = typeof val === 'object' ? JSON.stringify(val) : String(val)
      }
    }
  }
}

async function executeSingleStepDebug(step: OrchestratorStep): Promise<boolean> {
  const vars = buildEffectiveVarMap()
  let rawUrl = interpolateString(step.url || '', vars).trim()
  if (!rawUrl) {
    message.warning(`步骤【${step.name}】缺少请求地址`)
    return false
  }
  if (rawUrl.startsWith('/') && selectedEnvBaseUrl.value) {
    rawUrl = `${selectedEnvBaseUrl.value.replace(/\/+$/, '')}${rawUrl}`
  }

  const headers: Record<string, string> = {}
  for (const [k, v] of Object.entries(step.headers || {})) {
    headers[k] = interpolateString(String(v), vars)
  }
  const params: Record<string, string> = {}
  for (const [k, v] of Object.entries(step.params || {})) {
    params[k] = interpolateString(String(v), vars)
  }

  let bodyPayload: unknown = step.body
  if (typeof step.body === 'string') {
    bodyPayload = interpolateString(step.body, vars)
  } else if (step.body && typeof step.body === 'object') {
    const interpolatedJson = interpolateString(JSON.stringify(step.body), vars)
    try {
      bodyPayload = JSON.parse(interpolatedJson)
    } catch {
      bodyPayload = interpolatedJson
    }
  }

  const res = await caseApi.previewRequest(props.projectId || 1, {
    method: (step.method || 'GET').toUpperCase(),
    url: rawUrl,
    headers,
    params,
    cookies: step.cookies || {},
    body_type: String(step.body_type || 'none'),
    body: bodyPayload,
    multipart: [],
    auth: { type: 'none' },
    timeout: step.timeout || 30,
  })

  let parsedBodyJson: unknown = null
  if (res.body) {
    try {
      parsedBodyJson = JSON.parse(res.body)
    } catch {
      parsedBodyJson = null
    }
  }

  const evalPayload = {
    status_code: res.status_code,
    body: res.body,
    body_json: parsedBodyJson,
    headers: res.headers || {},
  }

  const { allPassed, details } = evaluateStepAssertions(step, evalPayload)
  extractStepVariables(step, evalPayload)

  stepDebugResults.value[step.uid] = {
    status_code: res.status_code,
    elapsed_ms: res.duration_ms,
    body: res.body,
    body_json: parsedBodyJson,
    headers: res.headers || {},
    passed: allPassed && res.status_code > 0 && res.status_code < 400,
    assertionDetails: details,
  }
  return stepDebugResults.value[step.uid].passed
}

async function debugCurrentStep(mode: 'single' | 'through') {
  if (!currentStep.value) return
  debugging.value = true
  try {
    if (mode === 'through') {
      const targetIdx = currentStepIndex.value
      for (let i = 0; i <= targetIdx; i++) {
        const s = steps.value[i]
        selectStep(s.uid)
        await executeSingleStepDebug(s)
      }
      message.success(`已从第 1 步连续执行至步骤 ${targetIdx + 1}`)
    } else {
      await executeSingleStepDebug(currentStep.value)
    }
  } catch (err: any) {
    message.error(`调试请求失败: ${err?.response?.data?.detail || err?.message || '请检查地址或网络'}`)
  } finally {
    debugging.value = false
  }
}

const flattenedResponseFields = computed(() => {
  const json = currentDebugResult.value?.body_json
  if (!json || typeof json !== 'object') return []
  const result: Array<{ path: string; rawValue: unknown; displayValue: string }> = []

  function walk(node: unknown, prefix: string, depth: number) {
    if (depth > 4 || result.length >= 60) return
    if (node === null || typeof node !== 'object') {
      result.push({
        path: prefix,
        rawValue: node,
        displayValue: JSON.stringify(node),
      })
      return
    }
    if (Array.isArray(node)) {
      result.push({
        path: prefix,
        rawValue: node.length,
        displayValue: `Array(${node.length})`,
      })
      if (node.length > 0) {
        walk(node[0], `${prefix}[0]`, depth + 1)
      }
      return
    }
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
      const nextPath = prefix ? `${prefix}.${k}` : `$.${k}`
      if (v !== null && typeof v === 'object') {
        walk(v, nextPath, depth + 1)
      } else {
        result.push({
          path: nextPath,
          rawValue: v,
          displayValue: typeof v === 'string' ? `"${v}"` : String(v),
        })
      }
    }
  }

  walk(json, '$', 0)
  return result.filter((item) => item.path !== '$')
})

const formattedResponseBody = computed(() => {
  const res = currentDebugResult.value
  if (!res) return ''
  if (res.body_json && typeof res.body_json === 'object') {
    return JSON.stringify(res.body_json, null, 2)
  }
  return res.body || ''
})

function quickAddAssertionFromField(field: { path: string; rawValue: unknown }) {
  if (!currentStep.value) return
  if (!currentStep.value.assertions) currentStep.value.assertions = []
  currentStep.value.assertions.push({
    target: 'jsonpath',
    expression: field.path,
    operator: 'eq',
    expected: field.rawValue === null || field.rawValue === undefined ? '' : String(field.rawValue),
  })
  inspectorMainTab.value = 'assertions'
  markDirty()
  message.success(`已添加校验: ${field.path}`)
}

function quickAddExtractionFromField(field: { path: string; rawValue: unknown }) {
  if (!currentStep.value) return
  if (!currentStep.value.extractions) currentStep.value.extractions = []
  const varName = field.path.split('.').pop()?.replace(/\[\d+\]/g, '') || 'extracted_var'
  currentStep.value.extractions.push({
    variable: varName,
    type: 'jsonpath',
    expression: field.path,
  })
  if (field.rawValue !== undefined && field.rawValue !== null) {
    runtimeVariables.value[varName] = String(field.rawValue)
  }
  inspectorMainTab.value = 'extractions'
  markDirty()
  message.success(`已提取变量 {{${varName}}} = ${field.path}`)
}

async function handleSaveScenario(silent = false): Promise<number | null> {
  if (!scenarioName.value.trim()) {
    message.warning('请输入场景名称')
    return null
  }
  if (!steps.value.length) {
    message.warning('请至少添加一个接口步骤')
    return null
  }

  saving.value = true
  try {
    const serializedSteps = steps.value.map((s, idx) => ({
      name: s.name || `步骤 ${idx + 1}`,
      method: (s.method || 'GET').toUpperCase(),
      url: s.url || '/',
      headers: s.headers || {},
      params: s.params || {},
      cookies: s.cookies || {},
      body_type: s.body_type || 'none',
      body: s.body ?? '',
      assertions: s.assertions || [],
      extractions: s.extractions || [],
      depends_on: idx > 0 ? [idx - 1] : [],
      timeout: s.timeout || 30,
      sourceCaseId: s.sourceCaseId,
    }))

    const payload = {
      project_id: props.projectId || 1,
      module_id: props.moduleId,
      name: scenarioName.value.trim(),
      description: scenarioDescription.value.trim(),
      env_id: selectedEnvId.value ?? null,
      steps: serializedSteps,
    }

    if (editingCaseId.value) {
      const updated = await apiScenarioApi.update(editingCaseId.value, payload)
      isDirty.value = false
      saveDraftToStorage()
      if (!silent) message.success('已保存到自动化场景列表')
      emit('saved', updated.id)
      return updated.id
    } else {
      const created = await apiScenarioApi.create(payload)
      editingCaseId.value = created.id
      isDirty.value = false
      saveDraftToStorage()
      if (!silent) message.success(`已保存到自动化场景列表（${created.scenario_code}）`)
      emit('saved', created.id)
      return created.id
    }
  } catch (err: any) {
    message.error(`保存场景失败: ${err?.response?.data?.detail || err?.message || '请检查输入'}`)
    return null
  } finally {
    saving.value = false
  }
}

async function handleRunScenario() {
  if (!steps.value.length) return
  runningScenario.value = true
  try {
    let scenarioId = editingCaseId.value
    if (!scenarioId || isDirty.value) {
      scenarioId = await handleSaveScenario(true)
    }
    const startedAt = performance.now()
    let allPassed = true
    let passedCount = 0
    for (let i = 0; i < steps.value.length; i++) {
      const s = steps.value[i]
      selectStep(s.uid)
      const stepOk = await executeSingleStepDebug(s)
      if (stepOk) {
        passedCount++
      } else {
        allPassed = false
      }
    }
    const durationMs = Math.round(performance.now() - startedAt)
    if (scenarioId) {
      await apiScenarioApi.recordRun(scenarioId, {
        status: allPassed ? 'passed' : 'failed',
        duration_ms: durationMs,
      })
      emit('saved', scenarioId)
    }
    if (allPassed) {
      message.success(`场景执行全部通过（${passedCount}/${steps.value.length} 步，耗时 ${durationMs} ms）`)
    } else {
      message.warning(`场景执行完成：${passedCount}/${steps.value.length} 步通过（耗时 ${durationMs} ms）`)
    }
  } catch (err: any) {
    message.error(`运行场景失败: ${err?.response?.data?.detail || err?.message || '请稍后重试'}`)
  } finally {
    runningScenario.value = false
  }
}

function handleMoreMenu({ key }: { key: string | number }) {
  if (key === 'load_scenario') {
    loadScenarioModalOpen.value = true
  } else if (key === 'new_scenario') {
    editingCaseId.value = null
    scenarioName.value = '新接口自动化场景'
    scenarioDescription.value = ''
    steps.value = []
    stepDebugResults.value = {}
    addBlankStep()
    isDirty.value = false
    saveDraftToStorage()
    runtimeVariables.value = {}
    message.success('已新建空白场景')
  } else if (key === 'clear_debug') {
    stepDebugResults.value = {}
    runtimeVariables.value = {}
    message.info('已清空调试结果')
  }
}
</script>

<style scoped>
.scenario-orchestrator {
  display: flex;
  flex-direction: column;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-height: 700px;
}

/* 顶部场景控制栏 */
.scenario-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: var(--c-bg-elevated);
  border-bottom: 1px solid var(--c-border);
  flex-wrap: wrap;
}

.scenario-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}

.back-btn {
  color: var(--c-text-secondary);
  font-weight: 500;
}

.scenario-name-input {
  width: 240px;
  font-weight: 600;
}

.save-state-badge {
  font-size: 12px;
  color: var(--c-text-tertiary);
  white-space: nowrap;
}
.save-state-badge.is-dirty {
  color: var(--c-warning);
  font-weight: 600;
}

.env-select {
  width: 150px;
}

.env-var-btn {
  padding: 0 4px;
  font-size: 12px;
}

.scenario-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 场景说明栏 */
.scenario-note-bar {
  padding: 6px 16px;
  background: var(--c-bg-subtle);
  border-bottom: 1px solid var(--c-border);
}

.scenario-note-input {
  width: 100%;
  border: none;
  background: transparent;
  color: var(--c-text-secondary);
  font-size: 12px;
  outline: none;
}
.scenario-note-input::placeholder {
  color: var(--c-text-tertiary);
  font-style: italic;
}

/* 三栏工作区 */
.scenario-workspace {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr) 390px;
  flex: 1;
  min-height: 620px;
}

/* 第一栏：步骤流 */
.steps-flow-pane {
  padding: 12px;
  background: var(--c-bg-subtle);
  border-right: 1px solid var(--c-border);
  overflow-y: auto;
}

.flow-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.flow-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text);
}

.add-step-btn {
  padding: 0;
  font-size: 12px;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-card {
  padding: 9px 10px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.step-card:hover {
  border-color: var(--c-primary);
}
.step-card.is-selected {
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
  box-shadow: 0 2px 8px rgba(88, 80, 236, 0.08);
}

.step-card-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.step-drag-handle {
  cursor: grab;
  color: var(--c-text-tertiary);
  font-size: 12px;
  user-select: none;
}

.step-card-title {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.step-card.is-selected .step-card-title {
  color: var(--c-primary);
}

.step-more-btn {
  border: none;
  background: transparent;
  color: var(--c-text-tertiary);
  cursor: pointer;
  padding: 0 4px;
  font-weight: 700;
}

.step-card-meta {
  margin-top: 4px;
  padding-left: 16px;
  font-size: 11px;
  color: var(--c-text-tertiary);
}

.step-card-status {
  margin-top: 6px;
  padding-left: 16px;
}

.steps-empty {
  margin-top: 32px;
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: 12px;
}

/* 第二栏：配置器 */
.step-inspector-pane {
  padding: 16px 20px;
  border-right: 1px solid var(--c-border);
  overflow-y: auto;
  min-width: 0;
}

.step-title-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.step-name-input {
  max-width: 320px;
  font-weight: 600;
}

.step-origin-tag {
  font-size: 12px;
  color: var(--c-text-tertiary);
}

.request-address-grid {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.field-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary);
  margin-bottom: 6px;
}

.method-select {
  width: 100%;
}

.url-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.url-input {
  flex: 1;
  min-width: 0;
}

.var-menu-sub {
  margin-left: 6px;
  font-size: 11px;
  color: var(--c-text-tertiary);
}

.body-type-bar {
  margin-bottom: 12px;
}

.json-sub-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.json-mode-pills {
  display: inline-flex;
  gap: 4px;
  background: var(--c-bg-subtle);
  padding: 2px;
  border-radius: 6px;
  border: 1px solid var(--c-border);
}

.sub-pill {
  border: none;
  background: transparent;
  padding: 3px 10px;
  font-size: 12px;
  border-radius: 4px;
  cursor: pointer;
  color: var(--c-text-secondary);
}
.sub-pill.active {
  background: var(--c-primary);
  color: #fff;
  font-weight: 600;
}

.json-textarea {
  font-family: 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 12.5px;
}

.json-error-tip {
  margin-top: 6px;
  color: var(--c-error);
  font-size: 12px;
}

.json-helper-note {
  margin-top: 8px;
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.json-preview-box {
  padding: 12px;
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  max-height: 280px;
  overflow: auto;
}

.kv-section,
.assertions-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary);
}

.kv-row,
.assertion-row,
.json-field-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kv-empty {
  padding: 24px 12px;
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: 12px;
  background: var(--c-bg-subtle);
  border-radius: 6px;
}

.inspector-footer-meta {
  margin-top: 20px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border-subtle);
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--c-text-tertiary);
}

.step-inspector-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  border-right: 1px solid var(--c-border);
  text-align: center;
}

/* 第三栏：实时响应与字段点选 */
.step-response-pane {
  padding: 14px;
  background: var(--c-bg-elevated);
  overflow-y: auto;
  min-width: 0;
}

.response-empty-hint {
  padding: 24px 8px;
  color: var(--c-text-tertiary);
  font-size: 12.5px;
}

.response-status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.elapsed-tag {
  font-size: 12px;
  color: var(--c-text-tertiary);
  margin-right: 6px;
}

.response-fields-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 520px;
  overflow-y: auto;
}

.response-field-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--c-border-subtle);
  border-radius: 6px;
  background: var(--c-bg-subtle);
}

.field-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.field-path {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-primary);
}

.field-val {
  font-size: 11.5px;
  color: var(--c-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.response-raw-pre {
  padding: 10px;
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  max-height: 520px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.assertion-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 12px;
}
.assertion-result-item.is-pass {
  background: var(--c-success-soft);
}
.assertion-result-item.is-fail {
  background: var(--c-error-soft);
}
.ar-badge {
  font-weight: 700;
  font-size: 11px;
}

.add-step-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.drawer-footer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.scenario-load-row,
.env-var-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--c-border-subtle);
  cursor: pointer;
}
.scenario-load-row:hover {
  background: var(--c-bg-subtle);
}

@media (max-width: 1180px) {
  .scenario-workspace {
    grid-template-columns: 200px minmax(0, 1fr);
  }
  .step-response-pane {
    grid-column: 1 / -1;
    border-top: 1px solid var(--c-border);
  }
}
</style>
