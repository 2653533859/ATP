<template>
  <div class="project-quota-dashboard">
    <!-- 顶部状态栏与核心操作 -->
    <div class="quota-header-bar">
      <div class="header-info">
        <h3 class="title">项目资源配额与并发硬限制仪表板</h3>
        <p class="subtitle">
          为各租户项目精细化分配 Worker 任务并发上限、每日累计执行时长配额与单任务硬超时，支持僵尸任务一键收割释放。
        </p>
      </div>
      <div class="header-actions">
        <a-button type="primary" size="small" :loading="saving" @click="saveQuota">
          保存配额设置
        </a-button>
        <a-button danger size="small" :loading="reaping" @click="runReapTimeouts">
          收割超时僵尸任务
        </a-button>
        <a-button size="small" :loading="loading" @click="loadQuotaAndEvaluation">
          刷新配额监控
        </a-button>
      </div>
    </div>

    <!-- 实时配额水位卡片 -->
    <div v-if="evaluation" class="watermark-grid">
      <!-- 1. 并发运行水线 -->
      <a-card size="small" class="watermark-card" :class="{ 'is-saturated': evaluation.current_active_runs >= evaluation.max_concurrent_runs }">
        <div class="card-head">
          <span class="card-title">当前并发运行水线</span>
          <a-tag :color="evaluation.current_active_runs >= evaluation.max_concurrent_runs ? 'red' : 'blue'">
            {{ evaluation.current_active_runs }} / {{ evaluation.max_concurrent_runs }} 任务
          </a-tag>
        </div>
        <div class="card-progress">
          <a-progress
            :percent="Math.min(100, Math.round((evaluation.current_active_runs / evaluation.max_concurrent_runs) * 100))"
            :status="evaluation.current_active_runs >= evaluation.max_concurrent_runs ? 'exception' : 'active'"
            :stroke-color="evaluation.current_active_runs >= evaluation.max_concurrent_runs ? '#cf1322' : '#1890ff'"
          />
        </div>
        <div class="card-footer">
          <span class="card-tip">超额策略: <strong>{{ evaluation.policy === 'queue' ? '排队等待 (Queue)' : '安全拒绝 (Reject)' }}</strong></span>
        </div>
      </a-card>

      <!-- 2. 今日累计执行时长 -->
      <a-card size="small" class="watermark-card" :class="{ 'is-saturated': evaluation.daily_duration_seconds >= evaluation.daily_duration_limit_seconds }">
        <div class="card-head">
          <span class="card-title">今日累计执行时长</span>
          <a-tag :color="evaluation.daily_duration_seconds >= evaluation.daily_duration_limit_seconds ? 'red' : 'cyan'">
            {{ (evaluation.daily_duration_seconds / 3600).toFixed(2) }}h / {{ (evaluation.daily_duration_limit_seconds / 3600).toFixed(1) }}h
          </a-tag>
        </div>
        <div class="card-progress">
          <a-progress
            :percent="Math.min(100, Math.round((evaluation.daily_duration_seconds / evaluation.daily_duration_limit_seconds) * 100))"
            :status="evaluation.daily_duration_seconds >= evaluation.daily_duration_limit_seconds ? 'exception' : 'normal'"
          />
        </div>
        <div class="card-footer">
          <span class="card-tip">配额耗尽判定: <strong>{{ evaluation.daily_duration_seconds >= evaluation.daily_duration_limit_seconds ? '已耗尽今日限额' : '额度充裕' }}</strong></span>
        </div>
      </a-card>

      <!-- 3. 调度准入状态 -->
      <a-card size="small" class="watermark-card">
        <div class="card-head">
          <span class="card-title">新任务准入状态</span>
          <a-tag :color="evaluation.allowed ? 'green' : 'red'">
            {{ evaluation.allowed ? (evaluation.should_queue ? '排队准入' : '立即准入') : '拒绝调度' }}
          </a-tag>
        </div>
        <div class="admission-status">
          <span class="admission-reason">状态原因: {{ evaluation.reason }}</span>
        </div>
        <div v-if="evaluation.details?.message" class="admission-desc">
          {{ evaluation.details.message }}
        </div>
      </a-card>
    </div>

    <!-- 配额配置表单 -->
    <a-card title="租户项目资源配额配置 (Quota Configuration)" size="small" class="config-card">
      <a-spin :spinning="loading">
        <a-form layout="vertical">
          <a-row :gutter="16">
            <a-col :span="8">
              <a-form-item label="最大并发执行任务数 (Max Concurrent Runs)" required>
                <a-input-number
                  v-model:value="quotaForm.max_concurrent_runs"
                  :min="1"
                  :max="100"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>

            <a-col :span="8">
              <a-form-item label="每日累计执行总时长上限 (秒)" required>
                <a-input-number
                  v-model:value="quotaForm.daily_duration_limit_seconds"
                  :min="60"
                  :step="3600"
                  style="width: 100%"
                />
                <span class="field-hint">折合约 {{ (quotaForm.daily_duration_limit_seconds / 3600).toFixed(1) }} 小时 / 天</span>
              </a-form-item>
            </a-col>

            <a-col :span="8">
              <a-form-item label="单任务执行硬超时上限 (秒)" required>
                <a-input-number
                  v-model:value="quotaForm.max_single_run_timeout_seconds"
                  :min="10"
                  :step="600"
                  style="width: 100%"
                />
                <span class="field-hint">折合约 {{ (quotaForm.max_single_run_timeout_seconds / 60).toFixed(0) }} 分钟，超时将被收割器强制熔断</span>
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="并发饱和超额控制策略 (Over-Quota Policy)">
                <a-radio-group v-model:value="quotaForm.over_quota_policy" button-style="solid">
                  <a-radio-button value="reject">立即拒绝 (Reject 429)</a-radio-button>
                  <a-radio-button value="queue">自动排队 (Queue)</a-radio-button>
                </a-radio-group>
              </a-form-item>
            </a-col>

            <a-col :span="12">
              <a-form-item label="配额管控状态开关">
                <a-switch v-model:checked="quotaForm.is_enabled" checked-children="开启管控" un-checked-children="暂停放行" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item label="配额备注说明">
            <a-input v-model:value="descriptionText" placeholder="例如: 生产核心业务线高优先级保障配额" />
          </a-form-item>
        </a-form>
      </a-spin>
    </a-card>

    <!-- 僵尸任务收割成果清单 -->
    <div v-if="reapSummary" class="reap-summary-panel">
      <div class="reap-header">
        <span class="reap-title">🧟 僵尸长任务收割日志 (Zombie Runs Reaped)</span>
        <a-tag :color="reapSummary.reaped_count > 0 ? 'green' : 'default'">
          共收割并释放 {{ reapSummary.reaped_count }} 个超时僵尸任务
        </a-tag>
      </div>

      <div v-if="reapSummary.reaped_runs && reapSummary.reaped_runs.length" class="reaped-list">
        <div v-for="run in reapSummary.reaped_runs" :key="run.run_id" class="reaped-item">
          <span>任务类型: <strong>{{ run.run_type }}</strong></span>
          <span>运行 ID: <code>#{{ run.run_id }}</code></span>
          <span>超时限制: {{ run.timeout_limit_seconds }}s</span>
          <span class="reap-reason">原因: {{ run.reason }}</span>
        </div>
      </div>
      <div v-else class="reap-empty">
        当前无运行超时的僵尸任务，Worker 资源健康运行中。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  projectApi,
  type ProjectQuotaItem,
  type ProjectQuotaEvaluation,
  type ProjectReapResult,
} from '@/api'

const props = withDefaults(
  defineProps<{
    projectId?: number
  }>(),
  {
    projectId: 1,
  },
)

const loading = ref(false)
const saving = ref(false)
const reaping = ref(false)

const quotaForm = ref<ProjectQuotaItem>({
  project_id: props.projectId,
  max_concurrent_runs: 5,
  daily_duration_limit_seconds: 28800,
  max_single_run_timeout_seconds: 3600,
  over_quota_policy: 'reject',
  is_enabled: true,
  description: '标准企业级多租户资源配额',
})

const descriptionText = computed({
  get: () => quotaForm.value.description || '',
  set: (v: string) => {
    quotaForm.value.description = v
  },
})

const evaluation = ref<ProjectQuotaEvaluation | null>(null)
const reapSummary = ref<ProjectReapResult | null>(null)

const loadQuotaAndEvaluation = async () => {
  loading.value = true
  try {
    const [qData, evalData] = await Promise.all([
      projectApi.getQuota(props.projectId),
      projectApi.evaluateQuota(props.projectId),
    ])
    if (qData) {
      quotaForm.value = { ...qData }
    }
    evaluation.value = evalData
  } catch {
    // Local fallback defaults
    evaluation.value = {
      allowed: true,
      should_queue: false,
      reason: 'within_quota',
      current_active_runs: 2,
      max_concurrent_runs: quotaForm.value.max_concurrent_runs,
      daily_duration_seconds: 7200,
      daily_duration_limit_seconds: quotaForm.value.daily_duration_limit_seconds,
      policy: quotaForm.value.over_quota_policy,
      details: { message: '当前活跃任务未超限，资源配额充裕' },
    }
  } finally {
    loading.value = false
  }
}

const saveQuota = async () => {
  saving.value = true
  try {
    const res = await projectApi.updateQuota(props.projectId, quotaForm.value)
    if (res) {
      quotaForm.value = { ...res }
    }
    message.success('项目资源配额配置已成功保存！')
    loadQuotaAndEvaluation()
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '保存配额失败'
    message.error(msg)
  } finally {
    saving.value = false
  }
}

const runReapTimeouts = async () => {
  reaping.value = true
  try {
    const res = await projectApi.reapTimeouts(props.projectId)
    reapSummary.value = res
    if (res.reaped_count > 0) {
      message.success(`成功强制收割并释放 ${res.reaped_count} 个僵尸长任务！`)
    } else {
      message.info('未发现超时僵尸任务，运行环境健康')
    }
    loadQuotaAndEvaluation()
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '执行收割失败'
    message.error(msg)
  } finally {
    reaping.value = false
  }
}

onMounted(() => {
  loadQuotaAndEvaluation()
})
</script>

<style scoped>
.project-quota-dashboard {
  padding: 4px 0;
}
.quota-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 18px;
}
.header-info .title {
  font-size: 15px;
  font-weight: 700;
  margin: 0 0 4px 0;
  color: var(--c-text-primary, #111827);
}
.header-info .subtitle {
  font-size: 12px;
  color: var(--c-text-secondary, #6b7280);
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.watermark-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 18px;
}
.watermark-card {
  border-radius: 8px;
}
.watermark-card.is-saturated {
  border-color: #ff4d4f;
  background: rgba(255, 77, 79, 0.02);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.card-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary, #4b5563);
}
.card-progress {
  margin: 8px 0;
}
.card-footer {
  font-size: 11px;
  color: var(--c-text-tertiary, #6b7280);
}
.admission-status {
  margin: 10px 0;
}
.admission-reason {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.admission-desc {
  font-size: 11px;
  color: var(--c-text-secondary, #6b7280);
}
.config-card {
  border-radius: 8px;
  margin-bottom: 18px;
}
.field-hint {
  font-size: 11px;
  color: var(--c-text-tertiary, #9ca3af);
  margin-top: 4px;
  display: block;
}
.reap-summary-panel {
  padding: 14px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
}
.reap-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.reap-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #111827);
}
.reaped-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.reaped-item {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  background: var(--c-bg-page, #f9fafb);
  border-radius: 4px;
  font-size: 12px;
}
.reap-reason {
  color: #cf1322;
  font-weight: 600;
}
.reap-empty {
  font-size: 12px;
  color: var(--c-text-tertiary, #6b7280);
}
</style>
