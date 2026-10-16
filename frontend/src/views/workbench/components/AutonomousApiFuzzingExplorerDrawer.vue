<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="自主探索式 API 模糊变异与隐蔽缺陷深度探查控制台"
    destroy-on-close
    class="fuzzing-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制说明 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <BugOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">状态反馈驱动的 API 模糊变异与反向安全鲁棒性探查引擎 (T3.3)</div>
          <div class="banner-desc">
            突破已知断言的局限性！针对目标接口注入 SQL 破坏性探针、XSS 脚本、截断控制符、超长数值溢出与类型混淆变异向量，主动探查后端未捕获异常、5xx 服务崩溃与 ReDoS 时延风险，并自动输出单行 cURL 复现命令行。
          </div>
        </div>
      </div>

      <!-- 探测目标与策略选择控制栏 -->
      <div class="config-section">
        <div class="section-title">变异目标接口与策略配置</div>
        <div class="config-row">
          <div class="target-input-group">
            <span class="label">目标接口:</span>
            <a-select v-model:value="targetMethod" size="small" class="w-24">
              <a-select-option value="POST">POST</a-select-option>
              <a-select-option value="GET">GET</a-select-option>
              <a-select-option value="PUT">PUT</a-select-option>
            </a-select>
            <a-input v-model:value="targetEndpoint" size="small" placeholder="/api/v1/orders/checkout" class="w-80" />
          </div>
          <a-button type="primary" size="small" :loading="running" @click="handleRunFuzzing">
            <ThunderboltOutlined /> 发起自主变异探索
          </a-button>
        </div>

        <div class="strategies-row mt-3">
          <span class="label">启用的变异策略库:</span>
          <a-checkbox-group v-model:value="selectedStrategies" class="strategy-checkboxes">
            <a-checkbox value="SQL_INJECTION_PROBE">SQL 注入探针</a-checkbox>
            <a-checkbox value="XSS_HTML_PAYLOAD">XSS 跨站脚本</a-checkbox>
            <a-checkbox value="UNICODE_CONTROL_CHARS">Unicode 控制截断</a-checkbox>
            <a-checkbox value="NUMERIC_OVERFLOW">64位数值溢出</a-checkbox>
            <a-checkbox value="FORMAT_STRING_INJECTION">格式化字符串溢出</a-checkbox>
            <a-checkbox value="TYPE_CONFUSION">对象/数组类型混淆</a-checkbox>
          </a-checkbox-group>
        </div>
      </div>

      <!-- 4 大核心 KPI 统计卡片 -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">累计变异探查数</div>
            <div class="stat-value text-primary">{{ currentSession?.total_mutations_count ?? 0 }} <span class="unit">次</span></div>
            <div class="stat-trend">多维度反向扰动测试</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">接口健壮性防御得分</div>
            <div class="stat-value" :class="getScoreColorClass(currentSession?.robustness_score_pct ?? 100)">
              {{ currentSession?.robustness_score_pct ?? 100 }}%
            </div>
            <div class="stat-trend">异常容错与防护水位</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">严重崩溃缺陷 (CRITICAL)</div>
            <div class="stat-value text-danger">{{ currentSession?.critical_count ?? 0 }} <span class="unit">处</span></div>
            <div class="stat-trend">5xx 未捕获崩溃与 SQL 漏洞</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">时延尖刺缺陷 (HIGH)</div>
            <div class="stat-value text-warning">{{ currentSession?.high_count ?? 0 }} <span class="unit">处</span></div>
            <div class="stat-trend">ReDoS 或算法复杂度飙升</div>
          </div>
        </a-col>
      </a-row>

      <!-- 探查缺陷发现卡片列表 -->
      <div class="findings-section">
        <div class="section-title">
          <span>探查发现的隐蔽缺陷与复现清单 (共 {{ currentSession?.findings.length ?? 0 }} 处)</span>
        </div>

        <div v-if="currentSession?.findings.length" class="findings-list">
          <div
            v-for="flaw in currentSession.findings"
            :key="flaw.flaw_id"
            class="flaw-card"
          >
            <div class="flaw-header">
              <div class="flaw-title-left">
                <a-tag :color="flaw.severity === 'CRITICAL' ? 'red' : 'orange'">{{ flaw.severity }}</a-tag>
                <a-tag color="purple">{{ flaw.flaw_type }}</a-tag>
                <span class="strategy-tag">策略: {{ flaw.strategy }}</span>
              </div>
              <span class="status-code-badge" :class="flaw.status_code >= 500 ? 'status-500' : 'status-warn'">
                HTTP {{ flaw.status_code }}
              </span>
            </div>

            <div class="flaw-meta">
              <span>变异字段: <code>{{ flaw.mutated_key }}</code></span>
              <span>变异注入值: <code>{{ String(flaw.mutated_value) }}</code></span>
            </div>

            <div class="response-excerpt-box">
              <span class="excerpt-label">服务端响应回显摘要:</span>
              <pre class="excerpt-code"><code>{{ flaw.response_excerpt }}</code></pre>
            </div>

            <div class="curl-reproduce-box">
              <div class="curl-header">
                <span class="curl-label">一键复现命令行 (cURL):</span>
                <a-button size="small" type="link" class="p-0" @click="handleCopyCurl(flaw.reproduction_curl)">
                  <CopyOutlined /> 复制 cURL
                </a-button>
              </div>
              <code class="curl-code">{{ flaw.reproduction_curl }}</code>
            </div>
          </div>
        </div>

        <div v-else class="empty-findings">
          <a-empty description="当前探测轮次未发现异常崩溃或未捕获漏洞，接口防御机制健壮！" />
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  BugOutlined,
  ThunderboltOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  autonomousApiFuzzingApi,
  type FuzzingExplorationSession,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const running = ref(false)
const targetMethod = ref('POST')
const targetEndpoint = ref('/api/v1/orders/checkout')
const selectedStrategies = ref<string[]>([
  'SQL_INJECTION_PROBE',
  'XSS_HTML_PAYLOAD',
  'UNICODE_CONTROL_CHARS',
  'NUMERIC_OVERFLOW',
])
const currentSession = ref<FuzzingExplorationSession | null>(null)

function handleClose() {
  emit('update:open', false)
}

function getScoreColorClass(score: number) {
  if (score >= 90) return 'text-success'
  if (score >= 70) return 'text-warning'
  return 'text-danger'
}

async function handleRunFuzzing() {
  running.value = true
  try {
    const res = await autonomousApiFuzzingApi.run({
      endpoint: targetEndpoint.value,
      method: targetMethod.value,
      base_payload: {
        order_id: 'ORD_1001',
        amount: 88.5,
        notes: 'normal checkout request',
      },
      strategies: selectedStrategies.value,
    })
    currentSession.value = res.session
    message.success(res.message || '变异探索测试完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '变异测试执行失败')
  } finally {
    running.value = false
  }
}

function handleCopyCurl(cmd: string) {
  navigator.clipboard.writeText(cmd)
  message.success('已复制 cURL 复现命令到剪贴板')
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      handleRunFuzzing()
    }
  }
)

onMounted(() => {
  if (props.open) {
    handleRunFuzzing()
  }
})
</script>

<style scoped>
.fuzzing-drawer :deep(.ant-drawer-body) {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
}

.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #dc2626;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #991b1b;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.5;
}

.config-section,
.findings-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
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

.target-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.w-24 { width: 90px; }
.w-80 { width: 320px; }

.strategy-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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
  font-size: 22px;
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
.text-danger { color: #dc2626; }

.findings-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.flaw-card {
  background: #fff1f2;
  border: 1px solid #fecdd3;
  border-radius: 6px;
  padding: 12px 14px;
}

.flaw-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.flaw-title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.strategy-tag {
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
}

.status-code-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-500 { background: #fee2e2; color: #dc2626; }
.status-warn { background: #fef3c7; color: #d97706; }

.flaw-meta {
  display: flex;
  gap: 20px;
  font-size: 11px;
  color: #475569;
  margin-bottom: 8px;
}

.response-excerpt-box,
.curl-reproduce-box {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 8px 12px;
  margin-top: 6px;
}

.excerpt-label,
.curl-label {
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  display: block;
  margin-bottom: 4px;
}

.excerpt-code {
  margin: 0;
  color: #b91c1c;
  font-family: monospace;
  font-size: 11px;
}

.curl-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.curl-code {
  font-family: monospace;
  font-size: 11px;
  color: #0369a1;
  word-break: break-all;
}

.empty-findings {
  padding: 40px 0;
}

.mt-3 { margin-top: 10px; }
.p-0 { padding: 0; }
</style>
