<template>
  <a-modal
    :open="open"
    :width="800"
    destroy-on-close
    :footer="null"
    @cancel="handleClose"
  >
    <template #title>
      <span>录制流量逆向合成用例与套件向导</span>
    </template>
    <div class="traffic-to-case-wizard">
      <!-- 步骤指示条 -->
      <a-steps :current="currentStep" size="small" class="wizard-steps">
        <a-step title="资产类型与元数据" />
        <a-step title="断言与落库策略" />
        <a-step title="合成确认与步骤预览" />
      </a-steps>

      <div class="step-content">
        <!-- 步骤 1: 资产类型与名称模块 -->
        <div v-if="currentStep === 0" class="step-pane">
          <a-form layout="vertical">
            <a-form-item label="逆向合成目标类型">
              <a-radio-group v-model:value="synthesisType" button-style="solid">
                <a-radio-button value="case">单场景用例 (TestCase)</a-radio-button>
                <a-radio-button value="suite">用例测试套件 (TestSuite)</a-radio-button>
              </a-radio-group>
            </a-form-item>

            <a-form-item
              :label="synthesisType === 'case' ? '生成的用例名称' : '生成的套件名称'"
              required
            >
              <a-input
                v-model:value="form.name"
                :placeholder="synthesisType === 'case' ? '例如: 订单微服务链路逆向自动化用例' : '例如: 交易核心主链路逆向套件'"
              />
            </a-form-item>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="归属模块 ID" required>
                  <a-input-number v-model:value="form.moduleId" :min="1" style="width: 100%" />
                </a-form-item>
              </a-col>

              <a-col v-if="synthesisType === 'case'" :span="6">
                <a-form-item label="用例优先级">
                  <a-select v-model:value="form.priority" style="width: 100%">
                    <a-select-option value="P0">P0 核心</a-select-option>
                    <a-select-option value="P1">P1 重要</a-select-option>
                    <a-select-option value="P2">P2 次要</a-select-option>
                    <a-select-option value="P3">P3 轻微</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>

              <a-col v-if="synthesisType === 'case'" :span="6">
                <a-form-item label="用例层级">
                  <a-select v-model:value="form.caseLevel" style="width: 100%">
                    <a-select-option value="core">核心用例</a-select-option>
                    <a-select-option value="regression">回归用例</a-select-option>
                    <a-select-option value="smoke">冒烟用例</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="资产业务描述">
              <a-textarea
                v-model:value="form.description"
                placeholder="描述该录制会话覆盖的核心业务链路..."
                :rows="2"
              />
            </a-form-item>
          </a-form>
        </div>

        <!-- 步骤 2: 智能断言与落库策略 -->
        <div v-else-if="currentStep === 1" class="step-pane">
          <a-card size="small" title="多维自动断言生成规则" class="policy-card">
            <ul class="policy-list">
              <li>
                <strong>HTTP 状态码强校验</strong>: 自动比对每个录制步骤的期望响应码（如 <code>200 OK</code>、<code>201 Created</code>）；
              </li>
              <li>
                <strong>业务状态 JSONPath 断言</strong>: 自动检测响应体中的 <code>code</code>、<code>success</code> 字段并注入等值判定；
              </li>
              <li>
                <strong>耗时 SLA 阈值红线</strong>: 按照录制实际耗时加权浮动上限，自动生成单步响应时延上限预警。
              </li>
            </ul>
          </a-card>

          <a-form layout="vertical" style="margin-top: 16px;">
            <a-form-item label="数据库原子持久化落库">
              <a-switch
                v-model:checked="form.persist"
                checked-children="落库保存"
                un-checked-children="仅内存预览"
              />
              <span class="persist-hint">
                {{ form.persist ? '将直接在平台数据库中生成正式 TestCase/TestSuite 记录，可直接调度运行' : '仅在当前界面预演转换步骤，不写入数据库' }}
              </span>
            </a-form-item>
          </a-form>
        </div>

        <!-- 步骤 3: 合成结果确认与步骤预览 -->
        <div v-else-if="currentStep === 2" class="step-pane">
          <div v-if="synthesizing" class="loading-box">
            <a-spin tip="正在执行参数依赖逆向合成与多步断言生成..." />
          </div>

          <div v-else-if="synthesisResult" class="result-box">
            <a-result
              status="success"
              :title="synthesisType === 'case' ? '测试用例逆向合成成功！' : '测试套件逆向合成成功！'"
              :sub-title="`共生成 ${synthesisResult.total_steps} 个自动化测试执行步骤，已绑定前置上下文参数依赖。`"
            >
              <template #extra>
                <div class="result-details">
                  <a-descriptions size="small" bordered :column="2">
                    <a-descriptions-item label="资产名称">
                      {{ synthesisResult.name || synthesisResult.suite_name }}
                    </a-descriptions-item>
                    <a-descriptions-item label="生成资产 ID">
                      <a-tag color="green">
                        {{ synthesisResult.case_id ? `#${synthesisResult.case_id}` : (synthesisResult.suite_id ? `#${synthesisResult.suite_id}` : '未落库预览') }}
                      </a-tag>
                    </a-descriptions-item>
                    <a-descriptions-item label="总步骤数">
                      {{ synthesisResult.total_steps }} 步
                    </a-descriptions-item>
                    <a-descriptions-item label="持久化状态">
                      <a-tag :color="synthesisResult.persisted ? 'blue' : 'default'">
                        {{ synthesisResult.persisted ? '已落库保存' : '内存预演' }}
                      </a-tag>
                    </a-descriptions-item>
                  </a-descriptions>
                </div>
              </template>
            </a-result>

            <!-- 步骤简表预览 -->
            <a-table
              v-if="synthesisResult.steps?.length"
              :data-source="synthesisResult.steps"
              :columns="stepColumns"
              row-key="step_no"
              size="small"
              :pagination="{ pageSize: 4 }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'step_no'">
                  <span>#{{ record.step_no }}</span>
                </template>
                <template v-if="column.key === 'action'">
                  <code>{{ record.action }}</code>
                </template>
                <template v-if="column.key === 'expected'">
                  <span class="expected-text">{{ record.expected_result }}</span>
                </template>
              </template>
            </a-table>
          </div>
        </div>
      </div>

      <!-- 底部步骤切换按钮 -->
      <div class="wizard-footer">
        <a-button v-if="currentStep > 0 && currentStep < 2" @click="currentStep--">
          上一步
        </a-button>

        <a-button
          v-if="currentStep === 0"
          type="primary"
          :disabled="!form.name.trim()"
          @click="currentStep++"
        >
          下一步: 断言策略
        </a-button>

        <a-button
          v-if="currentStep === 1"
          type="primary"
          :loading="synthesizing"
          @click="handleRunSynthesis"
        >
          确认合成并落库
        </a-button>

        <a-button
          v-if="currentStep === 2"
          type="primary"
          @click="handleFinish"
        >
          完成并关闭
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import { trafficRecordingApi } from '@/api/trafficRecording'

const props = withDefaults(
  defineProps<{
    open: boolean
    sessionId?: string
    projectId?: number
  }>(),
  {
    open: false,
    sessionId: undefined,
    projectId: 1,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'synthesized', val: any): void
}>()

const currentStep = ref(0)
const synthesisType = ref<'case' | 'suite'>('case')
const synthesizing = ref(false)
const synthesisResult = ref<any | null>(null)

const form = reactive({
  name: '订单微服务全链路逆向冒烟用例',
  moduleId: 1,
  priority: 'P1',
  caseLevel: 'regression',
  description: '由微服务反向代理流量录制自动逆向合成',
  persist: true,
})

const stepColumns = [
  { title: '序号', key: 'step_no', width: 70 },
  { title: '动作/接口', key: 'action' },
  { title: '自动生成预期断言', key: 'expected' },
]

function handleClose() {
  currentStep.value = 0
  synthesisResult.value = null
  emit('update:open', false)
}

function handleFinish() {
  handleClose()
}

async function handleRunSynthesis() {
  if (!props.sessionId) {
    message.warning('无效的录制会话 ID')
    return
  }
  currentStep.value = 2
  synthesizing.value = true

  try {
    let res: any
    if (synthesisType.value === 'case') {
      res = await trafficRecordingApi.synthesizeCase(props.sessionId, {
        case_name: form.name.trim(),
        module_id: form.moduleId,
        description: form.description,
        priority: form.priority,
        case_level: form.caseLevel,
        persist: form.persist,
      })
    } else {
      res = await trafficRecordingApi.synthesizeSuite(props.sessionId, {
        suite_name: form.name.trim(),
        module_id: form.moduleId,
        persist: form.persist,
      })
    }
    synthesisResult.value = res
    emit('synthesized', res)
    message.success('流量录制逆向合成成功！')
  } catch (err: any) {
    message.error(err.message || '逆向合成用例失败')
  } finally {
    synthesizing.value = false
  }
}
</script>

<style scoped>
.traffic-to-case-wizard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wizard-steps {
  margin-bottom: 8px;
}

.step-content {
  min-height: 280px;
}

.step-pane {
  padding: 8px 0;
}

.policy-card {
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 6px;
}

.policy-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.8;
  color: #334155;
}

.persist-hint {
  margin-left: 10px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.loading-box {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 220px;
}

.result-details {
  margin-bottom: 16px;
  text-align: left;
}

.expected-text {
  font-size: 12px;
  color: #059669;
}

.wizard-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border, #f1f5f9);
}
</style>
