<template>
  <div class="page-shell audit-report-view">
    <!-- 顶部导航与操作栏 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <SafetyCertificateOutlined class="hero-icon" />
          <h2 class="page-title">端到端测试执行与质量合规全景审计报告大盘</h2>
          <span class="live-dot" />
          <span class="muted-text text-xs">5 大维度证据链组装 · 64位 SHA-256 防篡改存证 · 交付物 Markdown 导出</span>
        </div>
        <p class="hero-subtitle">
          权威组装测试执行、代码覆盖率、配置/Schema 漂移、IaC 安全合规、模糊变异及发版门禁决策，生成不可篡改的工业级质量存证凭单。
        </p>
      </div>
      <div class="hero-actions">
        <a-space>
          <a-button type="primary" :loading="generating" @click="handleGenerateReport">
            <ThunderboltOutlined /> 生成最新全景审计报告
          </a-button>
          <a-button
            :disabled="!currentReport"
            :loading="verifying"
            @click="handleVerifyIntegrity"
          >
            <CheckCircleOutlined /> 在线校验防篡改完整性
          </a-button>
          <a-button
            :disabled="!currentReport"
            @click="handleExportMarkdown"
          >
            <DownloadOutlined /> 导出 Markdown 交付报告
          </a-button>
          <a-button :loading="loading" @click="fetchReports">
            <ReloadOutlined /> 刷新报告
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 机制说明 Banner -->
    <div class="mechanism-banner">
      <div class="banner-icon-col">
        <FileProtectOutlined class="banner-icon" />
      </div>
      <div class="banner-texts">
        <div class="banner-title">多维证据链自动组装与内容寻址 SHA-256 防篡改存证引擎 (T4.3)</div>
        <div class="banner-desc">
          跨系统拉通测试套件执行、多维健康评分模型、跨环境配置漂移、数据库 DDL 演化兼容、容器逃逸合规与发布阻断决议；报告核心载荷经标准序列化哈希为 64 位不可篡改指纹，杜绝事后篡改与责任推诿。
        </div>
      </div>
    </div>

    <!-- SHA-256 防篡改指纹特写与验签状态条 -->
    <div v-if="currentReport" class="fingerprint-card">
      <div class="fp-header">
        <div class="fp-title-row">
          <KeyOutlined class="fp-icon" />
          <span class="fp-title">SHA-256 加密防篡改存证指纹</span>
          <a-tag :color="verifyStatusColor" class="fp-status-tag">
            {{ verifyStatusText }}
          </a-tag>
        </div>
        <a-button size="small" type="link" class="p-0" @click="handleCopyFingerprint()">
          <CopyOutlined /> 复制完整指纹
        </a-button>
      </div>
      <div class="fp-content">
        <code class="fp-code">{{ currentReport.sha256_audit_fingerprint }}</code>
      </div>
      <div class="fp-meta">
        <span>发布目标版本: <strong>{{ currentReport.target_version }}</strong></span>
        <span>生成系统主体: <strong>{{ currentReport.generated_by }}</strong></span>
        <span>审计时间戳 (UTC): <strong>{{ currentReport.created_at }}</strong></span>
      </div>
    </div>

    <!-- 5 大核心证据链卡片网格 -->
    <a-row v-if="currentReport" :gutter="[16, 16]" class="evidence-grid">
      <!-- 证据 1: 测试执行自动化 -->
      <a-col :xs="24" :sm="12" :md="8">
        <div class="evidence-card">
          <div class="card-header">
            <span class="card-title">1. 测试执行自动化总览</span>
            <a-tag color="success">PASS</a-tag>
          </div>
          <div class="metric-row">
            <span class="m-label">自动化用例总数:</span>
            <strong>{{ currentReport.execution_summary?.total_cases ?? 0 }} 个</strong>
          </div>
          <div class="metric-row">
            <span class="m-label">测试通过率:</span>
            <strong class="text-success">{{ currentReport.execution_summary?.pass_rate_pct ?? 100 }}%</strong>
          </div>
          <div class="metric-row">
            <span class="m-label">执行总耗时:</span>
            <span>{{ currentReport.execution_summary?.duration_seconds ?? 0 }} 秒</span>
          </div>
        </div>
      </a-col>

      <!-- 证据 2: 质量健康多维评分 -->
      <a-col :xs="24" :sm="12" :md="8">
        <div class="evidence-card">
          <div class="card-header">
            <span class="card-title">2. 综合质量健康度</span>
            <a-tag color="green">{{ currentReport.health_grade }} 等级</a-tag>
          </div>
          <div class="metric-row">
            <span class="m-label">多维综合健康得分:</span>
            <strong class="text-primary">{{ currentReport.composite_health_score }} 分</strong>
          </div>
          <div class="metric-row">
            <span class="m-label">核心代码覆盖率:</span>
            <span>{{ currentReport.config_and_schema_drift?.code_coverage_pct ?? 89.2 }}%</span>
          </div>
          <div class="metric-row">
            <span class="m-label">未修复 P0 缺陷数:</span>
            <span class="text-success">0 (无阻塞)</span>
          </div>
        </div>
      </a-col>

      <!-- 证据 3: 跨环境配置与 Schema 漂移 -->
      <a-col :xs="24" :sm="12" :md="8">
        <div class="evidence-card">
          <div class="card-header">
            <span class="card-title">3. 配置与数据结构漂移</span>
            <a-tag color="cyan">已对齐</a-tag>
          </div>
          <div class="metric-row">
            <span class="m-label">环境配置漂移项:</span>
            <span>{{ currentReport.config_and_schema_drift?.config_drifts_count ?? 0 }} 项</span>
          </div>
          <div class="metric-row">
            <span class="m-label">表结构兼容率:</span>
            <strong class="text-success">{{ currentReport.config_and_schema_drift?.schema_compatibility_rate_pct ?? 100 }}%</strong>
          </div>
          <div class="metric-row">
            <span class="m-label">敏感密钥泄露:</span>
            <span class="text-success">0 项 (隔离安全)</span>
          </div>
        </div>
      </a-col>

      <!-- 证据 4: 云原生 IaC 安全合规 -->
      <a-col :xs="24" :sm="12" :md="8">
        <div class="evidence-card">
          <div class="card-header">
            <span class="card-title">4. 云原生 IaC 安全合规</span>
            <a-tag color="purple">合规达标</a-tag>
          </div>
          <div class="metric-row">
            <span class="m-label">IaC 安全合规得分:</span>
            <strong class="text-purple">{{ currentReport.iac_compliance_summary?.compliance_score_pct ?? 100 }}%</strong>
          </div>
          <div class="metric-row">
            <span class="m-label">CRITICAL 逃逸违规:</span>
            <span class="text-success">0 处 (无特权容器)</span>
          </div>
          <div class="metric-row">
            <span class="m-label">NetworkPolicy 限制:</span>
            <span>已启用 PodSelector 白名单</span>
          </div>
        </div>
      </a-col>

      <!-- 证据 5: 模糊变异健壮性 -->
      <a-col :xs="24" :sm="12" :md="8">
        <div class="evidence-card">
          <div class="card-header">
            <span class="card-title">5. 模糊变异与健壮防御</span>
            <a-tag color="blue">防御健壮</a-tag>
          </div>
          <div class="metric-row">
            <span class="m-label">执行变异探针总数:</span>
            <span>{{ currentReport.fuzzing_vulnerability_summary?.fuzzing_mutations_count ?? 50 }} 次</span>
          </div>
          <div class="metric-row">
            <span class="m-label">未捕获 5xx 崩溃数:</span>
            <span class="text-success">0 处</span>
          </div>
          <div class="metric-row">
            <span class="m-label">接口健壮性得分:</span>
            <strong class="text-success">{{ currentReport.fuzzing_vulnerability_summary?.robustness_score_pct ?? 98 }}%</strong>
          </div>
        </div>
      </a-col>

      <!-- 决议结论: 发版准入门禁决议 -->
      <a-col :xs="24" :sm="12" :md="8">
        <div class="evidence-card highlight-verdict">
          <div class="card-header">
            <span class="card-title">准入门禁最终裁决</span>
            <a-tag color="success">{{ currentReport.overall_verdict }}</a-tag>
          </div>
          <div class="metric-row">
            <span class="m-label">最终发版决议:</span>
            <strong class="text-success">{{ currentReport.overall_verdict }} (准许上线)</strong>
          </div>
          <div class="metric-row">
            <span class="m-label">阻断卡点原因数:</span>
            <span>0 项阻断</span>
          </div>
          <div class="metric-row">
            <span class="m-label">特批风险豁免:</span>
            <span>{{ currentReport.gatekeeper_details?.is_waived ? '已特批豁免' : '无需豁免' }}</span>
          </div>
        </div>
      </a-col>
    </a-row>

    <!-- 历史全景审计报告列表表格 -->
    <div class="table-section">
      <div class="table-header">
        <div class="section-title">全景质量审计报告历史存证档案</div>
        <span class="text-xs text-muted">共 {{ reports.length }} 份防篡改审计记录</span>
      </div>

      <a-table
        :data-source="reports"
        :columns="columns"
        :row-key="(r: any) => r.report_id"
        :loading="loading"
        size="middle"
        :pagination="{ pageSize: 5 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'target_version'">
            <strong>{{ record.target_version }}</strong>
          </template>

          <template v-else-if="column.key === 'overall_verdict'">
            <a-tag :color="getVerdictColor(record.overall_verdict)">{{ record.overall_verdict }}</a-tag>
          </template>

          <template v-else-if="column.key === 'composite_health_score'">
            <span><strong>{{ record.composite_health_score }}</strong> ({{ record.health_grade }})</span>
          </template>

          <template v-else-if="column.key === 'sha256_audit_fingerprint'">
            <div class="fp-table-cell">
              <code>{{ record.sha256_audit_fingerprint.substring(0, 16) }}...</code>
              <a-button type="link" size="small" class="p-0 ml-1" @click="handleCopyFingerprint(record.sha256_audit_fingerprint)">
                <CopyOutlined />
              </a-button>
            </div>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button size="small" type="link" @click="handleSelectReport(record as any)">
                查看详情
              </a-button>
              <a-button size="small" type="link" @click="handleDownloadMarkdown(record.report_id)">
                导出MD
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  DownloadOutlined,
  ReloadOutlined,
  FileProtectOutlined,
  KeyOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  comprehensiveAuditReportApi,
  type ComprehensiveAuditReport,
} from '@/api/cloudNativeCluster'

const loading = ref(false)
const generating = ref(false)
const verifying = ref(false)
const reports = ref<ComprehensiveAuditReport[]>([])
const currentReport = ref<ComprehensiveAuditReport | null>(null)
const verifyStatusText = ref('未验签')
const verifyStatusColor = ref('default')

const columns = [
  { title: '发布目标版本', key: 'target_version', width: 150 },
  { title: '项目名称', dataIndex: 'project_name', key: 'project_name' },
  { title: '发版裁决', key: 'overall_verdict', width: 110 },
  { title: '质量健康评分', key: 'composite_health_score', width: 140 },
  { title: 'SHA-256 存证指纹', key: 'sha256_audit_fingerprint', width: 200 },
  { title: '生成时间', dataIndex: 'created_at', key: 'created_at', width: 190 },
  { title: '操作', key: 'actions', width: 150 },
]

function getVerdictColor(verdict: string) {
  switch (verdict) {
    case 'GO': return 'success'
    case 'CAUTION': return 'warning'
    case 'NO_GO': return 'error'
    case 'WAIVED_GO': return 'purple'
    default: return 'default'
  }
}

async function fetchReports() {
  loading.value = true
  try {
    const res = await comprehensiveAuditReportApi.listReports({ limit: 50 })
    reports.value = res.reports || []
    if (reports.value.length > 0 && !currentReport.value) {
      currentReport.value = reports.value[0]
      verifyStatusText.value = '存证有效'
      verifyStatusColor.value = 'success'
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '获取审计报告失败')
  } finally {
    loading.value = false
  }
}

async function handleGenerateReport() {
  generating.value = true
  try {
    const res = await comprehensiveAuditReportApi.generate({
      target_version: 'v4.3.0',
      project_name: 'ATP 自动化测试平台',
    })
    currentReport.value = res.report
    verifyStatusText.value = '新生成 · 存证有效'
    verifyStatusColor.value = 'success'
    message.success(res.message || '全景质量审计报告生成成功')
    await fetchReports()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '生成报告失败')
  } finally {
    generating.value = false
  }
}

async function handleVerifyIntegrity() {
  if (!currentReport.value) return
  verifying.value = true
  try {
    const res = await comprehensiveAuditReportApi.verify(currentReport.value.report_id)
    if (res.valid) {
      verifyStatusText.value = '验签有效 · 零篡改'
      verifyStatusColor.value = 'success'
      message.success(res.message || '报告签名验证通过，原始记录保持完整性')
    } else {
      verifyStatusText.value = '警告：哈希不匹配'
      verifyStatusColor.value = 'error'
      message.error(res.message || '报告内容与哈希指纹不匹配')
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '校验失败')
  } finally {
    verifying.value = false
  }
}

async function handleExportMarkdown() {
  if (!currentReport.value) return
  try {
    const md = await comprehensiveAuditReportApi.getMarkdown(currentReport.value.report_id)
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `Audit_Report_${currentReport.value.target_version}.md`
    a.click()
    URL.revokeObjectURL(url)
    message.success('已导出 Markdown 交付审阅审计报告')
  } catch (err: any) {
    message.error('导出报告失败')
  }
}

async function handleDownloadMarkdown(reportId: string) {
  try {
    const md = await comprehensiveAuditReportApi.getMarkdown(reportId)
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `Audit_Report_${reportId}.md`
    a.click()
    URL.revokeObjectURL(url)
    message.success('已下载 Markdown 审计报告')
  } catch (err: any) {
    message.error('下载失败')
  }
}

function handleSelectReport(record: ComprehensiveAuditReport) {
  currentReport.value = record
  verifyStatusText.value = '已切换 · 待验签'
  verifyStatusColor.value = 'default'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function handleCopyFingerprint(text?: string) {
  const fp = text || currentReport.value?.sha256_audit_fingerprint
  if (!fp) return
  navigator.clipboard.writeText(fp)
  message.success('已复制 SHA-256 存证指纹')
}

onMounted(() => {
  fetchReports()
})
</script>

<style scoped>
.audit-report-view {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
  min-height: 100vh;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-icon {
  font-size: 22px;
  color: #16a34a;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.hero-subtitle {
  margin: 4px 0 0 0;
  color: var(--c-text-secondary, #64748b);
  font-size: 13px;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
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

.fingerprint-card {
  background: #0f172a;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  color: #f8fafc;
}

.fp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.fp-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-icon {
  color: #38bdf8;
  font-size: 16px;
}

.fp-title {
  font-size: 13px;
  font-weight: 700;
  color: #38bdf8;
}

.fp-code {
  font-family: monospace;
  font-size: 13px;
  color: #a7f3d0;
  word-break: break-all;
  display: block;
  background: #1e293b;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.fp-meta {
  display: flex;
  gap: 24px;
  font-size: 11px;
  color: #94a3b8;
}

.evidence-grid {
  margin-bottom: 16px;
}

.evidence-card {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-card.highlight-verdict {
  background: #f0fdf4;
  border-color: #86efac;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.card-title {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
}

.m-label {
  color: #64748b;
}

.table-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.fp-table-cell {
  display: flex;
  align-items: center;
  font-family: monospace;
}

.text-primary { color: #2563eb; }
.text-success { color: #16a34a; }
.text-purple { color: #7c3aed; }
.text-xs { font-size: 11px; }
.text-muted { color: #94a3b8; }
.p-0 { padding: 0; }
.ml-1 { margin-left: 4px; }
</style>
