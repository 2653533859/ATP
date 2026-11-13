<template>
  <section class="agent-panel panel" data-testid="android-agent-panel">
    <header class="panel-head compact-head">
      <div class="panel-title-block">
        <div class="panel-kicker">{{ t('android_agent.kicker') }}</div>
        <h2>{{ t('android_agent.title') }}</h2>
        <p class="agent-description">{{ t('android_agent.description') }}</p>
      </div>
      <div class="agent-head-actions">
        <a-select
          v-if="sessions.length"
          :value="sessionId ?? undefined"
          :options="sessionOptions"
          :placeholder="t('android_agent.session_select_placeholder')"
          size="small"
          class="session-select"
          allow-clear
          @change="handleSessionSelect"
        />
        <a-button
          size="small"
          :loading="loading"
          :aria-label="t('android_agent.refresh')"
          @click="refreshAll"
        >
          <ReloadOutlined /> {{ t('android_agent.refresh') }}
        </a-button>
      </div>
    </header>

    <a-alert
      v-if="agentDisabled"
      class="agent-alert"
      type="warning"
      show-icon
      :message="t('android_agent.disabled_notice')"
    />

    <a-alert
      v-if="errorMessage"
      class="agent-alert"
      type="error"
      show-icon
      :message="errorMessage"
      closable
      @close="errorMessage = ''"
    />

    <div v-if="!sessions.length && !session && !loading" class="agent-empty">
      <span>{{ t('android_agent.empty_session') }}</span>
    </div>

    <section class="agent-setup" :aria-label="t('android_agent.setup_title')">
      <div class="section-head">
        <strong class="section-title">{{ t('android_agent.setup_title') }}</strong>
      </div>

      <div class="setup-fields">
        <div class="field field-title">
          <label :for="'agent-title-input'">{{ t('android_agent.title_label') }}</label>
          <a-input
            id="agent-title-input"
            v-model:value="formTitle"
            :placeholder="t('android_agent.title_placeholder')"
            :maxlength="120"
            size="small"
          />
        </div>

        <div class="field field-model">
          <label :for="'agent-model-select'">{{ t('android_agent.model_label') }}</label>
          <a-select
            id="agent-model-select"
            v-model:value="formLlmConfigId"
            :options="modelOptions"
            :placeholder="t('android_agent.model_placeholder')"
            size="small"
            class="field-control"
            allow-clear
          />
          <span v-if="modelsLoaded && !models.length" class="form-hint">{{ t('android_agent.model_none_hint') }}</span>
        </div>

        <div class="field field-device">
          <label :for="'agent-device-select'">{{ t('android_agent.device_label') }}</label>
          <a-select
            id="agent-device-select"
            v-model:value="formDeviceId"
            :options="deviceOptions"
            :placeholder="t('app_workbench.device_placeholder')"
            size="small"
            class="field-control"
          />
        </div>

        <div class="field field-package">
          <label :for="'agent-package-input'">{{ t('android_agent.package_label') }}</label>
          <div class="package-control">
            <a-auto-complete
              id="agent-package-input"
              v-model:value="formPackage"
              :options="packageOptions"
              :placeholder="t('android_agent.package_placeholder')"
              size="small"
              class="package-input"
            />
            <a-button
              size="small"
              :loading="packagesLoading"
              :disabled="formDeviceId === undefined"
              :aria-label="t('android_agent.load_packages')"
              @click="loadDevicePackages(true)"
            >
              <SyncOutlined /> {{ t('android_agent.load_short') }}
            </a-button>
            <a-popover
              :open="historyOpen"
              trigger="click"
              placement="bottomRight"
              @open-change="handleHistoryOpen"
            >
              <template #content>
                <div class="package-history">
                  <p v-if="!packageHistory.length" class="form-hint">{{ t('android_agent.history_empty') }}</p>
                  <div v-else class="package-history-head" aria-hidden="true">
                    <span>{{ t('android_agent.history_time') }}</span>
                    <span>{{ t('android_agent.history_apps') }}</span>
                    <span>{{ t('android_agent.history_package') }}</span>
                  </div>
                  <button
                    v-for="item in packageHistory"
                    :key="item.id"
                    type="button"
                    class="package-history-item"
                    @click="applyHistory(item)"
                  >
                    <span class="tabular-nums">{{ formatTime(item.read_at) }}</span>
                    <span class="tabular-nums">{{ item.packages.length }}</span>
                    <span v-if="item.current_package" class="package-history-foreground">{{ item.current_package }}</span>
                  </button>
                </div>
              </template>
              <a-button
                size="small"
                :disabled="formDeviceId === undefined"
                :aria-label="t('android_agent.history')"
              >
                <HistoryOutlined /> {{ t('android_agent.history') }}
              </a-button>
            </a-popover>
          </div>
          <div v-if="apkPackages.length" class="apk-quick-pick">
            <span class="form-hint">{{ t('android_agent.apk_quick_pick') }}</span>
            <button
              v-for="pkg in apkPackages"
              :key="pkg"
              type="button"
              class="apk-quick-chip"
              @click="formPackage = pkg"
            >
              {{ pkg }}
            </button>
          </div>
          <div class="package-meta">
            <span v-if="packageHint" class="form-hint">{{ packageHint }}</span>
            <span v-if="devicePackages.length" class="package-count tabular-nums">
              {{ t('android_agent.packages_count', { count: devicePackages.length }) }}
            </span>
          </div>
        </div>

        <div class="field field-goal">
          <label :for="'agent-goal-input'">{{ t('android_agent.goal_label') }}</label>
          <a-textarea
            id="agent-goal-input"
            v-model:value="formGoal"
            :placeholder="t('android_agent.goal_placeholder')"
            :rows="2"
            :maxlength="500"
            show-count
          />
        </div>

        <div class="field field-outcome">
          <label :for="'agent-outcome-input'">{{ t('android_agent.outcome_label') }}</label>
          <a-textarea
            id="agent-outcome-input"
            v-model:value="formOutcome"
            :placeholder="t('android_agent.outcome_placeholder')"
            :rows="2"
            :maxlength="500"
            show-count
          />
        </div>

        <div class="field field-vars">
          <div class="vars-head">
            <span class="field-label">{{ t('android_agent.vars_label') }}</span>
            <a-button size="small" @click="addVarRow">{{ t('android_agent.vars_add') }}</a-button>
          </div>
          <div v-for="(pair, idx) in formVars" :key="idx" class="vars-row">
            <a-input
              v-model:value="pair.key"
              :placeholder="t('android_agent.vars_key_placeholder')"
              size="small"
            />
            <a-input
              v-model:value="pair.value"
              :placeholder="t('android_agent.vars_val_placeholder')"
              size="small"
            />
            <a-button size="small" danger @click="removeVarRow(idx)">×</a-button>
          </div>
        </div>

        <div class="field field-budget">
          <span class="field-label">{{ t('android_agent.budget_label') }}</span>
          <div class="budget-row">
            <label class="budget-input">
              <span>{{ t('android_agent.budget_steps') }}</span>
              <a-input-number v-model:value="formMaxSteps" :min="1" :max="100" size="small" />
            </label>
            <label class="budget-input">
              <span>{{ t('android_agent.budget_calls') }}</span>
              <a-input-number v-model:value="formMaxCalls" :min="1" :max="120" size="small" />
            </label>
          </div>
        </div>

        <p class="agent-sensitive-hint">{{ t('android_agent.sensitive_hint') }}</p>

        <div class="setup-actions">
          <span v-if="!canCreate" class="setup-required">{{ t('android_agent.setup_required') }}</span>
          <a-button
            type="primary"
            :disabled="!canCreate"
            :loading="creating"
            @click="createSession"
          >
            {{ t('android_agent.create') }}
          </a-button>
        </div>
      </div>
    </section>

    <div v-if="sessionId" class="agent-session">
      <div class="section-head session-head">
        <strong class="section-title">{{ t('android_agent.session_title') }}</strong>
        <span class="session-title-text">{{ session?.title || '' }}</span>
        <a-tag :color="statusColor(session?.status)">{{ statusLabel }}</a-tag>
        <a-tag v-if="session?.error_code" color="red" class="agent-error-code">
          {{ t('android_agent.error_code_label') }}: {{ session.error_code }}
        </a-tag>
      </div>

      <div class="session-meta-row">
        <span class="meta-item">{{ t('android_agent.controller_label') }}: {{ controllerLabel }}</span>
        <span class="meta-sep" aria-hidden="true" />
        <span class="meta-item tabular-nums">
          {{ t('android_agent.steps_used', { used: session?.steps_count ?? 0, total: session?.budget_max_steps ?? 0 }) }}
        </span>
        <span class="meta-sep" aria-hidden="true" />
        <span class="meta-item tabular-nums">
          {{ t('android_agent.calls_used', { used: session?.model_calls_count ?? 0, total: session?.budget_max_calls ?? 0 }) }}
        </span>
        <span class="meta-sep" aria-hidden="true" />
        <span class="meta-item tabular-nums">
          {{ t('android_agent.tokens_used', { used: session?.total_tokens ?? 0 }) }}
        </span>
      </div>

      <div class="agent-controls-bar" role="toolbar" :aria-label="t('android_agent.session_title')">
        <a-button type="primary" size="small" :disabled="!canStart" :loading="acting" @click="startSession">
          {{ t('android_agent.start') }}
        </a-button>
        <a-button
          size="small"
          :disabled="!canRunLoop"
          :loading="running"
          @click="runLoop"
        >
          {{ t('android_agent.run_loop') }}
        </a-button>
        <span class="control-sep" aria-hidden="true" />
        <a-button size="small" :disabled="!canPause" :loading="acting" @click="control('pause')">
          {{ t('android_agent.pause') }}
        </a-button>
        <a-button size="small" :disabled="!canTakeover" :loading="acting" @click="control('takeover')">
          {{ t('android_agent.takeover') }}
        </a-button>
        <a-button size="small" :disabled="!canResume" :loading="acting" @click="control('resume')">
          {{ t('android_agent.resume') }}
        </a-button>
        <a-button
          v-if="canComplete"
          size="small"
          :loading="completing"
          @click="toggleCompleteForm"
        >
          {{ t('android_agent.complete_btn') }}
        </a-button>
        <span class="control-spacer" aria-hidden="true" />
        <a-button size="small" danger :disabled="!canCancel" :loading="acting" @click="control('cancel')">
          {{ t('android_agent.cancel') }}
        </a-button>
      </div>
      <p class="agent-hint">{{ t('android_agent.control_hint') }}</p>

      <section v-if="showManualConsole" class="agent-subpanel agent-manual-console" data-testid="agent-manual-console">
        <div class="section-head">
          <strong>{{ t('android_agent.manual_title') }}</strong>
        </div>
        <p class="agent-hint">{{ t('android_agent.manual_hint') }}</p>
        <div class="subpanel-grid">
          <a-select
            v-model:value="manualActionType"
            :options="manualActionOptions"
            size="small"
            class="manual-action-select"
          />
          <a-input
            v-if="['tap', 'input'].includes(manualActionType)"
            v-model:value="manualResourceId"
            :placeholder="t('android_agent.manual_resource_placeholder')"
            size="small"
          />
          <a-input
            v-if="manualActionType === 'input' || manualActionType === 'swipe'"
            v-model:value="manualValue"
            :placeholder="t('android_agent.manual_value_placeholder')"
            size="small"
          />
          <a-input-number
            v-if="manualActionType === 'wait'"
            v-model:value="manualWaitMs"
            :min="100"
            :max="30000"
            size="small"
            :placeholder="t('android_agent.manual_wait_ms')"
          />
          <a-button size="small" type="primary" :loading="manualSending" @click="submitManualAction">
            {{ t('android_agent.manual_submit') }}
          </a-button>
        </div>
      </section>

      <section v-if="showCompleteForm && canComplete" class="agent-subpanel agent-complete-form" data-testid="agent-complete-form">
        <div class="section-head">
          <strong>{{ t('android_agent.complete_title') }}</strong>
          <a-button size="small" @click="addCompleteAssertion">{{ t('android_agent.complete_assertion_add') }}</a-button>
        </div>
        <p class="agent-hint">{{ t('android_agent.complete_hint') }}</p>
        <p class="field-label">{{ t('android_agent.complete_assertion_label') }}</p>
        <div v-for="(item, idx) in completeAssertions" :key="idx" class="assertion-edit-row">
          <a-select
            v-model:value="item.type"
            :options="assertionTypeOptions"
            size="small"
            class="assertion-type-select"
          />
          <a-input
            v-model:value="item.resource_id"
            :placeholder="t('android_agent.complete_resource_placeholder')"
            size="small"
          />
          <a-button
            v-if="completeAssertions.length > 1"
            size="small"
            danger
            @click="removeCompleteAssertion(idx)"
          >
            ×
          </a-button>
        </div>
        <a-input
          v-model:value="completeSummary"
          :placeholder="t('android_agent.complete_summary_placeholder')"
          size="small"
        />
        <div class="complete-footer">
          <a-checkbox v-model:checked="completeConfirmed">
            {{ t('android_agent.complete_confirm_check') }}
          </a-checkbox>
          <a-button
            size="small"
            type="primary"
            :disabled="!canSubmitComplete"
            :loading="completing"
            @click="completeSession"
          >
            {{ t('android_agent.complete_submit') }}
          </a-button>
        </div>
      </section>

      <div class="agent-session-body">
        <section class="agent-events">
          <div class="agent-events-head">
            <strong>{{ t('android_agent.events_title') }}</strong>
            <span class="agent-events-note">{{ t('android_agent.events_order') }}</span>
          </div>
          <p v-if="!events.length" class="agent-events-empty">{{ t('android_agent.events_empty') }}</p>
          <ul v-else class="agent-event-list">
            <li v-for="event in events" :key="event.seq" class="agent-event-row" :data-seq="event.seq">
              <span class="agent-event-seq">#{{ event.seq }}</span>
              <span class="agent-event-type">{{ event.event_type }}</span>
              <span v-if="eventSummary(event)" class="agent-event-detail">{{ eventSummary(event) }}</span>
              <span class="agent-event-time tabular-nums">{{ formatTime(event.created_at) }}</span>
            </li>
          </ul>
        </section>

        <section class="agent-draft">
          <div class="agent-draft-head">
            <strong>{{ draft ? t('android_agent.draft_title', { version: draft.version }) : t('android_agent.draft_section') }}</strong>
            <div class="draft-head-actions">
              <a-select
                v-if="drafts.length > 1"
                :value="draft?.id"
                :options="draftOptions"
                size="small"
                class="draft-version-select"
                :aria-label="t('android_agent.draft_version_select')"
                @change="selectDraftVersion"
              />
              <a-button
                v-if="draft && canModify"
                size="small"
                @click="editingDraft ? cancelEditDraft() : startEditDraft()"
              >
                {{ editingDraft ? t('android_agent.cancel_edit_btn') : t('android_agent.edit_draft_btn') }}
              </a-button>
              <a-button size="small" :disabled="!canCompile" :loading="compiling" @click="compileDraft">
                {{ t('android_agent.compile_draft') }}
              </a-button>
            </div>
          </div>
          <p v-if="!draft" class="agent-draft-empty">{{ t('android_agent.draft_empty') }}</p>
          <template v-if="draft">
          <div class="agent-draft-status">
            <a-tag :color="draft.status === 'blocked' ? 'red' : 'green'">{{ draftStatusLabel }}</a-tag>
            <span class="agent-draft-hash tabular-nums">{{ draft.content_hash.slice(0, 12) }}</span>
          </div>
          <div v-if="draft.blocking_issues.length" class="agent-blocking">
            <span>{{ t('android_agent.blocking_issues') }}</span>
            <ul>
              <li v-for="issue in draft.blocking_issues" :key="issue.code">{{ issue.code }} - {{ issue.message }}</li>
            </ul>
          </div>
          <div class="agent-steps">
            <span>{{ t('android_agent.steps_preview') }}</span>
            <ol>
              <li v-for="(step, index) in draft.steps" :key="index">
                {{ step.action }} {{ stepResource(step) }}
              </li>
            </ol>
          </div>
          <div class="agent-assertions">
            <span>{{ t('android_agent.draft_assertions_preview') }}</span>
            <p v-if="!draft.assertions.length" class="agent-hint">{{ t('android_agent.draft_assertions_empty') }}</p>
            <ul v-else>
              <li v-for="(assertion, idx) in draft.assertions" :key="idx">
                {{ assertion.type }} · {{ assertion.resource_id || '-' }}
              </li>
            </ul>
          </div>
          <div v-if="editingDraft" class="agent-subpanel agent-draft-editor" data-testid="agent-draft-editor">
            <div class="section-head">
              <strong>{{ t('android_agent.edit_draft_btn') }}</strong>
              <a-button size="small" @click="addDraftEditAssertion">{{ t('android_agent.draft_assertion_add') }}</a-button>
            </div>
            <div v-for="(item, idx) in editAssertions" :key="idx" class="assertion-edit-row">
              <a-select
                v-model:value="item.type"
                :options="assertionTypeOptions"
                size="small"
                class="assertion-type-select"
              />
              <a-input
                v-model:value="item.resource_id"
                :placeholder="t('android_agent.complete_resource_placeholder')"
                size="small"
              />
              <a-button size="small" danger @click="removeDraftEditAssertion(idx)">×</a-button>
            </div>
            <div class="draft-editor-actions">
              <a-button size="small" type="primary" :loading="savingDraft" @click="saveDraftEdits">
                {{ t('android_agent.save_draft_btn') }}
              </a-button>
              <a-button size="small" @click="cancelEditDraft">{{ t('android_agent.cancel_edit_btn') }}</a-button>
            </div>
          </div>
          <div class="agent-replay">
            <a-checkbox v-model:checked="replayStateConfirmed">
              {{ t('android_agent.replay_confirm_state') }}
            </a-checkbox>
            <div class="agent-replay-row">
              <span>{{ t('android_agent.replay_module') }}</span>
              <a-select v-model:value="replayModuleId" :options="moduleOptions" size="small" />
              <a-button size="small" :disabled="!previewReady" @click="openReplayPreview">
                {{ t('android_agent.replay_preview') }}
              </a-button>
              <a-button
                size="small"
                type="primary"
                :disabled="!canStartReplay"
                :loading="replaying"
                @click="startReplay"
              >
                {{ t('android_agent.replay_start') }}
              </a-button>
              <a-button size="small" :disabled="!canPublish" :loading="publishing" @click="publishDraft">
                {{ t('android_agent.publish') }}
              </a-button>
            </div>
            <p v-if="previewItems.length" class="agent-preview-items">
              <span v-for="item in previewItems" :key="item.code" :class="['agent-preview-item', item.status]">
                {{ item.code }}: {{ item.message }}
              </span>
            </p>
            <div v-if="latestReplay" class="agent-replay-status">
              <span>{{ t('android_agent.replay_status_label') }}:</span>
              <a-tag :color="statusColor(latestReplay.status)">#{{ latestReplay.id }} · {{ latestReplay.status }}</a-tag>
              <a-button size="small" @click="refreshReplayStatus">{{ t('android_agent.replay_refresh') }}</a-button>
              <a-button v-if="latestReplay.run_id" size="small" type="link" @click="openReplayRun(latestReplay.run_id)">
                {{ t('android_agent.open_replay_run', { id: latestReplay.run_id }) }}
              </a-button>
            </div>
            <div v-if="publishedCaseId" class="agent-published-row">
              <p class="agent-published tabular-nums">
                {{ t('android_agent.published_case', { id: publishedCaseId }) }}
              </p>
              <a-button size="small" type="link" @click="openPublishedCase(publishedCaseId)">
                {{ t('android_agent.open_published_case', { id: publishedCaseId }) }}
              </a-button>
            </div>
          </div>
        </template>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ReloadOutlined, HistoryOutlined, SyncOutlined } from '@ant-design/icons-vue'

import {
  androidAgentApi,
  deviceApi,
  type AgentAssertionItem,
  type AgentDraftItem,
  type AgentEventItem,
  type AgentManualActionPayload,
  type AgentReplayItem,
  type AgentSessionCreatePayload,
  type AgentSessionItem,
  type AgentVisionModelItem,
  type DevicePackageSnapshotItem,
} from '@/api'
import { getRuntimeMode } from '@/runtimeMode'
import { loadDevicePackagesAsync } from '@/utils/devicePackages'

const props = defineProps<{
  projectId: number | null
  devices: Array<{ id: number; serial?: string; name?: string | null; status?: string }>
  modules: Array<{ id: number; name: string }>
  apks?: Array<{ id: number; package_name?: string | null; filename?: string; version_name?: string | null }>
  canModify: boolean
}>()

const { t } = useI18n()
const appInstance = getCurrentInstance()

const models = ref<AgentVisionModelItem[]>([])
const modelsLoaded = ref(false)
const agentDisabled = ref(false)

const sessions = ref<AgentSessionItem[]>([])
const session = ref<AgentSessionItem | null>(null)
const events = ref<AgentEventItem[]>([])
const drafts = ref<AgentDraftItem[]>([])
const draft = ref<AgentDraftItem | null>(null)
const latestReplay = ref<AgentReplayItem | null>(null)
const previewItems = ref<Array<{ code: string; status: string; message: string }>>([])
const publishedCaseId = ref<number | null>(null)

const loading = ref(false)
const creating = ref(false)
const acting = ref(false)
const running = ref(false)
const completing = ref(false)
const manualSending = ref(false)
const compiling = ref(false)
const savingDraft = ref(false)
const replaying = ref(false)
const publishing = ref(false)
const errorMessage = ref('')

const formTitle = ref('')
const formLlmConfigId = ref<number | undefined>(undefined)
const formDeviceId = ref<number | undefined>(undefined)
const formPackage = ref('')
const devicePackages = ref<string[]>([])
const packagesLoading = ref(false)
const foregroundPackage = ref<string | null>(null)
const packageReadAt = ref<string | null>(null)
const packageHistory = ref<DevicePackageSnapshotItem[]>([])
const historyOpen = ref(false)
const formGoal = ref('')
const formOutcome = ref('')
const formVars = ref<Array<{ key: string; value: string }>>([])
const formMaxSteps = ref(30)
const formMaxCalls = ref(40)

const showCompleteForm = ref(false)
const completeAssertions = ref<AgentAssertionItem[]>([{ type: 'element_visible', resource_id: '' }])
const completeSummary = ref('')
const completeConfirmed = ref(false)

function resetCompletion() {
  completeAssertions.value = [{ type: 'element_visible', resource_id: '' }]
  completeSummary.value = ''
  completeConfirmed.value = false
  showCompleteForm.value = false
}

watch(completeAssertions, () => { completeConfirmed.value = false }, { deep: true, flush: 'sync' })
watch(() => session.value?.id, resetCompletion, { flush: 'sync' })
watch(() => props.projectId, resetCompletion, { flush: 'sync' })

const manualActionType = ref<AgentManualActionPayload['action']>('tap')
const manualResourceId = ref('')
const manualValue = ref('')
const manualWaitMs = ref<number>(1000)
const manualRequestKeys = new Map<string, string>()
let manualRequestSequence = 0

const editingDraft = ref(false)
const editAssertions = ref<AgentAssertionItem[]>([])

const replayStateConfirmed = ref(false)
const replayModuleId = ref<number | undefined>(undefined)

const sessionId = computed(() => session.value?.id ?? null)
const sessionOptions = computed(() =>
  sessions.value.map((s) => ({
    value: s.id,
    label: `${s.title} (#${s.id})`,
  })),
)
const modelOptions = computed(() =>
  models.value.map((m) => ({
    value: m.id,
    label: `${m.name} (${m.supports_vision ? t('android_agent.model_vision_tag') : t('android_agent.model_no_vision_tag')}) · ${m.model_name}`,
  })),
)
const deviceOptions = computed(() =>
  props.devices.map((device) => ({
    value: device.id,
    label: device.name || device.serial || '#' + device.id,
  })),
)
const moduleOptions = computed(() => props.modules.map((module) => ({ value: module.id, label: module.name })))
const apkPackages = computed(() => {
  const seen = new Set<string>()
  for (const apk of props.apks ?? []) {
    const pkg = apk.package_name?.trim()
    if (pkg) seen.add(pkg)
  }
  return Array.from(seen).slice(0, 6)
})
const draftOptions = computed(() =>
  drafts.value.map((d) => ({
    value: d.id,
    label: `v${d.version} · ${d.status}`,
  })),
)
const assertionTypeOptions = computed(() => [
  { value: 'element_visible', label: t('android_agent.complete_assertion_visible') },
  { value: 'element_absent', label: t('android_agent.complete_assertion_absent') },
])
const manualActionOptions = computed(() => [
  { value: 'tap', label: t('android_agent.manual_action_tap') },
  { value: 'input', label: t('android_agent.manual_action_input') },
  { value: 'swipe', label: t('android_agent.manual_action_swipe') },
  { value: 'back', label: t('android_agent.manual_action_back') },
  { value: 'wait', label: t('android_agent.manual_action_wait') },
])
const packageOptions = computed(() =>
  devicePackages.value.map((pkg) => ({
    value: pkg,
    label: pkg === foregroundPackage.value
      ? `${pkg} · ${t('android_agent.foreground_tag')}`
      : pkg,
  })),
)
const packageHint = computed(() => {
  const parts: string[] = []
  if (foregroundPackage.value) {
    parts.push(t('android_agent.foreground_hint', { package: foregroundPackage.value }))
  }
  if (packageReadAt.value) {
    parts.push(t('android_agent.read_at', { time: formatTime(packageReadAt.value) }))
  }
  return parts.join(' · ')
})

const statusValue = computed(() => session.value?.status ?? '')
const canCreate = computed(
  () =>
    !agentDisabled.value &&
    props.canModify &&
    Boolean(props.projectId) &&
    formDeviceId.value !== undefined &&
    formPackage.value.trim() !== '' &&
    formGoal.value.trim() !== '' &&
    formOutcome.value.trim() !== '',
)
const canStart = computed(() => !agentDisabled.value && props.canModify && statusValue.value === 'created')
const canPause = computed(() => props.canModify && ['running', 'prechecking'].includes(statusValue.value))
const canTakeover = computed(
  () =>
    props.canModify &&
    ['prechecking', 'running', 'pause_requested', 'paused'].includes(statusValue.value) &&
    session.value?.controller !== 'manual',
)
const canRunLoop = computed(() => !agentDisabled.value && props.canModify && statusValue.value === 'running')
const canResume = computed(() => !agentDisabled.value && props.canModify && statusValue.value === 'paused')
const canCancel = computed(
  () => props.canModify && !['completed', 'failed', 'cancelled'].includes(statusValue.value),
)
const canComplete = computed(
  () => props.canModify && ['running', 'paused'].includes(statusValue.value),
)
const showManualConsole = computed(
  () => props.canModify && statusValue.value === 'paused' && session.value?.controller === 'manual',
)
const hasValidCompleteAssertion = computed(() =>
  completeAssertions.value.some((item) => item.resource_id.trim() !== ''),
)
const canSubmitComplete = computed(
  () => canComplete.value && completeConfirmed.value && hasValidCompleteAssertion.value,
)
const canCompile = computed(
  () => props.canModify && ['completed', 'failed', 'cancelled'].includes(statusValue.value),
)
const draftStatusLabel = computed(() => {
  const value = draft.value?.status
  if (value === 'blocked') return t('android_agent.draft_blocked')
  if (value === 'pending_replay') return t('android_agent.draft_pending')
  if (value === 'verified') return t('android_agent.draft_verified')
  return t('android_agent.draft_replayable')
})
const previewReady = computed(() => Boolean(draft.value) && draft.value?.status !== 'blocked')
const canStartReplay = computed(
  () =>
    props.canModify &&
    Boolean(draft.value) &&
    draft.value?.status !== 'blocked' &&
    replayStateConfirmed.value &&
    replayModuleId.value !== undefined,
)
const canPublish = computed(() => props.canModify && Boolean(draft.value) && draft.value?.status !== 'blocked')

const controllerLabel = computed(() => {
  const value = session.value?.controller
  if (!value) return '-'
  const key = `android_agent.controller_map.${value}`
  const label = t(key)
  return label === key ? value : label
})

let pollTimer: ReturnType<typeof setInterval> | null = null

const statusLabel = computed(() => {
  const value = session.value?.status
  if (!value) return '-'
  const key = `android_agent.status_map.${value}`
  const label = t(key)
  return label === key ? value : label
})

function statusColor(status?: string) {
  if (status === 'running') return 'green'
  if (status === 'paused' || status === 'pause_requested') return 'orange'
  if (status === 'failed' || status === 'cancelled') return 'red'
  if (status === 'completed' || status === 'passed') return 'blue'
  return 'default'
}

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString()
}

function eventSummary(event: AgentEventItem): string {
  const payload = event.payload || {}
  const parts: string[] = []
  if (typeof payload.action === 'string' && payload.action) parts.push(payload.action)
  if (typeof payload.error_code === 'string' && payload.error_code) parts.push(payload.error_code)
  if (typeof payload.reason === 'string' && payload.reason) parts.push(payload.reason)
  else if (typeof payload.summary === 'string' && payload.summary) parts.push(payload.summary)
  const text = parts.join(' · ')
  return text.length > 80 ? `${text.slice(0, 77)}...` : text
}

function navigateTo(path: string) {
  const globalRouter = appInstance?.appContext?.config?.globalProperties?.$router as
    | { push?: (target: string) => unknown }
    | undefined
  if (globalRouter && typeof globalRouter.push === 'function') {
    void globalRouter.push(path)
    return
  }
  if (typeof window !== 'undefined') {
    window.location.assign(path)
  }
}

function openReplayRun(runId: number) {
  navigateTo(`/runs/${runId}`)
}

function openPublishedCase(caseId: number) {
  navigateTo(`/cases/${caseId}`)
}

function checkRuntimeFeatureFlag() {
  try {
    const mode = getRuntimeMode()
    if (mode?.mode === 'local' && Array.isArray(mode.features) && !mode.features.includes('android_agent')) {
      agentDisabled.value = true
    }
  } catch {
    // 测试环境未注入完整 runtimeMode 时忽略
  }
}

function stepResource(step: Record<string, unknown>) {
  const resourceId = step?.resource_id
  if (typeof resourceId === 'string' && resourceId) return resourceId
  const params = step?.params
  if (params && typeof params === 'object') {
    const value = (params as Record<string, unknown>).resource_id
    if (typeof value === 'string') return value
  }
  return ''
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    // 循环执行期间后端阻塞处理，轮询只会拿到中间态，等它收敛后再拉
    if (running.value) return
    void refreshSession()
    if (latestReplay.value && ['queued', 'running'].includes(latestReplay.value.status)) {
      void refreshReplayStatus()
    }
  }, 3000)
}

async function refreshEvents() {
  if (!props.projectId || !sessionId.value) return
  const page = await androidAgentApi.events(props.projectId, sessionId.value, 0, 200)
  events.value = page.items
}

function applyPackageSnapshot(snapshot: {
  packages: string[]
  current_package: string | null
  read_at: string | null
}) {
  devicePackages.value = snapshot.packages
  foregroundPackage.value = snapshot.current_package
  packageReadAt.value = snapshot.read_at
  if (!formPackage.value.trim() && snapshot.current_package) {
    formPackage.value = snapshot.current_package
  }
}

async function loadDevicePackages(force = false) {
  const deviceId = formDeviceId.value
  if (deviceId === undefined) {
    devicePackages.value = []
    foregroundPackage.value = null
    packageReadAt.value = null
    packageHistory.value = []
    return
  }
  packagesLoading.value = true
  try {
    const snapshot = await loadDevicePackagesAsync(deviceId, { force })
    if (formDeviceId.value !== deviceId) return
    applyPackageSnapshot(snapshot)
  } catch {
    if (formDeviceId.value === deviceId) {
      message.warning(t('android_agent.packages_failed'))
    }
  } finally {
    if (formDeviceId.value === deviceId) {
      packagesLoading.value = false
    }
  }
}

async function openPackageHistory() {
  const deviceId = formDeviceId.value
  if (deviceId === undefined) return
  try {
    packageHistory.value = await deviceApi.packageHistory(deviceId, 8)
  } catch {
    packageHistory.value = []
  }
}

function handleHistoryOpen(open: boolean) {
  historyOpen.value = open
  if (open) void openPackageHistory()
}

function applyHistory(item: DevicePackageSnapshotItem) {
  historyOpen.value = false
  applyPackageSnapshot(item)
  if (item.current_package) {
    formPackage.value = item.current_package
  }
}

watch(
  () => formDeviceId.value,
  () => {
    devicePackages.value = []
    foregroundPackage.value = null
    packageReadAt.value = null
    packageHistory.value = []
    void loadDevicePackages(false)
  },
)

function addVarRow() {
  formVars.value = [...formVars.value, { key: '', value: '' }]
}

function removeVarRow(index: number) {
  formVars.value = formVars.value.filter((_, idx) => idx !== index)
}

function buildContextValues(): Record<string, string> {
  const result: Record<string, string> = {}
  for (const row of formVars.value) {
    const key = row.key.trim()
    if (key) {
      result[key] = row.value
    }
  }
  return result
}

function getAgentApi() {
  try {
    return androidAgentApi ?? null
  } catch {
    return null
  }
}

async function refreshModels() {
  if (!props.projectId) return
  try {
    const api = getAgentApi()
    if (typeof api?.listModels !== 'function') return
    const list = await api.listModels(props.projectId)
    models.value = Array.isArray(list) ? list : []
    modelsLoaded.value = true
    if (formLlmConfigId.value === undefined && models.value.length) {
      const preferred = models.value.find((m) => m.supports_vision) ?? models.value[0]
      formLlmConfigId.value = preferred.id
    }
  } catch {
    modelsLoaded.value = true
  }
}

async function refreshDrafts() {
  if (!props.projectId || !sessionId.value) return
  try {
    const api = getAgentApi()
    if (typeof api?.listSessionDrafts !== 'function') return
    const list = await api.listSessionDrafts(props.projectId, sessionId.value)
    drafts.value = Array.isArray(list) ? list : []
    if (drafts.value.length) {
      const currentMatch = draft.value ? drafts.value.find((d) => d.id === draft.value?.id) : undefined
      const selected = currentMatch ?? drafts.value[0]
      draft.value = selected
      publishedCaseId.value = selected.published_case_id ?? null
      if (!replayModuleId.value && moduleOptions.value.length) {
        replayModuleId.value = moduleOptions.value[0].value
      }
    }
  } catch {
    // 尚无草稿或测试桩未提供 listSessionDrafts 时忽略
  }
}

function selectDraftVersion(val: unknown) {
  const draftId = typeof val === 'number' ? val : Number(val)
  const chosen = drafts.value.find((d) => d.id === draftId)
  if (!chosen) return
  draft.value = chosen
  editingDraft.value = false
  previewItems.value = []
  latestReplay.value = null
  publishedCaseId.value = chosen.published_case_id ?? null
}

async function refreshReplayStatus() {
  if (!props.projectId || !latestReplay.value) return
  try {
    const api = getAgentApi()
    if (typeof api?.getReplay !== 'function') return
    const updated = await api.getReplay(props.projectId, latestReplay.value.id)
    latestReplay.value = updated
    if (updated.status === 'passed' || updated.status === 'failed') {
      await refreshDrafts()
    }
  } catch (error) {
    errorMessage.value = describeError(error)
  }
}

async function refreshSession() {
  if (!props.projectId || !sessionId.value) return
  session.value = await androidAgentApi.getSession(props.projectId, sessionId.value)
  await refreshEvents()
}

async function refreshSessionsList() {
  if (!props.projectId) {
    sessions.value = []
    return
  }
  try {
    const api = getAgentApi()
    if (typeof api?.listSessions !== 'function') {
      sessions.value = []
      return
    }
    sessions.value = await api.listSessions(props.projectId)
  } catch {
    // 忽略加载历史列表异常
  }
}

async function handleSessionSelect(val: unknown) {
  const sid = typeof val === 'number' ? val : Number(val)
  if (!sid || isNaN(sid)) {
    session.value = null
    events.value = []
    drafts.value = []
    draft.value = null
    latestReplay.value = null
    editingDraft.value = false
    showCompleteForm.value = false
    previewItems.value = []
    publishedCaseId.value = null
    return
  }
  if (!props.projectId) return
  loading.value = true
  errorMessage.value = ''
  try {
    session.value = await androidAgentApi.getSession(props.projectId, sid)
    drafts.value = []
    draft.value = null
    latestReplay.value = null
    editingDraft.value = false
    showCompleteForm.value = false
    previewItems.value = []
    publishedCaseId.value = null
    await refreshEvents()
    await refreshDrafts()
    startPolling()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  if (!props.projectId) return
  loading.value = true
  errorMessage.value = ''
  try {
    await Promise.all([refreshModels(), refreshSessionsList()])
    if (sessionId.value) {
      await refreshSession()
      await refreshDrafts()
    }
  } catch {
    errorMessage.value = t('android_agent.error_generic')
  } finally {
    loading.value = false
  }
}

async function createSession() {
  const deviceId = formDeviceId.value
  if (!props.projectId || deviceId === undefined) return
  creating.value = true
  errorMessage.value = ''
  try {
    const payload: AgentSessionCreatePayload = {
      device_id: deviceId,
      package_name: formPackage.value.trim(),
      goal: formGoal.value.trim(),
      expected_outcome: formOutcome.value.trim(),
      budget: { max_steps: formMaxSteps.value, max_calls: formMaxCalls.value },
    }
    const trimmedTitle = formTitle.value.trim()
    if (trimmedTitle) payload.title = trimmedTitle
    if (formLlmConfigId.value !== undefined && formLlmConfigId.value !== null) {
      payload.llm_config_id = formLlmConfigId.value
    }
    const ctxVars = buildContextValues()
    if (Object.keys(ctxVars).length > 0) {
      payload.context_values = ctxVars
    }

    const created = await androidAgentApi.createSession(
      props.projectId,
      payload,
      'agent-session-' + Date.now(),
    )
    session.value = created
    sessions.value = [created, ...sessions.value]
    drafts.value = []
    draft.value = null
    latestReplay.value = null
    editingDraft.value = false
    showCompleteForm.value = false
    previewItems.value = []
    publishedCaseId.value = null
    await refreshEvents()
    startPolling()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    creating.value = false
  }
}

async function startSession() {
  if (!props.projectId || !sessionId.value) return
  acting.value = true
  try {
    session.value = await androidAgentApi.startSession(props.projectId, sessionId.value)
    await refreshEvents()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    acting.value = false
  }
}

async function runLoop() {
  if (!props.projectId || !sessionId.value) return
  running.value = true
  errorMessage.value = ''
  message.info(t('android_agent.run_started'))
  try {
    // 阻塞调用：后端一直跑到收敛（暂停/失败/预算耗尽）才返回，结果只给稳定状态与用量
    const result = await androidAgentApi.runSession(props.projectId, sessionId.value)
    message.info(t('android_agent.run_finished', { status: result.status, reason: result.reason }))
    await refreshSession()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    running.value = false
  }
}

async function control(action: 'pause' | 'takeover' | 'resume' | 'cancel') {
  if (!props.projectId || !session.value) return
  acting.value = true
  try {
    const result = await androidAgentApi.control(props.projectId, session.value.id, action, session.value.version)
    session.value = { ...session.value, status: result.status, controller: result.controller, control_epoch: result.control_epoch, version: result.version }
    await refreshEvents()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    acting.value = false
  }
}

function toggleCompleteForm() {
  showCompleteForm.value = !showCompleteForm.value
}

function addCompleteAssertion() {
  completeAssertions.value = [...completeAssertions.value, { type: 'element_visible', resource_id: '' }]
}

function removeCompleteAssertion(index: number) {
  completeAssertions.value = completeAssertions.value.filter((_, idx) => idx !== index)
}

async function completeSession() {
  if (!props.projectId || !sessionId.value) return
  const assertions = completeAssertions.value
    .map((item) => ({ type: item.type, resource_id: item.resource_id.trim() }))
    .filter((item) => item.resource_id !== '')
  if (!completeConfirmed.value || !assertions.length) return
  completing.value = true
  errorMessage.value = ''
  try {
    session.value = await androidAgentApi.completeSession(props.projectId, sessionId.value, {
      terminal_assertion_confirmed: true,
      terminal_assertions: assertions,
      summary: completeSummary.value.trim(),
    })
    showCompleteForm.value = false
    message.success(t('android_agent.complete_success'))
    await refreshEvents()
    await refreshDrafts()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    completing.value = false
  }
}

async function submitManualAction() {
  if (!props.projectId || !sessionId.value) return
  manualSending.value = true
  errorMessage.value = ''
  try {
    const params: Record<string, unknown> = {}
    if (manualResourceId.value.trim()) params.resource_id = manualResourceId.value.trim()
    if (manualActionType.value === 'input' && manualValue.value) params.text = manualValue.value
    if (manualActionType.value === 'swipe') params.direction = manualValue.value.trim() || 'up'
    if (manualActionType.value === 'wait') params.duration_ms = manualWaitMs.value || 1000
    const requestSignature = JSON.stringify([props.projectId, sessionId.value, manualActionType.value, params])
    let requestKey = manualRequestKeys.get(requestSignature)
    if (!requestKey) {
      requestKey = `manual-${sessionId.value}-${Date.now()}-${++manualRequestSequence}`
      manualRequestKeys.set(requestSignature, requestKey)
    }
    const res = await androidAgentApi.manualAction(props.projectId, sessionId.value, {
      action: manualActionType.value,
      params,
      idempotency_key: requestKey,
    })
    if (['succeeded', 'failed', 'cancelled'].includes(res.status)) manualRequestKeys.delete(requestSignature)
    manualValue.value = ''
    if (res.status === 'succeeded') {
      message.success(t('android_agent.manual_success', { seq: res.seq }))
    } else {
      errorMessage.value = t('android_agent.manual_failed', { status: res.status, code: res.error_code || '-' })
    }
    await refreshSession()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    manualSending.value = false
  }
}

function startEditDraft() {
  if (!draft.value) return
  const existing = (draft.value.assertions || []).map((item) => ({
    type: item.type === 'element_absent' ? ('element_absent' as const) : ('element_visible' as const),
    resource_id: typeof item.resource_id === 'string' ? item.resource_id : '',
  }))
  editAssertions.value = existing.length ? existing : [{ type: 'element_visible', resource_id: '' }]
  editingDraft.value = true
}

function cancelEditDraft() {
  editingDraft.value = false
}

function addDraftEditAssertion() {
  editAssertions.value = [...editAssertions.value, { type: 'element_visible', resource_id: '' }]
}

function removeDraftEditAssertion(index: number) {
  editAssertions.value = editAssertions.value.filter((_, idx) => idx !== index)
}

async function saveDraftEdits() {
  if (!props.projectId || !draft.value) return
  savingDraft.value = true
  errorMessage.value = ''
  try {
    const assertions = editAssertions.value
      .map((item) => ({ type: item.type, resource_id: item.resource_id.trim() }))
      .filter((item) => item.resource_id !== '')
    const updated = await androidAgentApi.updateDraft(props.projectId, draft.value.id, {
      expected_version: draft.value.version,
      assertions,
    })
    draft.value = updated
    drafts.value = [updated, ...drafts.value.filter((d) => d.id !== updated.id)]
    editingDraft.value = false
    previewItems.value = []
    latestReplay.value = null
    publishedCaseId.value = null
    message.success(t('android_agent.draft_saved', { version: updated.version }))
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    savingDraft.value = false
  }
}

async function compileDraft() {
  if (!props.projectId || !sessionId.value) return
  compiling.value = true
  try {
    draft.value = await androidAgentApi.compileDraft(props.projectId, sessionId.value)
    drafts.value = [draft.value, ...drafts.value.filter((d) => d.id !== draft.value?.id)]
    editingDraft.value = false
    latestReplay.value = null
    previewItems.value = []
    publishedCaseId.value = draft.value.published_case_id ?? null
    if (!replayModuleId.value && moduleOptions.value.length) replayModuleId.value = moduleOptions.value[0].value
    await refreshEvents()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    compiling.value = false
  }
}

async function openReplayPreview() {
  if (!props.projectId || !draft.value) return
  try {
    const preview = await androidAgentApi.replayPreview(props.projectId, draft.value.id)
    previewItems.value = preview.items
  } catch (error) {
    errorMessage.value = describeError(error)
  }
}

async function startReplay() {
  const moduleId = replayModuleId.value
  if (!props.projectId || !draft.value || moduleId === undefined) return
  replaying.value = true
  try {
    const handoff = await androidAgentApi.startReplay(props.projectId, draft.value.id, {
      initial_state_confirmed: replayStateConfirmed.value,
      module_id: moduleId,
      idempotency_key: 'agent-replay-' + draft.value.id + '-' + draft.value.version,
    })
    latestReplay.value = handoff.replay ?? null
    const replayId = handoff.replay?.id ?? handoff.run_id
    message.success(t('android_agent.replay_start') + ' #' + replayId)
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    replaying.value = false
  }
}

async function publishDraft() {
  if (!props.projectId || !draft.value) return
  publishing.value = true
  try {
    const result = await androidAgentApi.publishDraft(
      props.projectId,
      draft.value.id,
      'agent-publish-' + draft.value.id + '-' + draft.value.version,
    )
    publishedCaseId.value = result.case_id
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    publishing.value = false
  }
}

function describeError(error: unknown): string {
  const detail =
    typeof error === 'string'
      ? error
      : (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') {
    if (detail.includes('android_agent_disabled')) {
      agentDisabled.value = true
      return t('android_agent.error_disabled')
    }
    if (detail.includes('device_busy')) return t('android_agent.error_device_busy')
    if (detail.includes('model_capability_missing')) return t('android_agent.error_model_missing')
    return detail
  }
  return t('android_agent.error_generic')
}

watch(
  () => props.projectId,
  () => {
    stopPolling()
    sessions.value = []
    session.value = null
    events.value = []
    drafts.value = []
    draft.value = null
    latestReplay.value = null
    editingDraft.value = false
    showCompleteForm.value = false
    previewItems.value = []
    publishedCaseId.value = null
    models.value = []
    modelsLoaded.value = false
    formLlmConfigId.value = undefined
    void refreshModels()
    void refreshSessionsList()
  },
)

onMounted(() => {
  checkRuntimeFeatureFlag()
  void refreshModels()
  void refreshSessionsList()
})

onBeforeUnmount(stopPolling)

// 暴露给父组件与单测的契约面
defineExpose({
  refreshAll,
  refreshModels,
  refreshDrafts,
  refreshReplayStatus,
  createSession,
  startSession,
  runLoop,
  control,
  completeSession,
  submitManualAction,
  compileDraft,
  openReplayPreview,
  startEditDraft,
  saveDraftEdits,
  startReplay,
  publishDraft,
  models,
  agentDisabled,
  formTitle,
  formLlmConfigId,
  formDeviceId,
  formPackage,
  devicePackages,
  packagesLoading,
  loadDevicePackages,
  packageHistory,
  packageReadAt,
  openPackageHistory,
  applyHistory,
  formGoal,
  formOutcome,
  formVars,
  session,
  drafts,
  draft,
  latestReplay,
  showCompleteForm,
  completeAssertions,
  completeConfirmed,
  completeSummary,
  manualActionType,
  manualResourceId,
  manualValue,
  manualWaitMs,
  editingDraft,
  editAssertions,
  replayStateConfirmed,
  replayModuleId,
  publishedCaseId,
  errorMessage,
  canRunLoop,
  canStartReplay,
  canPublish,
})
</script>

<style scoped>
.agent-panel {
  margin-top: 16px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  padding: 20px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-kicker {
  color: var(--c-text-tertiary);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0;
  text-transform: none;
}

.panel-head h2 {
  margin: 4px 0 0;
  color: var(--c-text);
  font-size: 16px;
  font-weight: 600;
}

.agent-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-select {
  width: 220px;
}

.agent-description {
  margin: 6px 0 var(--space-4);
  color: var(--c-text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.agent-alert {
  margin-bottom: 16px;
  border-radius: var(--radius-sm);
}

.agent-empty {
  padding: 24px;
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: 13px;
  background: var(--c-bg-subtle);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}

.agent-setup {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.section-head {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--c-border-subtle);
  margin-bottom: var(--space-4);
}

.section-title {
  color: var(--c-text);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}

.setup-fields {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: var(--space-4);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.field label,
.field-label {
  color: var(--c-text-secondary);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}

.field-device {
  grid-column: span 4;
}

.field-package {
  grid-column: span 8;
}

.field-goal,
.field-outcome {
  grid-column: span 12;
}

.field-budget {
  grid-column: span 6;
}

.field-control,
.budget-row :deep(.ant-input-number) {
  width: 100%;
}

.package-control {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.package-input {
  flex: 1;
  min-width: 0;
}

.package-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 16px;
}

.package-count {
  flex: none;
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.form-hint {
  color: var(--c-text-tertiary);
  font-size: 11px;
  line-height: 1.4;
}

.package-history {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 260px;
  max-height: 240px;
  overflow: auto;
}

.package-history-head {
  display: grid;
  grid-template-columns: 76px 40px minmax(0, 1fr);
  gap: 8px;
  padding: 0 6px 4px;
  color: var(--c-text-tertiary);
  font-size: 11px;
  border-bottom: 1px solid var(--c-border-subtle);
  margin-bottom: 2px;
}

.package-history-item {
  display: grid;
  grid-template-columns: 76px 40px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  padding: 4px 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.package-history-item:hover {
  background: var(--c-bg-hover, rgba(0, 0, 0, 0.04));
}

.package-history-foreground {
  overflow: hidden;
  color: var(--c-text-tertiary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.budget-row {
  display: flex;
  gap: var(--space-4);
}

.budget-input {
  display: flex;
  flex: 1;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.budget-input span {
  flex: none;
}

.setup-actions {
  grid-column: span 6;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  min-width: 0;
}

.setup-required {
  color: var(--c-text-tertiary);
  font-size: 11px;
  line-height: 1.4;
  text-align: right;
}

.agent-session {
  margin-top: var(--space-5);
}

.session-head {
  align-items: baseline;
  margin-bottom: var(--space-3);
}

.session-title-text {
  flex: 1;
  overflow: hidden;
  color: var(--c-text-tertiary) !important;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tabular-nums {
  font-family: 'JetBrains Mono', monospace, sans-serif;
  font-variant-numeric: tabular-nums;
}

.session-meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.meta-item {
  color: var(--c-text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

.meta-sep {
  width: 1px;
  height: 12px;
  background: var(--c-border);
}

.agent-controls-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  padding: var(--space-2) 0;
  border-top: 1px solid var(--c-border-subtle);
  border-bottom: 1px solid var(--c-border-subtle);
}

.control-sep {
  width: 1px;
  height: 18px;
  margin: 0 var(--space-1);
  background: var(--c-border);
}

.control-spacer {
  flex: 1;
}

.agent-hint {
  margin: var(--space-2) 0 var(--space-4);
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.agent-session-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  gap: var(--space-4);
  align-items: start;
}

.agent-events,
.agent-draft {
  min-width: 0;
  padding: var(--space-4) 0 0;
  border: 0;
  border-top: 1px solid var(--c-border-subtle);
  border-radius: 0;
  background: transparent;
}

@media (max-width: 1180px) {
  .agent-session-body {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .field-device,
  .field-package,
  .field-budget,
  .setup-actions {
    grid-column: span 12;
  }

  .setup-actions {
    justify-content: space-between;
  }
}

.agent-events {
  margin-bottom: 0;
}

.agent-events-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.agent-events-head strong {
  font-size: 13px;
  color: var(--c-text);
}

.agent-events-note {
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.agent-events-empty {
  color: var(--c-text-tertiary);
  font-size: 12px;
  padding: 12px 0;
  text-align: center;
}

.agent-event-list {
  max-height: 240px;
  overflow-y: auto;
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  background: var(--c-bg-subtle);
}

.agent-event-row {
  display: grid;
  grid-template-columns: 60px 1fr 100px;
  gap: 12px;
  font-size: 12px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--c-border-subtle);
  align-items: center;
}

.agent-event-row:last-child {
  border-bottom: none;
}

.agent-event-seq {
  color: var(--c-text-tertiary);
  font-family: 'JetBrains Mono', monospace, sans-serif;
  font-variant-numeric: tabular-nums;
}

.agent-event-type {
  color: var(--c-text);
  font-weight: 500;
}

.agent-event-time {
  color: var(--c-text-tertiary);
  font-size: 11px;
  text-align: right;
}


.agent-draft-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.agent-draft-head strong {
  font-size: 13px;
  color: var(--c-text);
}

.agent-draft-empty {
  margin: 0;
  padding: var(--space-3) 0;
  color: var(--c-text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

.agent-draft-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.agent-draft-hash {
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.agent-blocking {
  background: var(--c-error-soft, rgba(220, 38, 38, 0.08));
  border: 1px solid var(--c-error, #dc2626);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  margin-bottom: 12px;
  color: var(--c-error, #dc2626);
  font-size: 12px;
}

.agent-blocking ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.agent-steps {
  margin-bottom: 16px;
  border: 1px solid var(--c-border-subtle);
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.agent-steps ol {
  margin: 6px 0 0;
  padding-left: 20px;
  color: var(--c-text);
}

.agent-steps li {
  margin-bottom: 4px;
}

.agent-replay {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.agent-replay-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.agent-preview-items {
  margin-top: 8px;
  font-size: 12px;
}

.agent-preview-item {
  display: block;
  margin-bottom: 4px;
}

.agent-preview-item.fail {
  color: var(--c-error, #dc2626);
}

.agent-preview-item.warn {
  color: var(--c-warning, #d97706);
}

.agent-published {
  color: var(--c-success, #059669);
  font-size: 12px;
  font-weight: 500;
  margin-top: 4px;
}

.agent-sensitive-hint {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-muted, #64748b);
}

.apk-quick-pick {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.apk-quick-chip {
  border: 1px solid var(--c-border);
  background: var(--c-bg);
  color: var(--c-text);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  cursor: pointer;
}

.apk-quick-chip:hover {
  border-color: var(--c-primary, #1677ff);
}

.vars-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.vars-row,
.assertion-edit-row,
.subpanel-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.vars-row > :not(button),
.assertion-edit-row > :not(button):not(.assertion-type-select) {
  flex: 1 1 160px;
}

.assertion-type-select,
.manual-action-select,
.draft-version-select {
  min-width: 170px;
}

.coord-pair {
  display: flex;
  gap: 6px;
}

.agent-subpanel {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  background: var(--c-bg);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.complete-footer,
.draft-head-actions,
.draft-editor-actions,
.agent-replay-status,
.agent-published-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.agent-event-detail {
  color: var(--c-text-muted, #64748b);
  font-size: 12px;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-assertions {
  font-size: 12px;
  margin-bottom: 8px;
}
</style>
