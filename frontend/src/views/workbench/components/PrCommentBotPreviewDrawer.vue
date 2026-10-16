<template>
  <a-drawer
    :open="open"
    :width="1100"
    placement="right"
    title="GitHub / GitLab 交互式 Reviewer 评论卡片预览与广播控制台"
    destroy-on-close
    class="pr-comment-bot-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部说明条 -->
      <div class="drawer-banner">
        <div class="banner-title">
          <RobotOutlined class="banner-icon" />
          <span>PR Reviewer 交互式机器评论卡片自动广播与多平台发布</span>
        </div>
        <p class="banner-desc">
          自动聚合单测通过率、代码变异得分与高危变更双人审批等多维准入结果，生成符合 GitHub / GitLab PR 评论区 Markdown 规范的高保真卡片，并支持一键通过 Webhook 广播至代码评审区。
        </p>
      </div>

      <!-- 广播参数配置栏 -->
      <div class="control-panel">
        <div class="control-row">
          <div class="control-item">
            <span class="item-label">目标平台:</span>
            <a-select v-model:value="platform" size="small" style="width: 140px">
              <a-select-option value="github">
                <GithubOutlined /> GitHub
              </a-select-option>
              <a-select-option value="gitlab">
                <GitlabOutlined /> GitLab
              </a-select-option>
              <a-select-option value="gitea">
                <CodeOutlined /> Gitea
              </a-select-option>
              <a-select-option value="generic_markdown">
                <FileMarkdownOutlined /> Markdown 文本
              </a-select-option>
            </a-select>
          </div>

          <div class="control-item">
            <span class="item-label">Git 仓库全名:</span>
            <a-input v-model:value="repoName" size="small" style="width: 200px" placeholder="owner/repo" />
          </div>

          <div class="control-item">
            <span class="item-label">卡片标题:</span>
            <a-input v-model:value="botTitle" size="small" style="width: 240px" />
          </div>

          <div class="control-item">
            <a-checkbox v-model:checked="simulateSuccess">
              模拟投递 (Dry Run)
            </a-checkbox>
          </div>

          <div class="control-actions">
            <a-space>
              <a-button size="small" @click="handleRegenerate">
                <ReloadOutlined /> 重新生成
              </a-button>
              <a-button size="small" @click="copyMarkdown">
                <CopyOutlined /> 复制 Markdown
              </a-button>
              <a-button
                type="primary"
                size="small"
                :loading="dispatching"
                @click="handleDispatch"
              >
                <SendOutlined /> 广播评论至 Git PR
              </a-button>
            </a-space>
          </div>
        </div>
      </div>

      <!-- 投递成功提示条 -->
      <div v-if="lastDeliveredComment" class="delivery-status-alert">
        <CheckCircleOutlined class="text-success status-icon" />
        <div class="status-info">
          <span class="status-title">评论卡片已成功推送至 {{ lastDeliveredComment.platform.toUpperCase() }} PR 评论区！</span>
          <span class="status-sub">
            评论 ID: <code>{{ lastDeliveredComment.comment_id }}</code> | 仓库: <code>{{ lastDeliveredComment.repo_name }}</code> | 时间: {{ lastDeliveredComment.created_at }}
          </span>
        </div>
      </div>

      <!-- 双栏所见即所得区域 -->
      <div class="split-editor-grid">
        <!-- 左侧：Markdown 源码编辑与微调 -->
        <div class="pane-card left-pane">
          <div class="pane-header">
            <span class="pane-title">
              <FileMarkdownOutlined /> PR 评论 Markdown 源码
            </span>
            <a-tag color="blue">实时所见即所得</a-tag>
          </div>
          <div class="pane-body">
            <a-textarea
              v-model:value="markdownContent"
              class="markdown-editor"
              :rows="22"
              placeholder="正在生成评论卡片 Markdown 源码..."
            />
          </div>
        </div>

        <!-- 右侧：GitHub / GitLab 风格真实效果仿真渲染 -->
        <div class="pane-card right-pane">
          <div class="pane-header">
            <span class="pane-title">
              <EyeOutlined /> Git 平台 PR 评论区仿真预览 (Preview)
            </span>
            <a-tag :color="platform === 'github' ? 'black' : 'orange'">
              {{ platform.toUpperCase() }} Comment
            </a-tag>
          </div>
          <div class="pane-body git-comment-container">
            <!-- 仿 GitHub PR 评论卡片外壳 -->
            <div class="git-bubble">
              <div class="git-bubble-header">
                <div class="author-badge">
                  <RobotOutlined class="bot-avatar" />
                  <span class="bot-name">atp-robot</span>
                  <a-tag size="small" class="bot-tag">Bot</a-tag>
                  <span class="comment-time">commented just now</span>
                </div>
                <div class="badge-right">
                  <a-tag :color="getVerdictTagColor(currentVerdict)" size="small">
                    {{ currentVerdict }}
                  </a-tag>
                </div>
              </div>

              <!-- 渲染生成的 Markdown 评论内容 -->
              <div class="git-bubble-content markdown-rendered-box">
                <div class="rendered-banner" :class="`banner-verdict-${currentVerdict.toLowerCase()}`">
                  <div class="rendered-banner-title">
                    <span>{{ getBannerVerdictEmoji(currentVerdict) }} [ATP CI Gatekeeper] {{ getBannerVerdictText(currentVerdict) }}</span>
                  </div>
                  <div class="rendered-banner-quote">
                    {{ getBannerVerdictQuote(currentVerdict) }}
                  </div>
                </div>

                <div class="rendered-meta-list">
                  <div>• <strong>Pull Request</strong>: <code>{{ gateReport?.pr_id || '#1024' }}</code> | <strong>Target Branch</strong>: <code>{{ gateReport?.target_branch || 'main' }}</code></div>
                  <div>• <strong>Commit SHA</strong>: <code>{{ (gateReport?.commit_sha || 'a1b2c3d').slice(0, 7) }}</code> | <strong>Author</strong>: {{ gateReport?.author || 'developer' }}</div>
                  <div>• <strong>Overall Compliance Score</strong>: <span class="score-highlight">{{ gateReport?.overall_compliance_score || 100 }}%</span></div>
                </div>

                <div class="rendered-table-heading">
                  <strong>📋 质量门禁规则多维裁决明细 (Quality Gate Audit Matrix)</strong>
                </div>

                <table class="rendered-table">
                  <thead>
                    <tr>
                      <th>Gate Rule</th>
                      <th>Status</th>
                      <th>Severity</th>
                      <th>Measured vs Threshold</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="rule in (gateReport?.evaluated_rules || defaultRules)" :key="rule.rule_id">
                      <td>{{ rule.rule_name }}</td>
                      <td>
                        <span :class="rule.passed ? 'pill-green' : 'pill-red'">
                          {{ rule.passed ? 'PASSED ✓' : 'FAILED ✗' }}
                        </span>
                      </td>
                      <td><code>{{ rule.severity }}</code></td>
                      <td><code>{{ rule.measured_value }}</code> (阈值: <code>{{ rule.threshold_value }}</code>)</td>
                    </tr>
                  </tbody>
                </table>

                <div v-if="gateReport && gateReport.remediation_steps.length > 0" class="rendered-remediation">
                  <div class="rem-heading"><strong>🔧 整改行动项与放行指南 (Remediation Steps):</strong></div>
                  <ol>
                    <li v-for="(step, idx) in gateReport.remediation_steps" :key="idx">
                      {{ step }}
                    </li>
                  </ol>
                </div>

                <div class="rendered-footer">
                  <i>✨ 由 ATP CI/CD 自动化质量门禁机器人自动裁决与发布 | <a href="#">查看完整变异得分热力大盘</a></i>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  RobotOutlined,
  GithubOutlined,
  GitlabOutlined,
  CodeOutlined,
  FileMarkdownOutlined,
  ReloadOutlined,
  CopyOutlined,
  SendOutlined,
  CheckCircleOutlined,
  EyeOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type GitPlatformType,
  type MergeGateVerdict,
  type PrCommentPayload,
  type PrGateVerdictReport,
} from '@/api/ciImpact'

const props = defineProps<{
  open: boolean
  defaultGateId?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'comment-dispatched', comment: PrCommentPayload): void
}>()

const platform = ref<GitPlatformType>('github')
const repoName = ref('2653533859/ATP')
const botTitle = ref('ATP CI 自动化质量门禁审核卡片')
const simulateSuccess = ref(true)
const dispatching = ref(false)

const gateReport = ref<PrGateVerdictReport | null>(null)
const markdownContent = ref('')
const lastDeliveredComment = ref<PrCommentPayload | null>(null)

const defaultRules = [
  {
    rule_id: 'RULE_UNIT_TEST_PASS_RATE',
    rule_name: '单元测试全量通过硬门禁',
    passed: true,
    severity: 'blocking',
    measured_value: '100.0%',
    threshold_value: '>= 100.0%',
  },
  {
    rule_id: 'RULE_MUTATION_SCORE',
    rule_name: '代码变异测试充分性门禁',
    passed: true,
    severity: 'blocking',
    measured_value: '85.0%',
    threshold_value: '>= 70.0%',
  },
]

const currentVerdict = computed<MergeGateVerdict>(() => {
  return gateReport.value?.verdict || 'MERGE_APPROVED'
})

const getVerdictTagColor = (verdict: MergeGateVerdict) => {
  switch (verdict) {
    case 'MERGE_APPROVED': return 'success'
    case 'MERGE_BLOCKED': return 'error'
    case 'CONDITIONAL_PASS': return 'warning'
    default: return 'default'
  }
}

const getBannerVerdictEmoji = (verdict: MergeGateVerdict) => {
  switch (verdict) {
    case 'MERGE_APPROVED': return '🟢'
    case 'MERGE_BLOCKED': return '🔴'
    case 'CONDITIONAL_PASS': return '🟡'
  }
}

const getBannerVerdictText = (verdict: MergeGateVerdict) => {
  switch (verdict) {
    case 'MERGE_APPROVED': return 'PR 合并准入审核通过 (MERGE APPROVED)'
    case 'MERGE_BLOCKED': return 'PR 合并准入审核阻断 (MERGE BLOCKED)'
    case 'CONDITIONAL_PASS': return 'PR 合并准入审核带条件通过 (CONDITIONAL PASS)'
  }
}

const getBannerVerdictQuote = (verdict: MergeGateVerdict) => {
  switch (verdict) {
    case 'MERGE_APPROVED': return '所有质量与安全门禁指标全部达标，准许合并入主干分支！'
    case 'MERGE_BLOCKED': return '检测到存在阻断性硬门禁违规，已自动锁定合流通道，请修复后重新提交！'
    case 'CONDITIONAL_PASS': return '存在次要风险告警，建议模块负责人复核签字后合入。'
  }
}

const loadGateData = async () => {
  try {
    const res = await ciImpactApi.listPrGateReports()
    if (res.reports && res.reports.length > 0) {
      gateReport.value = res.reports[0]
      await generateMarkdown(res.reports[0].gate_id)
    } else {
      // 默认示例
      gateReport.value = {
        gate_id: 'gate_demo_1024',
        pr_id: '#1024',
        commit_sha: 'a1b2c3d4e5f',
        author: 'dev-alice',
        target_branch: 'main',
        verdict: 'MERGE_APPROVED',
        is_mergeable: true,
        overall_compliance_score: 100.0,
        blocking_reasons: [],
        warning_reasons: [],
        evaluated_rules: defaultRules as any,
        remediation_steps: [],
        evaluated_at: '2026-10-16T14:00:00Z',
      }
      markdownContent.value = `## 🤖 ${botTitle.value}\n\n### 🟢 [ATP CI Gatekeeper] PR 合并准入审核通过 (MERGE APPROVED)\n\n> 🎉 **所有质量与安全门禁指标全部达标，准许合并入主干分支！**\n\n- **Pull Request**: \`#1024\` | **Target Branch**: \`main\`\n- **Commit SHA**: \`a1b2c3d\` | **Author**: dev-alice\n- **Overall Compliance Score**: **100.0%**\n\n#### 📋 质量门禁规则裁决明细:\n| Gate Rule | Status | Severity | Measured vs Threshold |\n|---|---|---|---|\n| 单元测试全量通过硬门禁 | PASSED ✓ | blocking | 100.0% (阈值: >= 100.0%) |\n| 代码变异测试充分性门禁 | PASSED ✓ | blocking | 85.0% (阈值: >= 70.0%) |\n`
    }
  } catch {
    // 离线容错预设
    markdownContent.value = `## 🤖 ${botTitle.value}\n\n### 🟢 [ATP CI Gatekeeper] PR 合并准入审核通过 (MERGE APPROVED)\n\n> 🎉 **所有质量与安全门禁指标全部达标，准许合并入主干分支！**\n`
  }
}

const generateMarkdown = async (gateId: string) => {
  try {
    const res = await ciImpactApi.generatePrComment({
      gate_id: gateId,
      bot_header_title: botTitle.value,
    })
    markdownContent.value = res.markdown
  } catch {
    // 降级
  }
}

const handleRegenerate = async () => {
  if (gateReport.value) {
    await generateMarkdown(gateReport.value.gate_id)
    message.success('已重新生成评论卡片 Markdown')
  }
}

const handleDispatch = async () => {
  if (!gateReport.value) {
    message.warning('请先加载有效门禁报告')
    return
  }

  dispatching.value = true
  try {
    const res = await ciImpactApi.dispatchPrComment({
      gate_id: gateReport.value.gate_id,
      repo_name: repoName.value,
      platform: platform.value,
      bot_header_title: botTitle.value,
      simulate_success: simulateSuccess.value,
    })

    lastDeliveredComment.value = res.comment
    message.success(res.message || `评论卡片已成功投递至 ${platform.value.toUpperCase()} PR 评论区`)
    emit('comment-dispatched', res.comment)
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '广播评论失败')
  } finally {
    dispatching.value = false
  }
}

const copyMarkdown = () => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(markdownContent.value)
    message.success('已复制 Markdown 文本至剪贴板')
  } else {
    message.info('当前环境不支持自动剪贴板，请手动从左侧选择复制')
  }
}

const handleClose = () => {
  emit('update:open', false)
}

watch(
  () => props.open,
  (newVal) => {
    if (newVal) {
      loadGateData()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-banner {
  background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%);
  border: 1px solid #bae6fd;
  border-radius: 8px;
  padding: 12px 16px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #0369a1;
  margin-bottom: 4px;
}

.banner-icon {
  font-size: 18px;
  color: #0284c7;
}

.banner-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin: 0;
}

.control-panel {
  padding: 12px 14px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #f8fafc;
}

.control-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.item-label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.control-actions {
  margin-left: auto;
}

.delivery-status-alert {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 6px;
}

.status-icon {
  font-size: 20px;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-title {
  font-size: 13px;
  font-weight: 700;
  color: #15803d;
}

.status-sub {
  font-size: 11px;
  color: #475569;
}

/* 双栏布局 */
.split-editor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  min-height: 520px;
}

.pane-card {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.pane-header {
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.pane-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.pane-body {
  padding: 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.markdown-editor {
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  background: #1e293b;
  color: #f8fafc;
  border-radius: 6px;
  flex: 1;
}

/* 仿 GitHub PR 评论卡片样式 */
.git-comment-container {
  background: #f6f8fa;
}

.git-bubble {
  border: 1px solid #d0d7de;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(31, 35, 40, 0.04);
}

.git-bubble-header {
  padding: 8px 12px;
  background: #f6f8fa;
  border-bottom: 1px solid #d0d7de;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.author-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.bot-avatar {
  font-size: 16px;
  color: #0969da;
}

.bot-name {
  font-weight: 600;
  color: #1f2328;
}

.bot-tag {
  font-size: 10px;
  padding: 0 4px;
}

.comment-time {
  color: #656d76;
}

.markdown-rendered-box {
  padding: 14px 16px;
  font-size: 13px;
  color: #1f2328;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rendered-banner {
  padding: 10px 14px;
  border-radius: 6px;
  border: 1px solid #d0d7de;
}

.banner-verdict-merge_approved {
  background: #dafbe1;
  border-color: #4ac26b;
  color: #1a7f37;
}

.banner-verdict-merge_blocked {
  background: #ffebe9;
  border-color: #ff8182;
  color: #cf222e;
}

.banner-verdict-conditional_pass {
  background: #fff8c5;
  border-color: #d4a72c;
  color: #9a6700;
}

.rendered-banner-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 4px;
}

.rendered-banner-quote {
  font-size: 12px;
}

.rendered-meta-list {
  font-size: 12px;
  color: #334155;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.score-highlight {
  font-weight: 700;
  color: #0969da;
}

.rendered-table-heading {
  font-size: 12px;
  margin-top: 4px;
}

.rendered-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.rendered-table th,
.rendered-table td {
  border: 1px solid #d0d7de;
  padding: 6px 8px;
  text-align: left;
}

.rendered-table th {
  background: #f6f8fa;
  font-weight: 600;
}

.pill-green {
  background: #dafbe1;
  color: #1a7f37;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 11px;
}

.pill-red {
  background: #ffebe9;
  color: #cf222e;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 11px;
}

.rendered-remediation {
  font-size: 12px;
  background: #f8fafc;
  padding: 8px 12px;
  border-radius: 4px;
  border-left: 3px solid #f59e0b;
}

.rem-heading {
  margin-bottom: 4px;
}

.rendered-remediation ol {
  margin: 0;
  padding-left: 18px;
}

.rendered-footer {
  margin-top: 6px;
  font-size: 11px;
  color: #656d76;
  border-top: 1px solid #d0d7de;
  padding-top: 8px;
}
</style>
