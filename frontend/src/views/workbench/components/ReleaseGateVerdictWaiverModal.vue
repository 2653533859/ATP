<template>
  <a-modal
    :open="open"
    :width="980"
    title="自动化发版准入阻断裁决 (Go/No-Go) 与特批风险豁免控制台"
    destroy-on-close
    class="release-gate-modal"
    @cancel="handleClose"
  >
    <template #footer>
      <a-button @click="handleClose">关闭</a-button>
    </template>

    <div class="modal-content">
      <!-- 头部机制说明 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <SafetyCertificateOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">发版准入阻断状态机与架构师特批风险豁免网关 (T4.2)</div>
          <div class="banner-desc">
            基于多维质量健康得分、P0/P1缺陷状态与IaC安全扫描输出客观发布裁决（<code>GO</code>、<code>CAUTION</code>、<code>NO_GO</code>）。对于阻断版本支持由架构师/管理层进行不可篡改的风险特批豁免签署（<code>WAIVED_GO</code>），并在防篡改审计日志中终身留痕。
          </div>
        </div>
      </div>

      <!-- 场景预设与快速评估控制栏 -->
      <div class="config-section">
        <div class="section-title">发版版本与门禁评估场景预设</div>
        <div class="config-row">
          <div class="preset-group">
            <span class="label">发版评估场景:</span>
            <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
              <a-radio-button value="approved_go">合格发版 (GO 放行)</a-radio-button>
              <a-radio-button value="caution_gray">灰度预警 (CAUTION 观察)</a-radio-button>
              <a-radio-button value="blocked_no_go">高危阻断 (NO_GO 严苛拦截)</a-radio-button>
            </a-radio-group>
          </div>
          <a-button type="primary" size="small" :loading="evaluating" @click="handleEvaluate">
            <ThunderboltOutlined /> 运行准入门禁裁决
          </a-button>
        </div>
      </div>

      <!-- 准入裁决大横幅 -->
      <div v-if="currentRecord" class="verdict-banner-wrap">
        <div class="verdict-banner" :class="getVerdictBannerClass(currentRecord.verdict)">
          <div class="verdict-badge-box">
            <span class="verdict-badge">{{ currentRecord.verdict }}</span>
            <span class="verdict-desc">{{ getVerdictDesc(currentRecord.verdict) }}</span>
          </div>

          <div class="verdict-meta">
            <span>目标版本: <strong>{{ currentRecord.target_version }}</strong></span>
            <span>综合质量分: <strong>{{ currentRecord.quality_score }} 分</strong></span>
            <span v-if="currentRecord.is_waived" class="waived-tag">架构师特批豁免</span>
          </div>

          <!-- 阻断原因清单 -->
          <div v-if="currentRecord.blocking_reasons.length" class="reasons-block blocking">
            <div class="reasons-title">🛑 触发上线发布严苛阻断原因:</div>
            <ul>
              <li v-for="(reason, idx) in currentRecord.blocking_reasons" :key="idx">{{ reason }}</li>
            </ul>
          </div>

          <!-- 预警原因清单 -->
          <div v-if="currentRecord.warning_reasons.length" class="reasons-block warning">
            <div class="reasons-title">⚠️ 灰度关注预警项:</div>
            <ul>
              <li v-for="(reason, idx) in currentRecord.warning_reasons" :key="idx">{{ reason }}</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- 特批风险豁免操作区域 (仅限 NO_GO 或 WAIVED_GO) -->
      <div
        v-if="currentRecord && (currentRecord.verdict === 'NO_GO' || currentRecord.is_waived)"
        class="waiver-section"
      >
        <div class="section-title">
          <ExclamationCircleOutlined /> 架构师/管理层特批风险豁免流转
        </div>

        <!-- 已豁免状态展示 -->
        <div v-if="currentRecord.is_waived && currentRecord.waiver_info" class="waived-info-box">
          <div class="waived-header">
            <span>特批签署人: <strong>{{ currentRecord.waiver_info.approver }}</strong></span>
            <span>签署时间: <strong>{{ currentRecord.waiver_info.waived_at.substring(0, 19) }}</strong></span>
          </div>
          <div class="waived-item">
            <span class="item-label">豁免申请理由:</span>
            <span class="item-text">{{ currentRecord.waiver_info.waiver_reason }}</span>
          </div>
          <div class="waived-item">
            <span class="item-label">应急回滚预案:</span>
            <span class="item-text">{{ currentRecord.waiver_info.rollback_plan }}</span>
          </div>
          <div class="revoke-btn-row">
            <a-button size="small" danger :loading="waiving" @click="handleRevokeWaiver">
              撤销特批豁免 (恢复为 NO_GO 阻断)
            </a-button>
          </div>
        </div>

        <!-- 填写豁免表单 -->
        <div v-else class="waiver-form">
          <div class="form-desc text-danger">
            当前版本因存在严重质量阻断项被系统拦截。若为紧急现网修复且具备完备回滚机制，可由首席架构师签署风险豁免特批放行。
          </div>
          <div class="form-item">
            <label class="form-label">申请豁免理由说明 (必填):</label>
            <a-input v-model:value="waiverReason" placeholder="如 线上核心故障紧急修复，非核心流程已通过灰度开关规避" size="small" />
          </div>
          <div class="form-item">
            <label class="form-label">故障应急快速回滚方案 (必填):</label>
            <a-input v-model:value="rollbackPlan" placeholder="如 10 分钟内一键回滚镜像并切回旧版本流量" size="small" />
          </div>
          <a-button type="primary" danger size="small" :loading="waiving" @click="handleGrantWaiver">
            <AuditOutlined /> 架构师签署特批豁免放行
          </a-button>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ExclamationCircleOutlined,
  AuditOutlined,
} from '@ant-design/icons-vue'
import {
  releaseGateVerdictApi,
  type ReleaseGateVerdictRecord,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const evaluating = ref(false)
const waiving = ref(false)
const selectedPreset = ref<'approved_go' | 'caution_gray' | 'blocked_no_go'>('blocked_no_go')
const currentRecord = ref<ReleaseGateVerdictRecord | null>(null)

const waiverReason = ref('紧急核心故障修复，经技术评审委员会讨论一致同意特批放行')
const rollbackPlan = ref('配置好灰度开关并在发现异常 5 分钟内执行 Helm 原子回滚')

const PRESET_EVALS = {
  approved_go: {
    target_version: 'v4.3.0',
    quality_score: 93.5,
    p0_defects_count: 0,
    p1_defects_count: 0,
    critical_security_flaws_count: 0,
    test_pass_rate_pct: 100.0,
  },
  caution_gray: {
    target_version: 'v4.3.0-rc1',
    quality_score: 79.0,
    p0_defects_count: 0,
    p1_defects_count: 1,
    critical_security_flaws_count: 0,
    test_pass_rate_pct: 98.5,
  },
  blocked_no_go: {
    target_version: 'v4.3.0-hotfix-p0',
    quality_score: 58.0,
    p0_defects_count: 1, // 存在阻塞缺陷
    p1_defects_count: 1,
    critical_security_flaws_count: 1,
    test_pass_rate_pct: 92.0,
  },
}

function handleClose() {
  emit('update:open', false)
}

function handlePresetChange() {
  handleEvaluate()
}

function getVerdictBannerClass(verdict: string) {
  switch (verdict) {
    case 'GO': return 'banner-go'
    case 'CAUTION': return 'banner-caution'
    case 'NO_GO': return 'banner-nogo'
    case 'WAIVED_GO': return 'banner-waived'
    default: return ''
  }
}

function getVerdictDesc(verdict: string) {
  switch (verdict) {
    case 'GO': return '发版准入通过 · 满足全量质量基线，准许上线发布'
    case 'CAUTION': return '警示灰度放行 · 存在非关键瑕疵，需重点灰度观察'
    case 'NO_GO': return '严苛发布阻断 · 触发高危缺陷/安全门禁，禁止上线'
    case 'WAIVED_GO': return '特批风险豁免 · 已由架构师特批放行并记录预案'
    default: return ''
  }
}

async function handleEvaluate() {
  evaluating.value = true
  try {
    const p = PRESET_EVALS[selectedPreset.value]
    const res = await releaseGateVerdictApi.evaluate(p)
    currentRecord.value = res.record
    message.success(res.message || '门禁裁决完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '门禁评估失败')
  } finally {
    evaluating.value = false
  }
}

async function handleGrantWaiver() {
  if (!currentRecord.value) return
  if (!waiverReason.value || !rollbackPlan.value) {
    message.warning('请完整填写豁免理由与回滚预案')
    return
  }
  waiving.value = true
  try {
    const res = await releaseGateVerdictApi.waive(currentRecord.value.release_id, {
      waiver_reason: waiverReason.value,
      rollback_plan: rollbackPlan.value,
    })
    message.success(res.message || '风险特批豁免成功签署')
    if (res.record) {
      currentRecord.value = res.record
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '豁免签署失败')
  } finally {
    waiving.value = false
  }
}

async function handleRevokeWaiver() {
  if (!currentRecord.value) return
  waiving.value = true
  try {
    const res = await releaseGateVerdictApi.revokeWaiver(currentRecord.value.release_id)
    message.success(res.message || '特批豁免已撤销')
    if (res.record) {
      currentRecord.value = res.record
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '撤销失败')
  } finally {
    waiving.value = false
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      handleEvaluate()
    }
  }
)

onMounted(() => {
  if (props.open) {
    handleEvaluate()
  }
})
</script>

<style scoped>
.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #eff6ff 0%, #e0f2fe 100%);
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #2563eb;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e3a8a;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #3b82f6;
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

.verdict-banner {
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  border: 1px solid transparent;
}

.banner-go {
  background: #f0fdf4;
  border-color: #86efac;
}

.banner-caution {
  background: #fffbeb;
  border-color: #fde68a;
}

.banner-nogo {
  background: #fef2f2;
  border-color: #fca5a5;
}

.banner-waived {
  background: #faf5ff;
  border-color: #d8b4fe;
}

.verdict-badge-box {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.verdict-badge {
  font-size: 16px;
  font-weight: 900;
  padding: 3px 10px;
  border-radius: 6px;
  color: #ffffff;
}

.banner-go .verdict-badge { background: #16a34a; }
.banner-caution .verdict-badge { background: #d97706; }
.banner-nogo .verdict-badge { background: #dc2626; }
.banner-waived .verdict-badge { background: #7c3aed; }

.verdict-desc {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.verdict-meta {
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: #475569;
  margin-bottom: 10px;
}

.waived-tag {
  background: #e9d5ff;
  color: #6b21a8;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
}

.reasons-block {
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 12px;
  margin-top: 8px;
}

.reasons-block.blocking {
  background: #fee2e2;
  color: #991b1b;
}

.reasons-block.warning {
  background: #fef3c7;
  color: #92400e;
}

.reasons-title {
  font-weight: 700;
  margin-bottom: 4px;
}

ul {
  margin: 0;
  padding-left: 20px;
}

.waiver-section {
  background: #ffffff;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 10px;
}

.waived-info-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
}

.waived-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  border-bottom: 1px dashed #cbd5e1;
  padding-bottom: 4px;
}

.item-label {
  font-weight: 700;
  color: #475569;
  margin-right: 6px;
}

.revoke-btn-row {
  margin-top: 6px;
  text-align: right;
}

.waiver-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-desc {
  font-size: 11px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 11px;
  font-weight: 600;
  color: #334155;
}

.text-danger { color: #dc2626; }
</style>
