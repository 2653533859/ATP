<template>
  <a-modal
    :open="open"
    :width="880"
    destroy-on-close
    :footer="null"
    @cancel="handleClose"
  >
    <template #title>
      <div class="modal-title-box">
        <span>变更影响用例自动化精准回归套件合成向导</span>
        <a-tag v-if="isBreaking" color="red">P0 紧急抢占回归</a-tag>
        <a-tag v-else color="orange">P1 核心精准回归</a-tag>
      </div>
    </template>

    <div class="targeted-regression-wizard">
      <!-- 步骤指示器 -->
      <a-steps :current="currentStep" size="small" class="wizard-steps">
        <a-step title="受损用例过滤与去重" />
        <a-step title="调度策略与套件配置" />
        <a-step title="合成结果与调度交付" />
      </a-steps>

      <!-- Step 0: 受损用例过滤与去重 -->
      <div v-if="currentStep === 0" class="step-content">
        <div class="step-header">
          <span class="step-desc">
            系统已自动对接口契约变更影响面推导出的受损用例进行原子去重，请确认纳入本次回归套件的用例清单：
          </span>
          <a-tag color="blue">待回归用例：{{ selectedCaseIds.length }} 个</a-tag>
        </div>

        <a-table
          :data-source="caseItems"
          :columns="caseColumns"
          row-key="id"
          size="small"
          :pagination="{ pageSize: 5 }"
          :row-selection="{
            selectedRowKeys: selectedCaseIds,
            onChange: onSelectCasesChange,
          }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'id'">
              <code>#{{ record.id }}</code>
            </template>
            <template v-if="column.key === 'name'">
              <strong>{{ record.name }}</strong>
            </template>
          </template>
        </a-table>

        <div class="wizard-footer">
          <a-space>
            <a-button @click="handleClose">取消</a-button>
            <a-button
              type="primary"
              :disabled="selectedCaseIds.length === 0"
              @click="currentStep = 1"
            >
              下一步：配置调度策略
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- Step 1: 调度策略与套件配置 -->
      <div v-else-if="currentStep === 1" class="step-content">
        <a-form layout="vertical" class="strategy-form">
          <a-form-item label="测试套件名称" required>
            <a-input v-model:value="suiteName" placeholder="请输入精准回归套件名称" />
          </a-form-item>

          <a-form-item label="变更破坏性与调度优先级">
            <div class="priority-choice-box">
              <a-checkbox v-model:checked="isBreaking">
                包含 Breaking 破坏性字段变更（自动提权至 <strong>P0 紧急抢占调度</strong>）
              </a-checkbox>
              <p class="priority-hint text-secondary">
                当勾选破坏性变更时，派发任务将获得 P0 最高优先级，满载时自动抢占挂起低优先级常规任务，优先保证线上阻断风险验证。
              </p>
            </div>
          </a-form-item>

          <div class="switch-row">
            <a-form-item label="套件持久化落库 (Persist to Suite)">
              <a-switch v-model:checked="persistSuite" />
              <span class="switch-hint">持久化保存为独立测试套件，便于后续在套件中心反复回放</span>
            </a-form-item>

            <a-form-item label="立即自动触发调度执行 (Auto Trigger)">
              <a-switch v-model:checked="autoTrigger" />
              <span class="switch-hint">直接向 Worker 集群派发任务队列，无需二次手动触发</span>
            </a-form-item>
          </div>
        </a-form>

        <div class="wizard-footer">
          <a-space>
            <a-button @click="currentStep = 0">上一步</a-button>
            <a-button
              type="primary"
              :danger="isBreaking"
              :loading="synthesizing"
              @click="handleSynthesizeAndTrigger"
            >
              一键合成并触发调度
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- Step 2: 合成结果与调度交付 -->
      <div v-else-if="currentStep === 2" class="step-content">
        <a-alert
          type="success"
          show-icon
          class="result-alert"
          message="精准回归测试套件合成成功！"
          :description="resultData?.message || '受损用例已成功完成去重组装，任务已顺利派发至调度集群。'"
        />

        <div v-if="resultData" class="kpi-grid">
          <div class="kpi-item">
            <span class="kpi-label">测试套件 ID</span>
            <strong class="kpi-val text-blue">
              {{ resultData.suite_id ? `#${resultData.suite_id}` : '未持久化' }}
            </strong>
          </div>

          <div class="kpi-item">
            <span class="kpi-label">调度任务优先级</span>
            <div class="kpi-val">
              <a-tag :color="resultData.task_priority === 'P0' ? 'red' : 'orange'">
                {{ resultData.task_priority }}
              </a-tag>
            </div>
          </div>

          <div class="kpi-item">
            <span class="kpi-label">调度任务 ID</span>
            <code class="task-id-text">{{ resultData.dispatched_task_id || '未触发' }}</code>
          </div>

          <div class="kpi-item">
            <span class="kpi-label">纳入回归用例总数</span>
            <strong class="kpi-val text-green">{{ resultData.total_cases_count }}</strong>
          </div>
        </div>

        <a-alert
          v-if="resultData?.task_preempted"
          type="warning"
          show-icon
          class="preempted-alert"
          message="[P0 弹性抢占生效] 本次紧急回归任务已成功让位插队，挂起低优先级任务腾出执行槽位！"
        />

        <div class="wizard-footer">
          <a-button type="primary" @click="handleFinish">完成并关闭</a-button>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  assetGraphApi,
  type TargetedRegressionResult,
} from '@/api/assetGraph'

interface CaseItem {
  id: number
  name: string
}

const props = withDefaults(
  defineProps<{
    open: boolean
    projectId?: number
    initialCaseIds?: number[]
    isBreakingChange?: boolean
  }>(),
  {
    open: false,
    projectId: 1,
    initialCaseIds: () => [],
    isBreakingChange: true,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'succeeded', res: TargetedRegressionResult): void
}>()

const currentStep = ref(0)
const synthesizing = ref(false)
const suiteName = ref('智能契约变更精准回归套件')
const isBreaking = ref(true)
const persistSuite = ref(true)
const autoTrigger = ref(true)
const selectedCaseIds = ref<number[]>([])
const caseItems = ref<CaseItem[]>([])
const resultData = ref<TargetedRegressionResult | null>(null)

const caseColumns = [
  { title: '用例编号', dataIndex: 'id', key: 'id', width: 120 },
  { title: '用例名称', dataIndex: 'name', key: 'name' },
]

function onSelectCasesChange(keys: any[]) {
  selectedCaseIds.value = keys.map((k) => Number(k))
}

function handleClose() {
  emit('update:open', false)
  currentStep.value = 0
}

function handleFinish() {
  if (resultData.value) {
    emit('succeeded', resultData.value)
  }
  handleClose()
}

async function handleSynthesizeAndTrigger() {
  synthesizing.value = true
  try {
    const res = await assetGraphApi.synthesizeAndTriggerRegression({
      impacted_case_ids: selectedCaseIds.value,
      project_id: props.projectId,
      suite_name: suiteName.value,
      is_breaking_change: isBreaking.value,
      persist: persistSuite.value,
      auto_trigger: autoTrigger.value,
    })

    resultData.value = res
    currentStep.value = 2
    message.success('精准回归套件合成与调度派发成功！')
  } catch (err: any) {
    message.error(err.message || '合成回归套件失败')
  } finally {
    synthesizing.value = false
  }
}

watch(
  () => props.open,
  (newVal) => {
    if (newVal) {
      currentStep.value = 0
      resultData.value = null
      isBreaking.value = props.isBreakingChange
      // 去重
      const uniqueIds = Array.from(new Set(props.initialCaseIds))
      selectedCaseIds.value = uniqueIds
      caseItems.value = uniqueIds.map((id) => ({
        id,
        name: `受损测试用例 #${id}`,
      }))
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.modal-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.targeted-regression-wizard {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 10px;
}

.wizard-steps {
  margin-bottom: 8px;
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.step-desc {
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
}

.wizard-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
  border-top: 1px solid var(--c-border, #e2e8f0);
  padding-top: 12px;
}

.strategy-form {
  padding: 8px 0;
}

.priority-choice-box {
  background: var(--c-bg-subtle, #f8fafc);
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.priority-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.switch-row {
  display: flex;
  gap: 24px;
}

.switch-hint {
  font-size: 11px;
  color: #94a3b8;
  margin-left: 8px;
}

.result-alert,
.preempted-alert {
  border-radius: 6px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-item {
  padding: 10px 14px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kpi-label {
  font-size: 11px;
  color: #64748b;
}

.kpi-val {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.task-id-text {
  font-size: 11px;
  font-family: monospace;
  color: #2563eb;
  word-break: break-all;
}

.text-blue {
  color: #2563eb;
}

.text-green {
  color: #16a34a;
}
</style>
