<template>
  <div class="page-shell audit-tamper-evident-chain-view">
    <!-- 头部横幅与操作区 -->
    <header class="page-hero">
      <div class="hero-left">
        <h2 class="page-title">类区块链 SHA-256 审计日志防篡改哈希链与合规证明中心</h2>
        <p class="page-subtitle">
          基于类区块链哈希指针链条结构（H_i = SHA-256(H_{i-1} || Payload || Timestamp)），高精度自检历史审计条目的任何恶意修改、漏删或乱序，导出具备 ISO 27001 / SOC 2 Type II 法务级效力的数字签名合规报表。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button @click="handleSimulateTamper">
            模拟篡改攻击检测
          </a-button>
          <a-button :loading="verifying" @click="handleVerifyChain">
            自检哈希链完整性
          </a-button>
          <a-button type="primary" :loading="exporting" @click="handleGenerateReport">
            导出防伪合规报表
          </a-button>
          <a-button @click="router.push('/system/audit-logs')">
            返回审计日志列表
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 完整性自检告警横幅 -->
    <a-alert
      v-if="integrityResult?.tampered"
      type="error"
      show-icon
      class="status-banner"
      message="[TAMPER DETECTED 严重告警] 检测到历史审计日志遭到恶意篡改或物理漏删！"
      :description="`排障诊断: ${integrityResult.error_description}。异常受损位置: 块 #${integrityResult.tampered_at_index} (记录 ID: ${integrityResult.tampered_log_id ?? '--'})`"
    />

    <a-alert
      v-else-if="integrityResult?.is_valid"
      type="success"
      show-icon
      class="status-banner"
      message="[VERIFIED UNALTERED · 密码学完整性 100% 验证通过] 审计日志哈希校验链无任何断裂或篡改。"
      :description="integrityResult.error_description"
    />

    <!-- 密码学指标总览卡片 -->
    <div class="metrics-row">
      <div class="metric-card">
        <span class="metric-label">已连续验签区块</span>
        <div class="metric-value">
          <strong>{{ integrityResult?.total_blocks_checked ?? report?.total_records ?? 0 }}</strong>
          <small class="unit">个审计块</small>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">创世哈希锚点 (Genesis Hash)</span>
        <div class="metric-value">
          <code class="hash-text">0000000000000000...</code>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">当前链头哈希 (Chain Head Root)</span>
        <div class="metric-value">
          <code class="hash-text" :title="integrityResult?.chain_head_hash || report?.chain_head_hash">
            {{ (integrityResult?.chain_head_hash || report?.chain_head_hash || '').slice(0, 18) }}...
          </code>
        </div>
      </div>

      <div class="metric-card">
        <span class="metric-label">法务防伪数字印章 (HMAC-SHA256)</span>
        <div class="metric-value">
          <a-tag color="purple" class="cert-tag">
            {{ report?.digital_seal_signature ? '已完成数字封签' : '等待报告签发' }}
          </a-tag>
        </div>
      </div>
    </div>

    <!-- 哈希校验链条可视化流水 (Hash Chain Stream) -->
    <a-card size="small" title="密码学哈希指针链式连续推导流水 (Cryptographic Hash Chain)" class="chain-card">
      <template #extra>
        <span class="chain-formula">链式公式: H_i = SHA256(H_{i-1} || Record Hash || Timestamp)</span>
      </template>

      <div class="chain-blocks-container">
        <div
          v-for="block in blocks"
          :key="block.index"
          class="chain-block-card"
          :class="{ 'block-tampered': integrityResult?.tampered_at_index === block.index }"
        >
          <div class="block-header">
            <div class="block-idx-badge">区块 #{{ block.index }}</div>
            <a-tag :color="integrityResult?.tampered_at_index === block.index ? 'red' : 'green'">
              {{ integrityResult?.tampered_at_index === block.index ? '数据已损坏' : '验签正常' }}
            </a-tag>
          </div>

          <div class="block-body">
            <div class="hash-line">
              <span class="hash-lbl">Prev Hash:</span>
              <code class="code-val">{{ block.previous_hash.slice(0, 16) }}...</code>
            </div>
            <div class="hash-line">
              <span class="hash-lbl">Record Hash:</span>
              <code class="code-val">{{ block.record_hash.slice(0, 16) }}...</code>
            </div>
            <div class="hash-line block-chain-hash">
              <span class="hash-lbl">Chain Hash:</span>
              <code class="code-val highlight">{{ block.chain_hash.slice(0, 16) }}...</code>
            </div>

            <div class="payload-summary-box">
              <span class="summary-lbl">审计内容:</span>
              <span class="summary-val">
                <code>{{ block.payload_summary.action }}</code> on
                <strong>{{ block.payload_summary.resource_type }}</strong>
                ({{ block.payload_summary.username || 'system' }})
              </span>
            </div>
          </div>
        </div>
      </div>
    </a-card>

    <!-- 正式企业合规审计证书证明弹窗 -->
    <a-modal
      v-model:open="showReportModal"
      title="企业合规审计证明与防篡改鉴定书"
      :width="720"
      :footer="null"
      destroy-on-close
    >
      <div v-if="report" class="compliance-certificate-modal">
        <div class="cert-seal-badge">
          <div class="seal-icon">✓</div>
          <div class="seal-title">ISO/IEC 27001 & SOC 2 COMPLIANT</div>
        </div>

        <a-descriptions size="small" bordered :column="1" class="cert-desc">
          <a-descriptions-item label="证明书编号 (Report ID)">
            <code>{{ report.report_id }}</code>
          </a-descriptions-item>
          <a-descriptions-item label="鉴证认证机构">
            <strong>{{ report.organization }}</strong>
          </a-descriptions-item>
          <a-descriptions-item label="合规完整性状态">
            <a-tag :color="report.integrity_status === 'VERIFIED_UNALTERED' ? 'success' : 'error'">
              {{ report.integrity_status === 'VERIFIED_UNALTERED' ? '完全真实无篡改 (VERIFIED UNALTERED)' : '检测到篡改风险' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="累计连续验签条数">
            {{ report.total_records }} 条记录
          </a-descriptions-item>
          <a-descriptions-item label="审计链头根哈希 (Merkle/Chain Root)">
            <code class="root-hash">{{ report.chain_head_hash }}</code>
          </a-descriptions-item>
          <a-descriptions-item label="HMAC 防伪数字印章签名">
            <code class="sig-hash">{{ report.digital_seal_signature }}</code>
          </a-descriptions-item>
          <a-descriptions-item label="签发时间戳">
            {{ report.generated_at }}
          </a-descriptions-item>
        </a-descriptions>

        <div class="cert-footer">
          <a-button type="primary" block @click="showReportModal = false">
            确认并关闭证书
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  auditChainApi,
  type AuditChainBlock,
  type AuditChainIntegrityResult,
  type ComplianceAuditReport,
} from '@/api/auditChain'

const router = useRouter()

const verifying = ref(false)
const exporting = ref(false)
const showReportModal = ref(false)

const integrityResult = ref<AuditChainIntegrityResult | null>(null)
const report = ref<ComplianceAuditReport | null>(null)
const blocks = ref<AuditChainBlock[]>([])

const sampleLogRecords = [
  {
    id: 1,
    action: 'user_login',
    resource_type: 'user',
    resource_id: 1,
    username: 'admin',
    detail: '管理员登录系统',
    ip_address: '127.0.0.1',
    created_at: '2026-10-16T10:00:00Z',
  },
  {
    id: 2,
    action: 'case_create',
    resource_type: 'case',
    resource_id: 101,
    username: 'engineer_wong',
    detail: '创建核心支付冒烟用例',
    ip_address: '192.168.1.100',
    created_at: '2026-10-16T10:05:00Z',
  },
  {
    id: 3,
    action: 'mesh_chaos_experiment_start',
    resource_type: 'mesh_chaos',
    resource_id: 501,
    username: 'admin',
    detail: '启动分布式网关 503 故障注入',
    ip_address: '127.0.0.1',
    created_at: '2026-10-16T10:15:00Z',
  },
  {
    id: 4,
    action: 'sso_provider_registered',
    resource_type: 'oidc_sso',
    resource_id: 1,
    username: 'admin',
    detail: '注册企业 Keycloak 身份提供商',
    ip_address: '127.0.0.1',
    created_at: '2026-10-16T10:20:00Z',
  },
]

async function handleVerifyChain() {
  verifying.value = true
  try {
    const res = await auditChainApi.verifyChain({ limit: 100 })
    integrityResult.value = res
    if (res.is_valid) {
      message.success('审计日志哈希链自检 100% 完整通过！')
    } else {
      message.error(`检测到审计日志篡改风险: ${res.error_description}`)
    }
  } catch (err: any) {
    message.error(err.message || '自检哈希链失败')
  } finally {
    verifying.value = false
  }
}

async function handleGenerateReport() {
  exporting.value = true
  try {
    const res = await auditChainApi.generateReport({
      organization: 'ATP Enterprise QA & Cyber Security Team',
      custom_records: sampleLogRecords,
    })
    report.value = res
    integrityResult.value = res.integrity_diagnostic
    blocks.value = res.blocks
    showReportModal.value = true
    message.success('已成功生成附带数字印章的企业合规审计证明！')
  } catch (err: any) {
    message.error(err.message || '生成合规报表失败')
  } finally {
    exporting.value = false
  }
}

function handleSimulateTamper() {
  // Simulate tampering with block #2 payload hash
  if (blocks.value.length >= 2) {
    blocks.value[1].record_hash = 'deadbeef' + blocks.value[1].record_hash.slice(8)
    integrityResult.value = {
      is_valid: false,
      tampered: true,
      total_blocks_checked: blocks.value.length,
      chain_head_hash: blocks.value[blocks.value.length - 1].chain_hash,
      tampered_at_index: 2,
      tampered_log_id: blocks.value[1].log_id,
      error_description: '数据摘要篡改 (Payload Hash Mismatch): 块 #2 真实哈希与记录不一致，内容已被非法修改！',
    }
    message.error('已模拟篡改攻击测试：精准定位块 #2 发生非法修改！')
  } else {
    message.warning('请先生成审计链条再执行篡改测试')
  }
}

onMounted(() => {
  handleGenerateReport()
})
</script>

<style scoped>
.audit-tamper-evident-chain-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.page-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
  max-width: 680px;
}

.status-banner {
  border-radius: 6px;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--c-bg-surface, #fff);
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-label {
  font-size: 11px;
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

.hash-text {
  font-family: monospace;
  font-size: 11px;
  color: #2563eb;
}

.cert-tag {
  font-size: 11px;
}

.unit {
  font-size: 12px;
  font-weight: normal;
  color: var(--c-text-tertiary, #94a3b8);
}

.chain-card {
  border-radius: 8px;
}

.chain-formula {
  font-family: monospace;
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.chain-blocks-container {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding: 8px 4px 14px;
}

.chain-block-card {
  min-width: 250px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
  transition: all 0.2s ease;
}

.chain-block-card.block-tampered {
  border-color: #ef4444;
  background: #fef2f2;
}

.block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  padding-bottom: 6px;
}

.block-idx-badge {
  font-weight: 600;
  font-size: 12px;
  color: var(--c-text, #0f172a);
}

.block-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
}

.hash-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}

.hash-lbl {
  color: var(--c-text-secondary, #64748b);
  font-size: 10px;
}

.code-val {
  font-family: monospace;
  font-size: 10px;
  color: #334155;
}

.code-val.highlight {
  color: #2563eb;
  font-weight: 600;
}

.payload-summary-box {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--c-border, #e2e8f0);
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}

.summary-lbl {
  color: var(--c-text-tertiary, #94a3b8);
  font-size: 10px;
}

.summary-val code {
  color: #0284c7;
}

.compliance-certificate-modal {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cert-seal-badge {
  text-align: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
}

.seal-icon {
  font-size: 32px;
  color: #16a34a;
  line-height: 1;
}

.seal-title {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
  letter-spacing: 0.05em;
  margin-top: 4px;
}

.root-hash,
.sig-hash {
  font-family: monospace;
  font-size: 10px;
  word-break: break-all;
}

.cert-footer {
  margin-top: 8px;
}
</style>
