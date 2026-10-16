<template>
  <a-modal
    :open="open"
    :width="840"
    title="企业级测试报告多模态聚合归档导出"
    :footer="null"
    destroy-on-close
    @cancel="handleClose"
  >
    <div class="report-bundler-modal">
      <!-- 头部介绍与合规标识 -->
      <div class="modal-banner">
        <div class="banner-left">
          <FileZipOutlined class="banner-icon" />
          <div>
            <div class="banner-title-row">
              <span class="banner-title">多模态测试报告归档引擎</span>
              <a-tag color="purple">ISO 27001 审计就绪</a-tag>
              <a-tag color="cyan">数字防伪印章</a-tag>
            </div>
            <p class="banner-desc">
              针对企业合规审计、跨部门汇报与离线质量归档需求，支持一键生成自包含 HTML5、明细表格、合规 PDF 或多合一 ZIP 包。
            </p>
          </div>
        </div>
      </div>

      <!-- 导出格式卡片选择区 (4 选 1) -->
      <div class="format-selection-section">
        <div class="section-label">选择归档与导出格式:</div>
        <div class="format-cards-grid">
          <div
            class="format-card"
            :class="{ 'format-card-selected': exportForm.format === 'html5' }"
            @click="exportForm.format = 'html5'"
          >
            <div class="format-header">
              <Html5Outlined class="format-icon text-orange" />
              <span class="format-ext">.html</span>
            </div>
            <div class="format-name">独立单文件 HTML5</div>
            <div class="format-desc">内置离线暗色现代样式与 ECharts，邮件直发即开即用。</div>
          </div>

          <div
            class="format-card"
            :class="{ 'format-card-selected': exportForm.format === 'excel_detailed' }"
            @click="exportForm.format = 'excel_detailed'"
          >
            <div class="format-header">
              <FileExcelOutlined class="format-icon text-green" />
              <span class="format-ext">.csv / .xlsx</span>
            </div>
            <div class="format-name">详细 Excel / CSV 表格</div>
            <div class="format-desc">UTF-8 BOM 编码，覆盖逐条用例执行流水、重试次数与耗时。</div>
          </div>

          <div
            class="format-card"
            :class="{ 'format-card-selected': exportForm.format === 'pdf_summary' }"
            @click="exportForm.format = 'pdf_summary'"
          >
            <div class="format-header">
              <FilePdfOutlined class="format-icon text-red" />
              <span class="format-ext">.pdf</span>
            </div>
            <div class="format-name">企业合规 PDF 凭证</div>
            <div class="format-desc">符合安全审计标准，附带防伪数字印章与 HMAC-SHA256 签名。</div>
          </div>

          <div
            class="format-card"
            :class="{ 'format-card-selected': exportForm.format === 'multi_modal_zip' }"
            @click="exportForm.format = 'multi_modal_zip'"
          >
            <div class="format-header">
              <FileZipOutlined class="format-icon text-blue" />
              <span class="format-ext">.zip</span>
            </div>
            <div class="format-name">多模态多合一 ZIP</div>
            <div class="format-desc">全景打包 HTML、CSV、PDF 与元数据 JSON，适合长期归档。</div>
          </div>
        </div>
      </div>

      <!-- 报告归档参数配置表单 -->
      <a-form layout="vertical" class="export-form">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="关联测试执行批次 (Run ID)" required>
              <a-input-number v-model:value="exportForm.run_id" :min="1" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="报告主标题" required>
              <a-input v-model:value="exportForm.title" placeholder="如: v3.5.0 全量自动化回归与质量验收凭据" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="所属业务项目名称" required>
              <a-input v-model:value="exportForm.project_name" placeholder="如: ATP-Platform" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="执行部署环境标识" required>
              <a-input v-model:value="exportForm.environment_name" placeholder="如: Production-Staging" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="6">
            <a-form-item label="用例总数">
              <a-input-number v-model:value="exportForm.total_cases" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="通过用例数">
              <a-input-number v-model:value="exportForm.passed_cases" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="失败用例数">
              <a-input-number v-model:value="exportForm.failed_cases" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="通过率 (%)">
              <a-input-number v-model:value="exportForm.pass_rate_pct" :min="0" :max="100" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="质量综合健康分 (0-100)">
              <a-input-number v-model:value="exportForm.quality_score" :min="0" :max="100" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="AI 智能自愈修复数">
              <a-input-number v-model:value="exportForm.healed_cases_count" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="防伪数字印章签名">
              <a-input v-model:value="exportForm.digital_seal_signature" placeholder="ISO-27001-ATP-SIG-VERIFIED" />
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 操作按钮与生成状态 -->
        <div class="form-actions-row">
          <a-button type="primary" size="large" :loading="exporting" @click="handleExportBundle">
            <CloudDownloadOutlined /> 开始多模态打包并生成产物
          </a-button>
          <a-button size="large" @click="handleClose">
            取消
          </a-button>
        </div>
      </a-form>

      <!-- 最新生成产物下载卡片 -->
      <div v-if="lastArtifact" class="generated-artifact-card">
        <div class="artifact-left">
          <CheckCircleFilled class="artifact-success-icon" />
          <div class="artifact-info">
            <div class="artifact-name">{{ lastArtifact.filename }}</div>
            <div class="artifact-meta">
              <span>体积: <strong>{{ formatBytes(lastArtifact.file_size_bytes) }}</strong></span>
              <span>格式: <code>{{ lastArtifact.format }}</code></span>
              <span>归档 ID: <code>{{ lastArtifact.bundle_id }}</code></span>
            </div>
          </div>
        </div>
        <div class="artifact-right">
          <a-button type="primary" :href="downloadUrl" target="_blank" download>
            <DownloadOutlined /> 立即下载归档文件
          </a-button>
        </div>
      </div>

      <!-- 历史导出记录列表 -->
      <div v-if="artifactsList.length > 0" class="history-artifacts-section">
        <div class="section-label">近期归档产物记录 (可再次下载):</div>
        <a-table
          :data-source="artifactsList"
          :columns="artifactColumns"
          row-key="bundle_id"
          size="small"
          :pagination="{ pageSize: 4 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'filename'">
              <span class="mono-text font-bold">{{ record.filename }}</span>
            </template>
            <template v-else-if="column.key === 'format'">
              <a-tag color="blue">{{ record.format }}</a-tag>
            </template>
            <template v-else-if="column.key === 'file_size_bytes'">
              <span class="mono-text">{{ formatBytes(record.file_size_bytes) }}</span>
            </template>
            <template v-else-if="column.key === 'created_at'">
              <small class="mono-text">{{ formatTime(record.created_at) }}</small>
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-button
                type="link"
                size="small"
                :href="`/api/v1/reporting/exports/download/${record.bundle_id}`"
                target="_blank"
                download
              >
                下载
              </a-button>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileZipOutlined,
  Html5Outlined,
  FileExcelOutlined,
  FilePdfOutlined,
  CloudDownloadOutlined,
  CheckCircleFilled,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import {
  reportBundlerApi,
  type ReportExportFormat,
  type ExportArtifactItem,
} from '@/api/reportBundler'

const props = withDefaults(
  defineProps<{
    open: boolean
    defaultRunId?: number
    defaultProjectName?: string
  }>(),
  {
    open: false,
    defaultRunId: 101,
    defaultProjectName: 'ATP-Platform',
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
}>()

const exporting = ref(false)
const lastArtifact = ref<ExportArtifactItem | null>(null)
const artifactsList = ref<ExportArtifactItem[]>([])

const exportForm = reactive({
  run_id: props.defaultRunId,
  title: 'v3.5.0 全量自动化回归与质量验收凭据',
  project_name: props.defaultProjectName,
  environment_name: 'Production-Staging',
  total_cases: 120,
  passed_cases: 116,
  failed_cases: 4,
  pass_rate_pct: 96.67,
  duration_sec: 142.5,
  format: 'multi_modal_zip' as ReportExportFormat,
  executed_by: 'ATP Cloud Native Worker',
  digital_seal_signature: 'ISO-27001-ATP-SIG-VERIFIED',
  quality_score: 94.5,
  healed_cases_count: 3,
})

const downloadUrl = computed(() => {
  if (!lastArtifact.value) return '#'
  return reportBundlerApi.getDownloadUrl(lastArtifact.value.bundle_id)
})

const artifactColumns = [
  { title: '产物文件名', key: 'filename' },
  { title: '格式', key: 'format', width: 140 },
  { title: '文件大小', key: 'file_size_bytes', width: 100 },
  { title: '归档时间', key: 'created_at', width: 150 },
  { title: '操作', key: 'actions', width: 80 },
]

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatTime(isoStr?: string): string {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    return `${d.getMonth() + 1}-${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return isoStr
  }
}

async function loadArtifacts() {
  try {
    const res = await reportBundlerApi.listArtifacts()
    artifactsList.value = res.artifacts || []
  } catch {
    // 忽略加载错误
  }
}

async function handleExportBundle() {
  exporting.value = true
  try {
    const res = await reportBundlerApi.exportBundle(exportForm)
    message.success(res.message || '多模态报告打包生成成功')
    lastArtifact.value = res.artifact
    await loadArtifacts()
  } catch (err: any) {
    message.error(`报告打包失败: ${err.message || err}`)
  } finally {
    exporting.value = false
  }
}

function handleClose() {
  emit('update:open', false)
  emit('close')
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      loadArtifacts()
    }
  }
)

onMounted(() => {
  if (props.open) {
    loadArtifacts()
  }
})
</script>

<style scoped>
.report-bundler-modal {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.banner-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.banner-icon {
  font-size: 24px;
  color: #6366f1;
  margin-top: 2px;
}

.banner-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.banner-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 8px;
}

/* 4 格式选择卡片 */
.format-cards-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.format-card {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
}

.format-card:hover {
  border-color: #6366f1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.format-card-selected {
  border-color: #6366f1;
  background: #eff6ff;
  box-shadow: 0 0 0 1px #6366f1;
}

.format-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.format-icon {
  font-size: 18px;
}

.format-ext {
  font-family: monospace;
  font-size: 10px;
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
  color: #64748b;
}

.format-name {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.format-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

.text-orange {
  color: #ea580c;
}

.text-green {
  color: #16a34a;
}

.text-red {
  color: #dc2626;
}

.text-blue {
  color: #2563eb;
}

.export-form {
  margin-top: 4px;
}

.form-actions-row {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

/* 产物下载卡片 */
.generated-artifact-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  border-radius: 8px;
}

.artifact-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.artifact-success-icon {
  font-size: 24px;
  color: #10b981;
}

.artifact-name {
  font-family: monospace;
  font-size: 13px;
  font-weight: 700;
  color: #065f46;
}

.artifact-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #047857;
  margin-top: 2px;
}

.history-artifacts-section {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}

.font-bold {
  font-weight: 700;
}
</style>
