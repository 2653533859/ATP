<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="接口契约与业务 Spec 驱动的端到端用例智能生成编排控制台"
    destroy-on-close
    class="synthesizer-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制说明 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <RobotOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">LLM 驱动的时序依赖 DAG 自动推导与代码级用例合成引擎 (T3.1)</div>
          <div class="banner-desc">
            解析自然语言业务流程或 PRD 文档，结合各微服务 OpenAPI 接口契约，智能推导跨步骤时序依赖图（Dependency DAG）；自动将上游响应字段提取为上下文变量并在下游动态消费，一键合成可执行的标准 Python 自动化测试脚本。
          </div>
        </div>
      </div>

      <!-- 场景预设与业务 Spec 配置 -->
      <div class="config-section">
        <div class="section-title">业务需求 Spec 与场景预设</div>
        <div class="config-row">
          <div class="preset-group">
            <span class="label">典型业务闭环预设:</span>
            <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
              <a-radio-button value="ecom_flow">电商交易闭环 (登录➔下单➔支付)</a-radio-button>
              <a-radio-button value="account_flow">账号安全体系 (注册➔激活➔授权)</a-radio-button>
              <a-radio-button value="refund_flow">售后退款审批 (申请➔风控➔退汇)</a-radio-button>
            </a-radio-group>
          </div>
          <a-button type="primary" size="small" :loading="generating" @click="handleGenerate">
            <ThunderboltOutlined /> 启动智能生成编排
          </a-button>
        </div>

        <div class="form-inputs mt-3">
          <div class="input-item">
            <span class="sub-label">场景标题:</span>
            <a-input v-model:value="specTitle" size="small" />
          </div>
          <div class="input-item">
            <span class="sub-label">流程描述:</span>
            <a-input v-model:value="businessFlowDesc" size="small" />
          </div>
        </div>
      </div>

      <!-- 4 大核心 KPI 统计卡片 -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">时序执行步骤数</div>
            <div class="stat-value text-primary">{{ currentCase?.steps_count ?? 0 }} <span class="unit">步</span></div>
            <div class="stat-trend">跨微服务端到端调用</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">流程完整度评分</div>
            <div class="stat-value text-success">{{ currentCase?.flow_completeness_score_pct ?? 95 }}%</div>
            <div class="stat-trend">时序依赖链路闭环度</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">上下文流转变量数</div>
            <div class="stat-value text-warning">{{ totalExtractedVars }} <span class="unit">个</span></div>
            <div class="stat-trend">自动提取并在下游消费</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">生成用例用例 ID</div>
            <div class="stat-value text-purple text-truncate">{{ currentCase?.case_id.substring(0, 14) ?? 'e2e_case' }}...</div>
            <div class="stat-trend">已持久化入用例资产库</div>
          </div>
        </a-col>
      </a-row>

      <!-- 双栏布局：左侧时序步骤 DAG + 右侧 Python 代码预览 -->
      <div class="workbench-layout">
        <!-- 左侧：多步骤时序流转卡片 -->
        <div class="steps-panel">
          <div class="panel-header">
            <span class="panel-title"><ApartmentOutlined /> 时序依赖 DAG 步骤流转链路</span>
            <span class="text-xs text-muted">包含参数级联依赖与断言</span>
          </div>

          <div class="steps-flow">
            <div
              v-for="step in currentCase?.steps ?? []"
              :key="step.step_index"
              class="step-card"
            >
              <div class="step-card-header">
                <span class="step-badge">Step {{ step.step_index }}</span>
                <span class="step-name">{{ step.step_name }}</span>
                <a-tag color="blue">{{ step.method }}</a-tag>
              </div>

              <div class="step-endpoint">
                <code>{{ step.endpoint }}</code>
              </div>

              <!-- 请求入参展示 -->
              <div class="step-payload-box">
                <span class="box-title">请求 Payload (含依赖注入):</span>
                <pre class="payload-code"><code>{{ JSON.stringify(step.request_payload, null, 2) }}</code></pre>
              </div>

              <!-- 导出的动态上下文变量 -->
              <div v-if="Object.keys(step.extracted_variables).length > 0" class="step-vars-box">
                <span class="box-title">导向下游的上下文变量:</span>
                <div class="var-tags">
                  <a-tag
                    v-for="(path, varName) in step.extracted_variables"
                    :key="varName"
                    color="green"
                    class="var-tag"
                  >
                    ${{ varName }} ➔ {{ path }}
                  </a-tag>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：生成的 Python 可执行脚本预览器 -->
        <div class="script-panel">
          <div class="panel-header">
            <span class="panel-title"><CodeOutlined /> 自动合成 Python 自动化测试脚本</span>
            <a-button
              size="small"
              type="primary"
              :disabled="!currentCase?.generated_python_script"
              @click="handleCopyScript"
            >
              <CopyOutlined /> 一键复制脚本
            </a-button>
          </div>

          <div v-if="currentCase?.generated_python_script" class="script-container">
            <pre class="script-code"><code>{{ currentCase.generated_python_script }}</code></pre>
          </div>
          <div v-else class="empty-script">
            <a-empty description="暂无生成的 Python 脚本" />
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  RobotOutlined,
  ThunderboltOutlined,
  ApartmentOutlined,
  CodeOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  llmSpecCaseSynthesizerApi,
  type SynthesizedE2ETestCase,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const generating = ref(false)
const selectedPreset = ref<'ecom_flow' | 'account_flow' | 'refund_flow'>('ecom_flow')
const specTitle = ref('电商交易闭环测试')
const businessFlowDesc = ref('用户先登录认证获取凭据与用户标识，随后创建交易订单，最后调用收银台完成支付结算。')
const currentCase = ref<SynthesizedE2ETestCase | null>(null)

const PRESET_SPECS = {
  ecom_flow: {
    title: '电商交易闭环测试',
    desc: '用户先登录认证获取凭据与用户标识，随后创建交易订单，最后调用收银台完成支付结算。',
  },
  account_flow: {
    title: '用户账号注册与授权体系',
    desc: '新用户提交手机号注册账号，获取初始凭证后更新用户资料档案，最后完成实名安全认证。',
  },
  refund_flow: {
    title: '售后退款全流程闭环',
    desc: '用户针对已支付订单发起退款售后申请，流转至商家端审核通过，最后由财务网关执行原路退汇并核验账单。',
  },
}

const totalExtractedVars = computed(() => {
  if (!currentCase.value) return 0
  return currentCase.value.steps.reduce((acc, cur) => acc + Object.keys(cur.extracted_variables || {}).length, 0)
})

function handleClose() {
  emit('update:open', false)
}

function handlePresetChange() {
  const p = PRESET_SPECS[selectedPreset.value]
  specTitle.value = p.title
  businessFlowDesc.value = p.desc
  handleGenerate()
}

async function handleGenerate() {
  generating.value = true
  try {
    const res = await llmSpecCaseSynthesizerApi.generate({
      spec_title: specTitle.value,
      business_flow_description: businessFlowDesc.value,
    })
    currentCase.value = res.case
    message.success(res.message || '用例生成完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '生成失败')
  } finally {
    generating.value = false
  }
}

function handleCopyScript() {
  if (!currentCase.value?.generated_python_script) return
  navigator.clipboard.writeText(currentCase.value.generated_python_script)
  message.success('已复制 Python 测试脚本到剪贴板')
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      handleGenerate()
    }
  }
)

onMounted(() => {
  if (props.open) {
    handleGenerate()
  }
})
</script>

<style scoped>
.synthesizer-drawer :deep(.ant-drawer-body) {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
}

.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #16a34a;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #14532d;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #15803d;
  line-height: 1.5;
}

.config-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 10px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.preset-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.form-inputs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sub-label {
  font-size: 11px;
  color: #64748b;
  width: 70px;
  flex-shrink: 0;
}

.kpi-row {
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
}

.stat-label {
  font-size: 11px;
  color: #64748b;
}

.stat-value {
  font-size: 20px;
  font-weight: 800;
  margin: 4px 0;
}

.stat-value .unit {
  font-size: 12px;
  font-weight: normal;
  color: #94a3b8;
}

.stat-trend {
  font-size: 11px;
  color: #94a3b8;
}

.text-primary { color: #2563eb; }
.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-purple { color: #7c3aed; }
.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workbench-layout {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 16px;
}

.steps-panel,
.script-panel {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.steps-flow {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 520px;
  overflow-y: auto;
}

.step-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
}

.step-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.step-badge {
  background: #2563eb;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.step-name {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
  flex: 1;
}

.step-endpoint {
  font-size: 11px;
  margin-bottom: 6px;
}

.step-payload-box,
.step-vars-box {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 8px;
  margin-top: 6px;
}

.box-title {
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  display: block;
  margin-bottom: 4px;
}

.payload-code {
  margin: 0;
  font-size: 10px;
  color: #334155;
  font-family: monospace;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 3px;
}

.var-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.var-tag {
  font-size: 10px;
  margin: 0;
}

.script-container {
  background: #0f172a;
  border-radius: 6px;
  padding: 12px 14px;
  max-height: 520px;
  overflow-y: auto;
}

.script-code {
  margin: 0;
  color: #38bdf8;
  font-family: monospace;
  font-size: 11px;
  white-space: pre-wrap;
}

.empty-script {
  padding: 40px 0;
}

.mt-3 {
  margin-top: 10px;
}

.text-xs {
  font-size: 11px;
}

.text-muted {
  color: #94a3b8;
}
</style>
