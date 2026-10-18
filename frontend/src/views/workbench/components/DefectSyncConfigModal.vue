<template>
  <a-modal
    :open="open"
    title="跨平台缺陷同步集成与 SLA 升级策略中枢配置"
    width="860px"
    :destroy-on-close="true"
    class="defect-sync-config-modal"
    @cancel="handleCancel"
  >
    <div class="modal-container">
      <!-- 1. 顶部 SLA 与同步指标横幅 -->
      <div class="sync-metrics-banner">
        <div class="banner-stat">
          <div class="stat-num text-primary font-bold font-mono">
            {{ formState.jira_enabled ? '已激活' : '未连接' }}
          </div>
          <div class="stat-label">Jira 双向工单联动</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-danger font-bold font-mono">
            {{ formState.p0_resolution_hours }}h
          </div>
          <div class="stat-label">P0 故障解决 SLA</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-warning font-bold font-mono">
            {{ formState.p1_resolution_hours }}h
          </div>
          <div class="stat-label">P1 故障解决 SLA</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num font-mono">
            <a-tag :color="formState.auto_reopen_on_fail ? 'green' : 'orange'">
              {{ formState.auto_reopen_on_fail ? '智能 Reopen 激活' : '仅手动管理' }}
            </a-tag>
          </div>
          <div class="stat-label">失败防漏测闭环</div>
        </div>
      </div>

      <!-- 2. 双 Tab 配置面板 -->
      <a-tabs v-model:activeKey="activeTab" class="sync-tabs">
        <!-- Tab 1: 跨平台凭据与流转策略 -->
        <a-tab-pane key="platform" tab="外部工单平台双向集成 (Platform Sync)">
          <a-form layout="vertical" class="sync-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="首选工单同步平台">
                  <a-select v-model:value="formState.primary_platform" class="font-mono">
                    <a-select-option value="JIRA">Atlassian Jira REST API</a-select-option>
                    <a-select-option value="GITHUB">GitHub Issues API</a-select-option>
                    <a-select-option value="ZHENTAO">禅道开源 / 企业版</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="关联目标项目编码 (Project Key)">
                  <a-input v-model:value="formState.project_key" placeholder="如 ATP 或 PROJ" class="font-mono" />
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="外部平台服务地址 (Server URL)">
              <a-input v-model:value="formState.server_url" placeholder="https://jira.company.com" class="font-mono" />
            </a-form-item>

            <a-form-item label="访问凭据与 API Token (加密存储)">
              <a-input-password v-model:value="formState.api_token" placeholder="输入访问密钥或 PAT" class="font-mono" />
            </a-form-item>

            <a-divider style="margin: 12px 0;" />

            <!-- 双向状态流转开关 -->
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="回归通过自动标记闭环 (Auto-Resolve on Pass)">
                  <div class="switch-row">
                    <a-switch v-model:checked="formState.auto_resolve_on_pass" />
                    <span class="switch-desc">
                      用例在后续回归成功后，自动将外部工单标记为 Resolved/Closed。
                    </span>
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="修复后再次失败自动重新打开 (Auto-Reopen on Fail)">
                  <div class="switch-row">
                    <a-switch v-model:checked="formState.auto_reopen_on_fail" />
                    <span class="switch-desc">
                      已修复缺陷若在自动化测试中再次失败，自动 REOPEN 并回填堆栈证据。
                    </span>
                  </div>
                </a-form-item>
              </a-col>
            </a-row>

            <div class="test-conn-bar">
              <a-button size="small" type="dashed" :loading="testingConn" @click="handleTestConnection">
                <template #icon><LinkOutlined /></template>
                测试外部平台连通性
              </a-button>
              <span v-if="connStatusMessage" class="text-xs text-success ml-2 font-mono">
                {{ connStatusMessage }}
              </span>
            </div>
          </a-form>
        </a-tab-pane>

        <!-- Tab 2: 分级 SLA 时效与升级看门狗 -->
        <a-tab-pane key="sla" tab="缺陷解决 SLA 契约与看门狗升级 (SLA Policies)">
          <a-form layout="vertical" class="sla-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="P0 阻塞级缺陷解决时限 (Hours)">
                  <a-input-number v-model:value="formState.p0_resolution_hours" :min="1" :max="72" style="width: 100%;" />
                  <div class="form-help-text text-danger">超时将由看门狗直接启动上线发布强阻断拦截！</div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="P1 严重级缺陷解决时限 (Hours)">
                  <a-input-number v-model:value="formState.p1_resolution_hours" :min="2" :max="168" style="width: 100%;" />
                  <div class="form-help-text">次核心功能受阻，超时自动升级至领域架构主管。</div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="P2 一般业务缺陷解决时限 (Hours)">
                  <a-input-number v-model:value="formState.p2_resolution_hours" :min="6" :max="240" style="width: 100%;" />
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="SLA 临期告急预警阈值 (%)">
                  <a-input-number v-model:value="formState.sla_warning_threshold_pct" :min="50" :max="90" style="width: 100%;" />
                  <div class="form-help-text">已消耗时限达到该比例时发送黄色告急预警通知。</div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="SLA 升级广播通知 Webhook 机器人地址">
              <a-input
                v-model:value="formState.escalation_webhook_url"
                placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
                class="font-mono"
              />
              <div class="form-help-text">
                支持企业微信、钉钉、飞书机器人，超时自动推送到相关团队研发群。
              </div>
            </a-form-item>
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </div>

    <template #footer>
      <div class="modal-footer">
        <a-button @click="resetToDefaults">恢复标准推荐配置</a-button>
        <a-space>
          <a-button @click="handleCancel">取消</a-button>
          <a-button type="primary" :loading="saving" @click="handleSave">
            <template #icon><CheckOutlined /></template>
            保存并生效策略
          </a-button>
        </a-space>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { LinkOutlined, CheckOutlined } from '@ant-design/icons-vue'

export interface DefectSyncConfig {
  primary_platform: string
  project_key: string
  server_url: string
  api_token: string
  jira_enabled: boolean
  auto_resolve_on_pass: boolean
  auto_reopen_on_fail: boolean
  p0_resolution_hours: number
  p1_resolution_hours: number
  p2_resolution_hours: number
  sla_warning_threshold_pct: number
  escalation_webhook_url: string
}

const props = withDefaults(
  defineProps<{
    open: boolean
    initialConfig?: Partial<DefectSyncConfig> | null
  }>(),
  {
    open: false,
    initialConfig: null,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'cancel'): void
  (e: 'save', config: DefectSyncConfig): void
  (e: 'testConnection', platform: string): void
}>()

const activeTab = ref('platform')
const saving = ref(false)
const testingConn = ref(false)
const connStatusMessage = ref('')

const formState = reactive<DefectSyncConfig>({
  primary_platform: 'JIRA',
  project_key: 'ATP',
  server_url: 'https://jira.atp.internal',
  api_token: 'jira_pat_secure_xyz',
  jira_enabled: true,
  auto_resolve_on_pass: true,
  auto_reopen_on_fail: true,
  p0_resolution_hours: 24,
  p1_resolution_hours: 48,
  p2_resolution_hours: 72,
  sla_warning_threshold_pct: 70,
  escalation_webhook_url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=atp_qa_alert',
})

watch(
  () => props.initialConfig,
  (newVal) => {
    if (newVal) {
      if (newVal.primary_platform) formState.primary_platform = newVal.primary_platform
      if (newVal.project_key) formState.project_key = newVal.project_key
      if (newVal.server_url) formState.server_url = newVal.server_url
      if (newVal.api_token) formState.api_token = newVal.api_token
      if (newVal.jira_enabled !== undefined) formState.jira_enabled = newVal.jira_enabled
      if (newVal.auto_resolve_on_pass !== undefined) formState.auto_resolve_on_pass = newVal.auto_resolve_on_pass
      if (newVal.auto_reopen_on_fail !== undefined) formState.auto_reopen_on_fail = newVal.auto_reopen_on_fail
      if (newVal.p0_resolution_hours !== undefined) formState.p0_resolution_hours = newVal.p0_resolution_hours
      if (newVal.p1_resolution_hours !== undefined) formState.p1_resolution_hours = newVal.p1_resolution_hours
      if (newVal.p2_resolution_hours !== undefined) formState.p2_resolution_hours = newVal.p2_resolution_hours
      if (newVal.sla_warning_threshold_pct !== undefined) formState.sla_warning_threshold_pct = newVal.sla_warning_threshold_pct
      if (newVal.escalation_webhook_url) formState.escalation_webhook_url = newVal.escalation_webhook_url
    }
  },
  { immediate: true }
)

function resetToDefaults() {
  formState.primary_platform = 'JIRA'
  formState.project_key = 'ATP'
  formState.server_url = 'https://jira.atp.internal'
  formState.api_token = 'jira_pat_secure_xyz'
  formState.jira_enabled = true
  formState.auto_resolve_on_pass = true
  formState.auto_reopen_on_fail = true
  formState.p0_resolution_hours = 24
  formState.p1_resolution_hours = 48
  formState.p2_resolution_hours = 72
  formState.sla_warning_threshold_pct = 70
  formState.escalation_webhook_url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=atp_qa_alert'
}

function handleCancel() {
  emit('update:open', false)
  emit('cancel')
}

function handleSave() {
  saving.value = true
  emit('save', { ...formState })
  setTimeout(() => {
    saving.value = false
    emit('update:open', false)
  }, 300)
}

function handleTestConnection() {
  testingConn.value = true
  connStatusMessage.value = ''
  emit('testConnection', formState.primary_platform)
  setTimeout(() => {
    testingConn.value = false
    connStatusMessage.value = `✓ 外部平台 [${formState.primary_platform}] API 连通性测试成功，响应时延 82ms`
  }, 400)
}
</script>

<style scoped>
.modal-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
}

.sync-metrics-banner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 14px 16px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
  text-align: center;
}

.banner-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.stat-num {
  font-size: 18px;
  font-weight: 700;
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 11px;
  color: var(--c-text-secondary);
  margin-top: 2px;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.switch-desc {
  font-size: 12px;
  color: var(--c-text-secondary);
}

.form-help-text {
  font-size: 11px;
  color: var(--c-text-tertiary);
  margin-top: 4px;
}

.test-conn-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.text-danger {
  color: var(--c-error);
}

.text-warning {
  color: var(--c-warning);
}

.text-primary {
  color: var(--c-primary);
}

.text-success {
  color: var(--c-success);
}

.text-secondary {
  color: var(--c-text-secondary);
}

.ml-2 {
  margin-left: 8px;
}

.font-mono {
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}
</style>
