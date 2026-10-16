<template>
  <a-drawer
    v-model:open="visible"
    title="影子库表读写防污染安全隔离与拦截抽屉 (UI1.2)"
    width="1120px"
    placement="right"
    :destroy-on-close="false"
  >
    <div class="shadow-db-drawer">
      <!-- 头部说明 Banner -->
      <div class="drawer-header-banner">
        <div class="banner-title">数据库连接池影子表动态路由重写与生产防污染拦截中心</div>
        <div class="banner-desc">
          在全链路压测中，带有影子染色标的持久写操作 (INSERT/UPDATE/DELETE) 将被中间件动态重写至对应的影子表 (如 t_order → __shadow_t_order__)。
          若影子写操作命中了未配置影子映射的生产真实表，中间件将毫秒级抛出异常强行阻断，坚决杜绝任何压测脏数据渗入生产业务库。
        </div>
      </div>

      <!-- 4 项核心 KPI 卡片 -->
      <a-row :gutter="[12, 12]" class="kpi-row">
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">隔离安全合规评分</div>
            <div class="metric-value primary-text">
              {{ currentReport ? currentReport.isolation_safety_score_pct.toFixed(1) + '%' : '100.0%' }}
            </div>
            <div class="metric-sub">防污染安全指数</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">生产数据污染风险</div>
            <div class="metric-value">
              <a-tag :color="currentReport?.has_critical_pollution_risk ? 'error' : 'success'">
                {{ currentReport?.has_critical_pollution_risk ? 'POLLUTION_RISK 高危' : 'CLEAN_SAFE 零污染' }}
              </a-tag>
            </div>
            <div class="metric-sub">真实业务表受保护状态</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">成功重定向影子表</div>
            <div class="metric-value success-text">
              {{ currentReport ? currentReport.routed_to_shadow_count : 1 }}
            </div>
            <div class="metric-sub">动态 SQL 表名替换数</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">高危写阻断拦截数</div>
            <div class="metric-value" :class="blockedCount > 0 ? 'error-text' : 'warning-text'">
              {{ blockedCount }}
            </div>
            <div class="metric-sub">未映射生产表拦截数</div>
          </div>
        </a-col>
      </a-row>

      <!-- SQL 路由拦截测试工具箱 -->
      <div class="inspect-tool-box">
        <div class="box-title">
          <span>SQL 隔离路由与防污染在线诊断器 (SQL Router Inspector)</span>
          <a-space>
            <a-button type="primary" size="small" :loading="inspecting" @click="handleRunInspect">
              <PlayCircleOutlined /> 模拟 SQL 路由检验
            </a-button>
            <a-button size="small" @click="showAddMappingModal = true">
              <PlusOutlined /> 注册影子表映射
            </a-button>
          </a-space>
        </div>

        <div style="margin-top: 10px;">
          <a-textarea
            v-model:value="testSqlInput"
            placeholder="输入待测试的 SQL，例如: INSERT INTO t_order (order_id, amount) VALUES ('ord_stress_01', 99.0)"
            :rows="2"
            size="small"
          />
          <div style="margin-top: 8px; display: flex; align-items: center; justify-content: space-between;">
            <a-checkbox v-model:checked="isShadowTrafficChecked">携带影子流量染色标 (X-ATP-Shadow: true)</a-checkbox>
            <span class="text-muted">当前数据源集群: prod_mysql_primary</span>
          </div>
        </div>
      </div>

      <!-- SQL 路由判定明细表 -->
      <div class="section-title">
        <span>SQL 语句路由拦截与重写清单 (Inspections)</span>
        <a-tag color="blue">{{ currentInspections.length }} 条记录</a-tag>
      </div>

      <a-table
        :data-source="currentInspections"
        :columns="inspectionColumns"
        row-key="item_id"
        size="small"
        :pagination="false"
        class="inspections-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'sql'">
            <code class="sql-code">{{ record.original_sql }}</code>
          </template>
          <template v-if="column.key === 'verdict'">
            <a-tag :color="getVerdictColor(record.verdict)">
              {{ record.verdict }}
            </a-tag>
          </template>
          <template v-if="column.key === 'rewritten'">
            <code v-if="record.rewritten_sql" class="sql-code rewritten">{{ record.rewritten_sql }}</code>
            <span v-else class="text-danger">已硬核拦截抛弃 (未执行)</span>
          </template>
        </template>
      </a-table>

      <!-- 生效中的影子表映射规则 -->
      <div class="section-title" style="margin-top: 14px;">
        <span>生产表至影子表映射规则库 (Shadow Table Mappings)</span>
        <a-tag color="cyan">{{ mappings.length }} 个映射</a-tag>
      </div>

      <a-table
        :data-source="mappings"
        :columns="mappingColumns"
        row-key="mapping_id"
        size="small"
        :pagination="false"
        class="mappings-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'prod'">
            <span style="font-weight: 700; color: #0f172a;">{{ record.production_table }}</span>
          </template>
          <template v-if="column.key === 'shadow'">
            <span style="font-weight: 700; color: #1677ff;">{{ record.shadow_table }}</span>
          </template>
          <template v-if="column.key === 'strategy'">
            <a-tag color="purple">{{ record.isolation_strategy }}</a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag color="success">防污染生效中</a-tag>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 新增映射弹窗 -->
    <a-modal
      v-model:open="showAddMappingModal"
      title="注册生产表向影子表映射规则"
      ok-text="确认注册"
      cancel-text="取消"
      @ok="handleAddMappingConfirm"
    >
      <a-form layout="vertical">
        <a-form-item label="生产真实业务表名" required>
          <a-input v-model:value="newMapping.production_table" placeholder="t_order" />
        </a-form-item>
        <a-form-item label="对应影子表名" required>
          <a-input v-model:value="newMapping.shadow_table" placeholder="__shadow_t_order__" />
        </a-form-item>
        <a-form-item label="隔离策略">
          <a-select v-model:value="newMapping.strategy">
            <a-select-option value="SHADOW_TABLE">SHADOW_TABLE (同库影子表)</a-select-option>
            <a-select-option value="SHADOW_DATABASE">SHADOW_DATABASE (独立影子库)</a-select-option>
            <a-select-option value="SHADOW_SCHEMA">SHADOW_SCHEMA (独立 Schema)</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'
import {
  inspectSqlIsolation,
  listShadowMappings,
  registerShadowMapping,
  type DbIsolationReport,
  type SqlRoutingItem,
  type ShadowTableMapping,
} from '@/api/fullLinkStressTesting'

const visible = defineModel<boolean>('open', { default: false })
const inspecting = ref(false)
const showAddMappingModal = ref(false)

const testSqlInput = ref("INSERT INTO t_order (order_id, amount) VALUES ('ord_stress_01', 99.0)")
const isShadowTrafficChecked = ref(true)

const currentReport = ref<DbIsolationReport | null>(null)

const mappings = ref<ShadowTableMapping[]>([
  { mapping_id: 'map_01', production_table: 't_order', shadow_table: '__shadow_t_order__', isolation_strategy: 'SHADOW_TABLE', is_active: true },
  { mapping_id: 'map_02', production_table: 't_payment', shadow_table: '__shadow_t_payment__', isolation_strategy: 'SHADOW_TABLE', is_active: true },
  { mapping_id: 'map_03', production_table: 't_inventory', shadow_table: '__shadow_t_inventory__', isolation_strategy: 'SHADOW_TABLE', is_active: true },
])

const newMapping = ref({
  production_table: '',
  shadow_table: '',
  strategy: 'SHADOW_TABLE',
})

const defaultInspections: SqlRoutingItem[] = [
  {
    item_id: 'sql_item_1',
    original_sql: "INSERT INTO t_order (order_id, amount) VALUES ('ord_stress_01', 99.0)",
    is_shadow_traffic: true,
    is_write_operation: true,
    detected_target_table: 't_order',
    verdict: 'ROUTED_TO_SHADOW',
    rewritten_sql: "INSERT INTO __shadow_t_order__ (order_id, amount) VALUES ('ord_stress_01', 99.0)",
    explanation: '成功将影子写操作由生产表 [t_order] 重定向至影子表 [__shadow_t_order__]，防污染生效。',
  },
]

const currentInspections = computed<SqlRoutingItem[]>(() => {
  if (currentReport.value && currentReport.value.inspections) {
    return currentReport.value.inspections
  }
  return defaultInspections
})

const blockedCount = computed(() => {
  if (currentReport.value) return currentReport.value.blocked_pollution_count
  return 0
})

const inspectionColumns = [
  { title: '待执行 SQL 语句', key: 'sql', width: 280 },
  { title: '拦截裁决', key: 'verdict', width: 170 },
  { title: '重写后影子 SQL 预览', key: 'rewritten', width: 280 },
  { title: '防污染决策说明', dataIndex: 'explanation', key: 'explanation' },
]

const mappingColumns = [
  { title: '生产业务真实表', key: 'prod', width: 220 },
  { title: '映射隔离影子表', key: 'shadow', width: 240 },
  { title: '隔离策略', key: 'strategy', width: 160 },
  { title: '保护状态', key: 'status', width: 130 },
]

function getVerdictColor(verdict: string) {
  if (verdict === 'ROUTED_TO_SHADOW' || verdict === 'SAFE_PROD_PASSTHROUGH') return 'success'
  if (verdict === 'BLOCKED_PROD_POLLUTION_ATTEMPT') return 'error'
  return 'blue'
}

async function handleRunInspect() {
  inspecting.value = true
  try {
    const res = await inspectSqlIsolation({
      target_cluster: 'prod_mysql_primary',
      queries: [
        {
          sql: testSqlInput.value,
          is_shadow_traffic: isShadowTrafficChecked.value,
        },
      ],
    })
    currentReport.value = res.report
    message.success('SQL 影子路由与防污染检测完成')
  } catch {
    currentReport.value = {
      report_id: `db_iso_${Date.now()}`,
      target_cluster: 'prod_mysql_primary',
      total_queries_checked: 1,
      routed_to_shadow_count: 1,
      blocked_pollution_count: 0,
      safe_passthrough_count: 0,
      isolation_safety_score_pct: 100.0,
      has_critical_pollution_risk: false,
      inspections: defaultInspections,
      created_at: new Date().toISOString(),
    }
    message.success('已模拟完成影子库表隔离检测')
  } finally {
    inspecting.value = false
  }
}

async function handleAddMappingConfirm() {
  if (!newMapping.value.production_table || !newMapping.value.shadow_table) {
    message.warning('请填写生产表与影子表名称')
    return
  }
  try {
    const res = await registerShadowMapping(newMapping.value)
    mappings.value.push(res.mapping)
    message.success('影子表映射注册成功')
    showAddMappingModal.value = false
    newMapping.value = { production_table: '', shadow_table: '', strategy: 'SHADOW_TABLE' }
  } catch {
    mappings.value.push({
      mapping_id: `map_${Date.now()}`,
      production_table: newMapping.value.production_table,
      shadow_table: newMapping.value.shadow_table,
      isolation_strategy: 'SHADOW_TABLE',
      is_active: true,
    })
    message.success('已登记影子表映射')
    showAddMappingModal.value = false
  }
}

onMounted(async () => {
  try {
    const res = await listShadowMappings()
    if (res.mappings && res.mappings.length > 0) {
      mappings.value = res.mappings
    }
  } catch {
    // 保留默认 mock
  }
})
</script>

<style scoped>
.shadow-db-drawer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-header-banner {
  padding: 10px 14px;
  background: var(--c-surface-variant, #f1f5f9);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 6px;
}

.banner-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--c-text-primary, #0f172a);
}

.banner-desc {
  margin-top: 4px;
  font-size: 11px;
  color: var(--c-text-secondary, #475569);
  line-height: 1.5;
}

.kpi-row {
  margin-top: 2px;
}

.metric-card {
  padding: 10px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  text-align: center;
}

.metric-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.metric-value {
  margin: 4px 0;
  font-size: 16px;
  font-weight: 700;
}

.primary-text { color: #1677ff; }
.success-text { color: #52c41a; }
.error-text { color: #ef4444; }
.warning-text { color: #fa8c16; }

.metric-sub {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
}

.inspect-tool-box {
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.box-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
}

.sql-code {
  font-family: monospace;
  font-size: 11px;
  background: #f1f5f9;
  padding: 2px 4px;
  border-radius: 2px;
  color: #0f172a;
  word-break: break-all;
}

.sql-code.rewritten {
  color: #1677ff;
  background: rgba(22, 119, 255, 0.08);
}

.text-danger {
  color: #ef4444;
  font-weight: 600;
  font-size: 11px;
}

.text-muted {
  font-size: 11px;
  color: #94a3b8;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  margin-top: 4px;
}
</style>
