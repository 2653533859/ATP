<template>
  <div class="performance-center">
    <div class="header">
      <div>
        <h2>{{ t('performance.title') }}</h2>
        <div class="subtitle">{{ t('performance.subtitle') }}</div>
      </div>
      <a-space>
        <a-select
          v-model:value="(projectId as number | undefined)"
          :options="projectOptions"
          :placeholder="t('performance.select_project')"
          style="width: 240px"
          @change="handleProjectChange"
        />
        <a-button :loading="loading" @click="refreshAll">
          <template #icon><ReloadOutlined /></template>
          {{ t('common.refresh') }}
        </a-button>
        <a-button type="primary" :disabled="!projectId" @click="openCreate">
          <template #icon><PlusOutlined /></template>
          {{ t('performance.create') }}
        </a-button>
      </a-space>
    </div>

    <section class="node-strip">
      <div class="node-strip-header">
        <div>
          <div class="section-label">{{ t('performance.nodes') }}</div>
          <div class="field-hint">{{ t('performance.node_hint') }}</div>
        </div>
        <a-space>
          <a-button size="small" :loading="nodesLoading" @click="loadNodes">
            <template #icon><ReloadOutlined /></template>
            {{ t('performance.node_refresh') }}
          </a-button>
          <a-button size="small" type="primary" @click="openNodeCreate">
            <template #icon><PlusOutlined /></template>
            {{ t('performance.node_register') }}
          </a-button>
        </a-space>
      </div>
      <a-empty v-if="nodes.length === 0" :image="false" :description="t('performance.no_nodes')" />
      <div v-else class="node-grid">
        <div v-for="node in nodes" :key="node.id" class="node-card" :class="`node-card-${node.status}`">
          <div class="node-card-title">
            <a-badge :status="nodeBadgeStatus(node.status)" />
            <strong>{{ node.name }}</strong>
            <a-tag>{{ nodeStatusLabel(node.status) }}</a-tag>
          </div>
          <div class="muted mono">{{ node.node_id }} · {{ node.queue_name }}</div>
          <div class="muted node-executors">{{ t('performance.node_executors') }}：{{ nodeExecutorLabel(node) }}</div>
          <div class="node-card-meta">
            <span>{{ t('performance.node_capacity') }}</span>
            <strong>{{ nodeCapacityLabel(node) }}</strong>
          </div>
          <div class="muted node-heartbeat">
            {{ node.last_heartbeat_at ? t('performance.node_last_heartbeat', { value: formatDateLabel(node.last_heartbeat_at) }) : t('performance.node_waiting_heartbeat') }}
          </div>
          <div v-if="node.last_error" class="node-error">
            <span>{{ t('performance.node_error') }}：</span>{{ node.last_error }}
          </div>
          <div class="node-card-actions">
            <a-button size="small" @click="openNodeEdit(node)">
              <template #icon><EditOutlined /></template>
              {{ t('common.edit') }}
            </a-button>
            <a-popconfirm
              :title="t('performance.node_delete_confirm')"
              @confirm="deleteNode(node)"
            >
              <a-button size="small" danger>
                <template #icon><DeleteOutlined /></template>
                {{ t('common.delete') }}
              </a-button>
            </a-popconfirm>
          </div>
        </div>
      </div>
    </section>

    <a-table
      :columns="testColumns"
      :data-source="tests"
      :loading="loading"
      :pagination="false"
      row-key="id"
      :locale="{ emptyText: t('performance.empty_tests') }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <div class="primary-text">{{ record.name }}</div>
          <div class="muted mono">{{ record.script_object_name }}</div>
          <div class="definition-meta">
            <a-tag v-if="record.baseline_run_id" color="purple">{{ t('performance.baseline_set') }}</a-tag>
            <a-tag v-if="record.schedule_enabled" color="cyan">{{ t('performance.schedule_enabled') }}</a-tag>
            <a-tag v-if="record.schedule_node_id" color="geekblue">{{ t('performance.node') }} #{{ record.schedule_node_id }}</a-tag>
            <a-tag v-if="record.dataset_id" color="green">{{ t('performance.dataset') }} #{{ record.dataset_id }}</a-tag>
          </div>
        </template>
        <template v-else-if="column.key === 'executor'">
          <a-tag color="blue">{{ record.executor }}</a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space>
            <a-tooltip :title="t('performance.run')">
              <a-button size="small" type="primary" @click="openRun(asPerfTest(record))">
                <template #icon><PlayCircleOutlined /></template>
              </a-button>
            </a-tooltip>
            <a-tooltip :title="t('common.edit')">
              <a-button size="small" @click="openEdit(asPerfTest(record))">
                <template #icon><EditOutlined /></template>
              </a-button>
            </a-tooltip>
            <a-tooltip :title="t('performance.schedule')">
              <a-button size="small" @click="openSchedule(asPerfTest(record))">
                <template #icon><ClockCircleOutlined /></template>
              </a-button>
            </a-tooltip>
            <a-popconfirm
              v-if="record.baseline_run_id"
              :title="t('performance.msg.clear_baseline_confirm')"
              @confirm="clearBaseline(asPerfTest(record))"
            >
              <a-tooltip :title="t('performance.clear_baseline')">
                <a-button size="small" danger>
                  <template #icon><DeleteOutlined /></template>
                </a-button>
              </a-tooltip>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <div class="insight-grid">
      <div class="insight-panel">
        <div class="section-title">{{ t('performance.trend_title') }}</div>
        <v-chart class="trend-chart" :option="trendOption" :theme="chartTheme" autoresize />
      </div>
      <div class="insight-panel">
        <div class="section-title">{{ t('performance.compare_title') }}</div>
        <a-alert
          v-if="compareRows.length < 2"
          type="info"
          show-icon
          :message="t('performance.compare_hint')"
        />
        <a-table
          v-else
          size="small"
          :columns="compareColumns"
          :data-source="compareRows"
          :pagination="false"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'delta'">
              <span :class="record.deltaClass">{{ record.delta }}</span>
            </template>
          </template>
        </a-table>
      </div>
    </div>

    <div class="section-toolbar">
      <div class="section-title">{{ t('performance.runs_title') }}</div>
      <a-button size="small" :disabled="selectedRunIds.length === 0 || !projectId" @click="capacityOpen = true">
        {{ t('performance.capacity_analyze') }} ({{ selectedRunIds.length }})
      </a-button>
    </div>
    <a-table
      :columns="runColumns"
      :data-source="runs"
      :loading="runsLoading"
      :pagination="{ pageSize: 10 }"
      :row-selection="runRowSelection"
      row-key="id"
      :locale="{ emptyText: t('performance.empty_runs') }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'node'">
          <a-tag v-if="record.performance_node_id" color="geekblue">
            {{ nodeName(record.performance_node_id) || `#${record.performance_node_id}` }}
          </a-tag>
          <span v-else class="muted">{{ t('performance.no_node') }}</span>
        </template>
        <template v-else-if="column.key === 'progress'">
          <div v-if="isActiveStatus(record.status)" class="run-progress">
            <a-progress :percent="progressPercent(asPerfRun(record))" size="small" :status="progressStatus(asPerfRun(record))" />
            <div class="muted">{{ progressLabel(asPerfRun(record)) }}</div>
          </div>
          <span v-else>{{ progressPercent(asPerfRun(record)) }}%</span>
        </template>
        <template v-else-if="column.key === 'metrics'">
          <a-space wrap>
            <a-statistic :title="t('performance.rps')" :value="metricValue(record.summary.rps)" :precision="2" />
            <a-statistic :title="t('performance.p95')" :value="metricValue(record.summary.p95_ms)" :precision="0" suffix="ms" />
            <a-statistic :title="t('performance.error_rate')" :value="percentValue(record.summary.error_rate)" :precision="2" suffix="%" />
          </a-space>
        </template>
        <template v-else-if="column.key === 'duration'">
          {{ formatDuration(record.duration_ms) }}
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space>
            <a-tooltip :title="t('common.view_detail')">
              <a-button size="small" @click="openRunDetail(asPerfRun(record))">
                <template #icon><FileSearchOutlined /></template>
              </a-button>
            </a-tooltip>
            <a-popconfirm
              v-if="isActiveStatus(record.status)"
              :title="t('performance.msg.stop_confirm')"
              @confirm="stopRun(asPerfRun(record))"
            >
              <a-tooltip :title="t('performance.stop')">
                <a-button size="small" danger :loading="stoppingRunId === record.id">
                  <template #icon><StopOutlined /></template>
                </a-button>
              </a-tooltip>
            </a-popconfirm>
            <a-tooltip v-if="record.status === 'success'" :title="t('performance.set_baseline')">
              <a-button size="small" @click="setBaseline(asPerfRun(record))">
                <template #icon><StarOutlined /></template>
              </a-button>
            </a-tooltip>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-drawer
      v-model:open="editorOpen"
      :title="editing ? t('performance.edit_title') : t('performance.create_title')"
      :width="680"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      @ok="saveTest"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('performance.name')" required>
          <a-input v-model:value="testForm.name" :placeholder="t('performance.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('performance.description')">
          <a-textarea v-model:value="testForm.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t('performance.executor')" required>
          <a-select
            v-model:value="testForm.executor"
            :options="executorOptions"
            :placeholder="t('performance.executor_placeholder')"
            @change="handleExecutorChange"
          />
          <div v-if="selectedExecutor" class="field-hint">{{ selectedExecutor.description }}</div>
        </a-form-item>
        <a-form-item :label="t('performance.dataset')">
          <a-select
            v-model:value="testForm.dataset_id"
            :options="datasetOptions"
            :disabled="selectedExecutor?.supports_dataset === false"
            allow-clear
            show-search
            option-filter-prop="label"
            :placeholder="t('performance.no_dataset')"
          />
          <div class="field-hint">
            {{ selectedExecutor?.supports_dataset === false ? t('performance.dataset_executor_unsupported') : t('performance.dataset_hint') }}
          </div>
        </a-form-item>
        <a-form-item :label="t('performance.creation_mode')">
          <a-radio-group v-model:value="testForm.mode" button-style="solid">
            <a-radio-button value="visual" :disabled="testForm.executor !== 'k6'">{{ t('performance.visual_mode') }}</a-radio-button>
            <a-radio-button value="script">{{ t('performance.script_mode') }}</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <template v-if="testForm.mode === 'visual' && testForm.executor === 'k6'">
          <a-alert
            type="info"
            show-icon
            :message="t('performance.visual_hint')"
            class="form-alert"
          />
          <a-form-item :label="t('performance.load_template')">
            <a-select
              v-model:value="testForm.scenario.loadTemplate"
              :options="loadTemplateOptions"
              @change="applyLoadTemplate"
            />
          </a-form-item>
          <a-row :gutter="12">
            <a-col :span="7">
              <a-form-item :label="t('performance.request_method')">
                <a-select v-model:value="testForm.scenario.method" :options="methodOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="17">
              <a-form-item :label="t('performance.request_url')" required>
                <a-input v-model:value="testForm.scenario.url" placeholder="https://example.test/api/health" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item :label="t('performance.request_headers')">
            <KvEditor v-model:value="testForm.scenario.headers" />
          </a-form-item>
          <a-form-item :label="t('performance.request_params')">
            <KvEditor v-model:value="testForm.scenario.params" />
          </a-form-item>
          <a-row :gutter="12">
            <a-col :span="8">
              <a-form-item :label="t('performance.body_type')">
                <a-select v-model:value="testForm.scenario.bodyType" :options="bodyTypeOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="16">
              <a-form-item :label="t('performance.expected_status')">
                <a-input-number v-model:value="testForm.scenario.expectedStatus" :min="100" :max="599" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item v-if="testForm.scenario.bodyType !== 'none'" :label="t('performance.request_body')">
            <a-textarea v-model:value="testForm.scenario.body" :rows="5" class="mono" />
          </a-form-item>
          <a-form-item :label="t('performance.auth_type')">
            <a-select v-model:value="testForm.scenario.authType" :options="authTypeOptions" />
          </a-form-item>
          <a-row v-if="testForm.scenario.authType === 'bearer'" :gutter="12">
            <a-col :span="24">
              <a-form-item :label="t('performance.token_variable')">
                <a-input v-model:value="testForm.scenario.bearerTokenKey" placeholder="API_TOKEN" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-row v-if="testForm.scenario.authType === 'basic'" :gutter="12">
            <a-col :span="12">
              <a-form-item :label="t('performance.username_variable')">
                <a-input v-model:value="testForm.scenario.basicUsernameKey" placeholder="API_USERNAME" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item :label="t('performance.password_variable')">
                <a-input v-model:value="testForm.scenario.basicPasswordKey" placeholder="API_PASSWORD" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item :label="t('performance.body_contains')">
            <a-input v-model:value="testForm.scenario.bodyContains" :placeholder="t('performance.body_contains_placeholder')" />
          </a-form-item>
          <div class="steps-editor behavior-editor">
            <div class="steps-toolbar">
              <div>
                <div class="section-label">{{ t('performance.behavior_steps') }}</div>
                <div class="field-hint">{{ t('performance.behavior_steps_hint') }}</div>
              </div>
              <a-switch
                :checked="(testForm.scenario.steps?.length || 0) > 0"
                :checked-children="t('common.enabled')"
                :un-checked-children="t('common.disabled')"
                @change="toggleMultiStep"
              />
            </div>
            <template v-if="(testForm.scenario.steps?.length || 0) > 0">
              <div v-for="(step, index) in testForm.scenario.steps || []" :key="index" class="behavior-step">
                <div class="behavior-step-header">
                  <strong>{{ t('performance.behavior_step', { value: index + 1 }) }}</strong>
                  <a-button type="text" danger @click="removeScenarioStep(index)">{{ t('common.delete') }}</a-button>
                </div>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-input v-model:value="step.name" :placeholder="t('performance.behavior_step_name')" />
                  </a-col>
                  <a-col :span="5">
                    <a-select v-model:value="step.method" :options="methodOptions" />
                  </a-col>
                  <a-col :span="7">
                    <a-input v-model:value="step.url" :placeholder="t('performance.request_url')" />
                  </a-col>
                  <a-col :span="4">
                    <a-input v-model:value="step.thinkTime" :placeholder="t('performance.behavior_think_time')" class="mono" />
                  </a-col>
                </a-row>
                <a-row :gutter="12" class="behavior-step-row">
                  <a-col :span="12">
                    <div class="section-label">{{ t('performance.request_headers') }}</div>
                    <KvEditor v-model:value="step.headers" />
                  </a-col>
                  <a-col :span="12">
                    <div class="section-label">{{ t('performance.request_params') }}</div>
                    <KvEditor v-model:value="step.params" />
                  </a-col>
                </a-row>
                <a-row :gutter="12" class="behavior-step-row">
                  <a-col :span="8">
                    <a-select v-model:value="step.bodyType" :options="bodyTypeOptions" />
                  </a-col>
                  <a-col :span="8">
                    <a-input-number v-model:value="step.expectedStatus" :min="100" :max="599" style="width: 100%" />
                  </a-col>
                  <a-col :span="8">
                    <a-input v-model:value="step.bodyContains" :placeholder="t('performance.body_contains_placeholder')" />
                  </a-col>
                </a-row>
                <a-textarea v-if="step.bodyType !== 'none'" v-model:value="step.body" :rows="3" class="mono behavior-step-row" />
              </div>
              <a-button type="dashed" block @click="addScenarioStep">{{ t('performance.add_behavior_step') }}</a-button>
            </template>
          </div>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item :label="t('performance.p95_threshold')">
                <a-input-number v-model:value="testForm.scenario.p95ThresholdMs" :min="0" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item :label="t('performance.error_threshold')">
                <a-input-number v-model:value="testForm.scenario.errorRateThresholdPercent" :min="0" :max="100" :step="0.1" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
          <div v-if="testForm.scenario.stages.length" class="stages-editor">
            <div class="section-label">{{ t('performance.stages') }}</div>
            <div v-for="(stage, index) in testForm.scenario.stages" :key="index" class="stage-row">
              <a-input v-model:value="stage.duration" :placeholder="t('performance.stage_duration')" />
              <a-input-number v-model:value="stage.target" :min="0" :placeholder="t('performance.stage_target')" />
              <a-button type="text" danger @click="removeStage(index)">{{ t('common.delete') }}</a-button>
            </div>
            <a-button type="dashed" block @click="addStage">{{ t('performance.add_stage') }}</a-button>
          </div>
        </template>
        <template v-else>
          <a-alert
            v-if="testForm.executor === 'grpc'"
            type="info"
            show-icon
            :message="t('performance.grpc_options_title')"
            :description="t('performance.grpc_options_hint')"
            class="form-alert"
          />
          <a-form-item :label="t('performance.script_object_name')" required>
            <a-space-compact class="script-input">
              <a-input v-model:value="testForm.script_object_name" class="mono" :placeholder="t('performance.script_placeholder')" />
              <a-upload
                :accept="scriptAccept"
                :before-upload="uploadScript"
                :show-upload-list="false"
              >
                <a-button :loading="scriptUploading">
                  <template #icon><UploadOutlined /></template>
                  {{ t('performance.upload_script') }}
                </a-button>
              </a-upload>
            </a-space-compact>
          </a-form-item>
          <a-form-item :label="t('performance.default_options')">
            <a-textarea v-model:value="testForm.defaultOptionsText" class="mono" :rows="10" />
          </a-form-item>
        </template>
        <div class="target-metrics-editor">
          <div class="target-metrics-header">
            <div>
              <div class="section-label">{{ t('performance.target_metrics') }}</div>
              <div class="field-hint">{{ t('performance.target_metrics_hint') }}</div>
            </div>
            <a-switch
              v-model:checked="testForm.targetMetrics.enabled"
              :checked-children="t('common.enabled')"
              :un-checked-children="t('common.disabled')"
            />
          </div>
          <template v-if="testForm.targetMetrics.enabled">
            <a-form-item :label="t('performance.target_metrics_source')">
              <a-radio-group v-model:value="testForm.targetMetrics.source" button-style="solid">
                <a-radio-button value="url">{{ t('performance.target_metrics_source_url') }}</a-radio-button>
                <a-radio-button value="env">{{ t('performance.target_metrics_source_env') }}</a-radio-button>
              </a-radio-group>
            </a-form-item>
            <a-form-item
              v-if="testForm.targetMetrics.source === 'url'"
              :label="t('performance.prometheus_url')"
              required
            >
              <a-input v-model:value="testForm.targetMetrics.prometheus_url" class="mono" placeholder="http://127.0.0.1:9090" />
            </a-form-item>
            <a-form-item
              v-else
              :label="t('performance.prometheus_url_env')"
              required
            >
              <a-input v-model:value="testForm.targetMetrics.url_env" class="mono" placeholder="PROMETHEUS_URL" />
            </a-form-item>
            <a-form-item :label="t('performance.target_metrics_timeout')">
              <a-input-number v-model:value="testForm.targetMetrics.timeout_seconds" :min="0.2" :max="10" :step="0.1" style="width: 100%" />
              <div class="field-hint">{{ t('performance.target_metrics_timeout_hint') }}</div>
            </a-form-item>
            <div class="target-metrics-queries">
              <div class="section-label">{{ t('performance.target_metrics_queries') }}</div>
              <div v-for="(query, index) in testForm.targetMetrics.queries" :key="index" class="target-metric-row">
                <a-input v-model:value="query.name" :placeholder="t('performance.target_metrics_name')" />
                <a-input v-model:value="query.query" class="mono" :placeholder="t('performance.target_metrics_query')" />
                <a-button type="text" danger :disabled="testForm.targetMetrics.queries.length <= 1" @click="removeTargetMetricQuery(index)">
                  {{ t('common.delete') }}
                </a-button>
              </div>
              <a-button type="dashed" block :disabled="testForm.targetMetrics.queries.length >= 8" @click="addTargetMetricQuery">{{ t('performance.add_target_metric_query') }}</a-button>
            </div>
          </template>
        </div>
      </a-form>
    </a-drawer>

    <a-modal
      v-model:open="nodeEditorOpen"
      :title="nodeEditing ? t('performance.node_edit_title') : t('performance.node_register_title')"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="nodeSaving"
      @ok="saveNode"
    >
      <a-alert
        type="info"
        show-icon
        :message="t('performance.node_register_hint')"
        class="form-alert"
      />
      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('performance.node_id')" required>
              <a-input
                v-model:value="nodeForm.node_id"
                class="mono"
                :disabled="!!nodeEditing"
                :placeholder="t('performance.node_id_placeholder')"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('performance.node_name')" required>
              <a-input v-model:value="nodeForm.name" :placeholder="t('performance.node_name_placeholder')" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('performance.node_queue')">
              <a-input v-model:value="nodeForm.queue_name" class="mono" placeholder="performance" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('performance.node_enabled')">
              <a-switch v-model:checked="nodeForm.enabled" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="t('performance.node_executors')" required>
          <a-select
            v-model:value="nodeForm.executors"
            mode="multiple"
            :options="nodeExecutorOptions"
            :placeholder="t('performance.node_executors_placeholder')"
          />
          <div class="field-hint">{{ t('performance.node_executors_hint') }}</div>
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('performance.node_max_vus')">
              <a-input-number v-model:value="nodeForm.max_vus" :min="1" allow-clear style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('performance.node_max_concurrency')">
              <a-input-number v-model:value="nodeForm.max_concurrency" :min="1" allow-clear style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="t('performance.node_allowlist')">
          <a-textarea
            v-model:value="nodeForm.egress_allowlist"
            :rows="3"
            class="mono"
            :placeholder="t('performance.node_allowlist_placeholder')"
          />
          <div class="field-hint">{{ t('performance.node_allowlist_hint') }}</div>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="runOpen"
      :title="t('performance.run_title')"
      :ok-text="t('performance.run')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="triggering"
      @ok="triggerRun"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('performance.environment')">
          <a-select
            v-model:value="runForm.environment_id"
            :options="environmentOptions"
            allow-clear
            :placeholder="t('performance.no_environment')"
          />
          <div class="field-hint">{{ t('performance.environment_hint') }}</div>
        </a-form-item>
        <a-form-item :label="t('performance.node')">
          <a-select
            v-model:value="runForm.performance_node_ids"
            :options="nodeOptions"
            allow-clear
            mode="multiple"
            show-search
            option-filter-prop="label"
            :placeholder="t('performance.no_node')"
          />
          <div class="field-hint">{{ t('performance.node_selector_hint') }}</div>
        </a-form-item>
        <a-alert
          v-if="runTarget?.dataset_id"
          type="info"
          show-icon
          :message="t('performance.dataset_bound', { value: datasetName(runTarget.dataset_id) || `#${runTarget.dataset_id}` })"
          class="form-alert"
        />
        <a-form-item :label="t('performance.run_options')">
          <a-textarea v-model:value="runForm.optionsText" class="mono" :rows="8" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="capacityOpen"
      :title="t('performance.capacity_title')"
      :ok-text="t('performance.capacity_analyze')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="capacityLoading"
      @ok="analyzeCapacity"
    >
      <a-alert
        type="info"
        show-icon
        :message="t('performance.capacity_hint', { count: selectedRunIds.length })"
        style="margin-bottom: 16px"
      />
      <a-form layout="vertical">
        <a-form-item :label="t('performance.capacity_error_rate')">
          <a-input-number v-model:value="capacityForm.max_error_rate_percent" :min="0" :max="100" :step="0.1" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('performance.capacity_p95')">
          <a-input-number v-model:value="capacityForm.max_p95_ms" :min="0" allow-clear style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('performance.capacity_min_stable')">
          <a-input-number v-model:value="capacityForm.min_stable_runs" :min="1" :max="selectedRunIds.length || 1" style="width: 100%" />
        </a-form-item>
      </a-form>
      <a-alert
        v-if="capacityResult"
        :type="capacityResult.status === 'ready' ? 'success' : 'warning'"
        show-icon
        :message="t('performance.capacity_result', { load: capacityResult.max_stable_load ?? '-' })"
        :description="t('performance.capacity_bottleneck', { value: capacityResult.bottleneck || t('performance.capacity_none') })"
      />
    </a-modal>

    <a-modal
      v-model:open="scheduleOpen"
      :title="t('performance.schedule_title')"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="scheduleSaving"
      @ok="saveSchedule"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('performance.schedule_enabled_label')">
          <a-switch v-model:checked="scheduleForm.enabled" />
        </a-form-item>
        <a-form-item :label="t('performance.cron_expression')" :required="scheduleForm.enabled">
          <a-input v-model:value="scheduleForm.cron_expression" placeholder="0 30 9 * * 1-5" class="mono" />
          <div class="field-hint">{{ t('performance.cron_hint') }}</div>
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('performance.schedule_timezone')">
              <a-input v-model:value="scheduleForm.timezone" placeholder="Asia/Shanghai" class="mono" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('performance.environment')">
              <a-select
                v-model:value="scheduleForm.environment_id"
                :options="environmentOptions"
                allow-clear
                :placeholder="t('performance.no_environment')"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="t('performance.node')">
          <a-select
            v-model:value="scheduleForm.performance_node_id"
            :options="nodeOptions"
            allow-clear
            show-search
            option-filter-prop="label"
            :placeholder="t('performance.no_node')"
          />
          <div class="field-hint">{{ t('performance.node_selector_hint') }}</div>
        </a-form-item>
        <a-form-item :label="t('performance.schedule_options')">
          <a-textarea v-model:value="scheduleForm.optionsText" class="mono" :rows="6" />
        </a-form-item>
        <a-alert v-if="scheduleTarget?.next_run_at" type="info" show-icon :message="t('performance.next_run_at', { value: formatDateLabel(scheduleTarget.next_run_at) })" />
      </a-form>
    </a-modal>

    <a-drawer v-model:open="detailOpen" :title="t('performance.run_detail')" :width="720">
      <template v-if="selectedRun">
        <div class="detail-toolbar">
          <div class="threshold-gate" :class="`threshold-gate-${thresholdGate.status}`">
            <div class="threshold-gate-label">{{ t('performance.threshold_gate') }}</div>
            <strong>{{ thresholdGateLabel }}</strong>
            <span>{{ thresholdGateSummary }}</span>
          </div>
          <a-space>
            <a-button size="small" :loading="exportingFormat === 'json'" @click="exportRunJson(selectedRun)">
              <template #icon><DownloadOutlined /></template>
              {{ t('performance.export_json') }}
            </a-button>
            <a-button size="small" :loading="exportingFormat === 'csv'" @click="exportRunCsv(selectedRun)">
              <template #icon><DownloadOutlined /></template>
              {{ t('performance.export_csv') }}
            </a-button>
          </a-space>
        </div>
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="ID">{{ selectedRun.id }}</a-descriptions-item>
          <a-descriptions-item :label="t('common.status')">
            <a-tag :color="statusColor(selectedRun.status)">{{ statusLabel(selectedRun.status) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="t('performance.node')">
            {{ selectedRun.performance_node_id ? (nodeName(selectedRun.performance_node_id) || `#${selectedRun.performance_node_id}`) : t('performance.no_node') }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('performance.rps')">{{ displayMetric(selectedRun.summary.rps) }}</a-descriptions-item>
          <a-descriptions-item :label="t('performance.p95')">{{ displayMetric(selectedRun.summary.p95_ms, 'ms') }}</a-descriptions-item>
          <a-descriptions-item :label="t('performance.p99')">{{ displayMetric(selectedRun.summary.p99_ms, 'ms') }}</a-descriptions-item>
          <a-descriptions-item :label="t('performance.error_rate')">
            {{ displayPercent(selectedRun.summary.error_rate) }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('performance.duration')">{{ formatDuration(selectedRun.duration_ms) }}</a-descriptions-item>
          <a-descriptions-item :label="t('performance.progress')">
            <a-progress :percent="progressPercent(selectedRun)" size="small" :status="progressStatus(selectedRun)" />
          </a-descriptions-item>
          <a-descriptions-item :label="t('performance.raw_result')">
            <a-space v-if="selectedRun.raw_result_object_name">
              <span class="mono">{{ selectedRun.raw_result_object_name }}</span>
              <a-button type="link" size="small" @click="openRawResult(selectedRun)">
                <template #icon><DownloadOutlined /></template>
                {{ t('performance.open_raw_result') }}
              </a-button>
            </a-space>
            <span v-else>-</span>
          </a-descriptions-item>
        </a-descriptions>
        <div v-if="selectedRun.error_message" class="detail-block">
          <a-alert type="error" :message="selectedRun.error_message" show-icon />
        </div>
        <div class="detail-block">
          <div class="section-label">{{ t('performance.thresholds') }}</div>
          <a-empty v-if="thresholdRows.length === 0" :description="t('performance.no_thresholds')" />
          <a-table
            v-else
            :columns="thresholdColumns"
            :data-source="thresholdRows"
            :pagination="false"
            size="small"
            row-key="key"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'ok'">
                <a-tag :color="record.ok ? 'success' : 'error'">
                  {{ record.ok ? t('performance.threshold_passed') : t('performance.threshold_failed') }}
                </a-tag>
              </template>
            </template>
          </a-table>
        </div>
        <div v-if="baselineComparison" class="detail-block">
          <div class="section-label">{{ t('performance.baseline_comparison') }}</div>
          <a-table
            :columns="baselineColumns"
            :data-source="baselineComparison.metrics"
            :pagination="false"
            size="small"
            row-key="metric"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'baseline' || column.key === 'current'">
                {{ formatBaselineMetric(record.metric, record[column.key]) }}
              </template>
              <template v-else-if="column.key === 'direction'">
                <a-tag :color="baselineDirectionColor(record.direction)">{{ t(`performance.baseline_direction_${record.direction}`) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'delta'">
                {{ formatBaselineDelta(record.delta_percent) }}
              </template>
            </template>
          </a-table>
        </div>
        <div class="detail-block">
          <div class="resource-toolbar">
            <div class="section-label">{{ t('performance.resource_timeline') }}</div>
            <a-space size="small" wrap>
              <a-select
                v-model:value="metricSource"
                size="small"
                :options="metricSourceOptions"
                :placeholder="t('performance.select_metric_source')"
                style="min-width: 180px"
                @change="handleMetricSourceChange"
              />
              <a-select
                v-model:value="resourceMetric"
                size="small"
                :options="resourceMetricOptions"
                :placeholder="t('performance.select_resource_metric')"
                style="min-width: 220px"
              />
            </a-space>
          </div>
          <a-empty v-if="metricSamples.length === 0" :description="t('performance.no_resource_metrics')" />
          <v-chart v-else class="resource-chart" :option="resourceTimelineOption" :theme="chartTheme" autoresize />
        </div>
        <div class="detail-block">
          <div class="section-label">{{ t('performance.summary_json') }}</div>
          <pre class="json-preview">{{ JSON.stringify(selectedRun.summary, null, 2) }}</pre>
        </div>
        <div class="detail-block">
          <div class="section-label">{{ t('performance.options_snapshot') }}</div>
          <pre class="json-preview">{{ JSON.stringify(selectedRun.options_snapshot, null, 2) }}</pre>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ClockCircleOutlined, DeleteOutlined, DownloadOutlined, EditOutlined, FileSearchOutlined, PlayCircleOutlined, PlusOutlined, ReloadOutlined, StarOutlined, StopOutlined, UploadOutlined } from '@ant-design/icons-vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import {
  datasetApi,
  environmentApi,
  performanceApi,
  projectApi,
  type DatasetListItem,
  type EnvironmentItem,
  type PerformanceBaselineComparisonItem,
  type PerformanceCapacityAnalysis,
  type PerformanceMetricSampleItem,
  type PerformanceNodeItem,
  type PerformanceExecutorItem,
  type PerformanceRunItem,
  type PerformanceTestItem,
  type ProjectItem,
} from '@/api'
import KvEditor from '@/components/common/KvEditor.vue'
import { useChartTheme } from '@/utils/chartTheme'
import { getPerformanceThresholdGate, getPerformanceThresholdRows } from '@/utils/performanceReport'
import {
  applyPerformanceLoadTemplate,
  buildPerformanceOptions,
  createDefaultPerformanceScenario,
  generatePerformanceK6Script,
  createDefaultPerformanceStep,
  type PerformanceLoadTemplate,
  type PerformanceScenario,
} from '@/utils/performanceScriptGenerator'
// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asPerfTest = (record: unknown) => record as PerformanceTestItem
const asPerfRun = (record: unknown) => record as PerformanceRunItem

const { t } = useI18n()
const { chartTheme } = useChartTheme()

const projectId = ref<number | null>(null)
const projectOptions = ref<{ label: string; value: number }[]>([])
const environmentOptions = ref<{ label: string; value: number }[]>([])
const datasetOptions = ref<{ label: string; value: number }[]>([])
const datasets = ref<DatasetListItem[]>([])
const nodes = ref<PerformanceNodeItem[]>([])
const executors = ref<PerformanceExecutorItem[]>([])
const tests = ref<PerformanceTestItem[]>([])
const runs = ref<PerformanceRunItem[]>([])
const loading = ref(false)
const runsLoading = ref(false)
const nodesLoading = ref(false)
const nodeEditorOpen = ref(false)
const nodeSaving = ref(false)
const nodeEditing = ref<PerformanceNodeItem | null>(null)
const editorOpen = ref(false)
const runOpen = ref(false)
const detailOpen = ref(false)
const scheduleOpen = ref(false)
const capacityOpen = ref(false)
const capacityLoading = ref(false)
const capacityResult = ref<PerformanceCapacityAnalysis | null>(null)
const triggering = ref(false)
const scheduleSaving = ref(false)
const stoppingRunId = ref<number | null>(null)
const exportingFormat = ref<'json' | 'csv' | null>(null)
const scriptUploading = ref(false)
const editing = ref<PerformanceTestItem | null>(null)
const runTarget = ref<PerformanceTestItem | null>(null)
const selectedRun = ref<PerformanceRunItem | null>(null)
const baselineComparison = ref<PerformanceBaselineComparisonItem | null>(null)
const metricSamples = ref<PerformanceMetricSampleItem[]>([])
const metricSource = ref('performance-worker')
const resourceMetric = ref('cpu_percent')
const scheduleTarget = ref<PerformanceTestItem | null>(null)
const selectedRunIds = ref<number[]>([])
const capacityForm = ref({ max_error_rate_percent: 1, max_p95_ms: undefined as number | undefined, min_stable_runs: 1 })
let runPollingTimer: ReturnType<typeof window.setInterval> | null = null

type PerformanceNodeForm = {
  node_id: string
  name: string
  queue_name: string
  enabled: boolean
  executors: string[]
  max_vus?: number
  max_concurrency?: number
  egress_allowlist: string
}

function createDefaultNodeForm(): PerformanceNodeForm {
  return {
    node_id: '',
    name: '',
    queue_name: 'performance',
    enabled: true,
    executors: ['k6'],
    max_vus: undefined,
    max_concurrency: undefined,
    egress_allowlist: '',
  }
}

const nodeForm = ref<PerformanceNodeForm>(createDefaultNodeForm())

type PerformanceCreationMode = 'visual' | 'script'
type TargetMetricSource = 'url' | 'env'
type TargetMetricQuery = { name: string; query: string }
type TargetMetricsForm = {
  enabled: boolean
  source: TargetMetricSource
  prometheus_url: string
  url_env: string
  timeout_seconds: number
  queries: TargetMetricQuery[]
}

function createDefaultTargetMetrics(): TargetMetricsForm {
  return {
    enabled: false,
    source: 'url',
    prometheus_url: '',
    url_env: '',
    timeout_seconds: 2,
    queries: [{ name: '', query: '' }],
  }
}

const executorOptions = computed(() => executors.value.map((executor) => ({
  label: executor.label,
  value: executor.name,
  disabled: !executor.ready,
  title: executor.description,
})))

const nodeExecutorOptions = computed(() => {
  const knownExecutors = new Map(executors.value.map((executor) => [executor.name, executor]))
  return (['k6', 'locust', 'grpc', 'jmeter'] as const).map((name) => {
    const executor = knownExecutors.get(name)
    return {
      label: executor?.label || name,
      value: name,
      disabled: executor ? !executor.ready : false,
    }
  })
})

const loadTemplateOptions = computed(() => [
  { label: t('performance.template_smoke'), value: 'smoke' },
  { label: t('performance.template_load'), value: 'load' },
  { label: t('performance.template_stress'), value: 'stress' },
  { label: t('performance.template_spike'), value: 'spike' },
  { label: t('performance.template_soak'), value: 'soak' },
])

const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({ label: value, value }))
const bodyTypeOptions = computed(() => [
  { label: t('performance.body_none'), value: 'none' },
  { label: t('performance.body_json'), value: 'json' },
  { label: t('performance.body_text'), value: 'text' },
])
const authTypeOptions = computed(() => [
  { label: t('performance.auth_none'), value: 'none' },
  { label: t('performance.auth_bearer'), value: 'bearer' },
  { label: t('performance.auth_basic'), value: 'basic' },
])

const testForm = ref<{
  mode: PerformanceCreationMode
  executor: 'k6' | 'locust' | 'grpc' | 'jmeter'
  name: string
  description: string
  script_object_name: string
  dataset_id?: number
  defaultOptionsText: string
  scenario: PerformanceScenario
  targetMetrics: TargetMetricsForm
}>({
  mode: 'visual',
  executor: 'k6',
  name: '',
  description: '',
  script_object_name: '',
  dataset_id: undefined,
  defaultOptionsText: '{\n  "env": {\n    "TARGET_URL": "https://example.test"\n  }\n}',
  scenario: createDefaultPerformanceScenario(),
  targetMetrics: createDefaultTargetMetrics(),
})

const selectedExecutor = computed(() => executors.value.find((item) => item.name === testForm.value.executor))
const scriptAccept = computed(() => (selectedExecutor.value?.script_extensions || ['.js', '.mjs']).join(','))

const runForm = ref<{ environment_id?: number; performance_node_ids: number[]; optionsText: string }>({
  environment_id: undefined,
  performance_node_ids: [],
  optionsText: '{}',
})

const scheduleForm = ref({
  enabled: false,
  cron_expression: '',
  timezone: 'Asia/Shanghai',
  environment_id: undefined as number | undefined,
  performance_node_id: undefined as number | undefined,
  optionsText: '{}',
})

const nodeOptions = computed(() => nodes.value.map((node) => ({
  label: `${node.name} (${node.node_id}) · ${nodeStatusLabel(node.status)} · ${nodeExecutorLabel(node)}`,
  value: node.id,
  disabled: node.status !== 'online' || !node.enabled,
})))

const testColumns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: t('performance.name'), key: 'name' },
  { title: t('performance.executor'), key: 'executor', width: 100 },
  { title: t('common.updated_at'), dataIndex: 'updated_at', key: 'updated_at', width: 180 },
  { title: t('common.actions'), key: 'actions', width: 170 },
])

const runColumns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: t('performance.test_id'), dataIndex: 'performance_test_id', key: 'performance_test_id', width: 110 },
  { title: t('common.status'), key: 'status', width: 110 },
  { title: t('performance.node'), key: 'node', width: 150 },
  { title: t('performance.progress'), key: 'progress', width: 180 },
  { title: t('performance.metrics'), key: 'metrics', width: 360 },
  { title: t('performance.duration'), key: 'duration', width: 120 },
  { title: t('common.created_at'), dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: t('common.actions'), key: 'actions', width: 150 },
])

const compareColumns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 72 },
  { title: t('common.status'), key: 'status', width: 100 },
  { title: t('performance.rps'), dataIndex: 'rps', key: 'rps', width: 90 },
  { title: t('performance.p95'), dataIndex: 'p95', key: 'p95', width: 90 },
  { title: t('performance.p99'), dataIndex: 'p99', key: 'p99', width: 90 },
  { title: t('performance.error_rate'), dataIndex: 'errorRate', key: 'errorRate', width: 100 },
  { title: t('performance.duration'), dataIndex: 'duration', key: 'duration', width: 100 },
  { title: t('performance.delta_vs_base'), key: 'delta' },
])

const runRowSelection = computed(() => ({
  selectedRowKeys: selectedRunIds.value,
  onChange: (keys: Array<string | number>) => {
    selectedRunIds.value = keys.map(Number).filter(Number.isFinite).slice(-4)
  },
}))

const thresholdColumns = computed(() => [
  { title: t('performance.threshold_metric'), dataIndex: 'metric', key: 'metric' },
  { title: t('performance.threshold_rule'), dataIndex: 'rule', key: 'rule' },
  { title: t('performance.threshold_status'), key: 'ok', width: 120 },
])

const thresholdRows = computed(() => getPerformanceThresholdRows(selectedRun.value?.summary))
const thresholdGate = computed(() => getPerformanceThresholdGate(selectedRun.value?.summary))
const thresholdGateLabel = computed(() => t(`performance.threshold_gate_${thresholdGate.value.status}`))
const thresholdGateSummary = computed(() => t('performance.threshold_gate_summary', {
  passed: thresholdGate.value.passed,
  total: thresholdGate.value.total,
}))

const baselineColumns = computed(() => [
  { title: t('performance.baseline_metric'), dataIndex: 'metric', key: 'metric' },
  { title: t('performance.baseline_value'), dataIndex: 'baseline', key: 'baseline' },
  { title: t('performance.current_value'), dataIndex: 'current', key: 'current' },
  { title: t('performance.baseline_delta'), key: 'delta' },
  { title: t('performance.baseline_direction'), key: 'direction' },
])

const resourceMetricKeys = [
  'cpu_percent',
  'memory_percent',
  'postgres_connections',
  'postgres_cache_hit_percent',
  'redis_connected_clients',
  'redis_ops_per_second',
  'minio_probe_ms',
  'minio_object_count',
  'minio_total_bytes',
]

const metricSourceOptions = computed(() => {
  const sources = [...new Set(metricSamples.value.map((sample) => sample.source).filter(Boolean))]
  return sources.map((source) => ({ label: metricSourceLabel(source), value: source }))
})

const metricSamplesForSource = computed(() => metricSamples.value.filter((sample) => sample.source === metricSource.value))

const resourceMetricOptions = computed(() => {
  const keys = [...new Set(metricSamplesForSource.value.flatMap((sample) => Object.keys(sample.metrics)))]
  return keys.map((key) => ({
    label: metricLabel(key),
    value: key,
  }))
})

const resourceTimelineOption = computed<EChartsOption>(() => {
  const labels = metricSamplesForSource.value.map((sample) => formatDateLabel(sample.captured_at))
  return {
    tooltip: { trigger: 'axis' },
    grid: { top: 24, right: 18, bottom: 42, left: 58 },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', name: metricLabel(resourceMetric.value) },
    series: [{
      name: metricLabel(resourceMetric.value),
      type: 'line',
      smooth: true,
      connectNulls: false,
      data: metricSamplesForSource.value.map((sample) => sample.metrics[resourceMetric.value] ?? null),
    }],
  }
})

const trendRuns = computed(() => [...runs.value].reverse().filter((run) => run.status === 'success'))

const trendOption = computed<EChartsOption>(() => {
  const labels = trendRuns.value.map((run) => formatDateLabel(run.created_at))
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: [t('performance.rps'), t('performance.p95'), t('performance.p99'), t('performance.error_rate')] },
    grid: { top: 42, right: 18, bottom: 32, left: 42 },
    xAxis: { type: 'category', data: labels },
    yAxis: [
      { type: 'value', name: t('performance.latency_axis') },
      { type: 'value', name: t('performance.error_axis'), min: 0, max: 100 },
    ],
    series: [
      { name: t('performance.rps'), type: 'line', smooth: true, data: trendRuns.value.map((run) => numericMetric(run.summary.rps)) },
      { name: t('performance.p95'), type: 'line', smooth: true, data: trendRuns.value.map((run) => numericMetric(run.summary.p95_ms)) },
      { name: t('performance.p99'), type: 'line', smooth: true, data: trendRuns.value.map((run) => numericMetric(run.summary.p99_ms)) },
      {
        name: t('performance.error_rate'),
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: trendRuns.value.map((run) => percentValue(run.summary.error_rate)),
      },
    ],
  }
})

const selectedCompareRuns = computed(() => {
  const byId = new Map(runs.value.map((run) => [run.id, run]))
  return selectedRunIds.value.map((id) => byId.get(id)).filter((run): run is PerformanceRunItem => !!run)
})

const compareRows = computed(() => {
  const base = selectedCompareRuns.value[0]
  const baseP95 = base ? numericMetric(base.summary.p95_ms) : null
  return selectedCompareRuns.value.map((run, index) => {
    const p95 = numericMetric(run.summary.p95_ms)
    const delta = index === 0 || baseP95 === null || p95 === null ? t('performance.baseline') : formatDelta(p95 - baseP95, 'ms')
    return {
      id: run.id,
      status: run.status,
      rps: displayMetric(run.summary.rps),
      p95: displayMetric(run.summary.p95_ms, 'ms'),
      p99: displayMetric(run.summary.p99_ms, 'ms'),
      errorRate: displayPercent(run.summary.error_rate),
      duration: formatDuration(run.duration_ms),
      delta,
      deltaClass: delta.startsWith('+') ? 'delta-bad' : delta.startsWith('-') ? 'delta-good' : 'muted',
    }
  })
})

async function loadProjects() {
  const items = await projectApi.list()
  projectOptions.value = items.map((project: ProjectItem) => ({ label: project.name, value: project.id }))
  if (!projectId.value && projectOptions.value.length) {
    projectId.value = projectOptions.value[0].value
    await refreshAll()
  }
}

async function handleProjectChange() {
  await refreshAll()
}

async function refreshAll() {
  await Promise.all([loadTests(), loadRuns(), loadEnvironments(), loadDatasets(), loadNodes(), loadExecutors()])
}

async function loadExecutors() {
  try {
    executors.value = await performanceApi.listExecutors()
  } catch {
    executors.value = []
  }
}

async function loadTests() {
  if (!projectId.value) {
    tests.value = []
    return
  }
  loading.value = true
  try {
    tests.value = await performanceApi.listTests(projectId.value)
  } catch {
    message.error(t('performance.msg.load_tests_failed'))
  } finally {
    loading.value = false
  }
}

async function loadRuns(options: { silent?: boolean } = {}) {
  if (!projectId.value) {
    runs.value = []
    stopRunPolling()
    return
  }
  if (!options.silent) runsLoading.value = true
  try {
    runs.value = await performanceApi.listRuns(projectId.value)
    selectedRunIds.value = selectedRunIds.value.filter((id) => runs.value.some((run) => run.id === id))
    if (selectedRun.value) {
      selectedRun.value = runs.value.find((run) => run.id === selectedRun.value?.id) || selectedRun.value
    }
  } catch {
    if (!options.silent) message.error(t('performance.msg.load_runs_failed'))
  } finally {
    if (!options.silent) runsLoading.value = false
    syncRunPolling()
  }
}

async function loadEnvironments() {
  if (!projectId.value) {
    environmentOptions.value = []
    return
  }
  try {
    const items = await environmentApi.list(projectId.value)
    environmentOptions.value = items.map((env: EnvironmentItem) => ({ label: env.name, value: env.id }))
  } catch {
    environmentOptions.value = []
  }
}

async function loadDatasets() {
  if (!projectId.value) {
    datasets.value = []
    datasetOptions.value = []
    return
  }
  try {
    datasets.value = await datasetApi.list(projectId.value)
    datasetOptions.value = datasets.value.map((dataset: DatasetListItem) => ({
      label: `${dataset.name} (${dataset.row_count})`,
      value: dataset.id,
    }))
  } catch {
    datasets.value = []
    datasetOptions.value = []
  }
}

async function loadNodes() {
  nodesLoading.value = true
  try {
    nodes.value = await performanceApi.listNodes()
  } catch {
    nodes.value = []
    message.error(t('performance.msg.load_nodes_failed'))
  } finally {
    nodesLoading.value = false
  }
}

function nodeExecutorNames(node: PerformanceNodeItem): string[] {
  const declared = node.capabilities?.executors
  if (Array.isArray(declared)) {
    const values = declared.map((value) => String(value).trim()).filter(Boolean)
    if (values.length) return values
  }
  if (typeof declared === 'string') {
    const values = declared.split(',').map((value) => value.trim()).filter(Boolean)
    if (values.length) return values
  }
  const legacy = node.capabilities?.executor
  return typeof legacy === 'string' && legacy.trim() ? [legacy.trim()] : ['k6']
}

function nodeExecutorLabel(node: PerformanceNodeItem) {
  return nodeExecutorNames(node).join(', ')
}

function parseNodeAllowlist(value: string) {
  return [...new Set(value.split(/[\n,]/).map((item) => item.trim().toLowerCase()).filter(Boolean))]
}

function openNodeCreate() {
  nodeEditing.value = null
  nodeForm.value = createDefaultNodeForm()
  nodeEditorOpen.value = true
}

function openNodeEdit(node: PerformanceNodeItem) {
  nodeEditing.value = node
  nodeForm.value = {
    node_id: node.node_id,
    name: node.name,
    queue_name: node.queue_name,
    enabled: node.enabled,
    executors: nodeExecutorNames(node),
    max_vus: node.max_vus ?? undefined,
    max_concurrency: node.max_concurrency ?? undefined,
    egress_allowlist: node.egress_allowlist.join('\n'),
  }
  nodeEditorOpen.value = true
}

async function saveNode() {
  const nodeId = nodeForm.value.node_id.trim()
  const name = nodeForm.value.name.trim()
  const queueName = nodeForm.value.queue_name.trim()
  const executorNames = [...new Set(nodeForm.value.executors.map((item) => item.trim()).filter(Boolean))]
  if (!nodeId || !name || !queueName || executorNames.length === 0) {
    message.warning(t('performance.msg.node_required'))
    return
  }
  const capabilities = {
    ...(nodeEditing.value?.capabilities || {}),
    executors: executorNames,
  }
  const payload = {
    name,
    queue_name: queueName,
    enabled: nodeForm.value.enabled,
    capabilities,
    max_vus: nodeForm.value.max_vus ?? null,
    max_concurrency: nodeForm.value.max_concurrency ?? null,
    egress_allowlist: parseNodeAllowlist(nodeForm.value.egress_allowlist),
  }
  nodeSaving.value = true
  try {
    if (nodeEditing.value) {
      await performanceApi.updateNode(nodeEditing.value.id, payload)
    } else {
      await performanceApi.createNode({ node_id: nodeId, ...payload })
    }
    message.success(nodeEditing.value ? t('performance.msg.node_update_success') : t('performance.msg.node_create_success'))
    nodeEditorOpen.value = false
    await loadNodes()
  } catch {
    message.error(nodeEditing.value ? t('performance.msg.node_update_failed') : t('performance.msg.node_create_failed'))
  } finally {
    nodeSaving.value = false
  }
}

async function deleteNode(node: PerformanceNodeItem) {
  try {
    await performanceApi.deleteNode(node.id)
    message.success(t('performance.msg.node_delete_success'))
    await loadNodes()
  } catch {
    message.error(t('performance.msg.node_delete_failed'))
  }
}

function openCreate() {
  editing.value = null
  testForm.value = {
    mode: 'visual',
    executor: 'k6',
    name: '',
    description: '',
    script_object_name: '',
    dataset_id: undefined,
    defaultOptionsText: '{\n  "env": {\n    "TARGET_URL": "https://example.test"\n  }\n}',
    scenario: createDefaultPerformanceScenario(),
    targetMetrics: createDefaultTargetMetrics(),
  }
  editorOpen.value = true
}

function openEdit(record: PerformanceTestItem) {
  editing.value = record
  const scenarioValue = record.default_options?.atp_scenario
  const visual = isPerformanceScenario(scenarioValue)
  const executor = record.executor === 'locust'
    ? 'locust'
    : record.executor === 'grpc'
      ? 'grpc'
      : record.executor === 'jmeter'
        ? 'jmeter'
        : 'k6'
  testForm.value = {
    mode: visual && executor === 'k6' ? 'visual' : 'script',
    executor,
    name: record.name,
    description: record.description || '',
    script_object_name: record.script_object_name,
    dataset_id: executor === 'grpc' ? undefined : record.dataset_id ?? undefined,
    defaultOptionsText: JSON.stringify(record.default_options || {}, null, 2),
    scenario: visual ? cloneScenario(scenarioValue) : createDefaultPerformanceScenario(),
    targetMetrics: targetMetricsFromOptions(record.default_options),
  }
  editorOpen.value = true
}

function handleExecutorChange(value: unknown) {
  if (value !== 'k6' && value !== 'locust' && value !== 'grpc' && value !== 'jmeter') return
  const previousExecutor = testForm.value.executor
  testForm.value.executor = value
  if (value !== 'k6') testForm.value.mode = 'script'
  if (value === 'grpc') testForm.value.dataset_id = undefined
  if (value === 'grpc' && previousExecutor !== 'grpc') {
    testForm.value.defaultOptionsText = JSON.stringify({
      target: 'localhost:50051',
      service: 'package.Service',
      method: 'Method',
      mode: 'unary',
      request: {},
      concurrency: 1,
      duration_seconds: 30,
      timeout_seconds: 10,
      metadata: {},
    }, null, 2)
  }
}

function openSchedule(record: PerformanceTestItem) {
  scheduleTarget.value = record
  scheduleForm.value = {
    enabled: record.schedule_enabled,
    cron_expression: record.cron_expression || '',
    timezone: record.schedule_timezone || 'Asia/Shanghai',
    environment_id: record.schedule_environment_id ?? undefined,
    performance_node_id: record.schedule_node_id ?? undefined,
    optionsText: JSON.stringify(record.schedule_options || {}, null, 2),
  }
  scheduleOpen.value = true
}

async function saveSchedule() {
  if (!scheduleTarget.value) return
  const options = parseJsonObject(scheduleForm.value.optionsText, t('performance.msg.options_invalid'))
  if (!options) return
  if (scheduleForm.value.enabled && !scheduleForm.value.cron_expression.trim()) {
    message.warning(t('performance.msg.cron_required'))
    return
  }
  scheduleSaving.value = true
  try {
    await performanceApi.updateSchedule(scheduleTarget.value.id, {
      enabled: scheduleForm.value.enabled,
      cron_expression: scheduleForm.value.cron_expression.trim() || null,
      timezone: scheduleForm.value.timezone.trim() || 'Asia/Shanghai',
      environment_id: scheduleForm.value.environment_id ?? null,
      performance_node_id: scheduleForm.value.performance_node_id ?? null,
      options,
    })
    message.success(t('performance.msg.schedule_saved'))
    scheduleOpen.value = false
    await loadTests()
  } catch {
    message.error(t('performance.msg.schedule_failed'))
  } finally {
    scheduleSaving.value = false
  }
}

function isPerformanceScenario(value: unknown): value is PerformanceScenario {
  return !!(
    value
    && typeof value === 'object'
    && !Array.isArray(value)
    && typeof (value as PerformanceScenario).url === 'string'
    && typeof (value as PerformanceScenario).method === 'string'
    && typeof (value as PerformanceScenario).loadTemplate === 'string'
  )
}

function cloneScenario(scenario: PerformanceScenario): PerformanceScenario {
  return {
    ...scenario,
    headers: { ...scenario.headers },
    params: { ...scenario.params },
    stages: (scenario.stages || []).map((stage) => ({ ...stage })),
    steps: (scenario.steps || []).map((step) => ({
      ...step,
      headers: { ...step.headers },
      params: { ...step.params },
    })),
  }
}

function toggleMultiStep(enabled: boolean | string | number) {
  const shouldEnable = Boolean(enabled)
  if (shouldEnable && !testForm.value.scenario.steps?.length) {
    testForm.value.scenario.steps = [createDefaultPerformanceStep(testForm.value.scenario)]
  } else if (!shouldEnable) {
    testForm.value.scenario.steps = []
  }
}

function addScenarioStep() {
  const scenario = testForm.value.scenario
  if (!scenario.steps) scenario.steps = []
  scenario.steps.push(createDefaultPerformanceStep({ url: scenario.url }))
}

function removeScenarioStep(index: number) {
  testForm.value.scenario.steps?.splice(index, 1)
}

function applyLoadTemplate(value: unknown) {
  const template = String(value) as PerformanceLoadTemplate
  testForm.value.scenario = applyPerformanceLoadTemplate(testForm.value.scenario, template)
}

function addStage() {
  testForm.value.scenario.stages.push({ duration: '30s', target: 10 })
}

function removeStage(index: number) {
  testForm.value.scenario.stages.splice(index, 1)
}

function addTargetMetricQuery() {
  if (testForm.value.targetMetrics.queries.length >= 8) return
  testForm.value.targetMetrics.queries.push({ name: '', query: '' })
}

function removeTargetMetricQuery(index: number) {
  if (testForm.value.targetMetrics.queries.length <= 1) return
  testForm.value.targetMetrics.queries.splice(index, 1)
}

function parseJsonObject(text: string, fallback: string): Record<string, unknown> | null {
  try {
    const value = JSON.parse(text || '{}')
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      message.warning(fallback)
      return null
    }
    return value as Record<string, unknown>
  } catch {
    message.warning(fallback)
    return null
  }
}

function targetMetricsFromOptions(options: Record<string, unknown>): TargetMetricsForm {
  const defaults = createDefaultTargetMetrics()
  const raw = options.target_metrics
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return defaults
  const config = raw as Record<string, unknown>
  const rawQueries = config.queries
  const queries = rawQueries && typeof rawQueries === 'object' && !Array.isArray(rawQueries)
    ? Object.entries(rawQueries as Record<string, unknown>)
      .map(([name, query]) => ({ name: name.trim(), query: String(query || '').trim() }))
      .filter((item) => item.name && item.query)
    : []
  const timeout = typeof config.timeout_seconds === 'number' && Number.isFinite(config.timeout_seconds)
    ? Math.min(10, Math.max(0.2, config.timeout_seconds))
    : defaults.timeout_seconds
  const prometheusUrl = typeof config.prometheus_url === 'string' ? config.prometheus_url : ''
  const urlEnv = typeof config.url_env === 'string' ? config.url_env : ''
  return {
    enabled: true,
    source: prometheusUrl.trim() ? 'url' : 'env',
    prometheus_url: prometheusUrl,
    url_env: urlEnv,
    timeout_seconds: timeout,
    queries: queries.length ? queries : defaults.queries,
  }
}

function applyTargetMetrics(options: Record<string, unknown>): Record<string, unknown> | null {
  const next = { ...options }
  delete next.target_metrics
  const form = testForm.value.targetMetrics
  if (!form.enabled) return next

  const sourceValue = form.source === 'url' ? form.prometheus_url.trim() : form.url_env.trim()
  if (!sourceValue) {
    message.warning(t(form.source === 'url' ? 'performance.msg.prometheus_url_required' : 'performance.msg.prometheus_url_env_required'))
    return null
  }
  if (form.source === 'url') {
    try {
      const parsed = new URL(sourceValue)
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') throw new Error('unsupported protocol')
    } catch {
      message.warning(t('performance.msg.prometheus_url_invalid'))
      return null
    }
  }
  const queries = Object.fromEntries(
    form.queries
      .map((item) => ({ name: item.name.trim(), query: item.query.trim() }))
      .filter((item) => item.name && item.query)
      .map((item) => [item.name, item.query]),
  )
  if (Object.keys(queries).length === 0) {
    message.warning(t('performance.msg.target_metrics_query_required'))
    return null
  }
  const queryNames = form.queries.map((item) => item.name.trim()).filter(Boolean)
  if (new Set(queryNames).size !== queryNames.length) {
    message.warning(t('performance.msg.target_metrics_query_duplicate'))
    return null
  }
  const targetMetrics: Record<string, unknown> = {
    queries,
    timeout_seconds: Math.min(10, Math.max(0.2, Number(form.timeout_seconds) || 2)),
  }
  if (form.source === 'url') targetMetrics.prometheus_url = sourceValue
  else targetMetrics.url_env = sourceValue
  next.target_metrics = targetMetrics
  return next
}

async function saveTest() {
  if (!projectId.value) return
  const name = testForm.value.name.trim()
  if (!name) {
    message.warning(t('performance.msg.required'))
    return
  }

  let scriptObjectName = testForm.value.script_object_name.trim()
  let defaultOptions: Record<string, unknown> | null
  if (testForm.value.mode === 'visual') {
    if (!testForm.value.scenario.url.trim()) {
      message.warning(t('performance.msg.visual_required'))
      return
    }
    defaultOptions = buildPerformanceOptions(testForm.value.scenario)
    defaultOptions = applyTargetMetrics(defaultOptions)
    if (!defaultOptions) return
    const filename = 'performance-' + slugify(name) + '.js'
    scriptUploading.value = true
    try {
      const script = generatePerformanceK6Script(testForm.value.scenario)
      const file = new File([script], filename, { type: 'application/javascript' })
      const result = await performanceApi.uploadScript(projectId.value, file, 'k6')
      scriptObjectName = result.script_object_name
    } catch {
      message.error(t('performance.msg.upload_failed'))
      return
    } finally {
      scriptUploading.value = false
    }
  } else {
    if (!scriptObjectName) {
      message.warning(t('performance.msg.required'))
      return
    }
    defaultOptions = parseJsonObject(testForm.value.defaultOptionsText, t('performance.msg.options_invalid'))
    if (!defaultOptions) return
    defaultOptions = applyTargetMetrics(defaultOptions)
    if (!defaultOptions) return
  }
  if (!defaultOptions) return

  try {
    if (editing.value) {
      await performanceApi.updateTest(editing.value.id, {
        name,
        description: testForm.value.description || null,
        executor: testForm.value.executor,
        script_object_name: scriptObjectName,
        dataset_id: testForm.value.dataset_id ?? null,
        default_options: defaultOptions,
      })
      message.success(t('performance.msg.update_success'))
    } else {
      await performanceApi.createTest({
        project_id: projectId.value,
        name,
        description: testForm.value.description || null,
        executor: testForm.value.executor,
        script_object_name: scriptObjectName,
        dataset_id: testForm.value.dataset_id ?? null,
        default_options: defaultOptions,
      })
      message.success(t('performance.msg.create_success'))
    }
    editorOpen.value = false
    await loadTests()
  } catch {
    message.error(t('performance.msg.save_failed'))
  }
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'scenario'
}

function isSupportedScript(file: File) {
  const extensions = selectedExecutor.value?.script_extensions || ['.js', '.mjs']
  return extensions.some((extension) => file.name.toLowerCase().endsWith(extension))
}

async function uploadScript(file: File) {
  if (!projectId.value) {
    message.warning(t('performance.msg.select_project_first'))
    return false
  }
  if (!isSupportedScript(file)) {
    message.warning(t('performance.msg.script_type_invalid'))
    return false
  }
  scriptUploading.value = true
  try {
    const result = await performanceApi.uploadScript(projectId.value, file, testForm.value.executor)
    testForm.value.script_object_name = result.script_object_name
    message.success(t('performance.msg.upload_success'))
  } catch {
    message.error(t('performance.msg.upload_failed'))
  } finally {
    scriptUploading.value = false
  }
  return false
}

function openRun(record: PerformanceTestItem) {
  runTarget.value = record
  runForm.value = { environment_id: undefined, performance_node_ids: [], optionsText: '{}' }
  runOpen.value = true
}

async function triggerRun() {
  if (!runTarget.value) return
  const options = parseJsonObject(runForm.value.optionsText, t('performance.msg.options_invalid'))
  if (!options) return
  triggering.value = true
  try {
    const run = await performanceApi.triggerRun(runTarget.value.id, {
      environment_id: runForm.value.environment_id ?? null,
      performance_node_ids: runForm.value.performance_node_ids,
      options,
    })
    runOpen.value = false
    message.success(t('performance.msg.run_started', { id: run.id }))
    await loadRuns()
  } catch {
    message.error(t('performance.msg.run_failed'))
  } finally {
    triggering.value = false
  }
}

async function analyzeCapacity() {
  if (!projectId.value || selectedRunIds.value.length === 0) {
    message.warning(t('performance.msg.capacity_select_runs'))
    return
  }
  capacityLoading.value = true
  try {
    capacityResult.value = await performanceApi.analyzeCapacity(projectId.value, {
      run_ids: selectedRunIds.value,
      max_error_rate: capacityForm.value.max_error_rate_percent / 100,
      max_p95_ms: capacityForm.value.max_p95_ms ?? null,
      min_stable_runs: capacityForm.value.min_stable_runs,
    })
  } catch {
    message.error(t('performance.msg.capacity_failed'))
  } finally {
    capacityLoading.value = false
  }
}

async function stopRun(record: PerformanceRunItem) {
  if (!isActiveStatus(record.status)) return
  stoppingRunId.value = record.id
  try {
    await performanceApi.stopRun(record.id)
    message.success(t('performance.msg.stop_success'))
    await loadRuns({ silent: true })
  } catch {
    message.error(t('performance.msg.stop_failed'))
  } finally {
    stoppingRunId.value = null
  }
}

async function setBaseline(record: PerformanceRunItem) {
  const test = tests.value.find((item) => item.id === record.performance_test_id)
  if (!test) return
  try {
    await performanceApi.setBaseline(test.id, record.id)
    message.success(t('performance.msg.baseline_saved'))
    await loadTests()
    if (selectedRun.value?.id === record.id) await loadBaselineComparison(record)
  } catch {
    message.error(t('performance.msg.baseline_failed'))
  }
}

async function clearBaseline(record: PerformanceTestItem) {
  try {
    await performanceApi.clearBaseline(record.id)
    message.success(t('performance.msg.baseline_cleared'))
    await loadTests()
    baselineComparison.value = null
  } catch {
    message.error(t('performance.msg.baseline_failed'))
  }
}

async function loadBaselineComparison(record: PerformanceRunItem) {
  baselineComparison.value = null
  const test = tests.value.find((item) => item.id === record.performance_test_id)
  if (!test?.baseline_run_id || test.baseline_run_id === record.id) return
  try {
    baselineComparison.value = await performanceApi.getBaselineComparison(record.id)
  } catch {
    baselineComparison.value = null
  }
}

async function loadResourceMetrics(record: PerformanceRunItem) {
  metricSamples.value = []
  try {
    metricSamples.value = await performanceApi.getMetrics(record.id)
    const sources = [...new Set(metricSamples.value.map((sample) => sample.source).filter(Boolean))]
    if (!sources.includes(metricSource.value)) metricSource.value = sources[0] || 'performance-worker'
    const available = resourceMetricOptions.value[0]?.value
    if (available && !resourceMetricOptions.value.some((option) => option.value === resourceMetric.value)) {
      resourceMetric.value = available
    }
  } catch {
    message.error(t('performance.msg.load_resource_metrics_failed'))
  }
}

async function openRunDetail(record: PerformanceRunItem) {
  selectedRun.value = record
  await Promise.all([loadBaselineComparison(record), loadResourceMetrics(record)])
  detailOpen.value = true
}

async function openRawResult(record: PerformanceRunItem) {
  try {
    const result = await performanceApi.getRawResult(record.id)
    window.open(result.url, '_blank', 'noopener,noreferrer')
  } catch {
    message.error(t('performance.msg.raw_result_failed'))
  }
}

async function exportRunJson(record: PerformanceRunItem) {
  await exportRun(record, 'json')
}

async function exportRunCsv(record: PerformanceRunItem) {
  await exportRun(record, 'csv')
}

async function exportRun(record: PerformanceRunItem, format: 'json' | 'csv') {
  exportingFormat.value = format
  try {
    const blob = format === 'json'
      ? await performanceApi.exportRunJson(record.id)
      : await performanceApi.exportRunCsv(record.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `performance-run-${record.id}-report.${format}`
    link.click()
    URL.revokeObjectURL(url)
    message.success(t('performance.msg.export_success'))
  } catch {
    message.error(t('performance.msg.export_failed'))
  } finally {
    exportingFormat.value = null
  }
}

function statusColor(status: string) {
  const colors: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    cancelling: 'warning',
    success: 'success',
    failed: 'error',
    cancelled: 'warning',
  }
  return colors[status] || 'default'
}

function isActiveStatus(status: string) {
  return status === 'pending' || status === 'running' || status === 'cancelling'
}

function progressPercent(record: PerformanceRunItem) {
  return Math.max(0, Math.min(100, Math.round(record.progress_percent ?? 0)))
}

function progressStatus(record: PerformanceRunItem) {
  return record.status === 'cancelling' ? 'exception' : 'active'
}

function progressLabel(record: PerformanceRunItem) {
  if (record.status === 'cancelling') return t('performance.status.cancelling')
  return `${progressPercent(record)}%`
}

function syncRunPolling() {
  const shouldPoll = !!projectId.value && runs.value.some((run) => isActiveStatus(run.status))
  if (shouldPoll && runPollingTimer === null) {
    runPollingTimer = window.setInterval(() => loadRuns({ silent: true }), 2000)
  } else if (!shouldPoll) {
    stopRunPolling()
  }
}

function stopRunPolling() {
  if (runPollingTimer !== null) {
    window.clearInterval(runPollingTimer)
    runPollingTimer = null
  }
}

function statusLabel(status: string) {
  return t(`performance.status.${status}`, status)
}

function nodeStatusLabel(status: string) {
  return t(`performance.node_status.${status}`, status)
}

function nodeBadgeStatus(status: string): 'success' | 'default' | 'error' | 'warning' {
  if (status === 'online') return 'success'
  if (status === 'draining') return 'warning'
  if (status === 'disabled') return 'default'
  return 'error'
}

function nodeName(id: number) {
  return nodes.value.find((node) => node.id === id)?.name || ''
}

function datasetName(id: number) {
  return datasets.value.find((dataset) => dataset.id === id)?.name || ''
}

function nodeCapacityLabel(node: PerformanceNodeItem) {
  const vus = t('performance.node_vus_limit', { value: node.max_vus ?? '∞' })
  const concurrency = t('performance.node_concurrency_limit', { value: node.max_concurrency ?? '∞' })
  return `${vus} · ${concurrency}`
}

function metricValue(value: unknown) {
  return typeof value === 'number' ? value : 0
}

function metricSourceLabel(source: string) {
  if (source === 'performance-worker') return t('performance.metric_source_worker')
  if (source === 'target-service-prometheus') return t('performance.metric_source_prometheus')
  if (source === 'atp-platform') return t('performance.metric_source_platform')
  return source
}

function metricLabel(key: string) {
  return resourceMetricKeys.includes(key) ? t(`performance.resource_metric_${key}`) : key
}

function handleMetricSourceChange() {
  resourceMetric.value = resourceMetricOptions.value[0]?.value || ''
}

function percentValue(value: unknown) {
  return typeof value === 'number' ? value * 100 : 0
}

function displayMetric(value: unknown, suffix = '') {
  if (typeof value !== 'number') return '-'
  return `${value.toFixed(value >= 100 ? 0 : 2)}${suffix}`
}

function numericMetric(value: unknown) {
  return typeof value === 'number' ? value : null
}

function displayPercent(value: unknown) {
  if (typeof value !== 'number') return '-'
  return `${(value * 100).toFixed(2)}%`
}

function formatDelta(value: number, suffix = '') {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(Math.abs(value) >= 100 ? 0 : 2)}${suffix}`
}

function formatDateLabel(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatDuration(value?: number | null) {
  if (!value) return '-'
  if (value < 1000) return `${value}ms`
  return `${(value / 1000).toFixed(1)}s`
}

function formatBaselineDelta(value: unknown) {
  if (typeof value !== 'number') return '-'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatBaselineMetric(metric: string, value: unknown) {
  if (typeof value !== 'number') return '-'
  if (metric === 'error_rate') return `${(value * 100).toFixed(2)}%`
  if (metric === 'p95_ms' || metric === 'p99_ms') return `${value.toFixed(2)}ms`
  return value.toFixed(2)
}

function baselineDirectionColor(direction: string) {
  return direction === 'improvement' ? 'success' : direction === 'regression' ? 'error' : 'default'
}

onMounted(loadProjects)
onBeforeUnmount(stopRunPolling)
</script>

<style scoped>
.performance-center {
  padding: 16px;
}

.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.header h2 {
  margin: 0;
}

.subtitle,
.muted {
  color: #8c8c8c;
}

.primary-text {
  font-weight: 600;
}

.node-strip {
  margin-bottom: 20px;
  padding: 14px 16px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fafafa;
}

.node-strip-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.node-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}

.node-card {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  background: #fff;
}

.node-card-online {
  border-color: #b7eb8f;
}

.node-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 5px;
}

.node-card-title strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-card-title :deep(.ant-tag) {
  margin-inline-start: auto;
  margin-inline-end: 0;
  font-size: 11px;
}

.node-card-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 10px;
  color: #595959;
  font-size: 12px;
}

.node-heartbeat {
  margin-top: 6px;
  font-size: 11px;
}

.node-error {
  margin-top: 8px;
  padding: 6px 8px;
  border: 1px solid #ffd591;
  border-radius: 4px;
  background: #fff7e6;
  color: #d46b08;
  font-size: 11px;
  line-height: 1.5;
  word-break: break-word;
}

.node-executors {
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

.node-card-actions {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.definition-meta {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

.definition-meta :deep(.ant-tag) {
  margin-inline-end: 0;
  font-size: 11px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.run-progress {
  min-width: 150px;
}

.run-progress :deep(.ant-progress) {
  margin-bottom: 0;
}

.detail-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.resource-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.resource-chart {
  height: 240px;
}

.threshold-gate {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fafafa;
}

.threshold-gate-label {
  color: #595959;
  font-size: 12px;
}

.threshold-gate span {
  color: #8c8c8c;
  font-size: 12px;
}

.threshold-gate-passed {
  border-color: #b7eb8f;
  background: #f6ffed;
  color: #389e0d;
}

.threshold-gate-failed {
  border-color: #ffa39e;
  background: #fff1f0;
  color: #cf1322;
}

.script-input {
  display: flex;
  width: 100%;
}

.script-input :deep(.ant-input) {
  flex: 1;
}

.form-alert {
  margin-bottom: 16px;
}

.target-metrics-editor {
  margin-top: 18px;
  padding: 14px;
  border: 1px solid #d6e4ff;
  border-radius: 8px;
  background: linear-gradient(135deg, #f7fbff 0%, #f0f5ff 100%);
}

.target-metrics-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.target-metrics-queries {
  padding-top: 4px;
}

.target-metric-row {
  display: grid;
  grid-template-columns: minmax(110px, 0.7fr) minmax(180px, 1.8fr) auto;
  gap: 8px;
  align-items: center;
  margin: 8px 0;
}

.field-hint {
  margin-top: 6px;
  color: #8c8c8c;
  font-size: 12px;
}

.stages-editor {
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fafafa;
}

.behavior-editor {
  margin: 12px 0 18px;
}

.steps-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.behavior-step {
  margin-bottom: 10px;
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  background: #fff;
}

.behavior-step-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.behavior-step-row {
  margin-top: 10px;
}

.stage-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.section-title {
  margin: 24px 0 12px;
  font-size: 16px;
  font-weight: 600;
}

.insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr);
  gap: 16px;
  margin-top: 20px;
}

.insight-panel {
  min-width: 0;
}

.trend-chart {
  width: 100%;
  height: 280px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
}

.delta-good {
  color: #389e0d;
  font-weight: 600;
}

.delta-bad {
  color: #cf1322;
  font-weight: 600;
}

.detail-block {
  margin-top: 16px;
}

.section-label {
  margin-bottom: 6px;
  color: #595959;
  font-weight: 600;
}

.json-preview {
  max-height: 280px;
  margin: 0;
  padding: 10px 12px;
  overflow: auto;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  background: #fafafa;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1080px) {
  .insight-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .detail-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .threshold-gate {
    flex-wrap: wrap;
  }

  .target-metric-row {
    grid-template-columns: 1fr;
  }
}
</style>
