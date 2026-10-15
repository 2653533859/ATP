<template>
  <a-drawer
    :open="open"
    :width="920"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <span>移动端真机智能回放与动作执行调度器</span>
    </template>

    <div class="device-playback-drawer">
      <!-- 头部控制栏：设备连接与目标 App -->
      <a-card size="small" class="control-card">
        <a-form layout="inline" class="control-form">
          <a-form-item label="设备平台">
            <a-select v-model:value="formPlatform" style="width: 110px" :disabled="session?.status === 'running'">
              <a-select-option value="android">Android</a-select-option>
              <a-select-option value="ios">iOS</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="设备序列号 / UDID" required>
            <a-input
              v-model:value="formSerial"
              placeholder="例如: emulator-5554"
              :disabled="session?.status === 'running'"
              style="width: 170px"
            />
          </a-form-item>

          <a-form-item label="目标应用 (Package / Bundle ID)" required>
            <a-input
              v-model:value="formTargetApp"
              placeholder="例如: com.example.app"
              :disabled="session?.status === 'running'"
              style="width: 190px"
            />
          </a-form-item>

          <a-form-item class="actions-form-item">
            <a-button
              v-if="session?.status !== 'running'"
              type="primary"
              :loading="loadingAction"
              @click="handleInitSession"
            >
              初始化真机连接
            </a-button>
            <a-button
              v-else
              danger
              type="primary"
              :loading="loadingAction"
              @click="handleTeardownSession"
            >
              安全回收会话
            </a-button>
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 状态与回放进度统计指标卡 -->
      <div class="metrics-row">
        <div class="metric-card">
          <span class="metric-label">连接状态</span>
          <div class="metric-value status-val">
            <span v-if="session?.status === 'running'" class="live-dot" />
            <a-tag :color="session?.status === 'running' ? 'success' : (session?.status === 'teardown' ? 'blue' : 'default')">
              {{ session?.status === 'running' ? '真机已连接就绪' : (session?.status === 'teardown' ? '已安全回收' : '空闲未连接') }}
            </a-tag>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">总执行步骤</span>
          <div class="metric-value">
            <strong>{{ session?.total_steps ?? executedSteps.length }}</strong>
            <small class="metric-unit">步</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">成功通过 / 失败</span>
          <div class="metric-value">
            <strong class="success-text">{{ session?.passed_steps ?? passedCount }}</strong>
            <span class="slash">/</span>
            <strong class="fail-text">{{ session?.failed_steps ?? failedCount }}</strong>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">失效智能自愈</span>
          <div class="metric-value">
            <strong class="heal-text">{{ session?.healed_steps ?? healedCount }}</strong>
            <small class="metric-unit">次自愈补偿</small>
          </div>
        </div>
      </div>

      <!-- 动作序列编排与上下文变量配置 -->
      <a-card size="small" title="待执行动作序列与变量上下文 ({{var}})" class="steps-card">
        <template #extra>
          <a-space>
            <a-button size="small" @click="loadPresetSteps">
              载入标准回放动作
            </a-button>
            <a-button size="small" type="primary" ghost class="healing-inspector-btn" @click="showHealingInspector = true">
              视觉/DOM 混合自愈排查
            </a-button>
            <a-button
              size="small"
              type="primary"
              :disabled="session?.status !== 'running' || executing"
              :loading="executing"
              @click="handleExecuteAll"
            >
              顺序执行全部步骤
            </a-button>
          </a-space>
        </template>

        <a-row :gutter="16">
          <a-col :span="14">
            <div class="sequence-list">
              <div v-for="(step, idx) in plannedSteps" :key="idx" class="sequence-item">
                <span class="seq-idx">#{{ idx + 1 }}</span>
                <a-tag :color="getActionColor(step.action)">{{ step.action }}</a-tag>
                <code class="seq-params">{{ JSON.stringify(step.params) }}</code>
              </div>
            </div>
          </a-col>

          <a-col :span="10">
            <div class="context-editor">
              <div class="ctx-title">运行时变量上下文 (JSON 动态注入)</div>
              <a-textarea
                v-model:value="contextJsonStr"
                :rows="5"
                placeholder='例如: { "keyword": "自动化测试", "btn_id": "search_btn" }'
                class="json-textarea"
              />
            </div>
          </a-col>
        </a-row>
      </a-card>

      <!-- 实时执行步骤明细流水 -->
      <a-card size="small" title="实时真机回放执行结果明细" class="results-card">
        <a-table
          :data-source="session?.step_records?.length ? session.step_records : executedSteps"
          :columns="resultColumns"
          row-key="step_no"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'step_no'">
              <span>步骤 #{{ record.step_no }}</span>
            </template>

            <template v-if="column.key === 'action'">
              <a-tag :color="getActionColor(record.action)">{{ record.action }}</a-tag>
            </template>

            <template v-if="column.key === 'params'">
              <code class="params-code">{{ JSON.stringify(record.params) }}</code>
            </template>

            <template v-if="column.key === 'status'">
              <a-tag v-if="record.status === 'passed'" color="green">执行成功</a-tag>
              <a-tag v-else-if="record.status === 'healed'" color="orange">智能自愈</a-tag>
              <a-tag v-else color="red">执行失败</a-tag>
            </template>

            <template v-if="column.key === 'duration_ms'">
              <span>{{ record.duration_ms }} ms</span>
            </template>
          </template>
        </a-table>
      </a-card>
      <VisualSelfHealingInspector v-model:open="showHealingInspector" />
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  devicePlaybackApi,
  type PlaybackSessionSummary,
  type PlaybackStepRecord,
} from '@/api/devicePlayback'
import VisualSelfHealingInspector from './VisualSelfHealingInspector.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    deviceId?: number
    serialOrUdid?: string
    platform?: 'android' | 'ios'
    targetApp?: string
  }>(),
  {
    open: false,
    deviceId: 1,
    serialOrUdid: 'emulator-5554',
    platform: 'android',
    targetApp: 'com.example.app',
  }
)
const showHealingInspector = ref(false)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const formPlatform = ref(props.platform)
const formSerial = ref(props.serialOrUdid)
const formTargetApp = ref(props.targetApp)
const loadingAction = ref(false)
const executing = ref(false)

const session = ref<PlaybackSessionSummary | null>(null)
const executedSteps = ref<PlaybackStepRecord[]>([])

const plannedSteps = ref<Array<{ action: string; params: Record<string, any> }>>([
  { action: 'click', params: { resource_id: 'btn_search', text: '搜索' } },
  { action: 'input_text', params: { text: '{{keyword}}', clear_first: true } },
  { action: 'click', params: { resource_id: 'btn_submit' } },
  { action: 'assert_text', params: { expected_text: '{{keyword}}' } },
])

const contextJsonStr = ref('{\n  "keyword": "自动化测试商品"\n}')

const resultColumns = [
  { title: '序号', key: 'step_no', width: 90 },
  { title: '动作类型', key: 'action', width: 110 },
  { title: '执行参数', key: 'params', ellipsis: true },
  { title: '执行状态', key: 'status', width: 100 },
  { title: '单步耗时', key: 'duration_ms', width: 95 },
]

const passedCount = computed(() => executedSteps.value.filter((s) => s.status === 'passed').length)
const failedCount = computed(() => executedSteps.value.filter((s) => s.status === 'failed').length)
const healedCount = computed(() => executedSteps.value.filter((s) => s.status === 'healed').length)

function getActionColor(action: string): string {
  switch (action) {
    case 'click':
      return 'blue'
    case 'input_text':
      return 'green'
    case 'swipe':
      return 'purple'
    case 'assert_text':
      return 'cyan'
    case 'screenshot':
      return 'orange'
    default:
      return 'default'
  }
}

function handleClose() {
  emit('update:open', false)
}

function loadPresetSteps() {
  plannedSteps.value = [
    { action: 'click', params: { resource_id: 'btn_search', text: '搜索' } },
    { action: 'input_text', params: { text: '{{keyword}}', clear_first: true } },
    { action: 'click', params: { resource_id: 'btn_submit' } },
    { action: 'assert_text', params: { expected_text: '{{keyword}}' } },
  ]
  message.success('已载入 4 个典型真机回放动作')
}

async function handleInitSession() {
  loadingAction.value = true
  try {
    const res = await devicePlaybackApi.initSession({
      platform: formPlatform.value,
      device_id: props.deviceId,
      serial_or_udid: formSerial.value.trim(),
      target_app: formTargetApp.value.trim(),
    })
    session.value = res
    executedSteps.value = []
    message.success('真机受控回放会话初始化成功！')
  } catch (err: any) {
    message.error(err.message || '初始化真机回放失败')
  } finally {
    loadingAction.value = false
  }
}

async function handleTeardownSession() {
  if (!session.value) return
  loadingAction.value = true
  try {
    const res = await devicePlaybackApi.teardownSession(session.value.session_id)
    session.value = res
    message.success('真机回放会话已安全回收！')
  } catch (err: any) {
    message.error(err.message || '安全回收失败')
  } finally {
    loadingAction.value = false
  }
}

async function handleExecuteAll() {
  if (!session.value || session.value.status !== 'running') {
    message.warning('请先初始化并拉起真机连接')
    return
  }
  executing.value = true
  try {
    for (let i = 0; i < plannedSteps.value.length; i++) {
      const step = plannedSteps.value[i]
      const res = await devicePlaybackApi.executeStep(session.value.session_id, {
        step_no: i + 1,
        step_dict: step,
      })
      executedSteps.value.push(res)
    }
    // Refresh session summary
    const updated = await devicePlaybackApi.getSession(session.value.session_id)
    session.value = updated
    message.success('全部预设动作步骤已执行完毕！')
  } catch (err: any) {
    message.error(err.message || '步骤执行失败')
  } finally {
    executing.value = false
  }
}
</script>

<style scoped>
.device-playback-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.control-card {
  border-radius: 8px;
}

.control-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.actions-form-item {
  margin-left: auto;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  display: block;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  color: var(--c-text, #0f172a);
  display: flex;
  align-items: center;
  gap: 6px;
}

.metric-unit {
  font-size: 12px;
  font-weight: normal;
  color: var(--c-text-tertiary, #94a3b8);
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 8px #22c55e;
}

.status-val {
  font-size: 14px;
}

.success-text {
  color: #16a34a;
}

.slash {
  color: var(--c-text-tertiary, #94a3b8);
  font-weight: normal;
}

.fail-text {
  color: #dc2626;
}

.heal-text {
  color: #ea580c;
}

.steps-card,
.results-card {
  border-radius: 8px;
}

.sequence-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 180px;
  overflow-y: auto;
}

.sequence-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  font-size: 12px;
}

.seq-idx {
  font-weight: 600;
  color: #64748b;
}

.seq-params {
  font-family: monospace;
  font-size: 11px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ctx-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--c-text-secondary, #64748b);
}

.json-textarea {
  font-family: monospace;
  font-size: 11px;
  border-radius: 6px;
}

.params-code {
  font-family: monospace;
  font-size: 11px;
  color: #475569;
}
</style>
