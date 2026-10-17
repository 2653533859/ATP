<template>
  <a-drawer
    :open="open"
    title="堆栈指纹拓扑与同源缺陷智能聚类透视抽屉"
    width="88%"
    placement="right"
    :destroy-on-close="true"
    class="defect-cluster-inspection-drawer"
    @close="handleClose"
  >
    <div class="drawer-container">
      <!-- 1. 顶部主缺陷聚合横幅 -->
      <div class="defect-hero-bar">
        <div class="hero-left">
          <div class="title-row">
            <BugOutlined class="hero-bug-icon text-danger" />
            <span class="cluster-title font-bold">{{ displayCluster.master_title }}</span>
            <a-tag color="volcano" class="font-mono">
              {{ displayCluster.exception_type }}
            </a-tag>
            <a-tag color="purple" class="font-mono">
              服务: {{ displayCluster.target_service }}
            </a-tag>
          </div>

          <div class="fingerprint-row font-mono text-xs">
            <span class="fp-label text-secondary">64位故障语义指纹:</span>
            <span class="fp-code font-bold text-primary">{{ displayCluster.primary_fingerprint }}</span>
          </div>

          <div class="hero-summary-pills font-mono">
            <span class="metric-pill">
              同源失败聚合: <strong class="text-danger">{{ displayCluster.total_failures_count }} 个用例</strong>
            </span>
            <span class="metric-pill">
              根因文件: <strong class="text-primary">{{ displayCluster.root_cause_file }}</strong>
            </span>
            <span class="metric-pill">
              归属团队: <strong class="text-secondary">{{ displayCluster.responsible_team || '资金结算与计费组' }}</strong>
            </span>
            <span class="metric-pill">
              智能指派: <strong class="text-success">{{ displayCluster.suggested_assignee || '李强 (支付架构师)' }}</strong>
            </span>
          </div>
        </div>

        <div class="hero-actions">
          <a-space>
            <a-button
              type="primary"
              :loading="merging"
              @click="handleOpenMergeModal"
            >
              <template #icon><BranchesOutlined /></template>
              合并至外部工单 (Merge)
            </a-button>

            <a-button @click="handleClose">关闭</a-button>
          </a-space>
        </div>
      </div>

      <!-- 2. 双栏栅格: 同源用例列表 + 根因堆栈脱敏对比 -->
      <a-row :gutter="[16, 16]">
        <!-- 左侧: 聚类关联用例列表 -->
        <a-col :xs="24" :lg="12">
          <a-card class="linked-cases-card" title="同源聚类测试用例 (Associated Test Cases)">
            <template #extra>
              <a-tag color="blue">共去重收敛 {{ displayCluster.linked_case_ids.length }} 处失败</a-tag>
            </template>
            <a-table
              :data-source="casesTableData"
              :columns="caseColumns"
              :pagination="false"
              row-key="case_id"
              size="small"
              class="cases-table font-mono"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'case_id'">
                  <span class="font-bold text-primary">{{ record.case_id }}</span>
                </template>
                <template v-else-if="column.key === 'status'">
                  <a-tag color="red">FAILED</a-tag>
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>

        <!-- 右侧: 规范化堆栈与根因代码帧 -->
        <a-col :xs="24" :lg="12">
          <a-card class="root-cause-card" title="根因代码帧与脱敏堆栈 (Root Cause Frame)">
            <template #extra>
              <a-tag color="green">置信度: 94.5%</a-tag>
            </template>

            <!-- 核心根因代码帧标注 -->
            <div class="root-frame-box font-mono">
              <div class="frame-header font-bold text-danger">
                <span>[Root Cause Frame] 最深业务调用帧:</span>
              </div>
              <div class="frame-body text-xs">
                <div>文件路径: <code>{{ displayCluster.root_cause_file }}</code></div>
                <div>异常代码: <code>raise DatabaseConnectionTimeout("pool exhausted")</code></div>
              </div>
            </div>

            <!-- 脱敏清洗后堆栈 -->
            <div class="stack-view-container mt-3">
              <div class="stack-title text-xs font-bold text-secondary mb-1">
                标准化清洗堆栈 (已抹平内存地址 &amp; UUID &amp; 时间戳):
              </div>
              <pre class="sanitized-stack-pre font-mono text-xs">{{ displayCluster.sanitized_stack_trace }}</pre>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 3. 根因归因证据链横幅 -->
      <a-card class="evidence-card" title="智能归因决策证据链 (Attribution Evidence Chain)">
        <div class="evidence-timeline font-mono text-xs">
          <div class="evidence-item">
            <span class="evi-dot bg-success" />
            <span class="evi-text">1. 异常堆栈业务调用帧提取：定位核心业务路径 <code>{{ displayCluster.root_cause_file }}</code>。</span>
          </div>
          <div class="evidence-item">
            <span class="evi-dot bg-primary" />
            <span class="evi-text">2. 领域服务权属映射：根据微服务架构 CODEOWNERS 自动归因至【资金结算与计费组】。</span>
          </div>
          <div class="evidence-item">
            <span class="evi-dot bg-warning" />
            <span class="evi-text">3. 聚类去重判定：64 位指纹高度重合，将 12 起级联用例失败统一收敛合并为单一致命缺陷。</span>
          </div>
        </div>
      </a-card>
    </div>

    <!-- 合并外部工单弹窗 -->
    <a-modal
      v-model:open="mergeModalVisible"
      title="合并关联至外部工单 (Jira / GitHub / 禅道)"
      @ok="handleConfirmMerge"
    >
      <a-form layout="vertical">
        <a-form-item label="外部工单编码 (External Issue Key)">
          <a-input
            v-model:value="externalTicketKeyInput"
            placeholder="如 JIRA-BUG-4021 或 #88"
            class="font-mono"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  BugOutlined,
  BranchesOutlined,
} from '@ant-design/icons-vue'

export interface ClusteredDefectItem {
  cluster_id: string
  primary_fingerprint: string
  master_title: string
  exception_type: string
  target_service: string
  root_cause_file: string
  total_failures_count: number
  linked_case_ids: string[]
  associated_case_names: string[]
  sanitized_stack_trace?: string
  responsible_team?: string
  suggested_assignee?: string
}

const props = withDefaults(
  defineProps<{
    open: boolean
    cluster?: ClusteredDefectItem | null
  }>(),
  {
    open: false,
    cluster: null,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
  (e: 'mergeToExternal', clusterId: string, externalId: string): void
}>()

const merging = ref(false)
const mergeModalVisible = ref(false)
const externalTicketKeyInput = ref('JIRA-BUG-4021')

const defaultCluster: ClusteredDefectItem = {
  cluster_id: 'cl_seed_master_01',
  primary_fingerprint: 'fp_hash_7fa8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8',
  master_title: '[payment-service] DatabaseConnectionTimeout in payment.py:execute_charge',
  exception_type: 'DatabaseConnectionTimeout',
  target_service: 'payment-service',
  root_cause_file: '/app/services/payment.py',
  total_failures_count: 12,
  linked_case_ids: [
    'case_checkout_wechat',
    'case_checkout_alipay',
    'case_checkout_card',
    'case_order_retry_01',
    'case_order_retry_02',
  ],
  associated_case_names: [
    '收银台微信支付扣款验证',
    '收银台支付宝扣款验证',
    '银行卡扣款验证',
    '订单异步重试01',
    '订单异步重试02',
  ],
  sanitized_stack_trace:
    'Traceback (most recent call last):\n' +
    '  File "/opt/venv/lib/site-packages/pytest/runner.py", line 120, in run\n' +
    '  File "/workspace/app/services/payment.py", line 45, in execute_charge\n' +
    '    raise DatabaseConnectionTimeout("Connection pool exhausted at <HEX_ADDR>")\n' +
    'DatabaseConnectionTimeout: PostgreSQL connection timed out on <HOST:PORT> for order_<ID>',
  responsible_team: '资金结算与计费组 (Billing & Payment Team)',
  suggested_assignee: '李强 (支付架构师)',
}

const displayCluster = computed(() => props.cluster || defaultCluster)

const caseColumns = [
  { title: '用例编码', dataIndex: 'case_id', key: 'case_id', width: 180 },
  { title: '用例名称', dataIndex: 'case_name', key: 'case_name' },
  { title: '状态', key: 'status', width: 90 },
]

const casesTableData = computed(() => {
  const ids = displayCluster.value.linked_case_ids || []
  const names = displayCluster.value.associated_case_names || []
  return ids.map((id, idx) => ({
    case_id: id,
    case_name: names[idx] || `测试场景用例_${idx + 1}`,
  }))
})

function handleClose() {
  emit('update:open', false)
  emit('close')
}

function handleOpenMergeModal() {
  mergeModalVisible.value = true
}

function handleConfirmMerge() {
  if (externalTicketKeyInput.value.trim()) {
    merging.value = true
    emit('mergeToExternal', displayCluster.value.cluster_id, externalTicketKeyInput.value.trim())
    setTimeout(() => {
      merging.value = false
      mergeModalVisible.value = false
    }, 300)
  }
}
</script>

<style scoped>
.drawer-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.defect-hero-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px 20px;
  background: var(--c-bg-subtle, #fafafa);
  border: 1px solid var(--c-border, #f0f0f0);
  border-radius: 8px;
}

.hero-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
}

.hero-bug-icon {
  font-size: 18px;
}

.fingerprint-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-code {
  background: #f0f5ff;
  border: 1px solid #adc6ff;
  padding: 2px 6px;
  border-radius: 4px;
}

.hero-summary-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 12px;
}

.metric-pill {
  padding: 4px 8px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e8e8e8);
  border-radius: 4px;
}

.root-frame-box {
  padding: 10px 12px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 6px;
}

.stack-view-container {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 10px 12px;
}

.sanitized-stack-pre {
  margin: 0;
  white-space: pre-wrap;
  color: #333;
}

.evidence-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.evi-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.bg-success {
  background: #52c41a;
}

.bg-primary {
  background: #1677ff;
}

.bg-warning {
  background: #faad14;
}

.mt-3 {
  margin-top: 12px;
}

.mb-1 {
  margin-bottom: 4px;
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

.text-secondary {
  color: var(--c-text-secondary, #666);
}
</style>
