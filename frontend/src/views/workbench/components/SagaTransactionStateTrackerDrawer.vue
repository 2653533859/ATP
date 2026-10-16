<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="Sagas / TCC 分布式事务状态机流转与悬挂事务探测控制台"
    destroy-on-close
    class="saga-tracker-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部介绍 Banner -->
      <div class="intro-banner">
        <div class="banner-top">
          <ApartmentOutlined class="banner-icon" />
          <div class="banner-texts">
            <div class="banner-title">多微服务 Sagas/TCC 分布式长事务一致性与悬挂防线 (T2.1)</div>
            <div class="banner-desc">
              跟踪跨微服务长事务的全局分支流转（Try / Confirm / Cancel 或 Forward / Compensate）。重点探测因网络乱序或重试迟滞引发的 <strong>悬挂事务 (Hanging Transaction)</strong>、<strong>空补偿 (Empty Compensation)</strong>、<strong>超时未决 (Timeout Pending)</strong> 与 <strong>部分提交数据撕裂</strong>，提供防悬挂状态机加固指导。
            </div>
          </div>
        </div>

        <!-- 4 大异常模式卡片 -->
        <div class="anomaly-cards">
          <div class="anomaly-card card-hanging">
            <div class="card-name">🚨 悬挂事务 (Hanging)</div>
            <div class="card-desc">Cancel 优先到达执行，晚到的 Try 产生永久资源冻结</div>
          </div>
          <div class="anomaly-card card-empty">
            <div class="card-name">⚠️ 空补偿 (Empty Compensation)</div>
            <div class="card-desc">未曾执行过 Try/Forward 即收到了 Cancel 回滚请求</div>
          </div>
          <div class="anomaly-card card-timeout">
            <div class="card-name">⏳ 超时未决 (Timeout Pending)</div>
            <div class="card-desc">分支长久处于 PENDING 状态，突破全局超时红线</div>
          </div>
          <div class="anomaly-card card-split">
            <div class="card-name">💥 部分提交 (Partial Failure)</div>
            <div class="card-desc">部分分支已确认提交但存在失败分支，跨库数据撕裂</div>
          </div>
        </div>
      </div>

      <!-- 快速演练场景与探测栏 -->
      <div class="action-bar">
        <div class="preset-row">
          <span class="preset-label">分布式事务场景演练:</span>
          <a-space :size="8" wrap>
            <a-button
              size="small"
              :type="presetKey === 'hanging' ? 'primary' : 'default'"
              danger
              @click="applyPreset('hanging')"
            >
              场景 1: 严重悬挂事务 (Cancel 先行 + 晚到 Try 悬挂)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'empty_compensation' ? 'primary' : 'default'"
              @click="applyPreset('empty_compensation')"
            >
              场景 2: 空补偿异常 (无 Try 收到 Cancel)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'timeout' ? 'primary' : 'default'"
              @click="applyPreset('timeout')"
            >
              场景 3: 超时未决 (分支长期 PENDING)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'normal' ? 'primary' : 'default'"
              @click="applyPreset('normal')"
            >
              场景 4: 正常提交 (Try+Confirm 达标)
            </a-button>
          </a-space>
        </div>

        <div class="ctrl-row">
          <a-space :size="12" align="center" wrap>
            <a-button size="small" :loading="loadingHanging" @click="fetchHangingList">
              <AlertOutlined /> 探测全网悬挂事务
            </a-button>
            <span v-if="hangingCount > 0" class="hanging-alert-text">
              全网当前存在 <strong>{{ hangingCount }}</strong> 笔处于未决/悬挂异常状态的全局事务！
            </span>
          </a-space>
        </div>
      </div>

      <!-- 事务一致性裁决大横幅 (Verdict Banner) -->
      <div v-if="report" class="verdict-banner" :class="`banner-${report.status.toLowerCase()}`">
        <div class="verdict-head">
          <div class="verdict-title-box">
            <span class="status-tag" :class="`tag-${report.status.toLowerCase()}`">
              {{ report.status }}
            </span>
            <a-tag :color="report.is_consistent ? 'green' : 'red'">
              {{ report.is_consistent ? '最终一致性达标' : '一致性受损' }}
            </a-tag>
            <span class="verdict-summary">{{ report.anomaly_description }}</span>
          </div>
          <div class="meta-box">
            <span>全局事务 ID: <code>{{ report.global_tx_id }}</code></span>
            <span class="sep">|</span>
            <span>业务单据: <strong>{{ report.business_key }}</strong></span>
            <span class="sep">|</span>
            <span>模式: <a-tag color="blue">{{ report.pattern }}</a-tag></span>
          </div>
        </div>
      </div>

      <!-- 分支事务流转明细表格 (Branches Table) -->
      <div v-if="report" class="branches-section">
        <div class="section-title">
          <span>分支事务阶段流转与状态机监控</span>
          <a-tag color="blue">共 {{ report.branches.length }} 个参与微服务分支</a-tag>
        </div>

        <a-table
          :data-source="report.branches"
          :columns="columns"
          row-key="branch_id"
          size="small"
          :pagination="false"
          bordered
          class="branches-table"
        >
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'seq'">
              <code>#{{ index + 1 }}</code>
            </template>

            <template v-if="column.key === 'service_action'">
              <div class="svc-cell">
                <a-tag :color="getServiceTagColor(record.service_name)">{{ record.service_name }}</a-tag>
                <strong>{{ record.action_name }}</strong>
                <code class="branch-id">{{ record.branch_id }}</code>
              </div>
            </template>

            <template v-if="column.key === 'stage'">
              <a-tag :color="getStageColor(record.stage)">
                {{ record.stage }}
              </a-tag>
            </template>

            <template v-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ record.status }}
              </a-tag>
              <span v-if="record.error_message" class="err-msg">
                {{ record.error_message }}
              </span>
            </template>

            <template v-if="column.key === 'duration'">
              <span>{{ record.duration_ms }} ms</span>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 防悬挂与修复指导建议卡片 -->
      <div v-if="report && report.remediation_advice.length > 0" class="remed-card">
        <div class="remed-title">🛠️ 分布式事务防悬挂加固指引 (Anti-Hanging Remediation Guide)</div>
        <ul class="remed-list">
          <li v-for="(advice, idx) in report.remediation_advice" :key="idx">
            {{ advice }}
          </li>
        </ul>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  AlertOutlined,
} from '@ant-design/icons-vue'
import {
  sagaTransactionApi,
  type SagaAuditReport,
  type BranchStage,
  type BranchStatus,
} from '@/api/distributedConsistency'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

function handleClose() {
  emit('update:open', false)
}

const loadingHanging = ref(false)
const hangingCount = ref(0)
const report = ref<SagaAuditReport | null>(null)
const presetKey = ref<'hanging' | 'empty_compensation' | 'timeout' | 'normal'>('hanging')

const columns = [
  { title: '执行序号', key: 'seq', width: 90 },
  { title: '参与微服务与动作', key: 'service_action', width: 340 },
  { title: '流转阶段 (Stage)', key: 'stage', width: 130 },
  { title: '分支状态 (Status)', key: 'status', width: 150 },
  { title: '执行耗时 (ms)', key: 'duration', width: 120 },
]

function getServiceTagColor(svc: string): string {
  switch (svc) {
    case 'order-service': return 'orange'
    case 'pay-service': return 'red'
    case 'inventory-service': return 'purple'
    default: return 'blue'
  }
}

function getStageColor(st: BranchStage): string {
  switch (st) {
    case 'TRY': return 'blue'
    case 'CONFIRM': return 'green'
    case 'CANCEL': return 'red'
    case 'FORWARD': return 'cyan'
    case 'COMPENSATE': return 'volcano'
    default: return 'default'
  }
}

function getStatusColor(st: BranchStatus): string {
  switch (st) {
    case 'SUCCESS': return 'green'
    case 'FAILED': return 'red'
    case 'PENDING': return 'orange'
    case 'TIMEOUT': return 'volcano'
    default: return 'default'
  }
}

async function applyPreset(key: 'hanging' | 'empty_compensation' | 'timeout' | 'normal') {
  presetKey.value = key
  try {
    const res = await sagaTransactionApi.simulateScenario(key)
    report.value = res.report
    message.success(res.message || '分布式事务仿真完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '仿真失败')
  }
}

async function fetchHangingList() {
  loadingHanging.value = true
  try {
    const res = await sagaTransactionApi.listHangingTransactions()
    hangingCount.value = res.total
    message.info(`全网共探测到 ${res.total} 笔未决或异常全局事务`)
  } catch {
    // ignore
  } finally {
    loadingHanging.value = false
  }
}

onMounted(() => {
  applyPreset('hanging')
})
</script>

<style scoped>
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.intro-banner {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.banner-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.banner-icon {
  font-size: 22px;
  color: #0284c7;
  margin-top: 2px;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.banner-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
  margin-top: 4px;
}

.anomaly-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.anomaly-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
}

.card-name {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.card-desc {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.action-bar {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.ctrl-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.hanging-alert-text {
  font-size: 12px;
  color: #dc2626;
}

/* 裁决横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 14px 18px;
  border: 1px solid transparent;
}

.banner-committed {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.banner-hanging {
  background: #fef2f2;
  border-color: #fecaca;
}

.banner-inconsistent {
  background: #faf5ff;
  border-color: #e9d5ff;
}

.banner-timeout {
  background: #fffbeb;
  border-color: #fde68a;
}

.banner-rolled_back {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.verdict-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.verdict-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-tag {
  font-size: 13px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
}

.tag-committed {
  background: #16a34a;
  color: #ffffff;
}

.tag-hanging {
  background: #dc2626;
  color: #ffffff;
}

.tag-inconsistent {
  background: #9333ea;
  color: #ffffff;
}

.tag-timeout {
  background: #d97706;
  color: #ffffff;
}

.tag-rolled_back {
  background: #0284c7;
  color: #ffffff;
}

.verdict-summary {
  font-size: 13px;
  color: #1e293b;
  font-weight: 600;
}

.meta-box {
  font-size: 11px;
  color: #64748b;
}

.sep {
  margin: 0 6px;
  color: #cbd5e1;
}

.branches-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.branches-table {
  background: #ffffff;
}

.svc-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.branch-id {
  font-size: 10px;
  color: #94a3b8;
}

.err-msg {
  font-size: 10px;
  color: #dc2626;
  display: block;
  margin-top: 2px;
}

.remed-card {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 12px 16px;
}

.remed-title {
  font-size: 13px;
  font-weight: 700;
  color: #991b1b;
  margin-bottom: 6px;
}

.remed-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #7f1d1d;
  line-height: 1.6;
}
</style>
