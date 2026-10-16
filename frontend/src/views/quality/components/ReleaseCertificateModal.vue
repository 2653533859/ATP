<template>
  <a-modal
    :open="open"
    :width="840"
    destroy-on-close
    :footer="null"
    @cancel="handleClose"
  >
    <template #title>
      <div class="modal-title-box">
        <span>自动化发版准入合格证书与防伪数字印章</span>
        <a-tag v-if="certificate?.verdict === 'APPROVED'" color="green">准予发版合格</a-tag>
        <a-tag v-else-if="certificate" color="red">发版准入驳回</a-tag>
      </div>
    </template>

    <div class="release-certificate-modal">
      <!-- 证书签发控制栏 -->
      <a-card size="small" class="form-card">
        <a-form layout="inline" class="cert-gen-form">
          <a-form-item label="发版版本号" required>
            <a-input v-model:value="releaseVersion" size="small" style="width: 120px" />
          </a-form-item>

          <a-form-item label="Commit SHA" required>
            <a-input v-model:value="commitSha" size="small" style="width: 110px" />
          </a-form-item>

          <a-form-item label="目标环境">
            <a-select v-model:value="targetEnv" size="small" style="width: 120px">
              <a-select-option value="production">production</a-select-option>
              <a-select-option value="staging">staging</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item>
            <a-space size="small">
              <a-button
                type="primary"
                size="small"
                :loading="generating"
                @click="handleGenerateCertificate"
              >
                签发准入证书
              </a-button>
            </a-space>
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 证书纸面主体 (Security Certificate Ticket) -->
      <div v-if="certificate" class="certificate-ticket-frame">
        <!-- 证书内衬防伪花纹边框 -->
        <div class="cert-inner-box">
          <!-- 官方安全徽标与标头 -->
          <div class="cert-header">
            <div class="cert-badges-row">
              <span class="cert-shield-badge">🛡️ ISO 27001 AUDITED</span>
              <span class="cert-shield-badge">🔒 SOC 2 TYPE II COMPLIANT</span>
              <span class="cert-shield-badge">⭐ ATP SECURITY TRUSTED</span>
            </div>
            <h3 class="cert-main-title">全生命周期软件发版准入合格证书</h3>
            <p class="cert-sub-title">Enterprise Release Readiness & Security Audit Certificate</p>
          </div>

          <!-- 证书编号与主体信息表 -->
          <div class="cert-info-grid">
            <div class="info-cell">
              <span class="info-label">证书唯一编号 (Certificate ID)</span>
              <strong class="info-val text-blue">{{ certificate.certificate_id }}</strong>
            </div>

            <div class="info-cell">
              <span class="info-label">发版版本号 (Release Version)</span>
              <strong class="info-val">{{ certificate.release_version }}</strong>
            </div>

            <div class="info-cell">
              <span class="info-label">代码 Commit SHA</span>
              <code class="info-val monospace">{{ certificate.commit_sha }}</code>
            </div>

            <div class="info-cell">
              <span class="info-label">目标发版环境</span>
              <span class="info-val">{{ certificate.target_environment }}</span>
            </div>

            <div class="info-cell">
              <span class="info-label">综合质量健康评分</span>
              <strong class="info-val text-green">{{ certificate.quality_score }} / 100 分</strong>
            </div>

            <div class="info-cell">
              <span class="info-label">签发时间戳 (Issued At)</span>
              <span class="info-val text-secondary">{{ certificate.issued_at }}</span>
            </div>
          </div>

          <!-- 决议结论印章区 -->
          <div class="cert-seal-section">
            <div class="seal-desc-box">
              <span class="seal-meta-title">质量门禁判定决议：</span>
              <p v-if="certificate.verdict === 'APPROVED'" class="verdict-statement text-green">
                本项目已通过四维质量模型多重核验，无阻塞性卡点违约，正式准予生产发版上线。
              </p>
              <p v-else class="verdict-statement text-red">
                检测到未达标的阻塞性卡点，发版准入已被强行阻断：{{ certificate.blocked_reasons.join('；') }}
              </p>
            </div>

            <!-- 仿真印章徽标 -->
            <div class="official-stamp" :class="certificate.verdict === 'APPROVED' ? 'stamp-approved' : 'stamp-rejected'">
              <span class="stamp-org">ATP 质量门禁委员会</span>
              <strong class="stamp-verdict">{{ certificate.verdict === 'APPROVED' ? '准予发布' : '阻断发版' }}</strong>
              <small class="stamp-code">{{ certificate.verdict }}</small>
            </div>
          </div>

          <!-- HMAC-SHA256 数字防伪印章 -->
          <div class="digital-seal-box">
            <div class="seal-header">
              <span class="seal-label">HMAC-SHA256 数字防伪印章签名 (Digital Security Seal):</span>
              <a-button
                size="small"
                type="link"
                :loading="verifying"
                @click="handleVerifySignature"
              >
                检验签名真伪与防篡改自检
              </a-button>
            </div>
            <code class="signature-text">{{ certificate.digital_seal_signature }}</code>
            <div class="hash-row">
              <small class="hash-text">完整性 SHA-256 摘要: {{ certificate.certificate_hash }}</small>
            </div>
          </div>
        </div>
      </div>

      <!-- 验签成功提示横幅 -->
      <a-alert
        v-if="verificationResult?.is_authentic"
        type="success"
        show-icon
        class="verify-alert"
        :message="`[数字印章验证通过] ${verificationResult.message}`"
        description="证书数字印章与系统 HMAC 私钥严格一致，内容无任何篡改，具备不可否认的法律级工程审计效力。"
      />

      <!-- 底部导出与操作栏 -->
      <div v-if="certificate" class="modal-footer-actions">
        <a-space>
          <a-button @click="handleExportJson">
            导出证书 JSON 凭据
          </a-button>
          <a-button type="primary" @click="handleClose">
            确定并关闭
          </a-button>
        </a-space>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  qualityGovernanceApi,
  type ReleaseCertificateItem,
  type VerifyCertificateResponse,
} from '@/api/qualityGovernance'

const props = withDefaults(
  defineProps<{
    open: boolean
    projectId?: number
    defaultReleaseVersion?: string
    defaultCommitSha?: string
  }>(),
  {
    open: false,
    projectId: 1,
    defaultReleaseVersion: 'v3.3.0',
    defaultCommitSha: '15c38686',
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const generating = ref(false)
const verifying = ref(false)

const releaseVersion = ref('v3.3.0')
const commitSha = ref('15c38686')
const targetEnv = ref('production')

const certificate = ref<ReleaseCertificateItem | null>(null)
const verificationResult = ref<VerifyCertificateResponse | null>(null)

function handleClose() {
  emit('update:open', false)
}

async function handleGenerateCertificate() {
  generating.value = true
  try {
    const res = await qualityGovernanceApi.generateCertificate({
      project_id: props.projectId,
      release_version: releaseVersion.value,
      commit_sha: commitSha.value,
      target_environment: targetEnv.value,
      gate_profile_id: 'gate_prod_release',
    })
    certificate.value = res
    verificationResult.value = null
    message.success(`发版准入合格证书签发成功: ${res.certificate_id}`)
  } catch (err: any) {
    message.error(err.message || '签发证书失败')
  } finally {
    generating.value = false
  }
}

async function handleVerifySignature() {
  if (!certificate.value) return
  verifying.value = true
  try {
    const res = await qualityGovernanceApi.verifyCertificate({
      certificate_id: certificate.value.certificate_id,
      release_version: certificate.value.release_version,
      commit_sha: certificate.value.commit_sha,
      verdict: certificate.value.verdict,
      quality_score: certificate.value.quality_score,
      issued_at: certificate.value.issued_at,
      digital_seal_signature: certificate.value.digital_seal_signature,
    })
    verificationResult.value = res
    if (res.is_authentic) {
      message.success('防伪数字印章验签通过：证书真实有效，未被篡改！')
    } else {
      message.error('警告：数字防伪印章签名校验失败，证书疑似遭到篡改！')
    }
  } catch (err: any) {
    message.error(err.message || '验签失败')
  } finally {
    verifying.value = false
  }
}

function handleExportJson() {
  if (!certificate.value) return
  const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(certificate.value, null, 2))
  const downloadAnchor = document.createElement('a')
  downloadAnchor.setAttribute('href', dataStr)
  downloadAnchor.setAttribute('download', `${certificate.value.certificate_id}.json`)
  document.body.appendChild(downloadAnchor)
  downloadAnchor.click()
  downloadAnchor.remove()
  message.success('发版证书凭据 JSON 文件已导出！')
}
</script>

<style scoped>
.modal-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.release-certificate-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-card {
  border-radius: 8px;
}

.certificate-ticket-frame {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  padding: 16px;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.4);
}

.cert-inner-box {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 20px;
  background: rgba(15, 23, 42, 0.6);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cert-header {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cert-badges-row {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.cert-shield-badge {
  font-size: 11px;
  background: rgba(255, 255, 255, 0.1);
  color: #38bdf8;
  padding: 2px 8px;
  border-radius: 12px;
}

.cert-main-title {
  color: #ffffff;
  font-size: 18px;
  font-weight: 700;
  margin: 4px 0 0;
  letter-spacing: 1px;
}

.cert-sub-title {
  color: #94a3b8;
  font-size: 11px;
  margin: 0;
  font-family: serif;
}

.cert-info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  background: rgba(30, 41, 59, 0.7);
  padding: 14px;
  border-radius: 8px;
}

.info-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 11px;
  color: #94a3b8;
}

.info-val {
  font-size: 13px;
  color: #f8fafc;
}

.monospace {
  font-family: monospace;
}

.text-blue {
  color: #38bdf8;
}

.text-green {
  color: #4ade80;
}

.text-red {
  color: #f87171;
}

.text-secondary {
  color: #cbd5e1;
}

.cert-seal-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 8px 4px;
}

.seal-desc-box {
  flex: 1;
}

.seal-meta-title {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
}

.verdict-statement {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
}

.official-stamp {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  border: 3px double;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transform: rotate(-12deg);
  opacity: 0.9;
  flex-shrink: 0;
}

.stamp-approved {
  border-color: #22c55e;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.08);
}

.stamp-rejected {
  border-color: #ef4444;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}

.stamp-org {
  font-size: 9px;
}

.stamp-verdict {
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 2px;
}

.stamp-code {
  font-size: 9px;
}

.digital-seal-box {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(56, 189, 248, 0.3);
  border-radius: 6px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.seal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.seal-label {
  font-size: 11px;
  color: #38bdf8;
  font-weight: 600;
}

.signature-text {
  font-size: 10px;
  color: #a5f3fc;
  font-family: monospace;
  word-break: break-all;
}

.hash-row {
  margin-top: 2px;
}

.hash-text {
  font-size: 10px;
  color: #64748b;
  font-family: monospace;
}

.verify-alert {
  border-radius: 6px;
}

.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--c-border, #e2e8f0);
  padding-top: 12px;
}
</style>
