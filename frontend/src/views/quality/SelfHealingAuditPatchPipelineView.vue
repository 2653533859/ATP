<template>
  <div class="page-shell self-healing-pipeline-view">
    <!-- 顶部导航与操作栏 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <SafetyCertificateOutlined class="hero-icon" />
          <h2 class="page-title">端到端测试自愈全流程审计追踪与一键回滚全景大盘</h2>
          <span class="live-dot" />
          <span class="muted-text text-xs">AI 自动化自愈四阶段流水线 · SHA-256 防篡改存证</span>
        </div>
        <p class="hero-subtitle">
          全链路可视自愈闭环：阶段 1 根因推导 → 阶段 2 补丁合成 → 阶段 3 沙箱试跑验证 → 阶段 4 防篡改审计存证与一键原子回滚。
        </p>
      </div>
      <div class="hero-actions">
        <a-space>
          <a-button type="primary" :loading="executing" @click="handleExecuteCurrent">
            <ThunderboltOutlined /> 触发四阶段自愈流水线
          </a-button>
          <a-button :loading="loading" @click="fetchReports">
            <ReloadOutlined /> 刷新审计大盘
          </a-button>
          <a-popconfirm title="确定清空所有自愈流水线审计记录吗？" @confirm="handleClearReports">
            <a-button danger :disabled="reports.length === 0">
              <DeleteOutlined /> 清空记录
            </a-button>
          </a-popconfirm>
        </a-space>
      </div>
    </header>

    <!-- 机制说明 Banner -->
    <div class="pipeline-banner">
      <div class="banner-stage-item">
        <span class="stage-badge stage-badge-1">STAGE 1</span>
        <div class="stage-info">
          <div class="stage-title">故障模式诊断</div>
          <div class="stage-desc">判定 UI 定位漂移 / API 响应格式裂变根因</div>
        </div>
      </div>
      <div class="stage-arrow">→</div>
      <div class="banner-stage-item">
        <span class="stage-badge stage-badge-2">STAGE 2</span>
        <div class="stage-info">
          <div class="stage-title">动态代码补丁合成</div>
          <div class="stage-desc">生成自适应选择器或 JSONPath 新断言</div>
        </div>
      </div>
      <div class="stage-arrow">→</div>
      <div class="banner-stage-item">
        <span class="stage-badge stage-badge-3">STAGE 3</span>
        <div class="stage-info">
          <div class="stage-title">隔离沙箱热试跑</div>
          <div class="stage-desc">零污染沙箱自动化双向回归，通过率 100% 卡点</div>
        </div>
      </div>
      <div class="stage-arrow">→</div>
      <div class="banner-stage-item">
        <span class="stage-badge stage-badge-4">STAGE 4</span>
        <div class="stage-info">
          <div class="stage-title">防篡改审计与原子生效</div>
          <div class="stage-desc">SHA-256 存证指纹、代码版本应用与一键原子回滚</div>
        </div>
      </div>
    </div>

    <!-- KPI 统计卡片 -->
    <a-row :gutter="[16, 16]" class="kpi-grid">
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">自愈流水线总执行数</div>
          <div class="stat-value text-primary">{{ reports.length }}</div>
          <div class="stat-trend">包含 UI 元素漂移与 API 断言裂变</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">自动生效成功率</div>
          <div class="stat-value text-success">{{ successRate }}%</div>
          <div class="stat-trend">沙箱试跑验证 100% 准入卡点</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">平均自愈耗时</div>
          <div class="stat-value text-warning">{{ avgDuration }} <span class="unit">ms</span></div>
          <div class="stat-trend">4 阶段端到端全流程耗时均值</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">已执行原子回滚数</div>
          <div class="stat-value text-danger">{{ rollbackCount }}</div>
          <div class="stat-trend">可审计无残留版本即时撤销</div>
        </div>
      </a-col>
    </a-row>

    <!-- 演练沙箱与最新自愈流水线报告 -->
    <div class="workbench-layout">
      <!-- 左侧：演练配置与触发控制台 -->
      <div class="trigger-panel">
        <div class="panel-header">
          <span class="panel-title"><ControlOutlined /> 端到端自愈演练触发器</span>
          <div class="preset-select">
            <span class="preset-label">场景预设:</span>
            <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
              <a-radio-button value="ui_locator">UI 定位漂移</a-radio-button>
              <a-radio-button value="api_envelope">API 外层包装</a-radio-button>
              <a-radio-button value="api_camel">API 驼峰演进</a-radio-button>
            </a-radio-group>
          </div>
        </div>

        <div class="form-body">
          <div class="form-item">
            <label class="form-label">待自愈用例 ID 与名称:</label>
            <div class="form-row">
              <a-input v-model:value="caseId" placeholder="用例 ID" class="case-id-input" />
              <a-input v-model:value="caseName" placeholder="用例名称" class="case-name-input" />
            </div>
          </div>

          <div class="form-item">
            <label class="form-label">控制台执行失败日志 / 异常堆栈:</label>
            <a-textarea v-model:value="consoleLogs" :rows="3" placeholder="异常日志" />
          </div>

          <div v-if="selectedPreset === 'ui_locator'" class="form-item">
            <label class="form-label">失效的原 UI 定位符 (Locator):</label>
            <a-input v-model:value="brokenLocator" placeholder="//button[@id='submit-btn']" />
          </div>

          <div v-else class="form-item">
            <label class="form-label">失效的 API 断言表达式:</label>
            <a-input v-model:value="originalAssertion" placeholder="$.order_id == 1001" />
          </div>

          <div class="form-item">
            <a-checkbox v-model:checked="autoApply">
              沙箱试跑通过后自动持久化应用补丁 (Auto-Apply)
            </a-checkbox>
          </div>

          <a-button type="primary" block :loading="executing" @click="handleExecuteCurrent">
            <ThunderboltOutlined /> 启动四阶段流水线自动化自愈
          </a-button>
        </div>
      </div>

      <!-- 右侧：最新流水线执行详情卡片 -->
      <div class="latest-report-panel">
        <div class="panel-header">
          <span class="panel-title"><FileProtectOutlined /> 最新自愈流水线执行态势</span>
          <a-tag v-if="latestReport?.is_applied" color="success">已持久化生效</a-tag>
          <a-tag v-else-if="latestReport?.is_rolled_back" color="error">已原子回滚</a-tag>
          <a-tag v-else color="warning">待审核 / 试跑中</a-tag>
        </div>

        <div v-if="latestReport" class="report-content">
          <!-- 四阶段动态时间轴 -->
          <div class="stages-timeline">
            <div
              v-for="st in latestReport.stages"
              :key="st.stage_index"
              class="timeline-step"
              :class="st.status === 'PASSED' ? 'step-success' : 'step-pending'"
            >
              <div class="step-num">{{ st.stage_index }}</div>
              <div class="step-content">
                <div class="step-title">{{ st.stage_name }}</div>
                <div class="step-meta">
                  <span>状态: <strong>{{ st.status }}</strong></span>
                  <span>耗时: <strong>{{ st.duration_ms }} ms</strong></span>
                </div>
                <div class="step-desc">{{ st.summary }}</div>
              </div>
            </div>

            <!-- SHA-256 存证指纹条目 -->
            <div class="fingerprint-box">
              <span class="fingerprint-label">SHA-256 防篡改审计存证指纹:</span>
              <code class="fingerprint-code">{{ latestReport.diff_sha256 }}</code>
              <a-button type="link" size="small" class="p-0" @click="handleCopy(latestReport.diff_sha256)">
                <CopyOutlined />
              </a-button>
            </div>
          </div>

          <!-- 补丁代码 Diff 框 -->
          <div class="code-diff-container">
            <div class="diff-header">
              <span>Python 自动化自愈脚本代码 Diff 变异补丁:</span>
              <a-space>
                <a-button size="small" @click="handleCopy(latestReport.patch_diff)">
                  <CopyOutlined /> 复制 Diff
                </a-button>
                <a-popconfirm
                  v-if="latestReport.is_applied && !latestReport.is_rolled_back"
                  title="确认原子级回滚此自愈补丁吗？这将撤销已应用的用例变更。"
                  @confirm="handleRollback(latestReport.pipeline_id)"
                >
                  <a-button size="small" danger :loading="rollingBackId === latestReport.pipeline_id">
                    <UndoOutlined /> 一键原子回滚
                  </a-button>
                </a-popconfirm>
              </a-space>
            </div>
            <pre class="diff-block"><code>{{ latestReport.patch_diff }}</code></pre>
          </div>
        </div>

        <div v-else class="empty-state">
          <a-empty description="暂无最新自愈流水线运行记录，请在左侧触发自愈演练" />
        </div>
      </div>
    </div>

    <!-- 历史自愈全流程审计存证大盘 (Audit Table) -->
    <div class="table-section">
      <div class="table-header">
        <span class="table-title"><AuditOutlined /> 自愈流水线历史防篡改审计与回滚日志</span>
        <span class="muted-text text-xs">共 {{ reports.length }} 条流水线存证</span>
      </div>

      <a-table
        :data-source="reports"
        :columns="columns"
        :row-key="(record: any) => record.pipeline_id"
        :loading="loading"
        :pagination="{ pageSize: 6, showTotal: (total: number) => `共 ${total} 条存证` }"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'pipeline_id'">
            <code class="pipeline-id-tag">{{ record.pipeline_id.substring(0, 16) }}...</code>
          </template>

          <template v-else-if="column.key === 'stages_progress'">
            <div class="stages-dots">
              <a-tooltip
                v-for="(st, idx) in record.stages"
                :key="st.stage_index"
                :title="`${st.stage_name}: ${st.status}`"
              >
                <span :class="st.status === 'PASSED' ? 'dot dot-success' : 'dot dot-warning'" />
                <span v-if="Number(idx) < record.stages.length - 1" class="dot-connector" />
              </a-tooltip>
            </div>
          </template>

          <template v-else-if="column.key === 'patch_type'">
            <a-tag :color="getPatchTypeColor(record.patch_type)">
              {{ record.patch_type }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'diff_sha256'">
            <div class="sha-cell">
              <code class="sha-text">{{ record.diff_sha256.substring(0, 12) }}...</code>
              <a-button type="link" size="small" class="p-0" @click="handleCopy(record.diff_sha256)">
                <CopyOutlined />
              </a-button>
            </div>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag v-if="record.is_rolled_back" color="error">已回滚 (ROLLED_BACK)</a-tag>
            <a-tag v-else-if="record.is_applied" color="success">已应用 (APPLIED)</a-tag>
            <a-tag v-else color="warning">未应用</a-tag>
          </template>

          <template v-else-if="column.key === 'total_duration_ms'">
            <span>{{ record.total_duration_ms }} ms</span>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button size="small" type="link" @click="handleInspect(record as any)">
                查看详情
              </a-button>
              <a-popconfirm
                v-if="record.is_applied && !record.is_rolled_back"
                title="确定对该补丁执行原子级版本回滚？"
                @confirm="handleRollback(record.pipeline_id)"
              >
                <a-button size="small" danger type="link" :loading="rollingBackId === record.pipeline_id">
                  原子回滚
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  DeleteOutlined,
  CopyOutlined,
  UndoOutlined,
  AuditOutlined,
  ControlOutlined,
  FileProtectOutlined,
} from '@ant-design/icons-vue'
import { selfHealingPipelineApi, type HealingAuditPipelineReport } from '@/api/testSelfHealing'

// 模拟场景预设
const PRESETS = {
  ui_locator: {
    case_id: 'case_ui_cart_button',
    case_name: '电商下单流程 UI 加购按钮定位自愈',
    console_logs: 'TimeoutError: locator("//button[@id=\'submit-btn\']") did not match any element in 10000ms',
    broken_locator: "//button[@id='submit-btn']",
    dom_candidates: [
      {
        candidate_id: 'cand_cart_active',
        tag_name: 'button',
        text_content: '立即结算',
        attributes: { id: 'checkout-submit-active', class: 'btn btn-primary' },
        bounding_box: { x: 100.0, y: 200.0, width: 80.0, height: 32.0 },
        xpath: "//button[@id='checkout-submit-active']",
      },
    ],
    original_assertion: '',
  },
  api_envelope: {
    case_id: 'case_api_order_create',
    case_name: '订单微服务 API 订单创建断言自愈',
    console_logs: "AssertionError: KeyError 'order_id' not found in response payload",
    broken_locator: '',
    dom_candidates: undefined,
    original_assertion: '$.order_id == 1001',
    http_status_code: 200,
    http_response_payload: {
      code: 0,
      message: 'success',
      data: {
        order_id: 1001,
        amount: 88.5,
        status: 'PAID',
      },
    },
  },
  api_camel: {
    case_id: 'case_api_user_profile',
    case_name: '用户微服务 API 用户详情断言规范自适应',
    console_logs: "AssertionError: key 'user_id' not found in response payload",
    broken_locator: '',
    dom_candidates: undefined,
    original_assertion: "response['user_id'] == 888",
    http_status_code: 200,
    http_response_payload: {
      userId: 888,
      nickname: 'Alex',
      role: 'Engineer',
    },
  },
}

const loading = ref(false)
const executing = ref(false)
const rollingBackId = ref<string | null>(null)
const reports = ref<HealingAuditPipelineReport[]>([])
const latestReport = ref<HealingAuditPipelineReport | null>(null)

// 演练表单响应式状态
const selectedPreset = ref<'ui_locator' | 'api_envelope' | 'api_camel'>('ui_locator')
const caseId = ref(PRESETS.ui_locator.case_id)
const caseName = ref(PRESETS.ui_locator.case_name)
const consoleLogs = ref(PRESETS.ui_locator.console_logs)
const brokenLocator = ref(PRESETS.ui_locator.broken_locator)
const originalAssertion = ref(PRESETS.ui_locator.original_assertion)
const autoApply = ref(true)

// KPI 统计
const successRate = computed(() => {
  if (reports.value.length === 0) return 100
  const appliedOrSuccess = reports.value.filter((r) => r.dry_run_verified && r.is_applied).length
  return Math.round((appliedOrSuccess / reports.value.length) * 100)
})

const avgDuration = computed(() => {
  if (reports.value.length === 0) return 0
  const sum = reports.value.reduce((acc, cur) => acc + (cur.total_duration_ms || 0), 0)
  return Math.round(sum / reports.value.length)
})

const rollbackCount = computed(() => {
  return reports.value.filter((r) => r.is_rolled_back).length
})

// 表格列配置
const columns = [
  { title: '流水线 ID', key: 'pipeline_id', dataIndex: 'pipeline_id', width: 140 },
  { title: '测试用例', dataIndex: 'case_name', key: 'case_name' },
  { title: '四阶段进度', key: 'stages_progress', width: 120 },
  { title: '补丁类型', key: 'patch_type', width: 150 },
  { title: 'SHA-256 存证指纹', key: 'diff_sha256', width: 160 },
  { title: '总耗时', key: 'total_duration_ms', width: 90 },
  { title: '生效状态', key: 'status', width: 130 },
  { title: '操作', key: 'actions', width: 150 },
]

function handlePresetChange(e: any) {
  const p = PRESETS[e.target.value as keyof typeof PRESETS]
  if (p) {
    caseId.value = p.case_id
    caseName.value = p.case_name
    consoleLogs.value = p.console_logs
    brokenLocator.value = p.broken_locator
    originalAssertion.value = p.original_assertion
  }
}

function getPatchTypeColor(type: string) {
  switch (type) {
    case 'LOCATOR_HEALING':
      return 'purple'
    case 'ENVELOPE_UNWRAP':
      return 'blue'
    case 'FIELD_RENAME':
      return 'cyan'
    default:
      return 'default'
  }
}

async function fetchReports() {
  loading.value = true
  try {
    const res = await selfHealingPipelineApi.listReports({ limit: 50 })
    reports.value = res.reports || []
    if (reports.value.length > 0 && !latestReport.value) {
      latestReport.value = reports.value[0]
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '获取流水线记录失败')
  } finally {
    loading.value = false
  }
}

async function handleExecuteCurrent() {
  executing.value = true
  try {
    const p = PRESETS[selectedPreset.value]
    const res = await selfHealingPipelineApi.execute({
      case_id: caseId.value,
      case_name: caseName.value,
      console_logs: consoleLogs.value,
      broken_locator: brokenLocator.value || undefined,
      dom_candidates: p.dom_candidates,
      original_assertion: originalAssertion.value || undefined,
      http_status_code: (p as any).http_status_code,
      http_response_payload: (p as any).http_response_payload,
      auto_apply: autoApply.value,
    })
    latestReport.value = res.report
    message.success(res.message || '四阶段自愈流水线执行完成')
    await fetchReports()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '自愈流水线执行失败')
  } finally {
    executing.value = false
  }
}

async function handleRollback(pipelineId: string) {
  rollingBackId.value = pipelineId
  try {
    const res = await selfHealingPipelineApi.rollback(pipelineId)
    message.success(res.message || '自愈补丁已安全原子回滚')
    await fetchReports()
    if (latestReport.value?.pipeline_id === pipelineId) {
      latestReport.value.is_rolled_back = true
      latestReport.value.is_applied = false
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '回滚失败')
  } finally {
    rollingBackId.value = null
  }
}

async function handleClearReports() {
  try {
    await selfHealingPipelineApi.clearReports()
    message.success('已清空所有自愈流水线记录')
    reports.value = []
    latestReport.value = null
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '清空失败')
  }
}

function handleInspect(record: HealingAuditPipelineReport) {
  latestReport.value = record
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function handleCopy(text: string) {
  if (!text) return
  navigator.clipboard.writeText(text)
  message.success('已复制到剪贴板')
}

onMounted(() => {
  fetchReports()
})
</script>

<style scoped>
.self-healing-pipeline-view {
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
  color: #10b981;
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

.pipeline-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 12px 18px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.banner-stage-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stage-badge {
  font-size: 11px;
  font-weight: 800;
  padding: 3px 6px;
  border-radius: 4px;
}

.stage-badge-1 { background: #fee2e2; color: #dc2626; }
.stage-badge-2 { background: #e0e7ff; color: #4338ca; }
.stage-badge-3 { background: #fef3c7; color: #d97706; }
.stage-badge-4 { background: #dcfce7; color: #15803d; }

.stage-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.stage-desc {
  font-size: 11px;
  color: #64748b;
}

.stage-arrow {
  color: #94a3b8;
  font-weight: bold;
}

.kpi-grid {
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
}

.stat-value {
  font-size: 24px;
  font-weight: 800;
  margin: 4px 0;
}

.stat-value .unit {
  font-size: 14px;
  font-weight: normal;
}

.stat-trend {
  font-size: 11px;
  color: #94a3b8;
}

.text-primary { color: #2563eb; }
.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-danger { color: #dc2626; }

.workbench-layout {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.trigger-panel,
.latest-report-panel {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.preset-select {
  display: flex;
  align-items: center;
  gap: 6px;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
}

.form-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.form-row {
  display: flex;
  gap: 8px;
}

.case-id-input {
  width: 130px;
}

.stages-timeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.timeline-step {
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.step-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #10b981;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
}

.step-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.step-meta {
  font-size: 11px;
  color: #475569;
  display: flex;
  gap: 12px;
  margin: 2px 0 4px 0;
}

.step-desc {
  font-size: 11px;
  color: #64748b;
}

.fingerprint-box {
  margin-top: 4px;
  background: #f1f5f9;
  padding: 8px 12px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.fingerprint-label {
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
}

.fingerprint-code {
  font-size: 11px;
  color: #0f172a;
  word-break: break-all;
  flex: 1;
}

.code-diff-container {
  background: #0f172a;
  border-radius: 6px;
  padding: 10px 14px;
  color: #f8fafc;
}

.diff-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 6px;
}

.diff-block {
  margin: 0;
  font-family: monospace;
  font-size: 11px;
  white-space: pre-wrap;
  color: #38bdf8;
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

.table-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.pipeline-id-tag {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.stages-dots {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot-success { background: #10b981; }
.dot-warning { background: #f59e0b; }

.dot-connector {
  width: 8px;
  height: 2px;
  background: #cbd5e1;
}

.sha-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sha-text {
  font-size: 11px;
  color: #475569;
}

.p-0 {
  padding: 0;
}
</style>
