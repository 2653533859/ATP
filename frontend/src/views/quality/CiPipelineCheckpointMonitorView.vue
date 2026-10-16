<template>
  <div class="page-shell ci-pipeline-checkpoint-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <DashboardOutlined class="hero-icon" />
          <h2 class="page-title">CI/CD 流水线 Checkpoint 检查点全景监控看板</h2>
        </div>
        <p class="page-subtitle">
          端到端串联「AST 语法差异提取 → 精准测试推荐 → 变更风险多维评分 → 偶发抖动抑制 → 全要素质量门禁」全流程，输出标准 Exit Code (0/1/2) 与高保真终端控制台日志。
        </p>
      </div>

      <div class="hero-actions">
        <a-space size="small">
          <a-button :loading="loading" size="small" @click="loadInitialData">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" @click="applyPreset('passed')">
            预设: 门禁全通 (Code 0)
          </a-button>
          <a-button size="small" @click="applyPreset('blocked')">
            预设: 变异分不足阻断 (Code 1)
          </a-button>
          <a-button size="small" @click="applyPreset('warning')">
            预设: 高危双签告警 (Code 2)
          </a-button>
          <a-button type="primary" size="small" @click="showRunModal = true">
            <PlayCircleOutlined /> 运行端到端检查点
          </a-button>
        </a-space>
      </div>
    </header>

    <a-spin :spinning="loading">
      <template v-if="currentReport">
        <!-- 核心退出码与流水线准入大横幅 -->
        <div class="verdict-banner" :class="`banner-code-${currentReport.exit_code}`">
          <div class="exit-code-badge-box">
            <span class="code-title">EXIT CODE</span>
            <span class="code-number">{{ currentReport.exit_code }}</span>
            <span class="code-status">{{ getExitCodeLabel(currentReport.exit_code) }}</span>
          </div>

          <div class="verdict-info-box">
            <div class="verdict-title-line">
              <span class="verdict-headline">
                {{ getExitCodeHeadline(currentReport.exit_code) }}
              </span>
              <a-tag :color="getOverallStatusColor(currentReport.overall_status)" class="status-tag">
                {{ currentReport.overall_status }}
              </a-tag>
            </div>

            <div class="pipeline-meta-row">
              <span class="meta-item">流水线: <strong>{{ currentReport.pipeline_name }}</strong></span>
              <span class="meta-item">PR 编号: <code>{{ currentReport.pr_id }}</code></span>
              <span class="meta-item">Commit: <code>{{ currentReport.commit_sha.slice(0, 7) }}</code></span>
              <span class="meta-item">总阶段数: 4 个阶段</span>
              <span class="meta-item">执行总耗时: {{ totalDurationMs }} ms</span>
            </div>

            <!-- 整改摘要 -->
            <div v-if="currentReport.remediation_summary.length > 0" class="remediation-summary-box">
              <span class="rem-title text-danger">⚠️ 流水线卡点阻断/告警原因:</span>
              <span class="rem-desc">{{ currentReport.remediation_summary.join('；') }}</span>
            </div>
            <div v-else class="remediation-summary-box">
              <span class="rem-title text-success">✓ 全阶段校验通过:</span>
              <span class="rem-desc text-success">无阻断项，流水线准许放行并继续部署！</span>
            </div>
          </div>
        </div>

        <!-- 四阶段端到端执行卡点流 (4-Stage Pipeline Flow) -->
        <div class="stages-section">
          <div class="section-heading">
            <span class="heading-title">流水线端到端四阶段卡点执行拓扑 (Pipeline Stages)</span>
            <span class="heading-sub">顺序流经 4 个卡点，任何阶段阻断均将拦截后续发布</span>
          </div>

          <div class="stages-grid">
            <div
              v-for="(stage, idx) in currentReport.stages"
              :key="stage.stage_name"
              class="stage-card"
              :class="`stage-${stage.status.toLowerCase()}`"
            >
              <div class="stage-top">
                <span class="stage-index">Stage {{ idx + 1 }}</span>
                <a-tag :color="getStageTagColor(stage.status)" size="small">
                  <component :is="getStageStatusIcon(stage.status)" />
                  <span style="margin-left: 4px">{{ stage.status }}</span>
                </a-tag>
                <span class="stage-duration">{{ stage.duration_ms }} ms</span>
              </div>

              <div class="stage-name">{{ stage.stage_name }}</div>
              <p class="stage-summary">{{ stage.summary }}</p>

              <!-- 阶段明细指标微卡片 -->
              <div v-if="stage.details" class="stage-details-box">
                <div v-for="(v, k) in stage.details" :key="k" class="detail-row">
                  <span class="detail-k">{{ formatKey(String(k)) }}:</span>
                  <span class="detail-v">{{ v }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 终端控制台日志输出查看器 -->
        <div class="console-log-panel">
          <div class="console-header">
            <div class="console-left">
              <CodeOutlined class="terminal-icon" />
              <span class="console-title">CI 检查点高对比度终端控制台输出 (Console Log Output)</span>
              <a-tag color="black" size="small">ANSI Terminal</a-tag>
            </div>
            <div class="console-right">
              <a-space size="small">
                <a-button size="small" type="text" class="console-btn" @click="copyConsoleLog">
                  <CopyOutlined /> 复制控制台日志
                </a-button>
                <a-button size="small" type="text" class="console-btn" @click="scrollToBottom">
                  <DownOutlined /> 滚至底部
                </a-button>
              </a-space>
            </div>
          </div>

          <pre ref="terminalRef" class="terminal-window"><code>{{ currentReport.console_log_output }}</code></pre>
        </div>
      </template>

      <div v-else class="empty-placeholder">
        <a-empty description="暂无检查点执行报告，请点击右上角运行端到端检查点" />
      </div>
    </a-spin>

    <!-- 运行端到端检查点模态框 -->
    <a-modal
      v-model:open="showRunModal"
      title="触发端到端 CI 流水线检查点"
      width="680px"
      @ok="handleRunSubmit"
    >
      <a-form layout="vertical">
        <a-form-item label="流水线作业名称:">
          <a-input v-model:value="runForm.pipeline_name" />
        </a-form-item>
        <a-form-item label="PR 编号与 Commit SHA:">
          <a-space>
            <a-input v-model:value="runForm.pr_id" placeholder="#1024" style="width: 140px" />
            <a-input v-model:value="runForm.commit_sha" placeholder="commit sha" style="width: 200px" />
          </a-space>
        </a-form-item>
        <a-form-item label="测试用例推荐策略:">
          <a-select v-model:value="runForm.selection_strategy" style="width: 200px">
            <a-select-option value="minimal">极小推荐 (Minimal)</a-select-option>
            <a-select-option value="balanced">均衡推荐 (Balanced)</a-select-option>
            <a-select-option value="comprehensive">全量保障 (Comprehensive)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="输入 Git Unified Diff 补丁:">
          <a-textarea
            v-model:value="runForm.diff_text"
            :rows="6"
            class="diff-input"
            placeholder="diff --git a/backend/main.py b/backend/main.py..."
          />
        </a-form-item>
        <a-form-item label="模拟参数:">
          <a-space size="large">
            <span>通过率: <a-input-number v-model:value="runForm.mock_test_pass_rate_pct" :min="0" :max="100" style="width: 80px" />%</span>
            <span>变异分: <a-input-number v-model:value="runForm.mutation_score_pct" :min="0" :max="100" style="width: 80px" />%</span>
            <span>高危双签: <a-switch v-model:checked="runForm.has_dual_approvals" /></span>
          </a-space>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  DashboardOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  CodeOutlined,
  CopyOutlined,
  DownOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type CheckpointExecutionReport,
  type PipelineStageStatus,
} from '@/api/ciImpact'

const loading = ref(false)
const showRunModal = ref(false)
const terminalRef = ref<HTMLPreElement | null>(null)

const currentReport = ref<CheckpointExecutionReport | null>(null)

const runForm = reactive({
  pipeline_name: 'CI-Pipeline-Worker',
  commit_sha: 'a1b2c3d4e5f',
  pr_id: '#1024',
  diff_text: `diff --git a/backend/app/services/discount.py b/backend/app/services/discount.py
--- a/backend/app/services/discount.py
+++ b/backend/app/services/discount.py
@@ -1,3 +1,3 @@
 def calculate_discount(price: float) -> float:
-    return price * 0.10
+    return price * 0.20
`,
  selection_strategy: 'balanced',
  mock_test_pass_rate_pct: 100.0,
  mock_test_failed_cases_count: 0,
  mutation_score_pct: 85.0,
  has_dual_approvals: true,
})

// 预设样例数据
const PRESET_PASSED: CheckpointExecutionReport = {
  checkpoint_id: 'chk_demo_pass_001',
  pipeline_name: 'CI-Pipeline-Worker',
  commit_sha: 'a1b2c3d4e5f',
  pr_id: '#1024',
  exit_code: 0,
  overall_status: 'PASSED',
  stages: [
    {
      stage_name: 'Stage 1: AST 差异提取与测试智能推荐',
      status: 'PASSED',
      duration_ms: 12.3,
      summary: '从 Git Diff 提取到 2 个类与 3 个方法，智能推荐 8 个关键测试用例 (节省 80% 运行时间)',
      details: { changed_files: 1, modified_methods: 3, selected_cases: 8 },
    },
    {
      stage_name: 'Stage 2: 变更风险多维评分',
      status: 'PASSED',
      duration_ms: 8.5,
      summary: '综合变更体量、圈复杂度与敏感度得分评定为 LOW 低危变更',
      details: { risk_level: 'LOW', overall_score: 24.5 },
    },
    {
      stage_name: 'Stage 3: 偶发抖动测试集抑制过滤',
      status: 'PASSED',
      duration_ms: 5.2,
      summary: '检出 1 个中度抖动用例，已自动附加退避重试；0 个隔离用例',
      details: { total_cases: 8, retried: 1, quarantined: 0 },
    },
    {
      stage_name: 'Stage 4: PR 全要素质量门禁裁决',
      status: 'PASSED',
      duration_ms: 6.8,
      summary: '单测通过率 100%, 变异得分 85.0%, 无违规硬门禁，裁决通过放行 (MERGE_APPROVED)',
      details: { pass_rate: '100%', mutation_score: '85%', verdict: 'MERGE_APPROVED' },
    },
  ],
  remediation_summary: [],
  console_log_output: `================================================================================
>>> [ATP CI Checkpoint] 开始执行端到端四阶段质量门禁检查点
>>> Pipeline: CI-Pipeline-Worker | Commit: a1b2c3d | PR: #1024
================================================================================
[STAGE 1/4] Git Diff AST 语法树语义解析与用例智能推荐...
  -> 变更解析: discount.py (+1, -1)
  -> 提取符号: calculate_discount (FunctionDef)
  -> TIA 推荐策略: balanced
  -> 命中候选测试用例: 8 个 (用时 12.30ms) [PASSED]

[STAGE 2/4] 代码变更三维风险多维打分 (Volume + Complexity + Criticality)...
  -> 风险得分: 24.50 / 100 (LOW) [PASSED]

[STAGE 3/4] Flaky 抖动用例自适应抑制过滤...
  -> 评估候选用例: 8 个, 稳固通过: 7 个, 附加重试: 1 个, 隔离观察: 0 个 [PASSED]

[STAGE 4/4] CI/CD PR 全要素质量门禁裁决...
  -> 单元测试通过率: 100.0% (阈值: >= 100.0%) [OK]
  -> 代码变异测试充分性得分: 85.0% (阈值: >= 70.0%) [OK]
  -> 变更审批合规性: LOW 风险级别, 无需双人同行审批 [OK]
  -> 最终门禁裁决: MERGE_APPROVED (准入通过)

================================================================================
[ATP CI Checkpoint] 流水线执行成功！所有质量与安全门禁全部放行！
[EXIT CODE]: 0 (SUCCESS)
================================================================================`,
  executed_at: '2026-10-16T15:00:00Z',
}

const PRESET_BLOCKED: CheckpointExecutionReport = {
  checkpoint_id: 'chk_demo_block_002',
  pipeline_name: 'CI-Pipeline-Worker',
  commit_sha: 'c3d4e5f6a7b',
  pr_id: '#1025',
  exit_code: 1,
  overall_status: 'BLOCKED',
  stages: [
    {
      stage_name: 'Stage 1: AST 差异提取与测试智能推荐',
      status: 'PASSED',
      duration_ms: 14.1,
      summary: '完成差异提取与用例推荐',
      details: { changed_files: 2, selected_cases: 12 },
    },
    {
      stage_name: 'Stage 2: 变更风险多维评分',
      status: 'PASSED',
      duration_ms: 9.3,
      summary: '风险评级为 MEDIUM 中危变更',
      details: { risk_level: 'MEDIUM', overall_score: 45.0 },
    },
    {
      stage_name: 'Stage 3: 偶发抖动测试集抑制过滤',
      status: 'PASSED',
      duration_ms: 4.8,
      summary: '完成抖动过滤',
      details: { total_cases: 12, quarantined: 0 },
    },
    {
      stage_name: 'Stage 4: PR 全要素质量门禁裁决',
      status: 'BLOCKED',
      duration_ms: 8.2,
      summary: '代码变异得分 50.0% 严重低于 70.0% 门禁线，存活变异体过多，阻断合流',
      details: { pass_rate: '100%', mutation_score: '50.0%', verdict: 'MERGE_BLOCKED' },
    },
  ],
  remediation_summary: [
    '代码变异得分 50.0% 低于硬性门禁阈值 70.0% (存在严重断言盲区)',
    '针对存活的一阶语法变异体补充针对性断言，重新运行使得分 ≥ 70%',
  ],
  console_log_output: `================================================================================
>>> [ATP CI Checkpoint] 开始执行端到端四阶段质量门禁检查点
>>> Pipeline: CI-Pipeline-Worker | Commit: c3d4e5f | PR: #1025
================================================================================
[STAGE 1/4] Git Diff AST 语法树语义解析与用例智能推荐... [PASSED]
[STAGE 2/4] 代码变更三维风险多维打分... [PASSED]
[STAGE 3/4] Flaky 抖动用例自适应抑制过滤... [PASSED]
[STAGE 4/4] CI/CD PR 全要素质量门禁裁决...
  -> 单元测试通过率: 100.0% [OK]
  -> 代码变异测试充分性得分: 50.0% (阈值: >= 70.0%) [FAILED]
  -> 最终门禁裁决: MERGE_BLOCKED (阻断合流)

[ERROR] 检测到硬性阻断规则违规，流水线立即中断并退出！
================================================================================
[EXIT CODE]: 1 (BLOCKED / FAILURE)
================================================================================`,
  executed_at: '2026-10-16T15:05:00Z',
}

const PRESET_WARNING: CheckpointExecutionReport = {
  checkpoint_id: 'chk_demo_warn_003',
  pipeline_name: 'CI-Pipeline-Worker',
  commit_sha: 'e5f6a7b8c9d',
  pr_id: '#1026',
  exit_code: 2,
  overall_status: 'WARNING',
  stages: [
    {
      stage_name: 'Stage 1: AST 差异提取与测试智能推荐',
      status: 'PASSED',
      duration_ms: 11.8,
      summary: '完成差异解析',
      details: { changed_files: 1, selected_cases: 6 },
    },
    {
      stage_name: 'Stage 2: 变更风险多维评分',
      status: 'WARNING',
      duration_ms: 12.0,
      summary: '变更命中认证涉密模块，评定为 CRITICAL 极高危变更',
      details: { risk_level: 'CRITICAL', overall_score: 85.0 },
    },
    {
      stage_name: 'Stage 3: 偶发抖动测试集抑制过滤',
      status: 'PASSED',
      duration_ms: 4.5,
      summary: '抖动过滤通过',
      details: { total_cases: 6, quarantined: 0 },
    },
    {
      stage_name: 'Stage 4: PR 全要素质量门禁裁决',
      status: 'WARNING',
      duration_ms: 7.2,
      summary: '单测与变异分达标，但 CRITICAL 变更缺少双人审批签字 (CONDITIONAL_PASS)',
      details: { verdict: 'CONDITIONAL_PASS', dual_approvals: false },
    },
  ],
  remediation_summary: [
    '变更风险评定为 CRITICAL 极高危，缺少双人同行专家审批签字',
  ],
  console_log_output: `================================================================================
>>> [ATP CI Checkpoint] 开始执行端到端四阶段质量门禁检查点
>>> Pipeline: CI-Pipeline-Worker | Commit: e5f6a7b | PR: #1026
================================================================================
[STAGE 1/4] Git Diff AST 语法树语义解析与用例智能推荐... [PASSED]
[STAGE 2/4] 代码变更三维风险多维打分... [WARNING]
  -> 触及涉密鉴权核心资产，标记为 CRITICAL
[STAGE 3/4] Flaky 抖动用例自适应抑制过滤... [PASSED]
[STAGE 4/4] CI/CD PR 全要素质量门禁裁决...
  -> 单测通过率: 100.0%, 变异得分: 88.0%
  -> 缺少双人审批签字 -> CONDITIONAL_PASS

[WARNING] 存在次要风险告警，建议模块负责人复核签字后合入！
================================================================================
[EXIT CODE]: 2 (WARNING / CONDITIONAL)
================================================================================`,
  executed_at: '2026-10-16T15:10:00Z',
}

const totalDurationMs = computed(() => {
  if (!currentReport.value?.stages) return 0
  const sum = currentReport.value.stages.reduce((acc, s) => acc + (s.duration_ms || 0), 0)
  return Math.round(sum)
})

const getExitCodeLabel = (code: number) => {
  switch (code) {
    case 0: return 'SUCCESS / 放行'
    case 1: return 'FAILURE / 阻断'
    case 2: return 'WARNING / 告警'
    default: return 'UNKNOWN'
  }
}

const getExitCodeHeadline = (code: number) => {
  switch (code) {
    case 0: return '流水线检查点全部通过 (Code 0)：所有质量与安全卡点合规，准许合流与发布！'
    case 1: return '流水线检查点硬门禁违规 (Code 1)：检测到严重质量短板，已阻断流水线！'
    case 2: return '流水线存在高危风险告警 (Code 2)：需满足双人签批或模块负责人核准方可合并。'
    default: return '检查点状态未知'
  }
}

const getOverallStatusColor = (status: PipelineStageStatus) => {
  switch (status) {
    case 'PASSED': return 'success'
    case 'BLOCKED': return 'error'
    case 'WARNING': return 'warning'
    default: return 'default'
  }
}

const getStageTagColor = (status: PipelineStageStatus) => {
  switch (status) {
    case 'PASSED': return 'success'
    case 'BLOCKED': return 'error'
    case 'WARNING': return 'warning'
    default: return 'default'
  }
}

const getStageStatusIcon = (status: PipelineStageStatus) => {
  switch (status) {
    case 'PASSED': return CheckCircleOutlined
    case 'BLOCKED': return CloseCircleOutlined
    case 'WARNING': return ExclamationCircleOutlined
    default: return CheckCircleOutlined
  }
}

const formatKey = (key: string) => {
  return key.replace(/_/g, ' ')
}

const applyPreset = (type: 'passed' | 'blocked' | 'warning') => {
  if (type === 'passed') currentReport.value = PRESET_PASSED
  else if (type === 'blocked') currentReport.value = PRESET_BLOCKED
  else currentReport.value = PRESET_WARNING
  message.info(`已切换至「${type}」预设流水线检查点报告`)
}

const loadInitialData = async () => {
  loading.value = true
  try {
    const res = await ciImpactApi.listCheckpointReports()
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
    } else {
      currentReport.value = PRESET_PASSED
    }
  } catch {
    currentReport.value = PRESET_PASSED
  } finally {
    loading.value = false
  }
}

const handleRunSubmit = async () => {
  loading.value = true
  showRunModal.value = false
  try {
    const res = await ciImpactApi.runPipelineCheckpoint({
      diff_text: runForm.diff_text,
      pipeline_name: runForm.pipeline_name,
      commit_sha: runForm.commit_sha,
      pr_id: runForm.pr_id,
      selection_strategy: runForm.selection_strategy,
      mock_test_pass_rate_pct: runForm.mock_test_pass_rate_pct,
      mock_test_failed_cases_count: runForm.mock_test_failed_cases_count,
      mutation_score_pct: runForm.mutation_score_pct,
      has_dual_approvals: runForm.has_dual_approvals,
    })
    currentReport.value = res.report
    message.success(res.message || `CI 检查点执行完成，Exit Code: ${res.report.exit_code}`)
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '检查点执行失败')
  } finally {
    loading.value = false
  }
}

const copyConsoleLog = () => {
  if (currentReport.value?.console_log_output && navigator.clipboard) {
    navigator.clipboard.writeText(currentReport.value.console_log_output)
    message.success('已复制控制台日志至剪贴板')
  } else {
    message.info('当前环境不支持自动剪贴板')
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (terminalRef.value) {
      terminalRef.value.scrollTop = terminalRef.value.scrollHeight
    }
  })
}

onMounted(() => {
  loadInitialData()
})
</script>

<style scoped>
.ci-pipeline-checkpoint-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-icon {
  font-size: 20px;
  color: #0284c7;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
  color: #0f172a;
}

.page-subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 6px 0 0 0;
  max-width: 860px;
}

/* 裁决横幅 */
.verdict-banner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 20px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  transition: all 0.3s ease;
}

.banner-code-0 {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border-color: #86efac;
}

.banner-code-1 {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border-color: #fca5a5;
}

.banner-code-2 {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-color: #fcd34d;
}

.exit-code-badge-box {
  width: 120px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.code-title {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.05em;
}

.code-number {
  font-size: 32px;
  font-weight: 900;
  line-height: 1.1;
  color: #0f172a;
}

.banner-code-0 .code-number { color: #16a34a; }
.banner-code-1 .code-number { color: #dc2626; }
.banner-code-2 .code-number { color: #d97706; }

.code-status {
  font-size: 11px;
  font-weight: 700;
  margin-top: 2px;
}

.banner-code-0 .code-status { color: #15803d; }
.banner-code-1 .code-status { color: #b91c1c; }
.banner-code-2 .code-status { color: #b45309; }

.verdict-info-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.verdict-title-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.verdict-headline {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.status-tag {
  font-weight: 700;
}

.pipeline-meta-row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: #475569;
  flex-wrap: wrap;
}

.remediation-summary-box {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  margin-top: 4px;
}

.rem-title {
  font-weight: 700;
  flex-shrink: 0;
}

.rem-desc {
  color: #334155;
}

.text-danger { color: #dc2626; }
.text-success { color: #16a34a; }

/* 四阶段执行拓扑网格 */
.stages-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.heading-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.heading-sub {
  font-size: 11px;
  color: #64748b;
}

.stages-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stage-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-top: 3px solid #cbd5e1;
}

.stage-passed { border-top-color: #10b981; }
.stage-blocked { border-top-color: #ef4444; }
.stage-warning { border-top-color: #f59e0b; }

.stage-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stage-index {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.stage-duration {
  font-size: 11px;
  font-family: monospace;
  color: #94a3b8;
}

.stage-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.stage-summary {
  font-size: 11px;
  color: #64748b;
  margin: 0;
  line-height: 1.4;
  flex: 1;
}

.stage-details-box {
  margin-top: 4px;
  padding: 6px 8px;
  background: #f8fafc;
  border-radius: 4px;
  font-size: 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
}

.detail-k {
  color: #64748b;
  text-transform: capitalize;
}

.detail-v {
  font-weight: 600;
  color: #1e293b;
}

/* 终端控制台面板 */
.console-log-panel {
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
  display: flex;
  flex-direction: column;
}

.console-header {
  padding: 8px 14px;
  background: #1e293b;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #334155;
}

.console-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.terminal-icon {
  color: #38bdf8;
}

.console-title {
  font-size: 12px;
  font-weight: 600;
  color: #f1f5f9;
}

.console-btn {
  color: #94a3b8;
  font-size: 11px;
  padding: 0 4px;
}

.console-btn:hover {
  color: #38bdf8;
}

.terminal-window {
  margin: 0;
  padding: 14px 16px;
  background: #0f172a;
  color: #38bdf8;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  max-height: 380px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.diff-input {
  font-family: monospace;
  font-size: 12px;
}

.empty-placeholder {
  padding: 40px 0;
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}
</style>
