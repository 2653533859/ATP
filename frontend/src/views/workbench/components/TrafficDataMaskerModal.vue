<template>
  <a-modal
    :open="open"
    :width="1120"
    title="生产敏感数据自适应脱敏规则配置与实时清洗工作台"
    :footer="null"
    destroy-on-close
    class="traffic-masker-modal"
    @cancel="handleClose"
  >
    <div class="modal-content">
      <!-- 头部说明条 -->
      <div class="modal-banner">
        <div class="banner-title">
          <SafetyCertificateOutlined class="banner-icon" />
          <span>生产数据合规脱敏防护引擎 (Traffic Sensitive Data Redactor)</span>
        </div>
        <p class="banner-desc">
          对网关捕获的生产镜像流量进行端到端 PII 去隐私清洗。覆盖手机号、身份证、银行卡、邮箱、JWT 授权 Token、登录密码及自定义敏感词，支持 MASK 掩码、HASH 不可逆伪名化（保持业务关联一致性）与 REDACT 完全擦除策略。
        </p>
      </div>

      <!-- 脱敏规则配置矩阵与列表 -->
      <div class="rules-section">
        <div class="section-header-bar">
          <div class="header-left">
            <span class="section-title">
              <SettingOutlined /> 脱敏规则配置矩阵 ({{ rules.length }} 项)
            </span>
            <span class="section-sub">支持在线动态切换脱敏策略与匹配字段名</span>
          </div>

          <div class="header-right">
            <a-space size="small">
              <a-button size="small" :loading="loadingRules" @click="loadRules">
                <ReloadOutlined /> 刷新规则
              </a-button>
              <a-button size="small" @click="handleResetRules">
                恢复出厂默认规则
              </a-button>
              <a-button type="primary" size="small" :loading="savingRules" @click="handleSaveRules">
                <SaveOutlined /> 保存并应用规则
              </a-button>
            </a-space>
          </div>
        </div>

        <a-table
          :data-source="rules"
          :columns="ruleColumns"
          row-key="rule_id"
          size="small"
          :pagination="false"
          :loading="loadingRules"
          class="rules-table"
        >
          <template #bodyCell="{ column, record }">
            <!-- 规则分类 -->
            <template v-if="column.key === 'category'">
              <a-tag :color="getCategoryColor(record.category)" size="small">
                {{ record.category }}
              </a-tag>
            </template>

            <!-- 规则名称 -->
            <template v-else-if="column.key === 'name'">
              <div class="rule-title-box">
                <span class="rule-name">{{ record.name }}</span>
                <span class="rule-id">{{ record.rule_id }}</span>
              </div>
            </template>

            <!-- 脱敏策略切换 -->
            <template v-else-if="column.key === 'strategy'">
              <a-select v-model:value="record.strategy" size="small" style="width: 130px">
                <a-select-option value="MASK">
                  <span class="strat-opt opt-mask">MASK (掩码)</span>
                </a-select-option>
                <a-select-option value="HASH">
                  <span class="strat-opt opt-hash">HASH (伪名化)</span>
                </a-select-option>
                <a-select-option value="REDACT">
                  <span class="strat-opt opt-redact">REDACT (擦除)</span>
                </a-select-option>
              </a-select>
            </template>

            <!-- 匹配字段 Key 关键词 -->
            <template v-else-if="column.key === 'patterns'">
              <a-input
                :value="record.field_key_patterns.join(', ')"
                placeholder="字段键名 (逗号分隔)"
                size="small"
                @change="(e: any) => record.field_key_patterns = e.target.value.split(/[,，\s]+/).map((s: string) => s.trim()).filter(Boolean)"
              />
            </template>

            <!-- 启用开关 -->
            <template v-else-if="column.key === 'enabled'">
              <a-switch v-model:checked="record.enabled" size="small" />
            </template>
          </template>
        </a-table>
      </div>

      <!-- 下半部分：在线实时脱敏演练沙箱 (Live Interactive Sandbox) -->
      <div class="sandbox-section">
        <div class="section-header-bar">
          <div class="header-left">
            <span class="section-title">
              <ExperimentOutlined /> 在线脱敏演练沙箱 (Live Interactive Sandbox)
            </span>
            <div class="presets-row">
              <a-button size="small" type="link" @click="loadSample('user_register')">
                示例 1: 用户注册含身份证/密码
              </a-button>
              <a-button size="small" type="link" @click="loadSample('payment_card')">
                示例 2: 绑卡交易含银行卡/CVV
              </a-button>
            </div>
          </div>

          <div class="header-right">
            <a-space size="small">
              <a-radio-group v-model:value="sandboxMode" size="small" button-style="solid">
                <a-radio-button value="JSON">JSON 树模式</a-radio-button>
                <a-radio-button value="TEXT">纯文本模式</a-radio-button>
              </a-radio-group>
              <a-button type="primary" size="small" :loading="masking" @click="handleRunMask">
                <ThunderboltOutlined /> 运行脱敏演练
              </a-button>
            </a-space>
          </div>
        </div>

        <div class="sandbox-grid">
          <!-- 左侧：原始带敏感信息输入 -->
          <div class="sandbox-pane input-pane">
            <div class="pane-header">
              <span class="pane-title">原始生产数据 (含明文高敏信息)</span>
              <a-tag color="red" size="small">未脱敏</a-tag>
            </div>
            <div class="pane-body">
              <a-textarea
                v-model:value="inputContent"
                class="code-editor"
                :rows="11"
                placeholder="请输入待测试脱敏的原始文本或 JSON 数据..."
              />
            </div>
          </div>

          <!-- 右侧：脱敏后数据高保真输出 -->
          <div class="sandbox-pane output-pane">
            <div class="pane-header">
              <span class="pane-title">合规安全输出 (已清洗脱敏)</span>
              <a-tag color="green" size="small">已合规清洗</a-tag>
            </div>
            <div class="pane-body">
              <pre class="code-preview"><code>{{ outputContent || '(点击右上角「运行脱敏演练」查看清洗结果)' }}</code></pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  SettingOutlined,
  ReloadOutlined,
  SaveOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  trafficMaskerApi,
  type SensitiveCategory,
  type SensitiveRuleItem,
} from '@/api/trafficGateway'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loadingRules = ref(false)
const savingRules = ref(false)
const masking = ref(false)
const sandboxMode = ref<'JSON' | 'TEXT'>('JSON')

const rules = ref<SensitiveRuleItem[]>([])
const inputContent = ref('')
const outputContent = ref('')

const ruleColumns = [
  { title: '敏感分类', key: 'category', width: 110 },
  { title: '规则名称与标识', key: 'name', width: 180 },
  { title: '脱敏策略', key: 'strategy', width: 150 },
  { title: '匹配字段键名 (Key Patterns)', key: 'patterns' },
  { title: '状态', key: 'enabled', width: 80 },
]

// 演练样例数据
const SAMPLE_USER_REGISTER = JSON.stringify({
  user_id: 10001,
  username: "alice_dev",
  password: "P@ssw0rd999!Secret",
  profile: {
    mobile: "13812345678",
    id_card: "110101199003071234",
    email: "alice_tester@enterprise.org",
  },
  auth: {
    token: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDAwMSJ9.signatureSecretKey",
  },
}, null, 2)

const SAMPLE_PAYMENT_CARD = JSON.stringify({
  order_id: "ORD_20261016001",
  amount: 299.0,
  payment_info: {
    payer_name: "张三",
    bank_card: "6222021234567890123",
    cvv: "888",
    phone: "13900001111",
  },
}, null, 2)

const loadRules = async () => {
  loadingRules.value = true
  try {
    const res = await trafficMaskerApi.getRules()
    rules.value = res.rules
  } catch {
    // 降级使用本地默认规则
    rules.value = [
      { rule_id: 'rule_phone', name: '大陆手机号脱敏', category: 'PHONE', strategy: 'MASK', field_key_patterns: ['phone', 'mobile'], enabled: true },
      { rule_id: 'rule_id_card', name: '居民身份证号脱敏', category: 'ID_CARD', strategy: 'MASK', field_key_patterns: ['id_card', 'idcard'], enabled: true },
      { rule_id: 'rule_bank_card', name: '银行卡号脱敏', category: 'BANK_CARD', strategy: 'MASK', field_key_patterns: ['bank_card', 'card_no'], enabled: true },
      { rule_id: 'rule_email', name: '电子邮箱地址脱敏', category: 'EMAIL', strategy: 'MASK', field_key_patterns: ['email', 'mail'], enabled: true },
      { rule_id: 'rule_jwt', name: 'JWT/Bearer 凭证脱敏', category: 'JWT_TOKEN', strategy: 'REDACT', field_key_patterns: ['authorization', 'token'], enabled: true },
      { rule_id: 'rule_password', name: '登录密码与密钥擦除', category: 'PASSWORD', strategy: 'REDACT', field_key_patterns: ['password', 'secret', 'pwd', 'cvv'], enabled: true },
    ]
  } finally {
    loadingRules.value = false
  }
}

const handleSaveRules = async () => {
  savingRules.value = true
  try {
    const res = await trafficMaskerApi.updateRules(rules.value)
    rules.value = res.rules
    message.success(res.message || '脱敏规则已成功更新并生效')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '保存规则失败')
  } finally {
    savingRules.value = false
  }
}

const handleResetRules = async () => {
  try {
    const res = await trafficMaskerApi.resetRules()
    rules.value = res.rules
    message.info('已恢复为系统出厂脱敏规则')
  } catch {
    await loadRules()
    message.info('已重置为出厂规则')
  }
}

const getCategoryColor = (cat: SensitiveCategory) => {
  switch (cat) {
    case 'PHONE': return 'green'
    case 'ID_CARD': return 'blue'
    case 'BANK_CARD': return 'orange'
    case 'EMAIL': return 'cyan'
    case 'JWT_TOKEN': return 'purple'
    case 'PASSWORD': return 'red'
    default: return 'default'
  }
}

const loadSample = (type: 'user_register' | 'payment_card') => {
  sandboxMode.value = 'JSON'
  inputContent.value = type === 'user_register' ? SAMPLE_USER_REGISTER : SAMPLE_PAYMENT_CARD
  handleRunMask()
}

const handleRunMask = async () => {
  if (!inputContent.value.trim()) {
    message.warning('请输入待脱敏演练数据')
    return
  }

  masking.value = true
  try {
    if (sandboxMode.value === 'JSON') {
      try {
        const parsed = JSON.parse(inputContent.value)
        const res = await trafficMaskerApi.maskPayload({ payload: parsed })
        outputContent.value = JSON.stringify(res.masked_payload, null, 2)
      } catch {
        // 若不是标准 JSON，降级走文本扫描
        const res = await trafficMaskerApi.maskText({ text: inputContent.value })
        outputContent.value = res.masked
      }
    } else {
      const res = await trafficMaskerApi.maskText({ text: inputContent.value })
      outputContent.value = res.masked
    }
    message.success('脱敏清洗演练完成')
  } catch (err: any) {
    message.error(err.message || '脱敏执行失败')
  } finally {
    masking.value = false
  }
}

const handleClose = () => {
  emit('update:open', false)
}

watch(
  () => props.open,
  (newVal) => {
    if (newVal) {
      loadRules()
      if (!inputContent.value) {
        inputContent.value = SAMPLE_USER_REGISTER
        handleRunMask()
      }
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.modal-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-banner {
  background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
  border: 1px solid #86efac;
  border-radius: 8px;
  padding: 12px 16px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #15803d;
  margin-bottom: 4px;
}

.banner-icon {
  font-size: 18px;
  color: #16a34a;
}

.banner-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin: 0;
}

.rules-section,
.sandbox-section {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.section-header-bar {
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-sub {
  font-size: 11px;
  color: #64748b;
}

.presets-row {
  display: flex;
  gap: 6px;
}

.rule-title-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rule-name {
  font-weight: 600;
  font-size: 12px;
  color: #0f172a;
}

.rule-id {
  font-size: 10px;
  font-family: monospace;
  color: #94a3b8;
}

.strat-opt {
  font-size: 11px;
  font-weight: 600;
}

.opt-mask { color: #0284c7; }
.opt-hash { color: #7c3aed; }
.opt-redact { color: #dc2626; }

/* 沙箱双栏 */
.sandbox-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 280px;
}

.sandbox-pane {
  display: flex;
  flex-direction: column;
}

.input-pane {
  border-right: 1px solid var(--c-border, #e2e8f0);
}

.pane-header {
  padding: 8px 12px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pane-title {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.pane-body {
  padding: 10px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.code-editor {
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.5;
  background: #1e293b;
  color: #f8fafc;
  border-radius: 6px;
  flex: 1;
}

.code-preview {
  margin: 0;
  padding: 10px;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.5;
  background: #f0fdf4;
  color: #166534;
  border-radius: 6px;
  border: 1px solid #bbf7d0;
  max-height: 240px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  flex: 1;
}
</style>
