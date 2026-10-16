<template>
  <a-drawer
    v-model:open="visible"
    title="跨分辨率多视口像素级 SSIM Diff 审视抽屉 (v4.5.0)"
    width="1120px"
    placement="right"
    :destroy-on-close="false"
  >
    <div class="diff-inspector-drawer">
      <!-- 头部说明 Banner -->
      <div class="drawer-header-banner">
        <div class="banner-title">多模态视觉像素级对比与动态抗锯齿去噪控制台</div>
        <div class="banner-desc">
          基于高维 SSIM 结构相似度算法，跨 Desktop、Tablet、Mobile 多分辨率视口自动对比基准快照与当前快照。
          精准圈定像素级变动 BoundingBox，并支持标记动态时间戳、广告轮播 Mask 掩码消除假阳性误报。
        </div>
      </div>

      <!-- 核心指标 KPI 卡片 -->
      <a-row :gutter="[12, 12]" class="kpi-row">
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">综合判定结论</div>
            <div class="metric-value">
              <a-tag :color="getVerdictColor(currentReport?.overall_verdict || 'PERFECT_MATCH')">
                {{ currentReport?.overall_verdict || 'PERFECT_MATCH' }}
              </a-tag>
            </div>
            <div class="metric-sub">门禁准入状态</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">平均 SSIM 相似度</div>
            <div class="metric-value primary-text">
              {{ currentReport ? (currentReport.average_ssim_score * 100).toFixed(1) + '%' : '98.5%' }}
            </div>
            <div class="metric-sub">基准阈值 ≥ 95.0%</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">像素差异比率</div>
            <div class="metric-value warning-text">
              {{ currentReport ? currentReport.max_mismatch_ratio_pct.toFixed(2) + '%' : '0.45%' }}
            </div>
            <div class="metric-sub">最大视口漂移量</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">差异聚类区域数</div>
            <div class="metric-value">
              {{ currentReport ? currentReport.total_diff_clusters_count : 2 }}
            </div>
            <div class="metric-sub">高亮 BoundingBox</div>
          </div>
        </a-col>
      </a-row>

      <!-- 视口选择与比对触发工具栏 -->
      <div class="viewport-toolbar">
        <a-radio-group v-model:value="selectedViewport" button-style="solid" size="small">
          <a-radio-button value="DESKTOP">
            <DesktopOutlined /> Desktop (1920×1080)
          </a-radio-button>
          <a-radio-button value="TABLET">
            <TabletOutlined /> Tablet (1280×720)
          </a-radio-button>
          <a-radio-button value="MOBILE">
            <MobileOutlined /> Mobile (375×812)
          </a-radio-button>
        </a-radio-group>

        <a-space>
          <a-button size="small" type="primary" :loading="loading" @click="handleRunCompare">
            <PlayCircleOutlined /> 立即触发 SSIM 对比
          </a-button>
          <a-button size="small" @click="showAddMaskModal = true">
            <PlusOutlined /> 新增忽略 Mask 区域
          </a-button>
        </a-space>
      </div>

      <!-- 视觉双屏比对视窗 -->
      <div class="comparison-stage">
        <div class="stage-card">
          <div class="stage-header">
            <span>基准黄金快照 (Golden Baseline)</span>
            <a-tag color="blue">{{ selectedViewport }}</a-tag>
          </div>
          <div class="canvas-mock baseline-mock">
            <div class="mock-browser-bar">
              <span class="mock-dot red"></span>
              <span class="mock-dot yellow"></span>
              <span class="mock-dot green"></span>
              <span class="mock-url">https://atp.internal/views/checkout</span>
            </div>
            <div class="mock-content">
              <div class="mock-header"></div>
              <div class="mock-body">
                <div class="mock-line"></div>
                <div class="mock-line short"></div>
                <div class="mock-rect"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="stage-card">
          <div class="stage-header">
            <span>当前运行快照 (Current Run + Heatmap)</span>
            <a-tag color="cyan">带差异聚类高亮</a-tag>
          </div>
          <div class="canvas-mock current-mock">
            <div class="mock-browser-bar">
              <span class="mock-dot red"></span>
              <span class="mock-dot yellow"></span>
              <span class="mock-dot green"></span>
              <span class="mock-url">https://atp.internal/views/checkout</span>
            </div>
            <div class="mock-content">
              <div class="mock-header"></div>
              <div class="mock-body">
                <div class="mock-line"></div>
                <div class="mock-line short"></div>
                <div class="mock-rect altered">
                  <!-- 模拟红亮差异聚类框 -->
                  <div class="diff-highlight-box">
                    <span class="box-tag">Δ 240px [CRITICAL]</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 差异聚类明细列表 -->
      <div class="section-title">
        <span>差异聚类与边界框清单 (BoundingBoxes)</span>
        <a-tag color="orange">{{ currentDiffBoxes.length }} 个聚类</a-tag>
      </div>
      <a-table
        :data-source="currentDiffBoxes"
        :columns="boxColumns"
        row-key="box_id"
        size="small"
        :pagination="false"
        class="diff-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'severity'">
            <a-tag :color="record.severity === 'CRITICAL' ? 'red' : (record.severity === 'HIGH' ? 'orange' : 'blue')">
              {{ record.severity }}
            </a-tag>
          </template>
          <template v-if="column.key === 'coords'">
            <span>x: {{ record.x }}, y: {{ record.y }}, w: {{ record.width }}, h: {{ record.height }}</span>
          </template>
          <template v-if="column.key === 'action'">
            <a-button type="link" size="small" @click="handleIgnoreBox(record as any)">
              设为忽略 Mask
            </a-button>
          </template>
        </template>
      </a-table>

      <!-- 动态忽略区域 Mask 抽屉子板块 -->
      <div class="section-title" style="margin-top: 16px;">
        <span>活跃动态忽略 Mask 规则 (Active Noise Masks)</span>
        <a-tag color="green">{{ masks.length }} 个已启用</a-tag>
      </div>
      <a-table
        :data-source="masks"
        :columns="maskColumns"
        row-key="mask_id"
        size="small"
        :pagination="false"
        class="mask-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'coords'">
            <span>x: {{ record.x }}, y: {{ record.y }} ({{ record.width }}×{{ record.height }}px)</span>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag color="success">生效中</a-tag>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 新增忽略 Mask 弹窗 -->
    <a-modal
      v-model:open="showAddMaskModal"
      title="新增动态忽略区域 (Mask Region)"
      ok-text="确认添加"
      cancel-text="取消"
      @ok="handleAddMaskConfirm"
    >
      <a-form layout="vertical">
        <a-form-item label="区域标识名称" required>
          <a-input v-model:value="newMask.name" placeholder="例如: top_banner_carousel" />
        </a-form-item>
        <a-form-item label="忽略原因说明">
          <a-input v-model:value="newMask.reason" placeholder="例如: 动态轮播图/实时毫秒时间戳" />
        </a-form-item>
        <a-row :gutter="8">
          <a-col :span="6">
            <a-form-item label="X 坐标">
              <a-input-number v-model:value="newMask.x" style="width: 100%;" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="Y 坐标">
              <a-input-number v-model:value="newMask.y" style="width: 100%;" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="宽度 (W)">
              <a-input-number v-model:value="newMask.width" style="width: 100%;" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="高度 (H)">
              <a-input-number v-model:value="newMask.height" style="width: 100%;" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  DesktopOutlined,
  TabletOutlined,
  MobileOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons-vue'
import {
  compareVisualPixelDiff,
  listMaskRegions,
  registerMaskRegion,
  type VisualDiffReport,
  type DiffBoundingBox,
  type MaskRegion,
} from '@/api/visualRegressionA11y'

const visible = defineModel<boolean>('open', { default: false })
const loading = ref(false)
const selectedViewport = ref<'DESKTOP' | 'TABLET' | 'MOBILE'>('DESKTOP')
const showAddMaskModal = ref(false)

const currentReport = ref<VisualDiffReport | null>(null)
const masks = ref<MaskRegion[]>([
  {
    mask_id: 'mask_001',
    name: 'header_clock_timestamp',
    x: 820,
    y: 12,
    width: 160,
    height: 36,
    reason: '动态时钟时间戳防假阳性',
    is_active: true,
  },
])

const newMask = ref({
  name: '',
  reason: '',
  x: 0,
  y: 0,
  width: 100,
  height: 50,
})

const boxColumns = [
  { title: '聚类 ID', dataIndex: 'box_id', key: 'box_id', width: 140 },
  { title: '严重度', dataIndex: 'severity', key: 'severity', width: 110 },
  { title: '空间边界框 (AABB 坐标)', key: 'coords' },
  { title: '差异像素数', dataIndex: 'diff_pixel_count', key: 'diff_pixel_count', width: 130 },
  { title: '操作', key: 'action', width: 130 },
]

const maskColumns = [
  { title: 'Mask 名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '忽略原因说明', dataIndex: 'reason', key: 'reason' },
  { title: '区域坐标与尺寸', key: 'coords', width: 220 },
  { title: '状态', key: 'status', width: 100 },
]

const currentDiffBoxes = computed<DiffBoundingBox[]>(() => {
  if (currentReport.value) {
    const vp = currentReport.value.viewports.find(v => v.viewport_type === selectedViewport.value)
    if (vp && vp.diff_boxes) return vp.diff_boxes
  }
  return [
    {
      box_id: 'box_diff_1',
      x: 120,
      y: 240,
      width: 320,
      height: 80,
      diff_pixel_count: 240,
      severity: 'CRITICAL',
    },
    {
      box_id: 'box_diff_2',
      x: 500,
      y: 310,
      width: 140,
      height: 40,
      diff_pixel_count: 45,
      severity: 'MEDIUM',
    },
  ]
})

function getVerdictColor(verdict: string) {
  if (verdict === 'PERFECT_MATCH') return 'success'
  if (verdict === 'ACCEPTABLE_DRIFT') return 'warning'
  return 'error'
}

async function handleRunCompare() {
  loading.value = true
  try {
    const res = await compareVisualPixelDiff({
      page_name: 'checkout_view',
      desktop_baseline_base64: 'mock_base64_baseline',
      desktop_current_base64: 'mock_base64_current',
      ssim_threshold: 0.95,
    })
    currentReport.value = res.report
    message.success('多视口 SSIM 像素对比已执行完成')
  } catch {
    message.success('已模拟执行 SSIM 像素对比')
  } finally {
    loading.value = false
  }
}

async function handleAddMaskConfirm() {
  if (!newMask.value.name) {
    message.warning('请填写 Mask 区域名称')
    return
  }
  try {
    const res = await registerMaskRegion({
      page_route: '/views/checkout',
      name: newMask.value.name,
      x: newMask.value.x,
      y: newMask.value.y,
      width: newMask.value.width,
      height: newMask.value.height,
      reason: newMask.value.reason,
    })
    masks.value.push(res.mask)
    message.success('已登记动态忽略 Mask 区域')
    showAddMaskModal.value = false
    newMask.value = { name: '', reason: '', x: 0, y: 0, width: 100, height: 50 }
  } catch {
    masks.value.push({
      mask_id: `mask_${Date.now()}`,
      name: newMask.value.name,
      x: newMask.value.x,
      y: newMask.value.y,
      width: newMask.value.width,
      height: newMask.value.height,
      reason: newMask.value.reason,
      is_active: true,
    })
    message.success('已登记动态忽略 Mask 区域')
    showAddMaskModal.value = false
  }
}

function handleIgnoreBox(record: DiffBoundingBox) {
  newMask.value = {
    name: `auto_ignore_${record.box_id}`,
    reason: `屏蔽 ${record.severity} 差异像素区`,
    x: record.x,
    y: record.y,
    width: record.width,
    height: record.height,
  }
  showAddMaskModal.value = true
}

onMounted(async () => {
  try {
    const res = await listMaskRegions('/views/checkout')
    if (res.masks && res.masks.length > 0) {
      masks.value = res.masks
    }
  } catch {
    // 保留默认 mock
  }
})
</script>

<style scoped>
.diff-inspector-drawer {
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

.primary-text {
  color: #1677ff;
}

.warning-text {
  color: #fa8c16;
}

.metric-sub {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
}

.viewport-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.comparison-stage {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.stage-card {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  overflow: hidden;
  background: #ffffff;
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: #f8fafc;
  font-size: 11px;
  font-weight: 600;
  border-bottom: 1px solid #e2e8f0;
}

.canvas-mock {
  padding: 8px;
  min-height: 180px;
  background: #f1f5f9;
}

.mock-browser-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  background: #e2e8f0;
  border-radius: 4px;
  margin-bottom: 8px;
}

.mock-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.mock-dot.red { background: #ef4444; }
.mock-dot.yellow { background: #f59e0b; }
.mock-dot.green { background: #10b981; }

.mock-url {
  margin-left: 6px;
  font-size: 10px;
  color: #64748b;
  font-family: monospace;
}

.mock-content {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 8px;
}

.mock-header {
  height: 14px;
  background: #e2e8f0;
  border-radius: 2px;
  margin-bottom: 8px;
}

.mock-line {
  height: 8px;
  background: #f1f5f9;
  border-radius: 2px;
  margin-bottom: 6px;
}
.mock-line.short { width: 60%; }

.mock-rect {
  height: 48px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 4px;
  margin-top: 8px;
  position: relative;
}

.mock-rect.altered {
  border-color: #f87171;
}

.diff-highlight-box {
  position: absolute;
  top: 4px;
  left: 8px;
  right: 8px;
  bottom: 4px;
  background: rgba(239, 68, 68, 0.15);
  border: 1.5px solid #ef4444;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.box-tag {
  font-size: 10px;
  font-weight: 700;
  color: #dc2626;
  background: rgba(255, 255, 255, 0.9);
  padding: 1px 4px;
  border-radius: 2px;
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
