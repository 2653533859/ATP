<template>
  <a-modal
    :open="open"
    title="动态噪声过滤规则配置与仿真校验弹窗"
    width="760px"
    :destroy-on-close="true"
    class="noise-filter-rule-modal"
    @cancel="handleCancel"
  >
    <div class="rule-modal-container">
      <!-- 快捷模板卡片条 -->
      <div class="templates-bar">
        <span class="templates-label">
          <ThunderboltOutlined /> 常用噪声模板:
        </span>
        <div class="template-pills">
          <a-tag
            v-for="tpl in quickTemplates"
            :key="tpl.name"
            class="template-tag cursor-pointer"
            color="blue"
            @click="applyTemplate(tpl)"
          >
            + {{ tpl.name }}
          </a-tag>
        </div>
      </div>

      <!-- 规则表单 -->
      <a-form layout="vertical" class="rule-form">
        <div class="form-row-2">
          <a-form-item label="规则名称 (Rule Name)" required>
            <a-input
              v-model:value="form.name"
              placeholder="例如: 忽略分布式链路跟踪 ID 偏离"
            />
          </a-form-item>

          <a-form-item label="噪声类型 (Noise Category)">
            <a-select v-model:value="form.noise_type">
              <a-select-option value="TIMESTAMP">时间戳与日期 (TIMESTAMP)</a-select-option>
              <a-select-option value="TRACE_ID">分布式链路 ID (TRACE_ID)</a-select-option>
              <a-select-option value="UUID_RANDOM">随机 UUID / Nonce (UUID_RANDOM)</a-select-option>
              <a-select-option value="LATENCY_DURATION">耗时偏差 (LATENCY_DURATION)</a-select-option>
              <a-select-option value="CUSTOM_RULE">通用自定义 (CUSTOM_RULE)</a-select-option>
            </a-select>
          </a-form-item>
        </div>

        <div class="form-row-2">
          <a-form-item label="目标路径匹配模式 (JSONPath Glob)">
            <a-input
              v-model:value="form.path_pattern"
              placeholder="例如: *.trace_id 或 $.meta.timestamp"
              class="font-mono"
            />
          </a-form-item>

          <a-form-item label="取值正则匹配模式 (Regex Pattern)">
            <a-input
              v-model:value="form.regex_pattern"
              placeholder="例如: ^[0-9a-fA-F]{32}$"
              class="font-mono"
            />
          </a-form-item>
        </div>

        <div class="form-row-status">
          <a-form-item label="启用状态 (Enabled)">
            <a-switch v-model:checked="form.enabled" checked-children="开启" un-checked-children="停用" />
          </a-form-item>

          <a-form-item label="规则描述 (Description)" style="flex: 1">
            <a-input
              v-model:value="form.description"
              placeholder="说明此规则的过滤目的与业务背景"
            />
          </a-form-item>
        </div>
      </a-form>

      <!-- 实时仿真测试沙箱 -->
      <div class="simulation-sandbox-card">
        <div class="sandbox-header">
          <span class="sandbox-title">
            <ExperimentOutlined /> 规则命中实时仿真演练 (Live Sandbox)
          </span>
          <a-button
            type="primary"
            size="small"
            :loading="testing"
            @click="runRuleSimulation"
          >
            即时验证
          </a-button>
        </div>

        <div class="sandbox-inputs-grid">
          <div class="sandbox-input-col">
            <label class="input-label">测试目标 JSONPath:</label>
            <a-input
              v-model:value="testPath"
              class="font-mono text-xs"
              placeholder="$.data.trace_id"
            />
          </div>

          <div class="sandbox-input-col">
            <label class="input-label">模拟基线样本取值:</label>
            <a-input
              v-model:value="testBaseVal"
              class="font-mono text-xs"
              placeholder="c74f9d1234567890abcdef1234567890"
            />
          </div>

          <div class="sandbox-input-col">
            <label class="input-label">模拟回放样本取值:</label>
            <a-input
              v-model:value="testActVal"
              class="font-mono text-xs"
              placeholder="92c14c281234567890abcdef1234567890"
            />
          </div>
        </div>

        <!-- 仿真结果输出 -->
        <div v-if="testResult" class="test-feedback-box" :class="testResult.matched ? 'feedback-matched' : 'feedback-unmatched'">
          <span class="feedback-badge font-bold">
            {{ testResult.matched ? '命中降噪规则 (MATCHED - 成功平滑)' : '未命中规则 (UNMATCHED - 保留为业务差异)' }}
          </span>
          <span class="feedback-reason text-xs">
            {{ testResult.reason }}
          </span>
        </div>
      </div>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" @click="handleSave">保存规则</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  ExperimentOutlined,
} from '@ant-design/icons-vue'
import { trafficReplayApi } from '@/api/trafficReplay'

const props = defineProps<{
  open: boolean
  initialRule?: any
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'saved', rule: any): void
}>()

const testing = ref(false)
const testResult = ref<any>(null)

const testPath = ref('$.trace_id')
const testBaseVal = ref('4bf92f3577b34da6a3ce929d0e0e4736')
const testActVal = ref('7c98835265353385929d0e0e47361234')

const form = ref({
  rule_id: '',
  name: '',
  noise_type: 'CUSTOM_RULE',
  path_pattern: '',
  regex_pattern: '',
  enabled: true,
  description: '',
})

const quickTemplates = [
  {
    name: '任意时间戳',
    noise_type: 'TIMESTAMP',
    path_pattern: '*timestamp*',
    regex_pattern: '^\\d{10,13}$',
    description: '过滤包含 timestamp 命名的数值型时间戳',
  },
  {
    name: '32位 TraceID',
    noise_type: 'TRACE_ID',
    path_pattern: '*.trace_id',
    regex_pattern: '^[0-9a-fA-F]{32}$',
    description: '过滤全链路 TraceID',
  },
  {
    name: '标准 UUID',
    noise_type: 'UUID_RANDOM',
    path_pattern: '*.uuid',
    regex_pattern: '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    description: '过滤符合 RFC 4122 规范的标准 UUID',
  },
  {
    name: '耗时与耗费',
    noise_type: 'LATENCY_DURATION',
    path_pattern: '*.cost_ms',
    regex_pattern: '',
    description: '过滤接口执行耗时字段',
  },
]

watch(
  () => props.initialRule,
  (val) => {
    if (val) {
      form.value = {
        rule_id: val.rule_id || `rule_${Date.now()}`,
        name: val.name || '',
        noise_type: val.noise_type || 'CUSTOM_RULE',
        path_pattern: val.path_pattern || '',
        regex_pattern: val.regex_pattern || '',
        enabled: val.enabled !== false,
        description: val.description || '',
      }
      if (val.path_pattern) {
        testPath.value = val.path_pattern
      }
    } else {
      form.value = {
        rule_id: `rule_${Date.now()}`,
        name: '',
        noise_type: 'CUSTOM_RULE',
        path_pattern: '',
        regex_pattern: '',
        enabled: true,
        description: '',
      }
    }
    testResult.value = null
  },
  { immediate: true }
)

function applyTemplate(tpl: any) {
  form.value.name = `忽略${tpl.name}`
  form.value.noise_type = tpl.noise_type
  form.value.path_pattern = tpl.path_pattern
  form.value.regex_pattern = tpl.regex_pattern
  form.value.description = tpl.description
  testPath.value = tpl.path_pattern.replace('*', 'data.')
  message.info(`已应用 [${tpl.name}] 模板配置`)
}

async function runRuleSimulation() {
  if (!form.value.path_pattern && !form.value.regex_pattern) {
    message.warning('请至少填写路径匹配模式或正则模式')
    return
  }

  testing.value = true
  try {
    const res = await trafficReplayApi.testNoiseRule({
      rule: form.value,
      test_json_path: testPath.value,
      test_baseline_value: testBaseVal.value,
      test_replayed_value: testActVal.value,
    })
    testResult.value = res
  } catch (err: any) {
    message.error(err?.message || '规则测试失败')
  } finally {
    testing.value = false
  }
}

function handleSave() {
  if (!form.value.name.trim()) {
    message.warning('请输入规则名称')
    return
  }
  if (!form.value.path_pattern.trim() && !form.value.regex_pattern.trim()) {
    message.warning('路径通配模式与正则表达式至少填写一项')
    return
  }

  emit('saved', { ...form.value })
  emit('update:open', false)
  message.success(`噪声规则 [${form.value.name}] 保存成功`)
}

function handleCancel() {
  emit('update:open', false)
}
</script>

<style scoped>
.rule-modal-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.templates-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--c-bg-subtle, #f8fafc);
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px dashed var(--c-border, #e2e8f0);
}

.templates-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary, #64748b);
  display: flex;
  align-items: center;
  gap: 4px;
}

.template-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.template-tag {
  cursor: pointer;
  user-select: none;
}

.rule-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-row-status {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.simulation-sandbox-card {
  background: #f8fafc;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sandbox-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sandbox-title {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--c-text-primary, #1e293b);
}

.sandbox-inputs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
}

.sandbox-input-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.input-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.test-feedback-box {
  padding: 8px 12px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.feedback-matched {
  background: #f0fdf4;
  border: 1px solid #86efac;
  color: #166534;
}

.feedback-unmatched {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.feedback-badge {
  font-size: 12px;
}

.feedback-reason {
  opacity: 0.85;
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: bold;
}

.text-xs {
  font-size: 12px;
}
</style>
