<template>
  <div class="page-shell schema-dashboard-view">
    <!-- 顶部导航与操作栏 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <DatabaseOutlined class="hero-icon" />
          <h2 class="page-title">数据库 Schema 结构与索引变更漂移双向比对大盘</h2>
          <span class="live-dot" />
          <span class="muted-text text-xs">8 类表结构差异模式 · 破坏性变更评级 · 自动化修复 DDL 导出</span>
        </div>
        <p class="hero-subtitle">
          深度比对生产基准与测试环境表结构、字段类型、非空约束与唯一/普通索引差异，防止 SQL 执行崩溃与性能全表扫描。
        </p>
      </div>
      <div class="hero-actions">
        <a-space>
          <a-button type="primary" :loading="comparing" @click="handleCompare">
            <ThunderboltOutlined /> 执行数据库 Schema 深度比对
          </a-button>
          <a-button :loading="loading" @click="fetchHistory">
            <ReloadOutlined /> 刷新报告
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 机制说明 Banner -->
    <div class="mechanism-banner">
      <div class="banner-icon-col">
        <AuditOutlined class="banner-icon" />
      </div>
      <div class="banner-texts">
        <div class="banner-title">数据库表结构契约演化兼容性与索引比对引擎 (T2.2)</div>
        <div class="banner-desc">
          自动识别整表缺失 (<code>TABLE_MISSING</code>)、列缺失 (<code>COLUMN_MISSING</code>)、类型突变 (<code>COLUMN_TYPE_MISMATCH</code>)、非空约束漂移与索引缺失等 8 类差异模式，评估破坏性风险等级并自动合成可执行的数据库修复 DDL 补丁。
        </div>
      </div>
    </div>

    <!-- 场景选择控制栏 -->
    <div class="config-section">
      <div class="section-title">对比环境与数据库配置</div>
      <div class="config-row">
        <div class="env-group">
          <span class="label">基准环境:</span>
          <a-select v-model:value="baseEnv" size="small" class="w-32">
            <a-select-option value="production">production (生产)</a-select-option>
            <a-select-option value="staging">staging (预发)</a-select-option>
          </a-select>
          <span class="arrow-sep">➔</span>
          <span class="label">目标环境:</span>
          <a-select v-model:value="targetEnv" size="small" class="w-32">
            <a-select-option value="testing">testing (测试)</a-select-option>
            <a-select-option value="development">development (开发)</a-select-option>
          </a-select>
        </div>

        <div class="preset-group">
          <span class="label">演练场景:</span>
          <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
            <a-radio-button value="multi_table_drift">典型综合表结构漂移 (用户与订单)</a-radio-button>
            <a-radio-button value="index_missing_only">高并发关键索引缺失</a-radio-button>
            <a-radio-button value="identical_schema">完全同步一致基准</a-radio-button>
          </a-radio-group>
        </div>
      </div>
    </div>

    <!-- 4 大核心 KPI 统计卡片 -->
    <a-row :gutter="[16, 16]" class="kpi-row">
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">检查数据表总数</div>
          <div class="stat-value text-primary">{{ currentReport?.total_tables_checked ?? 0 }} <span class="unit">张</span></div>
          <div class="stat-trend">两环境涉及数据库全量表</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">表结构契约兼容率</div>
          <div class="stat-value" :class="getScoreColorClass(currentReport?.compatibility_rate_pct ?? 100)">
            {{ currentReport?.compatibility_rate_pct ?? 100 }}%
          </div>
          <div class="stat-trend">完全一致表占比</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">表结构与索引差异数</div>
          <div class="stat-value text-warning">{{ currentReport?.drift_items_count ?? 0 }} <span class="unit">项</span></div>
          <div class="stat-trend">列/类型/约束/索引变异</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">最高破坏性风险等级</div>
          <div class="stat-value" :class="getSeverityColorClass(currentReport?.highest_severity ?? 'IDENTICAL')">
            {{ currentReport?.highest_severity ?? 'IDENTICAL' }}
          </div>
          <div class="stat-trend">生产变更发布风险指数</div>
        </div>
      </a-col>
    </a-row>

    <!-- 工作台：左侧差异矩阵 + 右侧自动合成修复 DDL 脚本 -->
    <div class="workbench-layout">
      <!-- 左侧：表结构差异矩阵表格 -->
      <div class="matrix-panel">
        <div class="panel-header">
          <span class="panel-title"><TableOutlined /> 表结构与索引漂移差分矩阵</span>
          <span class="text-xs text-muted">共 {{ currentReport?.drifts.length ?? 0 }} 项差异</span>
        </div>

        <a-table
          :data-source="currentReport?.drifts ?? []"
          :columns="columns"
          :row-key="(r: any) => `${r.table_name}_${r.object_name}_${r.drift_type}`"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'table_name'">
              <strong>{{ record.table_name }}</strong>
            </template>
            <template v-else-if="column.key === 'object_name'">
              <code class="obj-tag">{{ record.object_name }}</code>
            </template>
            <template v-else-if="column.key === 'drift_type'">
              <a-tag :color="getDriftTypeColor(record.drift_type)">{{ record.drift_type }}</a-tag>
            </template>
            <template v-else-if="column.key === 'severity'">
              <a-tag :color="getSeverityTagColor(record.severity)">{{ record.severity }}</a-tag>
            </template>
            <template v-else-if="column.key === 'risk_explanation'">
              <span class="text-xs">{{ record.risk_explanation }}</span>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 右侧：自动化迁移修复 DDL 脚本控制台 -->
      <div class="ddl-panel">
        <div class="panel-header">
          <span class="panel-title"><CodeOutlined /> 自动合成数据库迁移修复 DDL 脚本</span>
          <a-button
            size="small"
            type="primary"
            :disabled="!currentReport?.remediation_ddl_script"
            @click="handleCopyScript"
          >
            <CopyOutlined /> 一键复制 DDL
          </a-button>
        </div>

        <div v-if="currentReport?.remediation_ddl_script" class="ddl-container">
          <pre class="ddl-code"><code>{{ currentReport.remediation_ddl_script }}</code></pre>
        </div>
        <div v-else class="empty-ddl">
          <a-empty description="当前两环境表结构完全同步，无需执行修复 DDL 脚本" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  DatabaseOutlined,
  AuditOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  TableOutlined,
  CodeOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  dbSchemaDriftApi,
  type SchemaDriftReport,
} from '@/api/cloudNativeCluster'

const loading = ref(false)
const comparing = ref(false)
const baseEnv = ref('production')
const targetEnv = ref('testing')
const selectedPreset = ref<'multi_table_drift' | 'index_missing_only' | 'identical_schema'>('multi_table_drift')
const currentReport = ref<SchemaDriftReport | null>(null)

const PRESET_SCHEMAS = {
  multi_table_drift: {
    database_name: 'commerce_db',
    base: [
      {
        table_name: 'users',
        columns: [
          { name: 'id', data_type: 'BIGINT', nullable: false, is_primary_key: true },
          { name: 'email', data_type: 'VARCHAR(255)', nullable: false },
          { name: 'phone', data_type: 'VARCHAR(32)', nullable: true },
          { name: 'created_at', data_type: 'TIMESTAMP', nullable: false },
        ],
        indexes: [
          { name: 'uniq_users_email', columns: ['email'], is_unique: true },
        ],
      },
      {
        table_name: 'orders',
        columns: [
          { name: 'order_id', data_type: 'VARCHAR(64)', nullable: false, is_primary_key: true },
          { name: 'total_amount', data_type: 'DECIMAL', nullable: false },
        ],
        indexes: [],
      },
    ],
    target: [
      {
        table_name: 'users',
        columns: [
          { name: 'id', data_type: 'BIGINT', nullable: false, is_primary_key: true },
          { name: 'email', data_type: 'VARCHAR(255)', nullable: false },
          // 缺失 phone 列
          { name: 'created_at', data_type: 'BIGINT', nullable: false }, // 类型不一致 TIMESTAMP -> BIGINT
        ],
        indexes: [], // 缺失唯一索引
      },
      // 缺失 orders 整表
    ],
  },
  index_missing_only: {
    database_name: 'analytics_db',
    base: [
      {
        table_name: 'event_logs',
        columns: [
          { name: 'id', data_type: 'BIGINT', nullable: false, is_primary_key: true },
          { name: 'trace_id', data_type: 'VARCHAR(64)', nullable: false },
        ],
        indexes: [
          { name: 'idx_event_trace_id', columns: ['trace_id'], is_unique: false },
        ],
      },
    ],
    target: [
      {
        table_name: 'event_logs',
        columns: [
          { name: 'id', data_type: 'BIGINT', nullable: false, is_primary_key: true },
          { name: 'trace_id', data_type: 'VARCHAR(64)', nullable: false },
        ],
        indexes: [], // 缺失索引
      },
    ],
  },
  identical_schema: {
    database_name: 'core_db',
    base: [
      {
        table_name: 'app_settings',
        columns: [
          { name: 'id', data_type: 'INT', nullable: false, is_primary_key: true },
          { name: 'config_key', data_type: 'VARCHAR(128)', nullable: false },
        ],
        indexes: [],
      },
    ],
    target: [
      {
        table_name: 'app_settings',
        columns: [
          { name: 'id', data_type: 'INT', nullable: false, is_primary_key: true },
          { name: 'config_key', data_type: 'VARCHAR(128)', nullable: false },
        ],
        indexes: [],
      },
    ],
  },
}


const columns = [
  { title: '数据表', key: 'table_name', width: 140 },
  { title: '差异对象', key: 'object_name', width: 150 },
  { title: '差异模式', key: 'drift_type', width: 150 },
  { title: '严重度', key: 'severity', width: 90 },
  { title: '风险说明', key: 'risk_explanation' },
]

function handlePresetChange() {
  handleCompare()
}

function getDriftTypeColor(type: string) {
  switch (type) {
    case 'TABLE_MISSING': return 'red'
    case 'COLUMN_MISSING': return 'orange'
    case 'COLUMN_TYPE_MISMATCH': return 'purple'
    case 'INDEX_MISSING': return 'cyan'
    default: return 'default'
  }
}

function getSeverityTagColor(sev: string) {
  switch (sev) {
    case 'CRITICAL': return 'red'
    case 'HIGH': return 'orange'
    case 'MEDIUM': return 'gold'
    case 'LOW': return 'default'
    case 'IDENTICAL': return 'green'
    default: return 'default'
  }
}

function getSeverityColorClass(sev: string) {
  switch (sev) {
    case 'CRITICAL': return 'text-danger'
    case 'HIGH': return 'text-warning'
    case 'MEDIUM': return 'text-gold'
    default: return 'text-success'
  }
}

function getScoreColorClass(score: number) {
  if (score >= 90) return 'text-success'
  if (score >= 70) return 'text-warning'
  return 'text-danger'
}

async function handleCompare() {
  comparing.value = true
  try {
    const p = PRESET_SCHEMAS[selectedPreset.value]
    const res = await dbSchemaDriftApi.compare({
      database_name: p.database_name,
      base_env: baseEnv.value,
      target_env: targetEnv.value,
      base_tables: p.base,
      target_tables: p.target,
    })
    currentReport.value = res.report
    message.success(res.message || '数据库表结构比对完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '比对失败')
  } finally {
    comparing.value = false
  }
}

async function fetchHistory() {
  loading.value = true
  try {
    await handleCompare()
  } finally {
    loading.value = false
  }
}

function handleCopyScript() {
  if (!currentReport.value?.remediation_ddl_script) return
  navigator.clipboard.writeText(currentReport.value.remediation_ddl_script)
  message.success('已复制修复 DDL 脚本到剪贴板')
}

onMounted(() => {
  handleCompare()
})
</script>

<style scoped>
.schema-dashboard-view {
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
  color: #2563eb;
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

.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #eff6ff 0%, #e0f2fe 100%);
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #2563eb;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e3a8a;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #3b82f6;
  line-height: 1.5;
}

.config-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 10px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.env-group,
.preset-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.arrow-sep {
  color: #94a3b8;
  font-weight: bold;
}

.w-32 {
  width: 130px;
}

.kpi-row {
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
}

.stat-label {
  font-size: 11px;
  color: #64748b;
}

.stat-value {
  font-size: 22px;
  font-weight: 800;
  margin: 4px 0;
}

.stat-value .unit {
  font-size: 12px;
  font-weight: normal;
  color: #94a3b8;
}

.stat-trend {
  font-size: 11px;
  color: #94a3b8;
}

.text-primary { color: #2563eb; }
.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-danger { color: #dc2626; }
.text-gold { color: #ca8a04; }

.workbench-layout {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 16px;
}

.matrix-panel,
.ddl-panel {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.obj-tag {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #0f172a;
}

.ddl-container {
  background: #0f172a;
  border-radius: 6px;
  padding: 12px 16px;
  max-height: 400px;
  overflow-y: auto;
}

.ddl-code {
  margin: 0;
  color: #38bdf8;
  font-family: monospace;
  font-size: 11px;
  white-space: pre-wrap;
}

.empty-ddl {
  padding: 40px 0;
}

.text-xs {
  font-size: 11px;
}

.text-muted {
  color: #94a3b8;
}
</style>
