<template>
  <a-drawer
    :open="open"
    :width="860"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <span>视觉/DOM 混合自愈与 OCR 物理边界比对器</span>
    </template>

    <div class="visual-self-healing-inspector">
      <!-- 头部诊断触发栏 -->
      <a-card size="small" class="header-card">
        <div class="header-content">
          <div class="desc-box">
            <h4 class="title">三层级混合定位与动态自愈决策引擎 (Tier 1 ~ Tier 3)</h4>
            <p class="subtitle">
              当应用版本迭代导致 DOM ID 动态漂移或非标准组件（如 Unity、Flutter、Canvas）无无障碍树时，自动启用多维启发评分与截图 OCR 物理边界中心坐标补偿。
            </p>
          </div>
          <div class="btn-group">
            <a-button @click="loadSampleIncident">
              载入典型元素漂移现场
            </a-button>
            <a-button type="primary" :loading="locating" @click="handleRunLocate">
              执行自愈定位比对
            </a-button>
          </div>
        </div>

        <!-- 诊断结果状态卡 -->
        <div class="metrics-bar">
          <div class="metric-pill">
            <span class="lbl">自愈策略:</span>
            <a-tag :color="getStrategyColor(result?.matched_strategy)">
              {{ getStrategyLabel(result?.matched_strategy) }}
            </a-tag>
          </div>

          <div class="metric-pill">
            <span class="lbl">自愈状态:</span>
            <a-tag :color="result?.healed ? 'orange' : (result?.success ? 'green' : 'red')">
              {{ result?.healed ? '已触发自愈补偿' : (result?.success ? '原生定位正常' : '定位失败') }}
            </a-tag>
          </div>

          <div class="metric-pill highlight">
            <span class="lbl">置信度得分:</span>
            <strong>{{ result ? `${Math.round(result.confidence_score * 100)}%` : '--' }}</strong>
          </div>

          <div class="metric-pill coords-pill">
            <span class="lbl">衍生点击物理坐标:</span>
            <code v-if="result?.click_coordinates">
              X: {{ result.click_coordinates[0] }}, Y: {{ result.click_coordinates[1] }}
            </code>
            <span v-else class="empty-coord">暂未生成</span>
          </div>
        </div>
      </a-card>

      <!-- 视觉画布定位框 (Visual Bounding Box Viewport) -->
      <a-card size="small" title="移动端屏幕物理边界与自愈点击坐标可视化 (Screen Viewport)" class="viewport-card">
        <div class="screen-canvas-wrapper">
          <div class="mock-device-viewport">
            <div class="status-bar-mock">
              <span>09:41</span>
              <span>5G · 100%</span>
            </div>

            <div class="screen-content-mock">
              <div class="dummy-app-header">ATP 商城结算台</div>
              <div class="dummy-order-info">订单金额: ¥99.00</div>

              <!-- 标注识别出的 OCR 物理边界框 -->
              <div
                v-if="result?.click_coordinates"
                class="bounding-box-overlay"
                :style="boundingBoxStyle"
              >
                <div class="bbox-label">OCR 检测区 [{{ result.matched_strategy }}]</div>
                <!-- 中心物理十字准星 -->
                <div class="crosshair-point" />
              </div>

              <!-- 模拟漂移后的按钮 -->
              <div class="target-button-mock">
                <span>{{ targetParams.text || '确认支付' }}</span>
              </div>
            </div>
          </div>

          <!-- 右侧：三层级自愈决策链条流水 -->
          <div class="tier-breakdown-pane">
            <h5 class="tier-title">三层级判定链路执行明细:</h5>
            <a-timeline class="tier-timeline">
              <a-timeline-item :color="result?.matched_strategy === 'exact_dom' ? 'green' : 'gray'">
                <strong>Tier 1: 绝对精确 DOM / ID 匹配</strong>
                <p class="timeline-desc">
                  比对 <code>resource_id: "{{ targetParams.resource_id }}"</code>
                  <br />
                  <span v-if="result?.matched_strategy === 'exact_dom'" class="text-success">精确命中原组件 ID</span>
                  <span v-else class="text-muted">未命中 (检测到组件 ID 动态漂移)</span>
                </p>
              </a-timeline-item>

              <a-timeline-item :color="result?.matched_strategy === 'fuzzy_ax_tree' ? 'green' : 'gray'">
                <strong>Tier 2: 无障碍树启发模糊加权</strong>
                <p class="timeline-desc">
                  文本相似度评分判定 (阈值 65%)
                  <br />
                  <span v-if="result?.matched_strategy === 'fuzzy_ax_tree'" class="text-success">启发模糊相似度达标命中</span>
                  <span v-else class="text-muted">树形结构失真，转入视觉补全</span>
                </p>
              </a-timeline-item>

              <a-timeline-item :color="result?.matched_strategy === 'visual_ocr' ? 'green' : 'gray'">
                <strong>Tier 3: 视觉截图 OCR 物理边界自愈</strong>
                <p class="timeline-desc">
                  提取文字包围盒与计算中心点击物理坐标
                  <br />
                  <span v-if="result?.matched_strategy === 'visual_ocr'" class="text-success">
                    OCR 成功捕获文字中心坐标并自愈!
                  </span>
                  <span v-else class="text-muted">前置层级已命中，无需激活 Tier 3</span>
                </p>
              </a-timeline-item>
            </a-timeline>

            <div v-if="result?.healing_details" class="details-alert">
              <a-alert
                type="info"
                show-icon
                :message="result.healing_details"
              />
            </div>
          </div>
        </div>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  devicePlaybackApi,
  type HybridLocateResponse,
} from '@/api/devicePlayback'

const props = withDefaults(
  defineProps<{
    open: boolean
  }>(),
  {
    open: false,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'healed', val: HybridLocateResponse): void
}>()

const locating = ref(false)
const result = ref<HybridLocateResponse | null>(null)

const targetParams = reactive({
  resource_id: 'com.app.shop:id/btn_pay_v1',
  text: '确认支付',
  accessibility_id: 'btn_pay',
})

const axElements = ref<any[]>([
  {
    resource_id: 'com.app.shop:id/btn_pay_v2_dynamic_981',
    text: '确认支付 (¥99.00)',
    bounds: [40, 220, 240, 270],
  },
])

const ocrBlocks = ref<any[]>([
  {
    text: '确认支付',
    bounds: [40, 220, 240, 270],
    confidence: 0.95,
  },
])

const boundingBoxStyle = computed(() => {
  if (!result.value?.click_coordinates) return {}
  return {
    top: '220px',
    left: '40px',
    width: '200px',
    height: '50px',
  }
})

function getStrategyColor(strategy?: string): string {
  switch (strategy) {
    case 'exact_dom':
      return 'green'
    case 'fuzzy_ax_tree':
      return 'cyan'
    case 'visual_ocr':
      return 'purple'
    default:
      return 'default'
  }
}

function getStrategyLabel(strategy?: string): string {
  switch (strategy) {
    case 'exact_dom':
      return 'Tier 1 绝对 DOM'
    case 'fuzzy_ax_tree':
      return 'Tier 2 无障碍树启发'
    case 'visual_ocr':
      return 'Tier 3 视觉 OCR 自愈'
    default:
      return '未判定'
  }
}

function handleClose() {
  emit('update:open', false)
}

function loadSampleIncident() {
  targetParams.resource_id = 'com.app.shop:id/btn_pay_legacy'
  targetParams.text = '确认支付'
  message.success('已载入真实 DOM ID 漂移案例！')
}

async function handleRunLocate() {
  locating.value = true
  try {
    const res = await devicePlaybackApi.hybridLocate({
      target_params: targetParams,
      ax_elements: axElements.value,
      ocr_blocks: ocrBlocks.value,
    })
    result.value = res
    emit('healed', res)
    if (res.healed) {
      message.success(`智能自愈成功！采用 ${getStrategyLabel(res.matched_strategy)}，置信度 ${Math.round(res.confidence_score * 100)}%`)
    } else if (res.success) {
      message.success('原生定位比对成功！')
    } else {
      message.warning('定位失败，未能发现可用候选')
    }
  } catch (err: any) {
    message.error(err.message || '自愈比对分析失败')
  } finally {
    locating.value = false
  }
}
</script>

<style scoped>
.visual-self-healing-inspector {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-card,
.viewport-card {
  border-radius: 8px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.btn-group {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.metrics-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border, #f1f5f9);
}

.metric-pill {
  padding: 4px 10px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  align-items: center;
  gap: 6px;
}

.metric-pill.highlight {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.coords-pill code {
  color: #7c3aed;
  font-weight: 600;
}

.empty-coord {
  color: #94a3b8;
}

.screen-canvas-wrapper {
  display: flex;
  gap: 24px;
}

.mock-device-viewport {
  width: 280px;
  height: 380px;
  background: #0f172a;
  border-radius: 20px;
  border: 4px solid #334155;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
}

.status-bar-mock {
  height: 24px;
  display: flex;
  justify-content: space-between;
  padding: 4px 16px;
  font-size: 10px;
  color: #94a3b8;
}

.screen-content-mock {
  padding: 16px;
  color: #fff;
  height: calc(100% - 24px);
  position: relative;
  background: #1e293b;
}

.dummy-app-header {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}

.dummy-order-info {
  font-size: 12px;
  color: #cbd5e1;
}

.target-button-mock {
  position: absolute;
  top: 220px;
  left: 40px;
  width: 200px;
  height: 50px;
  background: #2563eb;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
}

.bounding-box-overlay {
  position: absolute;
  border: 2px dashed #f59e0b;
  background: rgba(245, 158, 11, 0.15);
  z-index: 10;
  pointer-events: none;
}

.bbox-label {
  position: absolute;
  top: -18px;
  left: 0;
  font-size: 9px;
  background: #f59e0b;
  color: #000;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 600;
  white-space: nowrap;
}

.crosshair-point {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  transform: translate(-50%, -50%);
  box-shadow: 0 0 6px #ef4444;
}

.tier-breakdown-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.tier-title {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.tier-timeline {
  margin-bottom: 12px;
}

.timeline-desc {
  font-size: 11px;
  color: #64748b;
  margin: 2px 0 0;
}

.text-success {
  color: #16a34a;
  font-weight: 500;
}

.text-muted {
  color: #94a3b8;
}

.details-alert {
  margin-top: auto;
}
</style>
