<template>
  <a-drawer
    :open="open"
    :width="1040"
    placement="right"
    title="CI 选定测试集高频抖动 Flaky 用例自适应抑制隔离控制台"
    destroy-on-close
    @close="handleClose"
  >
    <div class="flaky-quarantine-drawer">
      <!-- 头部介绍与模式调节 -->
      <div class="drawer-banner">
        <div class="banner-left">
          <FilterOutlined class="banner-icon" />
          <div>
            <div class="banner-title-row">
              <span class="banner-title">Flaky 抖动用例自适应抑制隔离引擎</span>
              <a-tag color="processing">历史统计贝叶斯探测</a-tag>
              <a-tag color="purple">主干 CI 零误阻断</a-tag>
            </div>
            <p class="banner-desc">
              自动探测选定测试集中的偶发性网络抖动与非致命 Flaky 用例，自适应执行自动重试保护或隔离至异步观察队列，杜绝假阳性失败阻断主干交付。
            </p>
          </div>
        </div>
      </div>

      <!-- 模式选择与控制条 -->
      <div class="filter-controls-row">
        <a-space>
          <span class="ctrl-lbl">抑制过滤模式:</span>
          <a-radio-group v-model:value="filterMode" size="small" button-style="solid" @change="handleRunFilter">
            <a-radio-button value="auto_adaptive">自适应智能抑制 (Auto-Adaptive)</a-radio-button>
            <a-radio-button value="quarantine_strict">严格隔离 (Quarantine All)</a-radio-button>
            <a-radio-button value="retry_only">仅重试放行 (Retry Only)</a-radio-button>
          </a-radio-group>
        </a-space>

        <a-space>
          <a-button size="small" :loading="loading" @click="handleRunFilter">
            <ReloadOutlined /> 重新探测
          </a-button>
          <a-button type="primary" size="small" ghost @click="showOverrideModal = true">
            <SafetyCertificateOutlined /> 录入治理白名单覆盖
          </a-button>
        </a-space>
      </div>

      <a-spin :spinning="loading">
        <template v-if="currentReport">
          <!-- 统计收益 KPI 卡片网格 -->
          <div class="metrics-grid">
            <div class="metric-card">
              <span class="m-lbl">评估用例总数</span>
              <span class="m-val">{{ currentReport.total_cases_evaluated }}</span>
              <span class="m-sub">候选测试集总量</span>
            </div>

            <div class="metric-card highlight-green">
              <span class="m-lbl">主干稳固用例</span>
              <span class="m-val text-success">{{ currentReport.stable_cases_count }}</span>
              <span class="m-sub">历史执行无抖动</span>
            </div>

            <div class="metric-card highlight-orange">
              <span class="m-lbl">检出 Flaky 抖动</span>
              <span class="m-val text-orange">{{ currentReport.flaky_cases_count }}</span>
              <span class="m-sub">抖动率 {{ currentReport.suppression_ratio_pct }}%</span>
            </div>

            <div class="metric-card highlight-purple">
              <span class="m-lbl">移出主干隔离数</span>
              <span class="m-val text-purple">{{ currentReport.isolated_cases_count }}</span>
              <span class="m-sub">移至次级观察队列</span>
            </div>

            <div class="metric-card highlight-blue">
              <span class="m-lbl">附加重试保护数</span>
              <span class="m-val text-blue">{{ currentReport.retried_cases_count }}</span>
              <span class="m-sub">自动配置 2 次退避重试</span>
            </div>
          </div>

          <!-- 选项卡展示用例清单 -->
          <a-card size="small" class="cases-panel-card" :bordered="false">
            <a-tabs v-model:activeKey="activeTab">
              <!-- Tab 1: 全部用例处置大表 -->
              <a-tab-pane key="all" tab="用例抖动处置总览 (All Evaluations)">
                <a-table
                  :data-source="currentReport.evaluations || []"
                  :columns="allColumns"
                  row-key="case_id"
                  size="small"
                  :pagination="{ pageSize: 6 }"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'case_name'">
                      <div class="case-name-cell">
                        <span class="case-title font-bold">#{{ record.case_id }} {{ record.case_name }}</span>
                        <small class="case-runs-meta">历史运行: {{ record.total_runs_analyzed }} 轮 (失败率: {{ Math.round(record.failure_rate * 100) }}%)</small>
                      </div>
                    </template>

                    <template v-else-if="column.key === 'flakiness_score'">
                      <div class="score-progress-box">
                        <a-progress
                          :percent="Math.round(record.flakiness_score * 100)"
                          size="small"
                          :stroke-color="record.flakiness_score >= 0.75 ? '#ef4444' : (record.flakiness_score >= 0.2 ? '#f59e0b' : '#10b981')"
                        />
                      </div>
                    </template>

                    <template v-else-if="column.key === 'action'">
                      <a-tag :color="getActionColor(record.action)">
                        {{ getActionLabel(record.action) }}
                      </a-tag>
                    </template>

                    <template v-else-if="column.key === 'suppression_reason'">
                      <span class="reason-text">{{ record.suppression_reason }}</span>
                    </template>

                    <template v-else-if="column.key === 'retry_count_recommended'">
                      <a-tag v-if="record.retry_count_recommended > 0" color="cyan">
                        重试 {{ record.retry_count_recommended }} 次
                      </a-tag>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </template>
                </a-table>
              </a-tab-pane>

              <!-- Tab 2: 主干阻塞放行用例集 -->
              <a-tab-pane key="actionable" tab="主干放行执行集 (Actionable Cases)">
                <div class="subset-tip text-success">
                  以下 {{ currentReport.actionable_case_ids?.length || 0 }} 个用例执行结果将决定当前 PR 的最终准入成败：
                </div>
                <div class="case-tags-box">
                  <a-tag v-for="cid in currentReport.actionable_case_ids || []" :key="cid" color="green">
                    用例 #{{ cid }}
                  </a-tag>
                </div>
              </a-tab-pane>

              <!-- Tab 3: 隔离观察用例集 -->
              <a-tab-pane key="quarantined" tab="隔离观察测试集 (Quarantined Cases)">
                <div class="subset-tip text-purple">
                  以下 {{ currentReport.quarantined_case_ids?.length || 0 }} 个用例已被移出主干 CI 队列，失败不会阻断发布：
                </div>
                <div class="case-tags-box">
                  <a-tag v-for="cid in currentReport.quarantined_case_ids || []" :key="cid" color="purple">
                    用例 #{{ cid }} (已隔离)
                  </a-tag>
                </div>
              </a-tab-pane>
            </a-tabs>
          </a-card>
        </template>

        <a-empty v-else description="暂无 Flaky 抑制报告，请点击「重新探测」" />
      </a-spin>
    </div>

    <!-- 录入治理白名单覆盖 Modal -->
    <a-modal
      v-model:open="showOverrideModal"
      title="录入用例级人工抖动治理白名单策略覆盖"
      @ok="handleOverrideSubmit"
    >
      <a-form layout="vertical">
        <a-form-item label="目标用例 ID" required>
          <a-input-number v-model:value="overrideForm.case_id" :min="1" style="width: 100%" />
        </a-form-item>
        <a-form-item label="指定处置动作" required>
          <a-select v-model:value="overrideForm.action">
            <a-select-option value="isolated_to_quarantine">强制隔离观察 (isolated_to_quarantine)</a-select-option>
            <a-select-option value="retry_attached">强制附加重试 (retry_attached)</a-select-option>
            <a-select-option value="normal_passthrough">强制正常放行 (normal_passthrough)</a-select-option>
            <a-select-option value="tagged_observation">仅打标观察 (tagged_observation)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="治理原因描述" required>
          <a-textarea v-model:value="overrideForm.reason" placeholder="如: 已知跨机房网络夜间割接偶发抖动，等待专线修复" :rows="3" />
        </a-form-item>
        <a-form-item label="关联工单 / Issue 编号 (可选)">
          <a-input v-model:value="overrideForm.ticket_id" placeholder="如: OPS-8848 或 BUG-1024" />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  FilterOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type FlakyFilterMode,
  type SuppressionAction,
  type FlakySuppressionReportItem,
} from '@/api/ciImpact'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
}>()

const loading = ref(false)
const filterMode = ref<FlakyFilterMode>('auto_adaptive')
const currentReport = ref<FlakySuppressionReportItem | null>(null)
const activeTab = ref<'all' | 'actionable' | 'quarantined'>('all')

const showOverrideModal = ref(false)
const overrideForm = reactive({
  case_id: 103,
  action: 'isolated_to_quarantine' as SuppressionAction,
  reason: '已知第三方结算通道夜间限流偶发抖动',
  ticket_id: 'OPS-8848',
})

// 演示候选测试集与历史统计
const sampleCases = [
  { case_id: 101, case_name: '订单结算优惠抵扣用例' },
  { case_id: 102, case_name: '下单收银台流程' },
  { case_id: 103, case_name: '第三方跨境支付渠道回调' },
  { case_id: 104, case_name: '积分抵现校验' },
  { case_id: 105, case_name: '优惠券防刷风控' },
]

const sampleStats: Record<number, any> = {
  101: { total_runs: 10, passed_runs: 10, failed_runs: 0 },
  102: { total_runs: 10, passed_runs: 8, failed_runs: 2 }, // 轻微抖动 (失败率 20%)
  103: { total_runs: 10, passed_runs: 5, failed_runs: 5 }, // 严重抖动 (失败率 50%, 指数 1.0)
  104: { total_runs: 10, passed_runs: 9, failed_runs: 1 },
  105: { total_runs: 10, passed_runs: 10, failed_runs: 0 },
}

const allColumns = [
  { title: '测试用例 ID 与名称', key: 'case_name', width: 280 },
  { title: '抖动指数 (Flakiness)', key: 'flakiness_score', width: 150 },
  { title: '处置动作', key: 'action', width: 120 },
  { title: '重试保护', key: 'retry_count_recommended', width: 100 },
  { title: '自适应抑制归因', key: 'suppression_reason' },
]

function getActionLabel(action: SuppressionAction): string {
  switch (action) {
    case 'normal_passthrough':
      return '正常放行'
    case 'retry_attached':
      return '附加重试'
    case 'isolated_to_quarantine':
      return '隔离观察'
    case 'tagged_observation':
      return '打标观察'
    default:
      return action
  }
}

function getActionColor(action: SuppressionAction): string {
  switch (action) {
    case 'normal_passthrough':
      return 'success'
    case 'retry_attached':
      return 'blue'
    case 'isolated_to_quarantine':
      return 'purple'
    case 'tagged_observation':
      return 'orange'
    default:
      return 'default'
  }
}

async function handleRunFilter() {
  loading.value = true
  try {
    const res = await ciImpactApi.filterFlakyTests({
      cases: sampleCases,
      mode: filterMode.value,
      flakiness_threshold: 0.20,
      historical_stats: sampleStats,
    })
    currentReport.value = res.report
    message.success(res.message || 'Flaky 用例自适应抑制完成')
  } catch (err: any) {
    message.error(`抑制过滤失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function handleOverrideSubmit() {
  try {
    const res = await ciImpactApi.setGovernanceOverride(overrideForm)
    message.success(res.message || '治理覆盖策略已生效')
    showOverrideModal.value = false
    await handleRunFilter()
  } catch (err: any) {
    message.error(`策略设置失败: ${err.message || err}`)
  }
}

function handleClose() {
  emit('update:open', false)
  emit('close')
}

onMounted(() => {
  handleRunFilter()
})
</script>

<style scoped>
.flaky-quarantine-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-banner {
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
  color: #7c3aed;
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

.filter-controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.ctrl-lbl {
  font-size: 12px;
  color: #64748b;
}

/* 核心 KPI 卡片网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.metric-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
}

.highlight-green {
  background: #ecfdf5;
  border-color: #a7f3d0;
}

.highlight-orange {
  background: #fffbeb;
  border-color: #fde68a;
}

.highlight-purple {
  background: #faf5ff;
  border-color: #e9d5ff;
}

.highlight-blue {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.m-lbl {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.m-val {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
  color: #0f172a;
}

.m-sub {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 4px;
}

.text-success {
  color: #10b981 !important;
}

.text-orange {
  color: #f59e0b !important;
}

.text-purple {
  color: #8b5cf6 !important;
}

.text-blue {
  color: #2563eb !important;
}

.text-muted {
  color: #cbd5e1;
}

/* 用例表格与子集区 */
.cases-panel-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.case-name-cell {
  display: flex;
  flex-direction: column;
}

.case-title {
  font-size: 12px;
  color: #0f172a;
}

.case-runs-meta {
  font-size: 10px;
  color: #94a3b8;
}

.font-bold {
  font-weight: 700;
}

.score-progress-box {
  width: 120px;
}

.reason-text {
  font-size: 11px;
  color: #475569;
}

.subset-tip {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
}

.case-tags-box {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 6px;
}
</style>
