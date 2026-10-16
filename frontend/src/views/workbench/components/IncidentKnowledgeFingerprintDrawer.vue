<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="历史已知缺陷经验知识库与向量指纹匹配控制台"
    destroy-on-close
    class="fingerprint-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制介绍 Banner -->
      <div class="intro-banner">
        <div class="banner-top">
          <BookOutlined class="banner-icon" />
          <div class="banner-texts">
            <div class="banner-title">历史已知缺陷向量指纹特征相似度检索与经验推荐 (T3.2)</div>
            <div class="banner-desc">
              对自动化测试中的异常堆栈提取抗噪声语义指纹（自动消除动态行号、内存物理地址、UUID 与时间戳干扰）。基于包含重叠度、余弦与 Jaccard 双重加权相似度，秒级检出历史同类缺陷并直接推荐已验证解决方案与关联 Jira/GitHub 工单。
            </div>
          </div>
        </div>
      </div>

      <!-- 双选项卡 -->
      <a-tabs v-model:activeKey="activeTab" size="small" class="drawer-tabs">
        <!-- Tab 1: 指纹相似度匹配与推荐 -->
        <a-tab-pane key="match" tab="🔍 异常指纹相似度匹配与方案推荐">
          <div class="tab-box">
            <!-- 快速演练预设 -->
            <div class="preset-row">
              <span class="preset-label">快捷匹配场景:</span>
              <a-space :size="8" wrap>
                <a-button
                  size="small"
                  :type="presetKey === 'deadlock' ? 'primary' : 'default'"
                  danger
                  @click="applyPreset('deadlock')"
                >
                  场景 1: MySQL 订单行锁并发死锁 (高相似度命中 JIRA-4891)
                </a-button>
                <a-button
                  size="small"
                  :type="presetKey === 'redis_timeout' ? 'primary' : 'default'"
                  @click="applyPreset('redis_timeout')"
                >
                  场景 2: Redis 连接池耗尽超时 (高相似度命中 JIRA-5120)
                </a-button>
                <a-button
                  size="small"
                  :type="presetKey === 'new_bug' ? 'primary' : 'default'"
                  @click="applyPreset('new_bug')"
                >
                  场景 3: 全新孤立异常 (零命中提示新问题)
                </a-button>
              </a-space>
            </div>

            <!-- 输入表单 -->
            <div class="match-form">
              <a-space :size="12" align="center" wrap>
                <span class="f-lbl">微服务名称:</span>
                <a-input v-model:value="matchForm.service_name" style="width: 160px" size="small" />

                <span class="f-lbl">最低相似度阈值:</span>
                <a-input-number v-model:value="matchForm.min_similarity" :min="0.1" :max="1.0" :step="0.05" style="width: 80px" size="small" />

                <a-button type="primary" size="small" :loading="matching" @click="handleRunMatch">
                  <ThunderboltOutlined /> 执行指纹向量相似度检索
                </a-button>
              </a-space>

              <div class="input-block">
                <span class="block-lbl">异常报错摘要:</span>
                <a-input v-model:value="matchForm.error_message" size="small" />
              </div>

              <div class="input-block">
                <span class="block-lbl">异常堆栈文本 (Stack Trace):</span>
                <a-textarea v-model:value="matchForm.stack_trace" :rows="2" size="small" />
              </div>
            </div>

            <!-- 匹配结果大横幅 (Match Result Banner) -->
            <div v-if="matchReport" class="match-banner" :class="matchReport.matches_count > 0 ? 'banner-matched' : 'banner-unmatched'">
              <div class="banner-head">
                <div class="banner-title-box">
                  <span class="matched-badge" :class="matchReport.matches_count > 0 ? 'badge-found' : 'badge-none'">
                    {{ matchReport.matches_count > 0 ? `🎯 命中 ${matchReport.matches_count} 条历史相似缺陷` : '⚪ 未检索到相似已知缺陷' }}
                  </span>
                  <span class="banner-summary">{{ matchReport.recommendation_summary }}</span>
                </div>
              </div>

              <!-- 推荐解决方案卡片 -->
              <div v-if="matchReport.best_match_resolution" class="solution-card">
                <div class="sol-top">
                  <span class="sol-title">💡 推荐历史已验证解决方案 (Verified Resolution)</span>
                  <a-button size="small" type="link" @click="copyResolution(matchReport.best_match_resolution)">
                    <CopyOutlined /> 复制方案
                  </a-button>
                </div>
                <div class="sol-body">{{ matchReport.best_match_resolution }}</div>
              </div>
            </div>

            <!-- 相似度比对列表 -->
            <div v-if="matchReport && matchReport.matches.length > 0" class="match-list-section">
              <div class="sec-title">相似度匹配命中明细</div>
              <div class="match-cards">
                <div
                  v-for="(m, idx) in matchReport.matches"
                  :key="idx"
                  class="match-card"
                  :class="`card-tier-${m.match_tier.toLowerCase()}`"
                >
                  <div class="card-top">
                    <div class="card-title">
                      <a-tag :color="getTierTagColor(m.match_tier)">{{ m.match_tier }} ({{ Math.round(m.similarity_score * 100) }}%)</a-tag>
                      <strong>{{ m.incident.title }}</strong>
                      <code class="svc-lbl">[{{ m.incident.service_name }}]</code>
                    </div>
                    <a-tag v-if="m.incident.external_ticket_ref" color="purple">
                      {{ m.incident.external_ticket_ref }}
                    </a-tag>
                  </div>

                  <div class="card-cause">
                    <strong>根因说明:</strong> {{ m.incident.root_cause_explanation }}
                  </div>

                  <div class="matched-tokens">
                    <span class="tokens-lbl">命中指纹 Token:</span>
                    <a-tag v-for="tk in m.matched_tokens" :key="tk" size="small">
                      {{ tk }}
                    </a-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- Tab 2: 已知缺陷经验知识库管理 -->
        <a-tab-pane key="repository" tab="📚 已知缺陷经验库清单">
          <div class="tab-box">
            <div class="tab-header">
              <a-space>
                <a-button size="small" :loading="loadingIncidents" @click="fetchIncidents">
                  <ReloadOutlined /> 刷新知识库
                </a-button>
                <span class="total-count">共登记 <strong>{{ incidents.length }}</strong> 条企业级缺陷经验</span>
              </a-space>
            </div>

            <a-table
              :data-source="incidents"
              :columns="incidentColumns"
              row-key="incident_id"
              size="small"
              :pagination="false"
              bordered
              class="incidents-table"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'title'">
                  <div>
                    <strong>{{ record.title }}</strong>
                    <code class="sub-id">({{ record.incident_id }})</code>
                  </div>
                </template>

                <template v-if="column.key === 'service_name'">
                  <a-tag color="blue">{{ record.service_name }}</a-tag>
                </template>

                <template v-if="column.key === 'category'">
                  <a-tag>{{ record.category }}</a-tag>
                </template>

                <template v-if="column.key === 'resolution'">
                  <div class="res-text">{{ record.verified_resolution }}</div>
                </template>

                <template v-if="column.key === 'ticket'">
                  <a-tag v-if="record.external_ticket_ref" color="purple">{{ record.external_ticket_ref }}</a-tag>
                  <span v-else class="text-muted">无</span>
                </template>

                <template v-if="column.key === 'action'">
                  <a-popconfirm
                    title="确定从知识库删除此经验条目吗？"
                    ok-text="删除"
                    cancel-text="取消"
                    @confirm="handleDeleteIncident(record.incident_id)"
                  >
                    <a-button size="small" type="link" danger>
                      删除
                    </a-button>
                  </a-popconfirm>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  BookOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  incidentFingerprintApi,
  type IncidentMatchReport,
  type IncidentKnowledgeItem,
} from '@/api/rootCauseDiagnosis'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

function handleClose() {
  emit('update:open', false)
}

const activeTab = ref<'match' | 'repository'>('match')
const matching = ref(false)
const loadingIncidents = ref(false)
const matchReport = ref<IncidentMatchReport | null>(null)
const incidents = ref<IncidentKnowledgeItem[]>([])
const presetKey = ref<'deadlock' | 'redis_timeout' | 'new_bug'>('deadlock')

const matchForm = reactive({
  service_name: 'order-service',
  error_message: 'pymysql.err.OperationalError: (1213, Deadlock found when trying to get lock)',
  stack_trace: 'File "order_service.py", line 299, in execute_checkout',
  min_similarity: 0.50,
})

const incidentColumns = [
  { title: '缺陷经验标题', key: 'title', width: 240 },
  { title: '微服务', key: 'service_name', width: 140 },
  { title: '分类', key: 'category', width: 110 },
  { title: '已验证解决方案', key: 'resolution' },
  { title: '关联工单', key: 'ticket', width: 120 },
  { title: '操作', key: 'action', width: 90 },
]

function getTierTagColor(tier: string): string {
  switch (tier) {
    case 'EXACT_MATCH': return 'green'
    case 'HIGH_SIMILARITY': return 'blue'
    case 'MEDIUM_SIMILARITY': return 'orange'
    default: return 'default'
  }
}

// 演练预设
const PRESETS = {
  deadlock: {
    service_name: 'order-service',
    error_message: "pymysql.err.OperationalError: (1213, 'Deadlock found when trying to get lock at 0xdeadbeef')",
    stack_trace: 'File "order_service.py", line 299, in execute_checkout',
    min_similarity: 0.50,
    mock_known: {
      title: 'MySQL 订单结算事务行锁并发争用死锁',
      category: 'DATABASE',
      service_name: 'order-service',
      error_pattern: 'Deadlock found when trying to get lock; try restarting transaction',
      root_cause_explanation: '高并发下不同事务更新订单行与用户优惠券表的加锁顺序相反导致循环等待死锁。',
      verified_resolution: '统一加锁顺序: 必须按 order_id 升序排列加锁，并调小 innodb_lock_wait_timeout。',
      external_ticket_ref: 'JIRA-4891',
      incident_id: 'inc_mysql_deadlock',
    },
  },
  redis_timeout: {
    service_name: 'cache-service',
    error_message: 'redis.exceptions.ConnectionError: ConnectionPool timeout while waiting for connection',
    stack_trace: 'File "redis_client.py", line 80, in get_connection',
    min_similarity: 0.50,
    mock_known: {
      title: 'Redis 连接池耗尽超时',
      category: 'TIMEOUT',
      service_name: 'cache-service',
      error_pattern: 'ConnectionPool timeout while waiting for connection',
      root_cause_explanation: 'Redis 连接池 max_connections 偏小且连接未在 finally 块释放导致泄露。',
      verified_resolution: '连接池扩容至 200 并采用上下文管理器确保 auto-close。',
      external_ticket_ref: 'JIRA-5120',
      incident_id: 'inc_redis_timeout',
    },
  },
  new_bug: {
    service_name: 'new-service',
    error_message: 'UnknownSpecialException: 0x9999 totally unexpected crash',
    stack_trace: 'File "unknown.py", line 1',
    min_similarity: 0.85,
    mock_known: null,
  },
}

async function applyPreset(key: 'deadlock' | 'redis_timeout' | 'new_bug') {
  presetKey.value = key
  const p = PRESETS[key]
  matchForm.service_name = p.service_name
  matchForm.error_message = p.error_message
  matchForm.stack_trace = p.stack_trace
  matchForm.min_similarity = p.min_similarity

  if (p.mock_known) {
    try {
      await incidentFingerprintApi.registerIncident(p.mock_known)
    } catch {
      // ignore
    }
  }

  await handleRunMatch()
}

async function handleRunMatch() {
  matching.value = true
  try {
    const res = await incidentFingerprintApi.match({
      service_name: matchForm.service_name,
      error_message: matchForm.error_message,
      stack_trace: matchForm.stack_trace,
      min_similarity: matchForm.min_similarity,
    })
    matchReport.value = res
    message.success('指纹相似度检索完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '匹配检索失败')
  } finally {
    matching.value = false
  }
}

async function fetchIncidents() {
  loadingIncidents.value = true
  try {
    const res = await incidentFingerprintApi.listIncidents()
    incidents.value = res.incidents
  } catch {
    // ignore
  } finally {
    loadingIncidents.value = false
  }
}

async function handleDeleteIncident(iid: string) {
  try {
    await incidentFingerprintApi.deleteIncident(iid)
    message.success('已从知识库删除该条目')
    await fetchIncidents()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '删除失败')
  }
}

function copyResolution(res: string) {
  void navigator.clipboard.writeText(res)
  message.success('已复制解决方案')
}

onMounted(async () => {
  await applyPreset('deadlock')
  await fetchIncidents()
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

.drawer-tabs {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
}

.tab-box {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 6px;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.match-form {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.f-lbl {
  font-size: 12px;
  color: #64748b;
}

.input-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.block-lbl {
  font-size: 11px;
  color: #475569;
  font-weight: 500;
}

/* 匹配横幅 */
.match-banner {
  border-radius: 8px;
  padding: 14px 18px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.banner-matched {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.banner-unmatched {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.banner-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.banner-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.matched-badge {
  font-size: 13px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
}

.badge-found {
  background: #16a34a;
  color: #ffffff;
}

.badge-none {
  background: #64748b;
  color: #ffffff;
}

.banner-summary {
  font-size: 13px;
  color: #1e293b;
  font-weight: 600;
}

.solution-card {
  background: #ffffff;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  padding: 10px 14px;
}

.sol-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.sol-title {
  font-size: 12px;
  font-weight: 700;
  color: #166534;
}

.sol-body {
  font-size: 12px;
  color: #14532d;
  line-height: 1.5;
}

.match-list-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sec-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.match-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.match-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
}

.card-tier-exact_match {
  border-left: 3px solid #16a34a;
}

.card-tier-high_similarity {
  border-left: 3px solid #0284c7;
}

.card-tier-medium_similarity {
  border-left: 3px solid #f59e0b;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.svc-lbl {
  color: #64748b;
  font-size: 11px;
}

.card-cause {
  font-size: 11px;
  color: #475569;
  margin-bottom: 8px;
}

.matched-tokens {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.tokens-lbl {
  font-size: 10px;
  color: #94a3b8;
}

.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.total-count {
  font-size: 12px;
  color: #64748b;
}

.incidents-table {
  background: #ffffff;
}

.sub-id {
  font-size: 10px;
  color: #94a3b8;
  margin-left: 4px;
}

.res-text {
  font-size: 11px;
  color: #334155;
  line-height: 1.4;
}

.text-muted {
  color: #94a3b8;
}
</style>
