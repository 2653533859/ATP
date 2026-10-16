<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="针对复杂业务边界条件的生产级测试合成数据控制台"
    destroy-on-close
    class="synthetic-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制说明 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <DatabaseOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">多模态生产级合成测试数据生成引擎 (T3.2)</div>
          <div class="banner-desc">
            拒绝盲目随机假数据与明文敏感生产数据！基于字段类型与业务规则自动合成三模态测试集：严格正向合法数据（<code>POSITIVE_VALID</code>）、临界极限边界值（<code>BOUNDARY_EDGE</code>）与受控异常违规数据（<code>NEGATIVE_ANOMALY</code>），全面检验接口防御鲁棒性。
          </div>
        </div>
      </div>

      <!-- 场景预设与生成行数配置栏 -->
      <div class="config-section">
        <div class="section-title">业务数据规则与合成参数</div>
        <div class="config-row">
          <div class="preset-group">
            <span class="label">数据模型预设:</span>
            <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
              <a-radio-button value="order_checkout">电商交易下单结算 (金额/手机/邮箱/状态)</a-radio-button>
              <a-radio-button value="user_kyc">用户实名认证 (身份证/年龄/姓名/等级)</a-radio-button>
              <a-radio-button value="coupon_rule">促销券营销资产 (券码/面额/限制条件)</a-radio-button>
            </a-radio-group>
          </div>
          <div class="count-group">
            <span class="label">合成数据行数:</span>
            <a-input-number v-model:value="rowCount" :min="4" :max="50" size="small" class="w-20" />
            <a-button type="primary" size="small" :loading="generating" @click="handleGenerate">
              <ThunderboltOutlined /> 生成高质量测试集
            </a-button>
          </div>
        </div>
      </div>

      <!-- 4 大核心 KPI 统计卡片 -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">合成测试数据总行数</div>
            <div class="stat-value text-primary">{{ currentBatch?.total_rows ?? 0 }} <span class="unit">行</span></div>
            <div class="stat-trend">{{ currentBatch?.fields_count ?? 0 }} 个业务字段</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">正向合法数据 (70%)</div>
            <div class="stat-value text-success">{{ currentBatch?.positive_count ?? 0 }} <span class="unit">行</span></div>
            <div class="stat-trend">完全符合校验规则</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">极限边界值数据 (15%)</div>
            <div class="stat-value text-warning">{{ currentBatch?.boundary_count ?? 0 }} <span class="unit">行</span></div>
            <div class="stat-trend">最小值/最大值/临界长度</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">负向异常违规数据 (15%)</div>
            <div class="stat-value text-danger">{{ currentBatch?.negative_count ?? 0 }} <span class="unit">行</span></div>
            <div class="stat-trend">格式损坏/越界溢出注入</div>
          </div>
        </a-col>
      </a-row>

      <!-- 合成测试数据集全景表格 -->
      <div class="table-section">
        <div class="table-header">
          <div class="section-title">合成测试数据明细表格</div>
          <a-space>
            <a-button size="small" :disabled="!currentBatch?.rows.length" @click="handleCopyJson">
              <CopyOutlined /> 复制 JSON 数据集
            </a-button>
          </a-space>
        </div>

        <a-table
          :data-source="currentBatch?.rows ?? []"
          :columns="columns"
          :row-key="(r: any) => r.row_index"
          size="small"
          :pagination="{ pageSize: 7 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'row_index'">
              <span class="row-num">#{{ record.row_index }}</span>
            </template>

            <template v-else-if="column.key === 'mode'">
              <a-tag :color="getModeColor(record.mode)">{{ record.mode }}</a-tag>
            </template>

            <template v-else-if="column.key === 'validity'">
              <a-tag v-if="record.is_expected_valid" color="success">预期通过 (VALID)</a-tag>
              <a-tag v-else color="error">预期阻断 (INVALID)</a-tag>
            </template>

            <template v-else-if="column.key === 'payload'">
              <pre class="data-json"><code>{{ JSON.stringify(record.data) }}</code></pre>
            </template>

            <template v-else-if="column.key === 'anomaly'">
              <div v-if="record.anomaly_field" class="anomaly-box">
                <span class="anomaly-field">[{{ record.anomaly_field }}]</span>
                <span class="anomaly-desc">{{ record.anomaly_reason }}</span>
              </div>
              <span v-else class="text-xs text-muted">正向合法数据</span>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  DatabaseOutlined,
  ThunderboltOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  syntheticTestDataApi,
  type SyntheticDatasetBatch,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const generating = ref(false)
const selectedPreset = ref<'order_checkout' | 'user_kyc' | 'coupon_rule'>('order_checkout')
const rowCount = ref(10)
const currentBatch = ref<SyntheticDatasetBatch | null>(null)

const PRESET_RULES = {
  order_checkout: {
    name: 'order_checkout_payloads',
    rules: [
      { field_name: 'order_amount', data_type: 'float', min_value: 1.0, max_value: 5000.0 },
      { field_name: 'buyer_email', data_type: 'email' },
      { field_name: 'contact_phone', data_type: 'phone' },
      { field_name: 'order_status', data_type: 'enum', enum_values: ['PENDING', 'PAID', 'SHIPPED', 'CANCELLED'] },
    ],
  },
  user_kyc: {
    name: 'user_kyc_verification',
    rules: [
      { field_name: 'citizen_id_card', data_type: 'id_card' },
      { field_name: 'user_age', data_type: 'integer', min_value: 18, max_value: 65 },
      { field_name: 'contact_email', data_type: 'email' },
      { field_name: 'user_vip_tier', data_type: 'enum', enum_values: ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM'] },
    ],
  },
  coupon_rule: {
    name: 'coupon_promotion_assets',
    rules: [
      { field_name: 'coupon_code', data_type: 'string', min_length: 6, max_length: 12 },
      { field_name: 'discount_amount', data_type: 'float', min_value: 5.0, max_value: 200.0 },
      { field_name: 'max_usage_limit', data_type: 'integer', min_value: 1, max_value: 100 },
    ],
  },
}

const columns = [
  { title: '行号', key: 'row_index', width: 60 },
  { title: '合成模式', key: 'mode', width: 140 },
  { title: '预期断言', key: 'validity', width: 130 },
  { title: '数据字段值 (Payload)', key: 'payload' },
  { title: '负向异常注入说明', key: 'anomaly', width: 240 },
]

function handleClose() {
  emit('update:open', false)
}

function handlePresetChange() {
  handleGenerate()
}

function getModeColor(mode: string) {
  switch (mode) {
    case 'POSITIVE_VALID': return 'green'
    case 'BOUNDARY_EDGE': return 'orange'
    case 'NEGATIVE_ANOMALY': return 'red'
    default: return 'default'
  }
}

async function handleGenerate() {
  generating.value = true
  try {
    const p = PRESET_RULES[selectedPreset.value]
    const res = await syntheticTestDataApi.generate({
      dataset_name: p.name,
      rules: p.rules,
      row_count: rowCount.value,
    })
    currentBatch.value = res.batch
    message.success(res.message || '测试数据集合成成功')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '生成失败')
  } finally {
    generating.value = false
  }
}

function handleCopyJson() {
  if (!currentBatch.value?.rows.length) return
  const dataList = currentBatch.value.rows.map((r) => r.data)
  navigator.clipboard.writeText(JSON.stringify(dataList, null, 2))
  message.success('已复制测试数据集 JSON 到剪贴板')
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      handleGenerate()
    }
  }
)

onMounted(() => {
  if (props.open) {
    handleGenerate()
  }
})
</script>

<style scoped>
.synthetic-drawer :deep(.ant-drawer-body) {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
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
  line-line: 1.5;
}

.config-section,
.table-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
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

.preset-group,
.count-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.w-20 {
  width: 70px;
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
.text-muted { color: #94a3b8; }

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.row-num {
  font-weight: 700;
  color: #64748b;
  font-size: 11px;
}

.data-json {
  margin: 0;
  font-family: monospace;
  font-size: 11px;
  color: #0f172a;
  background: #f8fafc;
  padding: 4px 8px;
  border-radius: 4px;
  max-width: 460px;
  overflow-x: auto;
  white-space: nowrap;
}

.anomaly-box {
  display: flex;
  flex-direction: column;
  font-size: 11px;
}

.anomaly-field {
  font-weight: 700;
  color: #dc2626;
}

.anomaly-desc {
  color: #b91c1c;
}

.text-xs {
  font-size: 11px;
}
</style>
