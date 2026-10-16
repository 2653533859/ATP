<template>
  <div class="page-shell cross-db-audit-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <DatabaseOutlined class="hero-icon" />
          <h2 class="page-title">跨微服务异构数据源最终一致性双向稽核对账大盘</h2>
        </div>
        <p class="page-subtitle">
          面向分布式微服务分库与异步事件同步架构，基于业务主键（join_key）双向对齐多源记录，精确识别漏同步（Missing In Target）、幽灵数据（Missing In Source）与字段值冲突，输出自动化对账达标率与数据补偿修复 SQL。
        </p>
      </div>
      <div class="hero-actions">
        <a-space>
          <a-button type="primary" :loading="auditing" @click="handleRunAudit">
            <ThunderboltOutlined /> 执行跨库一致性对账
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 参数配置与演练预设 -->
    <a-card size="small" class="control-card">
      <div class="control-grid">
        <div class="config-row">
          <span class="cfg-label">源服务/表:</span>
          <a-input v-model:value="configForm.source_service" style="width: 140px" size="small" />
          <span>/</span>
          <a-input v-model:value="configForm.source_table" style="width: 130px" size="small" />

          <span class="cfg-label">目标服务/表:</span>
          <a-input v-model:value="configForm.target_service" style="width: 140px" size="small" />
          <span>/</span>
          <a-input v-model:value="configForm.target_table" style="width: 130px" size="small" />

          <span class="cfg-label">关联主键:</span>
          <a-input v-model:value="configForm.join_key" style="width: 110px" size="small" />

          <span class="cfg-label">容差达标阈值:</span>
          <a-input-number v-model:value="configForm.tolerance_threshold_pct" :min="50" :max="100" style="width: 80px" size="small" />
          <span class="unit-text">%</span>
        </div>

        <div class="preset-row">
          <span class="preset-label">快捷对账演练预设:</span>
          <a-space :size="8" wrap>
            <a-button
              size="small"
              :type="presetKey === 'reconciled' ? 'primary' : 'default'"
              @click="applyPreset('reconciled')"
            >
              🟢 场景 1: 完全一致对账 (100.0% RECONCILED 零差异)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'missing_target' ? 'primary' : 'default'"
              danger
              @click="applyPreset('missing_target')"
            >
              🔴 场景 2: 下游漏同步缺失 (生成 INSERT 补偿 SQL)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'field_mismatch' ? 'primary' : 'default'"
              @click="applyPreset('field_mismatch')"
            >
              🟠 场景 3: 业务字段冲突 (生成 UPDATE 修复 SQL)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'ghost_source' ? 'primary' : 'default'"
              @click="applyPreset('ghost_source')"
            >
              🟣 场景 4: 存在幽灵冗余数据 (生成 DELETE 核查 SQL)
            </a-button>
          </a-space>
        </div>
      </div>
    </a-card>

    <!-- 最终对账裁决大横幅 (Verdict Banner) -->
    <div v-if="report" class="verdict-banner" :class="`banner-verdict-${report.verdict.toLowerCase()}`">
      <div class="banner-top">
        <div class="verdict-status-box">
          <span class="verdict-badge" :class="`badge-${report.verdict.toLowerCase()}`">
            {{ report.verdict }}
          </span>
          <span class="verdict-summary">{{ report.verdict_summary }}</span>
        </div>
        <div class="score-display">
          <div class="score-lbl">数据最终一致性达标率</div>
          <div class="score-num" :class="`score-${report.verdict.toLowerCase()}`">
            {{ report.consistency_rate_pct }}%
          </div>
        </div>
      </div>

      <!-- 4 项指标统计 KPI 卡片 -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-val text-blue">{{ report.total_records_checked }}</div>
          <div class="kpi-lbl">已稽核比对总记录数</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-val text-green">{{ report.consistent_records_count }}</div>
          <div class="kpi-lbl">双向完全一致记录数</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-val text-red">{{ report.mismatched_records_count }}</div>
          <div class="kpi-lbl">检出数据不一致/撕裂记录数</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-val text-orange">{{ report.missing_in_target_count + report.missing_in_source_count }}</div>
          <div class="kpi-lbl">跨库单边缺失记录数</div>
        </div>
      </div>
    </div>

    <!-- 差异明细与补偿修复 SQL 表格 -->
    <div v-if="report" class="diff-section">
      <div class="section-title">
        <span>跨微服务异构数据源差分明细与补偿修复指令</span>
        <a-tag color="blue">共 {{ report.diff_records.length }} 处差分项</a-tag>
      </div>

      <div v-if="report.diff_records.length === 0" class="empty-diff">
        <a-empty description="当前两端数据库数据完全对齐一致，零差异记录！" />
      </div>

      <a-table
        v-else
        :data-source="report.diff_records"
        :columns="tableColumns"
        row-key="join_key_value"
        size="small"
        :pagination="false"
        bordered
        class="diff-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'join_key'">
            <code>{{ record.join_key_value }}</code>
          </template>

          <template v-if="column.key === 'category'">
            <a-tag :color="getCategoryTagColor(record.category)">
              {{ record.category }}
            </a-tag>
          </template>

          <template v-if="column.key === 'field_diffs'">
            <div v-if="!record.field_diffs.length" class="no-field-diff">
              <span v-if="record.category === 'MISSING_IN_TARGET'">目标库整行记录未找到</span>
              <span v-else-if="record.category === 'MISSING_IN_SOURCE'">源库整行记录未找到 (幽灵数据)</span>
            </div>
            <div v-else class="field-diffs-list">
              <div v-for="fd in record.field_diffs" :key="fd.field_name" class="fd-item">
                <span class="fd-name">{{ fd.field_name }}:</span>
                <span class="fd-src">源='<code>{{ fd.source_value }}</code>'</span>
                <span>vs</span>
                <span class="fd-tgt">目标='<code>{{ fd.target_value }}</code>'</span>
              </div>
            </div>
          </template>

          <template v-if="column.key === 'remediation_sql'">
            <div class="sql-box">
              <pre class="sql-code">{{ record.remediation_sql }}</pre>
              <a-button size="small" type="link" @click="copySql(record.remediation_sql)">
                <CopyOutlined /> 复制 SQL
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  DatabaseOutlined,
  ThunderboltOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  crossDbAuditApi,
  type ConsistencyAuditReport,
} from '@/api/distributedConsistency'

const auditing = ref(false)
const report = ref<ConsistencyAuditReport | null>(null)
const presetKey = ref<'reconciled' | 'missing_target' | 'field_mismatch' | 'ghost_source'>('reconciled')

const configForm = reactive({
  source_service: 'order-service',
  source_table: 'orders',
  target_service: 'pay-service',
  target_table: 'payments',
  join_key: 'order_id',
  tolerance_threshold_pct: 98.0,
})

const tableColumns = [
  { title: '业务主键 (Join Key)', key: 'join_key', width: 170 },
  { title: '差异模式分类', key: 'category', width: 180 },
  { title: '字段级取值差分', key: 'field_diffs', width: 280 },
  { title: '补偿修复 SQL 脚本', key: 'remediation_sql' },
]

function getCategoryTagColor(cat: string): string {
  switch (cat) {
    case 'MISSING_IN_TARGET': return 'red'
    case 'MISSING_IN_SOURCE': return 'purple'
    case 'FIELD_VALUE_MISMATCH': return 'orange'
    default: return 'green'
  }
}

// 演练预设
const PRESETS = {
  reconciled: {
    source: [
      { order_id: 'ord_1001', amount: 99.0, status: 'PAID', user_id: 'u_1' },
      { order_id: 'ord_1002', amount: 199.5, status: 'REFUNDED', user_id: 'u_2' },
    ],
    target: [
      { order_id: 'ord_1001', amount: 99.0, status: 'PAID', user_id: 'u_1' },
      { order_id: 'ord_1002', amount: 199.5, status: 'REFUNDED', user_id: 'u_2' },
    ],
  },
  missing_target: {
    source: [
      { order_id: 'ord_1001', amount: 99.0, status: 'PAID', user_id: 'u_1' },
      { order_id: 'ord_1002', amount: 350.0, status: 'PAID', user_id: 'u_3' },  // 目标缺失
    ],
    target: [
      { order_id: 'ord_1001', amount: 99.0, status: 'PAID', user_id: 'u_1' },
    ],
  },
  field_mismatch: {
    source: [
      { order_id: 'ord_1001', amount: 120.0, status: 'PAID', user_id: 'u_1' },
    ],
    target: [
      { order_id: 'ord_1001', amount: 100.0, status: 'PENDING', user_id: 'u_1' },  // 金额与状态不一致
    ],
  },
  ghost_source: {
    source: [
      { order_id: 'ord_1001', amount: 99.0, status: 'PAID', user_id: 'u_1' },
    ],
    target: [
      { order_id: 'ord_1001', amount: 99.0, status: 'PAID', user_id: 'u_1' },
      { order_id: 'ord_ghost_999', amount: 50.0, status: 'PAID', user_id: 'u_x' }, // 幽灵数据
    ],
  },
}

function applyPreset(key: 'reconciled' | 'missing_target' | 'field_mismatch' | 'ghost_source') {
  presetKey.value = key
  handleRunAudit()
}

async function handleRunAudit() {
  auditing.value = true
  try {
    const p = PRESETS[presetKey.value]
    const res = await crossDbAuditApi.executeAudit({
      rule_name: `${configForm.source_service}与${configForm.target_service}双向对账`,
      source_service: configForm.source_service,
      source_table: configForm.source_table,
      target_service: configForm.target_service,
      target_table: configForm.target_table,
      join_key: configForm.join_key,
      tolerance_threshold_pct: configForm.tolerance_threshold_pct,
      source_records: p.source,
      target_records: p.target,
    })
    report.value = res.report
    message.success(res.message || '对账稽核执行完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '对账执行失败')
  } finally {
    auditing.value = false
  }
}

function copySql(sql: string) {
  if (!sql) return
  void navigator.clipboard.writeText(sql)
  message.success('已复制补偿 SQL 语句')
}

onMounted(() => {
  handleRunAudit()
})
</script>

<style scoped>
.cross-db-audit-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
}

.hero-icon {
  font-size: 20px;
  color: #0284c7;
}

.control-card {
  border-radius: 8px;
}

.control-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cfg-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
  margin-left: 6px;
}

.unit-text {
  font-size: 12px;
  color: #64748b;
  margin-left: -4px;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

/* 裁决大横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid transparent;
}

.banner-verdict-reconciled {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.banner-verdict-warning {
  background: #fffbeb;
  border-color: #fde68a;
}

.banner-verdict-critical {
  background: #fef2f2;
  border-color: #fecaca;
}

.banner-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.verdict-status-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.verdict-badge {
  font-size: 13px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.badge-reconciled {
  background: #16a34a;
  color: #ffffff;
}

.badge-warning {
  background: #d97706;
  color: #ffffff;
}

.badge-critical {
  background: #dc2626;
  color: #ffffff;
}

.verdict-summary {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.score-display {
  text-align: right;
}

.score-lbl {
  font-size: 11px;
  color: #64748b;
}

.score-num {
  font-size: 24px;
  font-weight: 800;
  line-height: 1.2;
}

.score-reconciled {
  color: #16a34a;
}

.score-warning {
  color: #d97706;
}

.score-critical {
  color: #dc2626;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
  text-align: center;
}

.kpi-val {
  font-size: 20px;
  font-weight: 800;
}

.kpi-lbl {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.text-blue {
  color: #0284c7;
}

.text-green {
  color: #16a34a;
}

.text-red {
  color: #dc2626;
}

.text-orange {
  color: #ea580c;
}

.diff-section {
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

.empty-diff {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 32px;
}

.diff-table {
  background: #ffffff;
}

.field-diffs-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
}

.fd-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.fd-name {
  font-weight: 600;
  color: #0f172a;
}

.sql-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sql-code {
  font-family: Consolas, monospace;
  font-size: 11px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 4px 8px;
  border-radius: 4px;
  margin: 0;
  color: #0369a1;
  max-width: 440px;
  overflow-x: auto;
  white-space: pre;
}

.no-field-diff {
  font-size: 11px;
  color: #64748b;
  font-style: italic;
}
</style>
