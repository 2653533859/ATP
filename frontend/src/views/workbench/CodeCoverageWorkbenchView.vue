<template>
  <div class="page-shell code-coverage-workbench-view">
    <!-- 1. 顶部页头 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <CodeOutlined class="hero-icon text-primary" />
          <h2 class="page-title">全链路代码覆盖率动态染色与增量发布准入中台</h2>
          <span class="live-dot" />
          <a-tag color="cyan">v5.9.0 动态代码染色在线</a-tag>
        </div>
        <p class="page-subtitle">
          支持 Coverage.py / JaCoCo / LCOV 多源覆盖率融合、Git Diff 增量代码行与分支染色计算、高危分支挖掘与自动化补测中枢
        </p>
      </div>

      <div class="hero-right">
        <a-space>
          <a-button type="primary" @click="openStainingDrawer(selectedFile)">
            <template #icon><EyeOutlined /></template>
            源码逐行染色透视
          </a-button>

          <a-button @click="openConfigModal">
            <template #icon><SafetyCertificateOutlined /></template>
            发布门禁与补测中枢
          </a-button>

          <a-button :loading="loading" @click="fetchData">
            <template #icon><ReloadOutlined /></template>
            刷新覆盖率指标
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 2. 4 大 Bento KPI 卡片 -->
    <div class="bento-kpi-grid">
      <!-- KPI 1 -->
      <div class="bento-card kpi-success">
        <div class="kpi-header">
          <span class="kpi-title">增量代码行覆盖率 (Diff Line)</span>
          <CheckCircleOutlined class="kpi-icon text-success" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-success font-mono">88.5%</span>
          <span class="kpi-trend text-success font-mono">≥ 85.0% 达标</span>
        </div>
        <div class="kpi-footer font-mono">
          本次变更执行: 115 / 130 可执行行
        </div>
      </div>

      <!-- KPI 2 -->
      <div class="bento-card kpi-primary">
        <div class="kpi-header">
          <span class="kpi-title">增量条件分支覆盖率 (Branch)</span>
          <BranchesOutlined class="kpi-icon text-primary" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-primary font-mono">82.0%</span>
          <span class="kpi-sub text-success font-mono">≥ 70.0% 门槛</span>
        </div>
        <div class="kpi-footer font-mono">
          分支双向走通: 41 / 50 条件分支
        </div>
      </div>

      <!-- KPI 3 -->
      <div class="bento-card kpi-cyan">
        <div class="kpi-header">
          <span class="kpi-title">发布门禁准入裁决</span>
          <SafetyCertificateOutlined class="kpi-icon text-cyan" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-cyan">PASSED</span>
          <span class="kpi-badge">准予合并发布</span>
        </div>
        <div class="kpi-footer font-mono">
          CI/CD 准入卡点: 无任何 P0 漏测违规
        </div>
      </div>

      <!-- KPI 4 -->
      <div class="bento-card kpi-purple">
        <div class="kpi-header">
          <span class="kpi-title">未覆盖高危分支数 (P0)</span>
          <AuditOutlined class="kpi-icon text-purple" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-purple font-mono">0 处</span>
          <span class="kpi-trend text-success font-mono">零资损安全防线</span>
        </div>
        <div class="kpi-footer font-mono">
          资金结算与鉴权拦截已全量测试闭环
        </div>
      </div>
    </div>

    <!-- 3. 源码文件覆盖率与增量染色流水大盘表 -->
    <a-card class="coverage-table-card mt-4" title="变更文件增量代码覆盖率大盘 (Changed Files Coverage)">
      <template #extra>
        <a-space>
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="按文件路径检索..."
            style="width: 240px;"
            size="small"
            @search="handleSearch"
          />
          <a-tag color="blue">变更源码数: {{ filteredFiles.length }}</a-tag>
        </a-space>
      </template>

      <a-table
        :data-source="filteredFiles"
        :columns="tableColumns"
        :pagination="false"
        row-key="file_path"
        size="middle"
        class="coverage-files-table font-mono"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'file_path'">
            <a class="file-link font-bold text-primary" @click="openStainingDrawer(record)">
              {{ record.file_path }}
            </a>
          </template>

          <template v-else-if="column.key === 'diff_line_coverage'">
            <div class="cov-bar-box">
              <span class="font-bold" :class="record.diff_line_coverage_pct >= 85 ? 'text-success' : 'text-danger'">
                {{ record.diff_line_coverage_pct }}%
              </span>
              <a-progress
                :percent="record.diff_line_coverage_pct"
                :status="record.diff_line_coverage_pct >= 85 ? 'success' : 'exception'"
                size="small"
                :show-info="false"
                style="width: 100px;"
              />
            </div>
          </template>

          <template v-else-if="column.key === 'diff_branch_coverage'">
            <span :class="record.diff_branch_coverage_pct >= 70 ? 'text-primary' : 'text-warning'">
              {{ record.diff_branch_coverage_pct }}%
            </span>
          </template>

          <template v-else-if="column.key === 'lines_stat'">
            <span>{{ record.covered_lines }} / {{ record.total_lines }} 行</span>
          </template>

          <template v-else-if="column.key === 'uncovered_lines'">
            <a-space v-if="record.uncovered_lines.length > 0" size="small" wrap>
              <a-tag
                v-for="ln in record.uncovered_lines"
                :key="ln"
                color="red"
                class="cursor-pointer"
                @click="openStainingDrawer(record, ln)"
              >
                Line {{ ln }}
              </a-tag>
            </a-space>
            <span v-else class="text-success">全覆盖</span>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space size="small">
              <a-button size="small" type="link" @click="openStainingDrawer(record)">
                逐行染色
              </a-button>
              <a-button size="small" type="link" @click="openConfigModal">
                门禁配置
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 4. 联动组件: 源码逐行染色抽屉 (UI3.1) -->
    <CoverageSourceStainingDrawer
      v-model:open="stainingDrawerOpen"
      :file-path="selectedFile?.file_path"
      :diff-line-coverage-pct="selectedFile?.diff_line_coverage_pct"
      @requestSynthesizeTest="handleSynthesizeFromLine"
    />

    <!-- 5. 联动组件: 增量门禁配置与补测弹窗 (UI3.2) -->
    <CoverageGateConfigModal
      v-model:open="configModalOpen"
      @save="handleSaveGatePolicy"
      @exportCases="handleExportCases"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  CodeOutlined,
  EyeOutlined,
  SafetyCertificateOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  BranchesOutlined,
  AuditOutlined,
} from '@ant-design/icons-vue'
import CoverageSourceStainingDrawer from './components/CoverageSourceStainingDrawer.vue'
import CoverageGateConfigModal, { type IncrementalCoverageGatePolicy } from './components/CoverageGateConfigModal.vue'

interface ChangedFileCoverageItem {
  file_path: string
  diff_line_coverage_pct: number
  diff_branch_coverage_pct: number
  covered_lines: number
  total_lines: number
  uncovered_lines: number[]
}

const loading = ref(false)
const searchKeyword = ref('')
const stainingDrawerOpen = ref(false)
const configModalOpen = ref(false)

const filesList = ref<ChangedFileCoverageItem[]>([
  {
    file_path: 'backend/app/services/payment.py',
    diff_line_coverage_pct: 90.0,
    diff_branch_coverage_pct: 75.0,
    covered_lines: 9,
    total_lines: 10,
    uncovered_lines: [8],
  },
  {
    file_path: 'backend/app/services/order.py',
    diff_line_coverage_pct: 100.0,
    diff_branch_coverage_pct: 100.0,
    covered_lines: 8,
    total_lines: 8,
    uncovered_lines: [],
  },
  {
    file_path: 'backend/app/services/auth.py',
    diff_line_coverage_pct: 85.7,
    diff_branch_coverage_pct: 80.0,
    covered_lines: 12,
    total_lines: 14,
    uncovered_lines: [11, 12],
  },
  {
    file_path: 'frontend/src/views/workbench/CodeCoverageWorkbenchView.vue',
    diff_line_coverage_pct: 94.2,
    diff_branch_coverage_pct: 88.0,
    covered_lines: 49,
    total_lines: 52,
    uncovered_lines: [35],
  },
])

const selectedFile = ref<ChangedFileCoverageItem>(filesList.value[0])

const tableColumns = [
  { title: '源码文件路径', dataIndex: 'file_path', key: 'file_path', width: 340 },
  { title: '增量代码行覆盖率', key: 'diff_line_coverage', width: 200 },
  { title: '增量分支覆盖率', key: 'diff_branch_coverage', width: 140 },
  { title: '变更代码行覆盖统计', key: 'lines_stat', width: 180 },
  { title: '未覆盖红色行定位', key: 'uncovered_lines' },
  { title: '快捷操作', key: 'actions', width: 160 },
]

const filteredFiles = computed(() => {
  if (!searchKeyword.value.trim()) return filesList.value
  const kw = searchKeyword.value.trim().toLowerCase()
  return filesList.value.filter((f) => f.file_path.toLowerCase().includes(kw))
})

function openStainingDrawer(fileItem?: any, _targetLine?: number) {
  if (fileItem) {
    selectedFile.value = fileItem
  }
  stainingDrawerOpen.value = true
}

function openConfigModal() {
  configModalOpen.value = true
}

function fetchData() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
  }, 400)
}

function handleSearch() {
  // filteredFiles handles filter
}

function handleSynthesizeFromLine(_ln: number) {
  openConfigModal()
}

function handleSaveGatePolicy(_policy: IncrementalCoverageGatePolicy) {
  // policy saved
}

function handleExportCases(_cases: any[]) {
  // export dispatched
}
</script>

<style scoped>
.code-coverage-workbench-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 18px 24px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #f0f0f0);
  border-radius: 8px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 22px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--c-text-secondary, #666);
}

.bento-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.bento-card {
  padding: 16px;
  border-radius: 8px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #f0f0f0);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.2s ease;
}

.bento-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--c-border-strong, #d9d9d9);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kpi-title {
  font-size: 13px;
  color: var(--c-text-secondary, #666);
}

.kpi-icon {
  font-size: 18px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 12px 0 8px;
}

.kpi-number {
  font-size: 26px;
  font-weight: 700;
}

.kpi-trend,
.kpi-sub {
  font-size: 12px;
}

.kpi-badge {
  font-size: 11px;
  padding: 2px 6px;
  background: #e6fffb;
  border: 1px solid #87e8de;
  color: #13c2c2;
  border-radius: 4px;
}

.kpi-footer {
  font-size: 11px;
  color: var(--c-text-tertiary, #999);
}

.cov-bar-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mt-4 {
  margin-top: 16px;
}

.text-danger {
  color: #ff4d4f;
}

.text-success {
  color: #52c41a;
}

.text-warning {
  color: #faad14;
}

.text-primary {
  color: #1677ff;
}

.text-cyan {
  color: #13c2c2;
}

.text-purple {
  color: #722ed1;
}

.cursor-pointer {
  cursor: pointer;
}

@media (max-width: 1024px) {
  .bento-kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .bento-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
