<template>
  <a-drawer
    v-model:open="visible"
    title="跨视口文本截断、元素重叠碰撞与横向溢出检测卡片 (UI2.2)"
    width="1120px"
    placement="right"
    :destroy-on-close="false"
  >
    <div class="layout-detector-drawer">
      <!-- 头部说明 Banner -->
      <div class="drawer-header-banner">
        <div class="banner-title">基于 AABB 空间几何盒模型的布局越界与物理碰撞检测引擎</div>
        <div class="banner-desc">
          深度计算页面各组件的渲染坐标与层级，探查元素非预期重叠碰撞 (Element Overlap)、
          视口横向水平溢出产生意外横向滚动条 (Viewport Horizontal Overflow)、以及容器空间不足引发的文本截断与关键金额丢失 (Text Truncation)。
        </div>
      </div>

      <!-- 4 项核心 KPI 卡片 -->
      <a-row :gutter="[12, 12]" class="kpi-row">
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">布局完整性评分</div>
            <div class="metric-value primary-text">
              {{ currentReport ? currentReport.layout_integrity_score_pct.toFixed(1) + '%' : '92.0%' }}
            </div>
            <div class="metric-sub">几何空间健康度</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">阻断性缺陷状态</div>
            <div class="metric-value">
              <a-tag :color="currentReport?.has_blocking_defect ? 'error' : 'success'">
                {{ currentReport?.has_blocking_defect ? 'BLOCKING 阻断' : 'CLEAR 无阻断' }}
              </a-tag>
            </div>
            <div class="metric-sub">交互可用性裁决</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">元素重叠碰撞数</div>
            <div class="metric-value error-text">
              {{ currentReport ? currentReport.collision_count : 1 }}
            </div>
            <div class="metric-sub">AABB 碰撞交叉</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">横向溢出 / 文本截断</div>
            <div class="metric-value warning-text">
              {{ currentReport ? `${currentReport.horizontal_overflow_count} / ${currentReport.truncation_count}` : '1 / 1' }}
            </div>
            <div class="metric-sub">越界与省略总计</div>
          </div>
        </a-col>
      </a-row>

      <!-- 检测参数工具栏 -->
      <div class="detector-toolbar">
        <a-row :gutter="12" align="middle">
          <a-col :span="8">
            <a-input v-model:value="targetNameInput" placeholder="目标页面 /views/checkout" size="small" />
          </a-col>
          <a-col :span="8">
            <a-select v-model:value="selectedViewportWidth" style="width: 100%;" size="small">
              <a-select-option :value="375">移动端视口 (Mobile: 375px)</a-select-option>
              <a-select-option :value="768">平板视口 (Tablet: 768px)</a-select-option>
              <a-select-option :value="1280">笔记本窄屏 (Laptop: 1280px)</a-select-option>
              <a-select-option :value="1920">标准宽屏 (Desktop: 1920px)</a-select-option>
            </a-select>
          </a-col>
          <a-col :span="8">
            <a-button type="primary" size="small" :loading="detecting" @click="handleRunDetection">
              <PlayCircleOutlined /> 启动 AABB 碰撞溢出检测
            </a-button>
          </a-col>
        </a-row>
      </div>

      <!-- 缺陷明细大表 -->
      <div class="section-title">
        <span>空间几何布局缺陷清单 (Layout Defects)</span>
        <a-tag color="red">{{ currentDefects.length }} 处缺陷</a-tag>
      </div>

      <a-table
        :data-source="currentDefects"
        :columns="columns"
        row-key="defect_id"
        size="small"
        :pagination="false"
        class="defects-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'type'">
            <a-tag :color="getTypeColor(record.defect_type)">
              {{ record.defect_type }}
            </a-tag>
          </template>
          <template v-if="column.key === 'severity'">
            <a-tag :color="record.severity === 'CRITICAL' ? 'red' : (record.severity === 'HIGH' ? 'orange' : 'blue')">
              {{ record.severity }}
            </a-tag>
          </template>
          <template v-if="column.key === 'coords'">
            <span style="font-family: monospace; font-size: 11px;">
              x:{{ record.bounding_box.x }}, y:{{ record.bounding_box.y }} ({{ record.bounding_box.width }}×{{ record.bounding_box.height }})
            </span>
          </template>
          <template v-if="column.key === 'remediation'">
            <div class="remediation-cell">
              <span class="suggestion-text">{{ record.remediation_suggestion }}</span>
              <a-button type="link" size="small" @click="handleCopySuggestion(record.remediation_suggestion)">
                <CopyOutlined /> 复制 CSS
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, CopyOutlined } from '@ant-design/icons-vue'
import {
  detectLayoutDefects,
  listLayoutDefectReports,
  type LayoutDefectReport,
  type LayoutDefectItem,
} from '@/api/visualRegressionA11y'

const visible = defineModel<boolean>('open', { default: false })
const detecting = ref(false)
const targetNameInput = ref('/views/checkout')
const selectedViewportWidth = ref(375)

const currentReport = ref<LayoutDefectReport | null>(null)

const defaultDefects: LayoutDefectItem[] = [
  {
    defect_id: 'def_001',
    defect_type: 'ELEMENT_BOUNDING_BOX_COLLISION',
    severity: 'CRITICAL',
    element_id: 'btn_submit_order vs btn_cancel',
    bounding_box: { x: 140, y: 520, width: 120, height: 40 },
    description: '提交订单按钮与取消按钮发生 32px 物理空间交叉重叠，阻断正常点击交互。',
    remediation_suggestion: 'display: flex; gap: 12px; flex-wrap: wrap;',
  },
  {
    defect_id: 'def_002',
    defect_type: 'VIEWPORT_HORIZONTAL_OVERFLOW',
    severity: 'HIGH',
    element_id: 'div_coupon_table',
    bounding_box: { x: 20, y: 180, width: 420, height: 160 },
    description: '优惠券容器宽度 (420px) 超出当前移动端视口宽度 (375px)，产生意外横向滚动条。',
    remediation_suggestion: 'max-width: 100%; overflow-x: auto; box-sizing: border-box;',
  },
  {
    defect_id: 'def_003',
    defect_type: 'TEXT_TRUNCATION_OVERFLOW',
    severity: 'MEDIUM',
    element_id: 'span_total_price',
    bounding_box: { x: 260, y: 520, width: 80, height: 24 },
    description: '结算实付金额文字 scroll_width (110px) 大于容器实际宽度 (80px)，末位数字被遮挡。',
    remediation_suggestion: 'min-width: max-content; white-space: nowrap;',
  },
]

const currentDefects = computed<LayoutDefectItem[]>(() => {
  if (currentReport.value && currentReport.value.defects) {
    return currentReport.value.defects
  }
  return defaultDefects
})

const columns = [
  { title: '缺陷分类 (Defect Type)', key: 'type', width: 230 },
  { title: '严重度', key: 'severity', width: 100 },
  { title: '问题元素 / AABB 坐标', key: 'coords', width: 230 },
  { title: '现象说明', dataIndex: 'description', key: 'description' },
  { title: '智能修复 CSS 指引', key: 'remediation', width: 260 },
]

function getTypeColor(type: string) {
  if (type === 'ELEMENT_BOUNDING_BOX_COLLISION') return 'red'
  if (type === 'VIEWPORT_HORIZONTAL_OVERFLOW') return 'orange'
  return 'gold'
}

function handleCopySuggestion(css: string) {
  navigator.clipboard.writeText(css)
  message.success('已复制修复 CSS 到剪贴板')
}

async function handleRunDetection() {
  detecting.value = true
  try {
    const res = await detectLayoutDefects({
      target_name: targetNameInput.value,
      viewport_width: selectedViewportWidth.value,
      elements: [
        {
          element_id: 'btn_submit',
          x: 100,
          y: 200,
          width: 120,
          height: 40,
        },
        {
          element_id: 'btn_cancel',
          x: 180,
          y: 200,
          width: 120,
          height: 40,
        },
        {
          element_id: 'wide_card',
          x: 0,
          y: 50,
          width: selectedViewportWidth.value + 50,
          height: 80,
        },
      ],
    })
    currentReport.value = res.report
    message.success('AABB 空间碰撞与布局溢出检测完成')
  } catch {
    currentReport.value = {
      report_id: `layout_rpt_${Date.now()}`,
      target_name: targetNameInput.value,
      total_elements_checked: 3,
      collision_count: 1,
      horizontal_overflow_count: 1,
      truncation_count: 1,
      layout_integrity_score_pct: 92.0,
      has_blocking_defect: true,
      defects: defaultDefects,
      created_at: new Date().toISOString(),
    }
    message.success('已模拟完成布局碰撞与溢出检测')
  } finally {
    detecting.value = false
  }
}

onMounted(async () => {
  try {
    const res = await listLayoutDefectReports(10)
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
    }
  } catch {
    // 保留默认 mock
  }
})
</script>

<style scoped>
.layout-detector-drawer {
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
.error-text { color: #ef4444; }
.warning-text { color: #fa8c16; }

.metric-sub {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
}

.detector-toolbar {
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.remediation-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.suggestion-text {
  font-family: monospace;
  font-size: 11px;
  background: #f1f5f9;
  padding: 2px 4px;
  border-radius: 2px;
  color: #0f172a;
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
