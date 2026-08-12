<template>
  <div>
    <a-page-header :title="t('run.detail_title')" @back="router.back()">
      <template #extra>
        <a-space>
          <a-button size="small" :loading="exportingHtml" @click="handleExportHtml">
            <FileTextOutlined /> {{ exportingHtml ? t('run.generating') : t('run.export_html') }}
          </a-button>
          <a-button size="small" :loading="exportingPdf" @click="handleExportPdf">
            <FilePdfOutlined /> {{ exportingPdf ? t('run.generating_pdf') : t('run.export_pdf') }}
          </a-button>
          <a-button
            v-if="canCreateBug && run && (run.status === 'failed' || run.status === 'error')"
            size="small"
            type="primary"
            danger
            @click="openBugModal"
          >
            <BugOutlined /> {{ t('run.create_bug') }}
          </a-button>
          <a-tag v-if="run" :color="statusColor(run.status)" style="font-size: 14px">
            {{ run.status }}
          </a-tag>
          <a-spin v-if="isRunning" size="small" />
        </a-space>
      </template>
    </a-page-header>

    <a-spin :spinning="loading">
      <template v-if="run">
        <!-- 基本信息 -->
        <a-descriptions bordered :column="4" size="small" style="margin-bottom: 24px">
          <a-descriptions-item :label="t('run.labels.run_id')">{{ run.id }}</a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.case_id')">{{ run.case_id }}</a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.trace_id')" :span="2">
            <code>{{ run.trace_id || '-' }}</code>
            <a
              v-if="jaegerSearchUrl"
              :href="jaegerSearchUrl"
              target="_blank"
              rel="noopener noreferrer"
              style="margin-left: 8px"
            >
              <LinkOutlined /> {{ t('run.open_in_jaeger') }}
            </a>
          </a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.environment')">{{ run.environment ?? '-' }}</a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.duration')">
            {{ run.duration_ms != null ? `${run.duration_ms} ms` : (isRunning ? t('common.running') : '-') }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.triggered_at')" :span="2">
            {{ run.created_at?.slice(0, 19).replace('T', ' ') }}
          </a-descriptions-item>
          <a-descriptions-item v-if="run.parent_run_id != null" :label="t('run.labels.parent_run')">
            <router-link :to="{ name: 'run-detail', params: { id: run.parent_run_id } }">#{{ run.parent_run_id }}</router-link>
          </a-descriptions-item>
          <a-descriptions-item v-if="run.iteration_index != null" :label="t('run.labels.iteration')">
            <a-tag color="blue">#{{ run.iteration_index }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item v-if="run.iteration_data" :label="t('run.labels.iteration_data')" :span="2">
            <code style="font-size:12px">{{ JSON.stringify(run.iteration_data) }}</code>
          </a-descriptions-item>
          <a-descriptions-item v-if="isParameterizedParent" :label="t('run.labels.iteration_summary')" :span="2">
            <a-tag color="green">{{ t('run.iteration.passed') }}: {{ iterationStats.passed }}</a-tag>
            <a-tag color="red">{{ t('run.iteration.failed') }}: {{ iterationStats.failed }}</a-tag>
            <a-tag v-if="iterationStats.error > 0" color="orange">{{ t('run.iteration.error') }}: {{ iterationStats.error }}</a-tag>
            <a-tag>{{ t('run.iteration.total') }}: {{ iterationStats.total }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item v-if="run.error_message" :label="t('run.labels.error_message')" :span="2">
            <span style="color: #ff4d4f">
              <template v-if="run.error_message.length > 500 && !expandedErrors.has('run')">
                {{ run.error_message.slice(0, 500) }}...
                <a-button type="link" size="small" @click="expandedErrors.add('run')">{{ t('run.expand_all') }}</a-button>
              </template>
              <template v-else>
                {{ run.error_message }}
                <a-button v-if="run.error_message.length > 500" type="link" size="small" @click="expandedErrors.delete('run')">{{ t('run.collapse') }}</a-button>
              </template>
            </span>
          </a-descriptions-item>
          <a-descriptions-item v-if="bugInfo" :label="t('run.labels.linked_bug')" :span="2">
            <a :href="bugInfo.bug_url" target="_blank">
              <LinkOutlined /> {{ bugInfo.bug_id }}
            </a>
            <span style="margin-left: 8px; color: #666">{{ bugInfo.title }}</span>
            <a-tag v-if="bugInfo.status" style="margin-left: 8px">{{ bugInfo.status }}</a-tag>
            <a-button size="small" type="link" :loading="bugStatusRefreshing" @click="refreshBugStatus">{{ t('run.msg.refresh_status') }}</a-button>
          </a-descriptions-item>
        </a-descriptions>

        <section v-if="androidMatrixSummary" class="device-matrix-summary">
          <div class="device-matrix-summary-header">
            <div>
              <div class="section-title">{{ t('run.device_matrix.title') }}</div>
              <div class="section-subtitle">{{ t('run.device_matrix.subtitle') }}</div>
            </div>
            <a-space wrap>
              <a-tag>{{ t('run.device_matrix.total') }}: {{ androidMatrixSummary.total }}</a-tag>
              <a-tag color="green">{{ t('run.device_matrix.passed') }}: {{ androidMatrixSummary.passed }}</a-tag>
              <a-tag v-if="androidMatrixSummary.failed > 0" color="red">{{ t('run.device_matrix.failed') }}: {{ androidMatrixSummary.failed }}</a-tag>
              <a-tag v-if="androidMatrixSummary.error > 0" color="orange">{{ t('run.device_matrix.error') }}: {{ androidMatrixSummary.error }}</a-tag>
            </a-space>
          </div>
          <div class="device-matrix-table-wrap">
            <table class="device-matrix-table">
              <thead>
                <tr>
                  <th>{{ t('run.device_matrix.device') }}</th>
                  <th>{{ t('run.device_matrix.status') }}</th>
                  <th>{{ t('run.device_matrix.duration') }}</th>
                  <th>{{ t('run.device_matrix.error_message') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in androidMatrixSummary.results" :key="`${item.run_id ?? item.index}-${item.serial}`">
                  <td>
                    <router-link v-if="item.run_id" :to="{ name: 'run-detail', params: { id: item.run_id } }">
                      {{ item.serial || t('run.device_matrix.unknown_device') }}
                    </router-link>
                    <span v-else>{{ item.serial || t('run.device_matrix.unknown_device') }}</span>
                  </td>
                  <td><a-tag :color="statusColor(item.status)">{{ item.status }}</a-tag></td>
                  <td>{{ item.duration_ms != null ? `${item.duration_ms} ms` : '-' }}</td>
                  <td class="device-matrix-error">{{ item.error || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="investigation-panel">
          <div class="investigation-header">
            <div>
              <div class="section-title">{{ t('run.investigation.title') }}</div>
              <div class="section-subtitle">{{ t('run.investigation.subtitle') }}</div>
            </div>
            <a-space wrap>
              <a-button
                v-if="canGenerateFailureDiagnosis"
                size="small"
                :loading="failureDiagnosisLoading"
                @click="handleGenerateFailureDiagnosis"
              >
                <BulbOutlined /> {{ failureDiagnosis ? t('run.investigation.regenerate_failure_diagnosis') : t('run.investigation.generate_failure_diagnosis') }}
              </a-button>
              <a-button v-if="jaegerSearchUrl" size="small" :href="jaegerSearchUrl" target="_blank">
                <LinkOutlined /> {{ t('run.open_in_jaeger') }}
              </a-button>
              <a-button
                v-if="canCreateBug && run && (run.status === 'failed' || run.status === 'error')"
                size="small"
                danger
                @click="openBugModal"
              >
                <BugOutlined /> {{ t('run.create_bug') }}
              </a-button>
            </a-space>
          </div>

          <a-row :gutter="[12, 12]" class="investigation-metrics">
            <a-col :xs="12" :md="6">
              <button class="investigation-card" type="button" @click="focusFirstProblemStep">
                <span class="investigation-icon investigation-icon-error"><WarningOutlined /></span>
                <span class="investigation-card-body">
                  <span class="investigation-value">{{ failedOrErrorSteps.length }}</span>
                  <span class="investigation-label">{{ t('run.investigation.problem_steps') }}</span>
                </span>
              </button>
            </a-col>
            <a-col :xs="12" :md="6">
              <button class="investigation-card" type="button" @click="focusFirstScreenshotStep">
                <span class="investigation-icon investigation-icon-primary"><CameraOutlined /></span>
                <span class="investigation-card-body">
                  <span class="investigation-value">{{ screenshotCount }}</span>
                  <span class="investigation-label">{{ t('run.investigation.screenshots') }}</span>
                </span>
              </button>
            </a-col>
            <a-col :xs="12" :md="6">
              <a :class="['investigation-card', { 'is-disabled': !jaegerSearchUrl }]" :href="jaegerSearchUrl || undefined" target="_blank">
                <span class="investigation-icon investigation-icon-info"><LinkOutlined /></span>
                <span class="investigation-card-body">
                  <span class="investigation-value">{{ run.trace_id ? t('common.yes') : t('common.no') }}</span>
                  <span class="investigation-label">{{ t('run.investigation.trace') }}</span>
                </span>
              </a>
            </a-col>
            <a-col :xs="12" :md="6">
              <button class="investigation-card" type="button" @click="focusHealing">
                <span class="investigation-icon investigation-icon-warning"><BulbOutlined /></span>
                <span class="investigation-card-body">
                  <span class="investigation-value">{{ diagnosisStatusText }}</span>
                  <span class="investigation-label">{{ t('run.investigation.ai_diagnosis') }}</span>
                </span>
              </button>
            </a-col>
          </a-row>

          <a-row :gutter="[12, 12]" class="investigation-details">
            <a-col :xs="24" :md="12">
              <div class="investigation-block">
                <div class="block-title">{{ t('run.investigation.error_summary') }}</div>
                <pre class="error-snippet">{{ primaryErrorSummary }}</pre>
              </div>
            </a-col>
            <a-col :xs="24" :md="12">
              <div class="investigation-block">
                <div class="block-title">{{ t('run.investigation.problem_step_list') }}</div>
                <a-empty
                  v-if="failedOrErrorSteps.length === 0"
                  :description="t('run.investigation.no_problem_steps')"
                  :image="Empty.PRESENTED_IMAGE_SIMPLE"
                />
                <div v-else class="problem-step-list">
                  <button
                    v-for="step in failedOrErrorSteps.slice(0, 5)"
                    :key="step.step_index"
                    class="problem-step-item"
                    type="button"
                    @click="focusStep(step.step_index)"
                  >
                    <span class="problem-step-title">#{{ step.step_index + 1 }} {{ step.name }}</span>
                    <a-tag :color="statusColor(step.status)">{{ step.status }}</a-tag>
                  </button>
                </div>
              </div>
            </a-col>
          </a-row>

          <div v-if="failureDiagnosis || canGenerateFailureDiagnosis" class="failure-diagnosis-card">
            <div class="failure-diagnosis-header">
              <div>
                <div class="block-title">{{ t('run.investigation.failure_diagnosis') }}</div>
                <div class="failure-diagnosis-meta">
                  <a-tag v-if="failureDiagnosis" :color="failureDiagnosis.source === 'llm' ? 'green' : 'blue'">
                    {{ t(`run.investigation.failure_diagnosis_source_${failureDiagnosis.source}`) }}
                  </a-tag>
                  <span v-if="failureDiagnosis">
                    {{ t('run.investigation.failure_diagnosis_evidence', {
                      steps: failureDiagnosis.failed_step_count,
                      screenshots: failureDiagnosis.screenshot_count,
                    }) }}
                  </span>
                </div>
              </div>
              <a-button
                v-if="canGenerateFailureDiagnosis"
                size="small"
                :loading="failureDiagnosisLoading"
                @click="handleGenerateFailureDiagnosis"
              >
                {{ failureDiagnosis ? t('common.refresh') : t('run.investigation.generate_failure_diagnosis') }}
              </a-button>
            </div>
            <pre v-if="failureDiagnosis?.summary" class="failure-diagnosis-text">{{ failureDiagnosis.summary }}</pre>
            <a-empty
              v-else
              :description="t('run.investigation.no_failure_diagnosis')"
              :image="Empty.PRESENTED_IMAGE_SIMPLE"
            />
            <div v-if="failureDiagnosis?.repair_suggestions?.length" class="repair-suggestion-list">
              <div class="repair-suggestion-title">{{ t('run.investigation.repair_suggestions') }}</div>
              <div
                v-for="suggestion in failureDiagnosis.repair_suggestions"
                :key="`${suggestion.step_index}-${suggestion.suggestion_type}`"
                class="repair-suggestion-item"
              >
                <div class="repair-suggestion-head">
                  <span>#{{ suggestion.step_index + 1 }} {{ suggestion.step_name }}</span>
                  <a-tag color="geekblue">
                    {{ t(`run.investigation.repair_type_${suggestion.suggestion_type}`) }}
                  </a-tag>
                </div>
                <div class="repair-suggestion-body">{{ suggestion.suggested_change }}</div>
                <div class="repair-suggestion-meta">
                  {{ t('run.investigation.repair_target') }}: {{ suggestion.target }}
                  <span v-if="suggestion.evidence"> · {{ t('run.investigation.repair_evidence') }}: {{ suggestion.evidence }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 步骤统计 -->
        <div class="steps-header">
          <strong>{{ t('run.labels.steps') }}</strong>
          <span class="steps-summary">
            {{ t('run.summary.total_steps', { count: steps.length }) }}
            <template v-if="stepStats.passed > 0">
              <span class="stat-passed">{{ t('run.summary.passed', { count: stepStats.passed }) }}</span>
            </template>
            <template v-if="stepStats.failed > 0">
              <span class="stat-failed">{{ t('run.summary.failed', { count: stepStats.failed }) }}</span>
            </template>
            <template v-if="stepStats.error > 0">
              <span class="stat-error">{{ t('run.summary.error', { count: stepStats.error }) }}</span>
            </template>
            <template v-if="stepStats.skipped > 0">
              <span class="stat-skipped">{{ t('run.summary.skipped', { count: stepStats.skipped }) }}</span>
            </template>
          </span>
        </div>

        <!-- 步骤进度条 -->
        <div v-if="steps.length" class="steps-progress">
          <div
            v-for="step in steps"
            :key="step.step_index"
            :class="['progress-segment', `segment-${step.status}`]"
            :style="{ flex: Math.max(step.duration_ms ?? 1, 1) }"
            :title="`#${step.step_index + 1} ${step.name} (${step.status}, ${step.duration_ms ?? 0}ms)`"
          />
        </div>

        <!-- 运行级 AI 诊断（iter3 多 step 综合分析）-->
        <div v-if="runHealing" class="run-healing-card">
          <a-divider orientation="left" style="margin: 16px 0 8px">
            <BulbOutlined />
            <span style="margin-left: 6px">{{ t('run.healing.run_title') }}</span>
            <a-tag :color="healingTagColor(runHealing.status)" style="margin-left: 8px">
              {{ healingStatusLabel(runHealing.status) }}
            </a-tag>
            <a-tag
              v-if="runHealing.cache_hit && runHealing.status === 'done'"
              color="purple"
              style="margin-left: 4px"
            >
              ⚡ {{ t('run.healing.cache_hit') }}
            </a-tag>
          </a-divider>
          <div v-if="runHealing.status === 'pending'" class="healing-pending">
            <LoadingOutlined /> <span style="margin-left: 6px">{{ t('run.healing.run_diagnosing') }}</span>
          </div>
          <pre
            v-else-if="runHealing.status === 'done' && runHealing.suggestion"
            class="healing-text"
          >{{ runHealing.suggestion }}</pre>
          <a-empty
            v-else-if="runHealing.status === 'failed'"
            :description="t('run.healing.run_failed_fallback')"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
          />
          <a-empty
            v-else-if="runHealing.status === 'skipped'"
            :description="runHealing.suggestion === 'daily-limit-reached'
              ? t('run.healing.daily_limit_reached')
              : t('run.healing.run_skipped_too_few_failures')"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
          />
        </div>

        <!-- 录像播放 -->
        <div v-if="videoUrl" class="video-section">
          <a-divider orientation="left" style="margin: 16px 0 12px">
            <VideoCameraOutlined /> {{ t('run.labels.video') }}
          </a-divider>
          <video
            :src="videoUrl"
            controls
            class="video-player"
          >
            {{ t('run.no_video_support') }}
          </video>
        </div>

        <a-collapse
          v-if="steps.length"
          :activeKey="expandedKeys"
          @change="onCollapseChange"
        >
          <a-collapse-panel
            v-for="step in steps"
            :key="step.step_index"
            :class="{ 'step-failed': step.status === 'failed', 'step-error': step.status === 'error' }"
            :data-run-step="step.step_index"
          >
            <template #header>
              <div class="step-panel-header">
                <span class="step-number">#{{ step.step_index + 1 }}</span>
                <span class="step-name">{{ step.name }}</span>
              </div>
            </template>
            <template #extra>
              <a-space>
                <a-tag :color="statusColor(step.status)">{{ step.status }}</a-tag>
                <span v-if="step.duration_ms != null" class="step-duration">
                  {{ step.duration_ms }} ms
                </span>
              </a-space>
            </template>

            <!-- 错误信息优先展示 -->
            <a-alert
              v-if="step.error_message"
              type="error"
              style="margin-bottom: 12px"
              show-icon
            >
              <template #message>
                <template v-if="step.error_message.length > 500 && !expandedErrors.has(`step-${step.step_index}`)">
                  {{ step.error_message.slice(0, 500) }}...
                <a-button type="link" size="small" @click="expandedErrors.add(`step-${step.step_index}`)">{{ t('run.expand_all') }}</a-button>
                </template>
                <template v-else>
                  {{ step.error_message }}
                  <a-button v-if="step.error_message.length > 500" type="link" size="small" @click="expandedErrors.delete(`step-${step.step_index}`)">{{ t('run.collapse') }}</a-button>
                </template>
              </template>
            </a-alert>

            <!-- AI 诊断建议（P3.A）-->
            <a-collapse
              v-if="step.healing_status"
              class="healing-panel"
              data-run-healing="step"
              ghost
              :bordered="false"
              style="margin-bottom: 12px"
            >
              <a-collapse-panel :key="`healing-${step.step_index}`">
                <template #header>
                  <span class="healing-title">
                    <BulbOutlined />
                    <span style="margin-left: 6px">{{ t('run.healing.title') }}</span>
                    <a-tag :color="healingTagColor(step.healing_status)" style="margin-left: 8px">
                      {{ healingStatusLabel(step.healing_status) }}
                    </a-tag>
                    <a-tag
                      v-if="step.healing_cache_hit && step.healing_status === 'done'"
                      color="purple"
                      style="margin-left: 4px"
                    >
                      ⚡ {{ t('run.healing.cache_hit') }}
                    </a-tag>
                  </span>
                </template>
                <div v-if="step.healing_status === 'pending'" class="healing-body healing-pending">
                  <LoadingOutlined /> <span style="margin-left: 6px">{{ t('run.healing.diagnosing') }}</span>
                </div>
                <pre
                  v-else-if="step.healing_status === 'done' && step.healing_suggestion"
                  class="healing-text"
                >{{ step.healing_suggestion }}</pre>
                <!-- iter3 反馈按钮：仅 done 态显示 -->
                <div
                  v-if="step.healing_status === 'done' && step.healing_suggestion"
                  class="healing-feedback-row"
                >
                  <template v-if="step.healing_feedback">
                    <a-tag :color="step.healing_feedback === 'adopted' ? 'green' : 'red'">
                      {{ step.healing_feedback === 'adopted'
                        ? t('run.healing.feedback_adopted')
                        : t('run.healing.feedback_rejected') }}
                    </a-tag>
                    <span class="feedback-thanks">{{ t('run.healing.feedback_thanks') }}</span>
                  </template>
                  <template v-else>
                    <a-button
                      size="small"
                      type="primary"
                      ghost
                      @click="onHealingFeedback(step, 'adopted')"
                    >
                      ✓ {{ t('run.healing.adopt') }}
                    </a-button>
                    <a-button
                      size="small"
                      danger
                      @click="onHealingFeedback(step, 'rejected')"
                    >
                      ✗ {{ t('run.healing.reject') }}
                    </a-button>
                  </template>
                  <a-button
                    v-if="canApplyHealingPatch"
                    size="small"
                    :loading="healingPatchLoading && healingPatchStep?.step_index === step.step_index"
                    @click="openHealingPatchPreview(step)"
                  >
                    <BulbOutlined /> {{ t('run.healing.preview_patch') }}
                  </a-button>
                </div>
                <a-empty
                  v-else-if="step.healing_status === 'failed'"
                  :description="t('run.healing.failed_fallback')"
                  :image="Empty.PRESENTED_IMAGE_SIMPLE"
                />
                <a-empty
                  v-else-if="step.healing_status === 'skipped'"
                  :description="step.healing_suggestion === 'daily-limit-reached'
                    ? t('run.healing.daily_limit_reached')
                    : t('run.healing.skipped_no_config')"
                  :image="Empty.PRESENTED_IMAGE_SIMPLE"
                />
              </a-collapse-panel>
            </a-collapse>

            <!-- 截图展示 -->
            <div v-if="step.screenshot_url" class="screenshot-section">
              <div class="panel-label">
                <CameraOutlined /> {{ t('run.labels.screenshot') }}
              </div>
              <a-image
                :src="step.screenshot_url"
                :width="480"
                :preview="{ src: step.screenshot_url }"
                class="step-screenshot"
                :fallback="fallbackImage"
              />
            </div>

            <a-row :gutter="16" style="margin-top: 12px">
              <!-- 请求 -->
              <a-col :span="12">
                <div class="panel-label">{{ t('run.labels.request') }}</div>
                <pre class="code-block">{{ formatJson(step.request_data) }}</pre>
              </a-col>
              <!-- 响应 -->
              <a-col :span="12">
                <div class="panel-label">{{ t('run.labels.response') }}</div>
                <pre class="code-block">{{ formatJson(step.response_data) }}</pre>
              </a-col>
            </a-row>
          </a-collapse-panel>
        </a-collapse>

        <a-empty v-else :description="t('run.empty_steps')" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
      </template>
    </a-spin>

    <!-- 创建缺陷 Modal -->
    <a-modal
      v-model:open="bugModalOpen"
      :title="bugModalTitle"
      :ok-text="bugModalOkText"
      :cancel-text="t('common.cancel')"
      :confirm-loading="bugCreating"
      @ok="confirmCreateBug"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('run.bug.mode')">
          <a-radio-group v-model:value="bugMode">
            <a-radio-button value="create">{{ t('run.bug.mode_create') }}</a-radio-button>
            <a-radio-button value="link">{{ t('run.bug.mode_link') }}</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('run.bug.tracker')">
          <a-select
            v-model:value="bugTrackerId"
            :placeholder="t('common.search')"
            style="width: 100%"
            :options="bugTrackerOptions"
            :loading="bugTrackerLoading"
          />
        </a-form-item>
        <template v-if="bugMode === 'create'">
        <a-form-item :label="t('run.bug.related_step')">
          <a-select
            v-model:value="bugStepIndex"
            :placeholder="t('run.bug.no_step')"
            allow-clear
            style="width: 100%"
          >
            <a-select-option
              v-for="s in failedSteps"
              :key="s.step_index"
              :value="s.step_index"
            >
              #{{ s.step_index + 1 }} {{ s.name }} ({{ s.status }})
            </a-select-option>
          </a-select>
        </a-form-item>
        </template>
        <template v-else>
          <a-form-item :label="t('run.bug.existing_bug_id')" required>
            <a-input v-model:value="linkedBugId" placeholder="BUG-123" />
          </a-form-item>
          <a-form-item :label="t('run.bug.existing_bug_url')">
            <a-input v-model:value="linkedBugUrl" placeholder="https://..." />
          </a-form-item>
          <a-form-item :label="t('run.bug.existing_bug_title')">
            <a-input v-model:value="linkedBugTitle" :placeholder="caseDisplayName" />
          </a-form-item>
          <a-form-item :label="t('run.bug.existing_bug_status')">
            <a-input v-model:value="linkedBugStatus" placeholder="open" />
          </a-form-item>
        </template>
      </a-form>
      <a-divider v-if="bugMode === 'create' && bugPreviewTitle" style="margin: 12px 0 8px">{{ t('run.bug.preview') }}</a-divider>
      <div v-if="bugMode === 'create' && bugPreviewTitle" class="bug-preview">
        <div class="bug-preview-label">{{ t('run.bug.title') }}</div>
        <div class="bug-preview-value">{{ bugPreviewTitle }}</div>
        <div class="bug-preview-label" style="margin-top: 8px">{{ t('run.bug.desc') }}</div>
        <pre class="bug-preview-value bug-preview-desc">{{ bugPreviewDesc }}</pre>
      </div>
    </a-modal>

    <!-- AI 自愈 Patch 预览 -->
    <a-modal
      v-model:open="healingPatchModalOpen"
      :title="t('run.healing.patch_preview_title')"
      :ok-text="t('run.healing.apply_and_regress')"
      :cancel-text="t('common.cancel')"
      :ok-button-props="{ disabled: !healingPatchPreview?.accepted }"
      :confirm-loading="healingPatchApplying"
      width="720px"
      @ok="confirmApplyHealingPatch"
    >
      <a-alert
        v-if="healingPatchPreview"
        :type="healingPatchPreview.accepted ? 'success' : 'warning'"
        :message="healingPatchPreview.accepted
          ? t('run.healing.patch_accepted')
          : t('run.healing.patch_rejected')"
        show-icon
      />
      <div v-if="healingPatchPreview?.reasons.length" class="healing-patch-section">
        <div class="bug-preview-label">{{ t('run.healing.patch_reasons') }}</div>
        <ul class="healing-patch-reasons">
          <li v-for="reason in healingPatchPreview.reasons" :key="reason">{{ reason }}</li>
        </ul>
      </div>
      <div v-if="healingPatchPreview?.normalized_patch" class="healing-patch-section">
        <div class="bug-preview-label">{{ t('run.healing.normalized_patch') }}</div>
        <pre class="bug-preview-value bug-preview-desc">{{ formatJson(healingPatchPreview.normalized_patch) }}</pre>
      </div>
      <div v-if="healingPatchPreview?.preview_config" class="healing-patch-section">
        <div class="bug-preview-label">{{ t('run.healing.preview_config') }}</div>
        <pre class="bug-preview-value bug-preview-desc">{{ formatJson(healingPatchPreview.preview_config) }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Empty, message } from 'ant-design-vue'
import { VideoCameraOutlined, CameraOutlined, FileTextOutlined, FilePdfOutlined, BugOutlined, LinkOutlined, BulbOutlined, LoadingOutlined, WarningOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { runApi, bugTrackerApi, tracingApi, aiHealingPatchApi, type BugLinkInfo, type BugTrackerItem, type FailureDiagnosisResult, type HealingPatchPreviewResult, type RunDetailItem, type RunStepItem } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { createRunWebSocket, type WsMessage } from '@/utils/websocket'
import {
  computeExpandedKeys as computeExpandedStepKeys,
  countScreenshotSteps,
  failedOrErrorSteps as pickFailedOrErrorSteps,
  healingTagColor as computeHealingTagColor,
  isParameterizedParent as computeIsParameterizedParent,
  normalizeFailureDiagnosis,
  normalizeRunHealing,
  primaryErrorText,
  readIterationStats,
  runStatusColor as computeRunStatusColor,
  summarizeStepStatuses,
  truncateText,
  type RunHealingPayload,
} from '@/utils/runDetail'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const auth = useAuthStore()
const runId = Number(route.params.runId)

const run = ref<RunDetailItem | null>(null)
const steps = ref<RunStepItem[]>([])

type AndroidMatrixResult = {
  run_id?: number
  index: number
  serial: string
  status: string
  duration_ms: number | null
  error: string | null
}
const loading = ref(false)
const expandedKeys = ref<number[]>([])
const exportingHtml = ref(false)
const jaegerUiUrl = ref('')
const failureDiagnosisLoading = ref(false)

const jaegerSearchUrl = computed(() => {
  const tid = run.value?.trace_id
  const base = jaegerUiUrl.value
  if (!tid || !base) return ''
  const tags = encodeURIComponent(JSON.stringify({ 'app.trace_id': tid }))
  return `${base.replace(/\/$/, '')}/search?tags=${tags}`
})
const exportingPdf = ref(false)
const bugModalOpen = ref(false)
const bugMode = ref<'create' | 'link'>('create')
const bugTrackerId = ref<number | undefined>(undefined)
const bugStepIndex = ref<number | undefined>(undefined)
const linkedBugId = ref('')
const linkedBugUrl = ref('')
const linkedBugTitle = ref('')
const linkedBugStatus = ref('open')
const bugTrackerOptions = ref<Array<{ label: string; value: number }>>([])
const bugTrackerLoading = ref(false)
const bugCreating = ref(false)
const bugStatusRefreshing = ref(false)
const healingPatchModalOpen = ref(false)
const healingPatchLoading = ref(false)
const healingPatchApplying = ref(false)
const healingPatchStep = ref<RunStepItem | null>(null)
const healingPatchPreview = ref<HealingPatchPreviewResult | null>(null)
const expandedErrors = reactive(new Set<string>())
let wsHandle: ReturnType<typeof createRunWebSocket> | null = null

const fallbackImage = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjOTk5IiBmb250LXNpemU9IjE0Ij7miKrlm77liqDovb3lpLHotKU8L3RleHQ+PC9zdmc+'

const isRunning = computed(() => run.value?.status === 'running' || run.value?.status === 'pending')
const canCreateBug = computed(() => ['admin', 'engineer'].includes(auth.user?.role ?? ''))
const canApplyHealingPatch = computed(() => ['admin', 'engineer'].includes(auth.user?.role ?? ''))

const isParameterizedParent = computed(() =>
  computeIsParameterizedParent(run.value?.result_summary as Record<string, unknown> | undefined),
)
const iterationStats = computed(() =>
  readIterationStats(run.value?.result_summary as Record<string, unknown> | undefined),
)

const androidMatrixSummary = computed(() => {
  const summary = run.value?.result_summary as Record<string, unknown> | undefined
  if (!summary || (!Array.isArray(summary.device_matrix_results) && !Array.isArray(summary.device_matrix_variants))) {
    return null
  }

  let rawItems: unknown[] = []
  if (Array.isArray(summary.device_matrix_results)) {
    rawItems = summary.device_matrix_results
  } else if (Array.isArray(summary.device_matrix_variants)) {
    rawItems = summary.device_matrix_variants
  }
  const results: AndroidMatrixResult[] = rawItems.map((raw, index) => {
    const item = raw && typeof raw === 'object' ? raw as Record<string, unknown> : {}
    return {
      run_id: typeof item.run_id === 'number' ? item.run_id : undefined,
      index: typeof item.index === 'number' ? item.index : index,
      serial: typeof item.serial === 'string' ? item.serial : '',
      status: typeof item.status === 'string' ? item.status : 'pending',
      duration_ms: typeof item.duration_ms === 'number' ? item.duration_ms : null,
      error: typeof item.error === 'string' ? item.error : null,
    }
  })
  const count = (key: 'passed' | 'failed' | 'error', fallback: number) =>
    typeof summary[`device_matrix_${key}`] === 'number'
      ? Number(summary[`device_matrix_${key}`])
      : fallback

  return {
    total: typeof summary.device_matrix_total === 'number' ? summary.device_matrix_total : results.length,
    passed: count('passed', results.filter(item => item.status === 'passed').length),
    failed: count('failed', results.filter(item => item.status === 'failed').length),
    error: count('error', results.filter(item => item.status === 'error').length),
    results,
  }
})

const stepStats = computed(() => summarizeStepStatuses(steps.value))

const failedOrErrorSteps = computed(() => pickFailedOrErrorSteps(steps.value))

const screenshotCount = computed(() => countScreenshotSteps(steps.value))

const canGenerateFailureDiagnosis = computed(() =>
  Boolean(run.value && (run.value.status === 'failed' || run.value.status === 'error' || failedOrErrorSteps.value.length > 0)),
)

const failureDiagnosis = computed<FailureDiagnosisResult | null>(() =>
  normalizeFailureDiagnosis(run.value?.result_summary?.failure_diagnosis),
)

const primaryErrorSummary = computed(
  () => primaryErrorText(steps.value, run.value?.error_message) ?? t('run.investigation.no_error_summary'),
)

function statusColor(status: string) {
  return computeRunStatusColor(status)
}

function healingTagColor(status?: string | null) {
  return computeHealingTagColor(status)
}

function healingStatusLabel(status?: string | null) {
  if (!status) return ''
  const key = `run.healing.status_${status}`
  return t(key)
}

async function onHealingFeedback(step: RunStepItem, action: 'adopted' | 'rejected') {
  if (!run.value || step.id == null) return
  try {
    await runApi.submitHealingFeedback(run.value.id, step.id, action)
    const idx = steps.value.findIndex(s => s.step_index === step.step_index)
    if (idx >= 0) {
      steps.value[idx] = {
        ...steps.value[idx],
        healing_feedback: action,
        healing_feedback_at: new Date().toISOString(),
      }
    }
    message.success(t('run.healing.feedback_thanks'))
  } catch {
    // axios 拦截器已弹出错误
  }
}

async function handleGenerateFailureDiagnosis() {
  if (!run.value) return
  failureDiagnosisLoading.value = true
  try {
    const diagnosis = await runApi.generateFailureDiagnosis(run.value.id)
    run.value.result_summary = {
      ...(run.value.result_summary || {}),
      failure_diagnosis: diagnosis,
    }
    message.success(t('run.investigation.failure_diagnosis_generated'))
  } catch {
    message.error(t('run.investigation.failure_diagnosis_failed'))
  } finally {
    failureDiagnosisLoading.value = false
  }
}

async function openHealingPatchPreview(step: RunStepItem) {
  if (!run.value || !step.healing_suggestion || !canApplyHealingPatch.value) return
  healingPatchStep.value = step
  healingPatchPreview.value = null
  healingPatchLoading.value = true
  try {
    healingPatchPreview.value = await aiHealingPatchApi.preview({
      case_id: run.value.case_id,
      raw_suggestion: step.healing_suggestion,
    })
    healingPatchModalOpen.value = true
  } catch {
    // axios 拦截器已弹出错误
  } finally {
    healingPatchLoading.value = false
  }
}

async function confirmApplyHealingPatch() {
  if (!run.value || !healingPatchStep.value?.healing_suggestion || !healingPatchPreview.value?.accepted) return
  healingPatchApplying.value = true
  try {
    const result = await aiHealingPatchApi.apply({
      case_id: run.value.case_id,
      raw_suggestion: healingPatchStep.value.healing_suggestion,
      trigger_regression: true,
      source_run_id: run.value.id,
      source_step_id: healingPatchStep.value.id ?? null,
    })
    healingPatchModalOpen.value = false
    message.success(
      result.regression_run_id
        ? t('run.healing.patch_applied_with_regression', { id: result.regression_run_id })
        : t('run.healing.patch_applied'),
    )
    if (result.regression_run_id) {
      router.push({ name: 'run-detail', params: { runId: result.regression_run_id } })
    }
  } catch {
    // axios 拦截器已弹出错误
  } finally {
    healingPatchApplying.value = false
  }
}

function formatJson(data: Record<string, unknown> | null | undefined) {
  if (data == null) return '-'
  return JSON.stringify(data, null, 2)
}

function computeExpandedKeys(stepList: RunStepItem[]) {
  return computeExpandedStepKeys(stepList)
}

function errorMessage(error: unknown, fallback = '') {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

// a-collapse 的 Key 是 string | number；本面板 key 恒为步骤序号 number
function onCollapseChange(keys: string | number | (string | number)[]) {
  expandedKeys.value = (Array.isArray(keys) ? keys : [keys]).map(Number)
}

function focusStep(stepIndex: number) {
  if (!expandedKeys.value.includes(stepIndex)) {
    expandedKeys.value = [...expandedKeys.value, stepIndex]
  }
  requestAnimationFrame(() => {
    document.querySelector(`[data-run-step="${stepIndex}"]`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  })
}

function focusFirstProblemStep() {
  const step = failedOrErrorSteps.value[0]
  if (step) focusStep(step.step_index)
}

function focusFirstScreenshotStep() {
  const step = steps.value.find(item => item.screenshot_url)
  if (step) focusStep(step.step_index)
}

function focusHealing() {
  const healingEl = document.querySelector('.failure-diagnosis-card') ?? document.querySelector('.run-healing-card') ?? document.querySelector('[data-run-healing="step"]')
  if (healingEl) {
    healingEl.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  focusFirstProblemStep()
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function handleExportHtml() {
  exportingHtml.value = true
  try {
    const blob = await runApi.exportHtml(runId)
    downloadBlob(blob, `run-${runId}-report.html`)
  } catch (e: unknown) {
    const messageText = e instanceof Error ? e.message : ''
    message.error(messageText || t('run.msg.export_html_failed'))
  } finally {
    exportingHtml.value = false
  }
}

async function handleExportPdf() {
  exportingPdf.value = true
  try {
    const blob = await runApi.exportPdf(runId)
    downloadBlob(blob, `run-${runId}-report.pdf`)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('run.msg.export_pdf_failed')))
  } finally {
    exportingPdf.value = false
  }
}

// ── 创建缺陷 ───────────────────────────────────────────
const failedSteps = computed(() =>
  steps.value.filter(s => s.status === 'failed' || s.status === 'error'),
)

const caseDisplayName = computed(() => {
  if (!run.value) return ''
  return run.value.case_name || run.value.case?.name || `Case-${run.value.case_id}`
})

const bugInfo = computed<BugLinkInfo | null>(() => {
  const info = run.value?.result_summary?.bug
  return info && typeof info === 'object' ? info as BugLinkInfo : null
})

const videoUrl = computed(() => {
  const value = run.value?.result_summary?.video_url
  return typeof value === 'string' ? value : ''
})

const runHealing = computed<RunHealingPayload | null>(() =>
  normalizeRunHealing(run.value?.result_summary?.healing),
)

const diagnosisStatusText = computed(() => {
  if (runHealing.value?.status) return healingStatusLabel(runHealing.value.status)
  const stepDiagnosis = steps.value.find(step => step.healing_status)?.healing_status
  return stepDiagnosis ? healingStatusLabel(stepDiagnosis) : t('run.investigation.no_ai_diagnosis')
})

const bugPreviewTitle = computed(() => {
  if (!run.value) return ''
  let title = `[ATP] ${caseDisplayName.value}`
  if (bugStepIndex.value !== undefined) {
    const step = steps.value.find((s) => s.step_index === bugStepIndex.value)
    if (step?.name) title += ` - ${step.name}`
  }
  title += ` ${t('run.bug.title_suffix')}`
  return title
})

const bugModalTitle = computed(() => bugMode.value === 'create' ? t('run.create_bug') : t('run.bug.link_existing'))
const bugModalOkText = computed(() => bugMode.value === 'create' ? t('common.create') : t('run.bug.link_existing'))

const bugPreviewDesc = computed(() => {
  if (!run.value) return ''
  const lines: string[] = [
    t('run.bug.desc_from', { id: run.value.id }),
    t('run.bug.desc_case', { name: caseDisplayName.value }),
    t('run.bug.desc_env', { environment: run.value.environment || '-' }),
  ]
  if (bugStepIndex.value !== undefined) {
    const step = steps.value.find((s) => s.step_index === bugStepIndex.value)
    if (step) {
      lines.push(t('run.bug.desc_failed_step', { index: step.step_index + 1, name: step.name }))
      if (step.error_message) {
        lines.push(`\n${t('run.bug.desc_error')}\n${truncateText(step.error_message, 500)}`)
      }
    }
  } else if (run.value.error_message) {
    lines.push(`\n${t('run.bug.desc_error')}\n${truncateText(run.value.error_message, 500)}`)
  }
  return lines.join('\n')
})

async function openBugModal() {
  if (!canCreateBug.value) {
    return
  }

  bugTrackerId.value = undefined
  bugMode.value = 'create'
  bugStepIndex.value = failedSteps.value.length > 0 ? failedSteps.value[0].step_index : undefined
  linkedBugId.value = ''
  linkedBugUrl.value = ''
  linkedBugTitle.value = ''
  linkedBugStatus.value = 'open'
  bugModalOpen.value = true

  bugTrackerLoading.value = true
  try {
    const trackers = await bugTrackerApi.list({ project_id: run.value?.project_id })
    bugTrackerOptions.value = trackers
      .filter((t: BugTrackerItem) => t.is_enabled)
      .map((t: BugTrackerItem) => ({
        label: `${t.name} (${trackerTypeLabel(t.tracker_type)})`,
        value: t.id,
      }))
  } catch {
    bugTrackerOptions.value = []
  } finally {
    bugTrackerLoading.value = false
  }
}

async function confirmCreateBug() {
  if (!bugTrackerId.value) { message.warning(t('run.msg.select_tracker')); return }
  if (bugMode.value === 'link') {
    await confirmLinkBug()
    return
  }
  bugCreating.value = true
  try {
    const payload: { tracker_id: number; step_index?: number } = { tracker_id: bugTrackerId.value }
    if (bugStepIndex.value !== undefined) {
      payload.step_index = bugStepIndex.value
    }
    const result = await bugTrackerApi.createBug(runId, payload)
    // 更新本地数据以展示缺陷链接
    if (run.value) {
      run.value.result_summary = {
        ...(run.value.result_summary || {}),
        bug: {
          ...(bugInfo.value || {}),
          bug_id: result.bug_id,
          bug_url: result.bug_url,
          title: result.title || bugPreviewTitle.value,
          duplicate_of: result.duplicate_of ?? null,
          attachment_uploaded: result.attachment_uploaded ?? false,
        },
      }
    }
    if (result.duplicate_of) {
      message.warning(t('run.msg.duplicate_bug', { id: result.duplicate_of }))
    } else if (result.attachment_uploaded) {
      message.success(t('run.msg.bug_created_with_attachment', { id: result.bug_id }))
    } else {
      message.success(t('run.msg.bug_created', { id: result.bug_id }))
    }
    bugModalOpen.value = false
    window.open(result.bug_url, '_blank')
  } catch (e: unknown) {
    const msg = errorMessage(e)
    // 双语 fallback：兼容后端返回中文/英文错误消息；待后端切到 error_code 后可清理
    if (msg.includes('401') || msg.includes('认证') || msg.includes('Unauthorized')) {
      message.error(t('run.msg.bug_auth_failed'))
    } else if (msg.includes('timeout') || msg.includes('ETIMEDOUT') || msg.includes('超时')) {
      message.error(t('run.msg.bug_timeout'))
    } else if (msg.includes('404') || msg.includes('不存在')) {
      message.error(t('run.msg.bug_project_missing'))
    } else {
      message.error(msg || t('run.msg.create_bug_failed'))
    }
  } finally {
    bugCreating.value = false
  }
}

function trackerTypeLabel(type: string) {
  return { jira: 'Jira', github: 'GitHub Issues', gitlab: 'GitLab Issues', zentao: 'Zentao' }[type] ?? type
}

async function confirmLinkBug() {
  const bugId = linkedBugId.value.trim()
  if (!bugId) {
    message.warning(t('run.msg.enter_bug_id'))
    return
  }
  bugCreating.value = true
  try {
    const result = await bugTrackerApi.linkBug(runId, {
      tracker_id: bugTrackerId.value as number,
      bug_id: bugId,
      bug_url: linkedBugUrl.value.trim() || undefined,
      title: linkedBugTitle.value.trim() || undefined,
      status: linkedBugStatus.value.trim() || undefined,
    })
    if (run.value) {
      run.value.result_summary = {
        ...(run.value.result_summary || {}),
        bug: {
          ...(bugInfo.value || {}),
          bug_id: result.bug_id,
          bug_url: result.bug_url || linkedBugUrl.value.trim(),
          title: linkedBugTitle.value.trim() || result.bug_id,
          status: result.status,
          linked_manually: true,
        },
      }
    }
    message.success(t('run.msg.bug_linked', { id: result.bug_id }))
    bugModalOpen.value = false
  } catch (e: unknown) {
    message.error(errorMessage(e) || t('run.msg.link_bug_failed'))
  } finally {
    bugCreating.value = false
  }
}

async function refreshBugStatus() {
  if (!run.value?.result_summary?.bug) return
  bugStatusRefreshing.value = true
  try {
    const result = await bugTrackerApi.getBugStatus(runId)
    run.value.result_summary = {
      ...(run.value.result_summary || {}),
      bug: {
        ...(bugInfo.value || {}),
        status: result.status,
        bug_url: result.bug_url || bugInfo.value?.bug_url,
      },
    }
    message.success(t('run.msg.bug_status_refreshed', { status: result.status }))
  } catch (e: unknown) {
    const messageText = e instanceof Error ? e.message : typeof e === 'string' ? e : ''
    message.error(messageText || t('run.msg.refresh_bug_status_failed'))
  } finally {
    bugStatusRefreshing.value = false
  }
}

function applyWsMessage(msg: WsMessage) {
  if (msg.type === 'run_status') {
    if (run.value && msg.status) run.value.status = msg.status
    return
  }

  if (msg.type === 'step_result' && msg.step) {
    const idx = steps.value.findIndex(s => s.step_index === msg.step!.step_index)
    if (idx >= 0) {
      steps.value[idx] = { ...steps.value[idx], ...msg.step }
    } else {
      steps.value.push(msg.step)
      steps.value.sort((a, b) => a.step_index - b.step_index)
    }
    expandedKeys.value = computeExpandedKeys(steps.value)
    return
  }

  if (msg.type === 'healing_suggestion' && msg.step_index != null) {
    const idx = steps.value.findIndex(s => s.step_index === msg.step_index)
    if (idx >= 0) {
      steps.value[idx] = {
        ...steps.value[idx],
        healing_status: msg.status,
        healing_suggestion: msg.suggestion ?? null,
        healing_cache_hit: msg.cache_hit ?? false,
      }
    }
    return
  }

  if (msg.type === 'run_healing_suggestion' && run.value) {
    run.value.result_summary = {
      ...(run.value.result_summary || {}),
      healing: {
        status: msg.status,
        suggestion: msg.suggestion ?? null,
        at: new Date().toISOString(),
        cache_hit: msg.cache_hit ?? false,
      },
    }
    return
  }

  if (msg.type === 'completed') {
    if (run.value) {
      if (msg.status) run.value.status = msg.status
      if (msg.duration_ms != null) run.value.duration_ms = msg.duration_ms
      if (msg.video_url) {
        run.value.result_summary = {
          ...(run.value.result_summary || {}),
          video_url: msg.video_url,
        }
      }
    }
    wsHandle?.close()
  }
}

onMounted(async () => {
  if (auth.token && !auth.user) {
    await auth.fetchMe()
  }

  // Jaeger 跳转链接是 best-effort，配置缺失或接口失败都不影响详情页主流程
  try {
    const cfg = await tracingApi.getConfig()
    jaegerUiUrl.value = cfg.jaeger_ui_url || ''
  } catch {
    jaegerUiUrl.value = ''
  }

  loading.value = true
  try {
    const data = await runApi.get(runId) as RunDetailItem
    run.value = data
    steps.value = data.steps ?? []
    expandedKeys.value = computeExpandedKeys(steps.value)
  } finally {
    loading.value = false
  }

  if (run.value?.status === 'pending' || run.value?.status === 'running') {
    wsHandle = createRunWebSocket(runId, applyWsMessage, () => {
      runApi.get(runId).then((d: RunDetailItem) => {
        run.value = d
        steps.value = d.steps ?? []
        expandedKeys.value = computeExpandedKeys(steps.value)
      })
    })
  }

  if (run.value?.result_summary?.bug) {
    void refreshBugStatus()
  }
})

onUnmounted(() => {
  wsHandle?.close()
})
</script>

<style scoped>
.investigation-panel {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-elevated);
}
.investigation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text);
}
.section-subtitle {
  margin-top: 2px;
  color: var(--c-text-secondary);
  font-size: 12px;
}
.investigation-metrics {
  margin-bottom: 12px;
}
.investigation-card {
  width: 100%;
  min-height: 78px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-subtle);
  color: inherit;
  cursor: pointer;
  text-align: left;
  text-decoration: none;
}
.investigation-card:hover {
  border-color: var(--c-primary);
}
.investigation-card.is-disabled {
  cursor: default;
  opacity: 0.65;
  pointer-events: none;
}
.investigation-icon {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 19px;
}
.investigation-icon-error {
  color: var(--c-error);
  background: var(--c-error-soft);
}
.investigation-icon-primary {
  color: var(--c-primary);
  background: var(--c-primary-soft);
}
.investigation-icon-info {
  color: var(--c-info);
  background: var(--c-info-soft);
}
.investigation-icon-warning {
  color: var(--c-warning);
  background: var(--c-warning-soft);
}
.investigation-card-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.investigation-value {
  overflow: hidden;
  color: var(--c-text);
  font-size: 20px;
  font-weight: 650;
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.investigation-label {
  margin-top: 6px;
  color: var(--c-text-secondary);
  font-size: 12px;
}
.investigation-block {
  height: 100%;
  min-height: 140px;
  padding: 12px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-subtle);
}
.block-title {
  margin-bottom: 8px;
  color: var(--c-text);
  font-weight: 600;
}
.error-snippet {
  max-height: 160px;
  margin: 0;
  overflow: auto;
  color: var(--c-text-secondary);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.failure-diagnosis-card {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-subtle);
}
.failure-diagnosis-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.failure-diagnosis-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--c-text-secondary);
  font-size: 12px;
}
.failure-diagnosis-text {
  margin: 10px 0 0;
  color: var(--c-text);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.repair-suggestion-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.repair-suggestion-title {
  color: var(--c-text);
  font-weight: 600;
}
.repair-suggestion-item {
  padding: 10px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-elevated);
}
.repair-suggestion-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--c-text);
  font-weight: 600;
}
.repair-suggestion-body {
  margin-top: 6px;
  color: var(--c-text);
  line-height: 1.6;
}
.repair-suggestion-meta {
  margin-top: 6px;
  color: var(--c-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.problem-step-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.problem-step-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-elevated);
  cursor: pointer;
  text-align: left;
}
.problem-step-item:hover {
  border-color: var(--c-primary);
}
.problem-step-title {
  min-width: 0;
  overflow: hidden;
  color: var(--c-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.device-matrix-summary {
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid var(--c-border);
  border-radius: 10px;
  background: var(--c-bg-elevated);
}
.device-matrix-summary-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.device-matrix-table-wrap {
  overflow-x: auto;
}
.device-matrix-table {
  width: 100%;
  border-collapse: collapse;
  color: var(--c-text);
  font-size: 13px;
}
.device-matrix-table th,
.device-matrix-table td {
  padding: 9px 10px;
  border-top: 1px solid var(--c-border);
  text-align: left;
  vertical-align: top;
}
.device-matrix-table th {
  color: var(--c-text-secondary);
  font-weight: 600;
}
.device-matrix-error {
  max-width: 420px;
  color: var(--c-text-secondary);
  word-break: break-word;
}
.steps-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}
.steps-summary {
  color: #8c8c8c;
  font-size: 13px;
  margin-left: 12px;
  display: flex;
  gap: 10px;
}
.stat-passed { color: #52c41a; font-weight: 500; }
.stat-failed { color: #ff4d4f; font-weight: 500; }
.stat-error { color: #fa8c16; font-weight: 500; }
.stat-skipped { color: #8c8c8c; font-weight: 500; }

/* 步骤进度条 */
.steps-progress {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 16px;
  gap: 2px;
}
.progress-segment {
  min-width: 4px;
  border-radius: 2px;
  transition: opacity 0.2s;
}
.progress-segment:hover {
  opacity: 0.75;
}
.segment-passed { background: #52c41a; }
.segment-failed { background: #ff4d4f; }
.segment-error { background: #fa8c16; }
.segment-running { background: #1890ff; }
.segment-pending { background: #d9d9d9; }
.segment-skipped { background: #bfbfbf; }

/* 失败/异常步骤高亮 */
.step-failed :deep(.ant-collapse-header) {
  background: #fff2f0 !important;
  border-left: 3px solid #ff4d4f !important;
}
.step-error :deep(.ant-collapse-header) {
  background: #fff7e6 !important;
  border-left: 3px solid #fa8c16 !important;
}

.step-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-number {
  font-weight: 600;
  color: #8c8c8c;
  min-width: 28px;
}
.step-name {
  font-weight: 500;
}
.step-duration {
  color: #8c8c8c;
  font-size: 12px;
}

/* 截图区域 */
.screenshot-section {
  margin-bottom: 12px;
}
.step-screenshot {
  border-radius: 6px;
  border: 1px solid #f0f0f0;
  cursor: pointer;
}

/* 录像播放 */
.video-section {
  margin-bottom: 16px;
}
.video-player {
  width: 100%;
  max-width: 800px;
  border-radius: 8px;
  background: #000;
}

.panel-label {
  font-weight: 600;
  margin-bottom: 6px;
  color: #595959;
}
.code-block {
  background: #f5f5f5;
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

/* 缺陷预览 */
.bug-preview-label {
  font-weight: 600;
  color: #595959;
  font-size: 13px;
  margin-bottom: 4px;
}
.bug-preview-value {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  padding: 8px 12px;
  font-size: 13px;
}
.bug-preview-desc {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  margin: 0;
}

.healing-panel :deep(.ant-collapse-header) {
  padding: 6px 0 !important;
  font-size: 13px;
}

.healing-title {
  display: inline-flex;
  align-items: center;
  color: #1677ff;
  font-weight: 500;
}

.healing-pending {
  color: #1677ff;
  font-size: 13px;
}

.healing-text {
  margin: 0;
  padding: 8px 12px;
  background: #f6f8fa;
  border-left: 3px solid #1677ff;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
}

.healing-feedback-row {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.feedback-thanks {
  color: #999;
  font-size: 12px;
}

.run-healing-card {
  margin: 12px 0;
}

.healing-patch-section {
  margin-top: 12px;
}

.healing-patch-reasons {
  margin: 0;
  padding: 8px 12px 8px 28px;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  font-size: 13px;
}
@media (max-width: 768px) {
  .investigation-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
