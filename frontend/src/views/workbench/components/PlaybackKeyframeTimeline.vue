<template>
  <a-drawer
    :open="open"
    :width="920"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <span>MP4 录屏毫秒级时间线对齐与异常高亮播放器</span>
    </template>

    <div class="playback-keyframe-timeline">
      <!-- 头部音画元数据与生成控制栏 -->
      <a-card size="small" class="header-card">
        <div class="header-content">
          <div class="desc-box">
            <h4 class="title">音画逐帧同步对齐与关键现场标记 (Video Keyframe Alignment)</h4>
            <p class="subtitle">
              将真机自动化回放执行动作序列的起止时间戳，高精度映射至 MP4 录屏轨道（计算毫秒级相对秒数与绝对帧号），自动对异常失败与自愈步骤建立关键帧书签。
            </p>
          </div>
          <div class="btn-group">
            <a-button @click="loadSampleIncident">
              载入典型异常对齐现场
            </a-button>
            <a-button type="primary" :loading="compiling" @click="handleCompileReport">
              生成时间线报告
            </a-button>
          </div>
        </div>

        <!-- 视频与执行指标卡 -->
        <div class="metrics-bar">
          <div class="metric-pill">
            <span class="lbl">录屏时长:</span>
            <strong>{{ report?.video_summary?.duration_seconds ?? 60.0 }} 秒</strong>
            <small class="unit">({{ report?.video_summary?.fps ?? 30 }} FPS)</small>
          </div>

          <div class="metric-pill">
            <span class="lbl">总视频帧数:</span>
            <strong>{{ report?.video_summary?.total_frames ?? 1800 }} 帧</strong>
          </div>

          <div class="metric-pill highlight">
            <span class="lbl">回放成功率:</span>
            <strong>{{ report?.execution_summary?.success_rate ?? 100 }}%</strong>
          </div>

          <div class="metric-pill">
            <span class="lbl">回放总体状态:</span>
            <a-tag :color="report?.execution_summary?.overall_status === 'passed' ? 'success' : 'error'">
              {{ report?.execution_summary?.overall_status === 'passed' ? '全部通过' : '存在异常/失败' }}
            </a-tag>
          </div>
        </div>
      </a-card>

      <!-- 交互式音画同步进度轨 (Interactive Timeline Scrubber) -->
      <a-card size="small" title="交互式时间轴轨道与关键帧书签 (Seek Markers)" class="track-card">
        <div class="timeline-scrubber-box">
          <div class="time-header">
            <span>00:00.00</span>
            <span class="current-seek-badge">
              当前跳转位点: <strong>{{ currentSeekTime.toFixed(2) }} 秒</strong> (帧 #{{ currentFrame }})
            </span>
            <span>{{ (report?.video_summary?.duration_seconds ?? 60.0).toFixed(2) }} 秒</span>
          </div>

          <!-- 时间轴长条 -->
          <div class="timeline-track-bar">
            <!-- 标记点 (Seek Markers) -->
            <div
              v-for="marker in report?.seek_markers ?? []"
              :key="marker.step_no"
              class="seek-marker-pin"
              :style="{
                left: `${Math.min(96, Math.max(4, (marker.timestamp_sec / (report?.video_summary?.duration_seconds || 60.0)) * 100))}%`,
                backgroundColor: marker.color || '#52c41a',
              }"
              :title="`步骤 #${marker.step_no} (${marker.type}): ${marker.timestamp_sec}s 帧 #${marker.frame}`"
              @click="seekToTime(marker.timestamp_sec, marker.frame, marker.step_no)"
            >
              <div class="marker-tooltip">
                #{{ marker.step_no }} ({{ marker.type }})
              </div>
            </div>

            <!-- 当前播放进度指示线 -->
            <div
              class="playhead-line"
              :style="{ left: `${Math.min(99, Math.max(0, (currentSeekTime / (report?.video_summary?.duration_seconds || 60.0)) * 100))}%` }"
            />
          </div>
        </div>
      </a-card>

      <!-- 逐步骤音画对齐数据清单 -->
      <a-card size="small" title="回放步骤毫秒级视频帧对齐明细" class="steps-card">
        <a-table
          :data-source="report?.timeline ?? []"
          :columns="columns"
          row-key="step_no"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'step_no'">
              <span :class="{ 'active-step-row': activeStepNo === record.step_no }">
                步骤 #{{ record.step_no }}
              </span>
            </template>

            <template v-if="column.key === 'action'">
              <code>{{ record.action }}</code>
            </template>

            <template v-if="column.key === 'video_range'">
              <span class="range-code">{{ record.video_start_sec }}s ~ {{ record.video_end_sec }}s</span>
            </template>

            <template v-if="column.key === 'keyframe'">
              <a-tag color="blue">帧 #{{ record.keyframe_frame }}</a-tag>
            </template>

            <template v-if="column.key === 'highlight'">
              <a-tag v-if="record.highlight_type === 'self_healed'" color="orange">
                自愈关键帧
              </a-tag>
              <a-tag v-else-if="record.highlight_type === 'failure'" color="red">
                失败现场关键帧
              </a-tag>
              <a-tag v-else color="green">
                正常回放
              </a-tag>
            </template>

            <template v-if="column.key === 'seek_action'">
              <a-button
                size="small"
                type="link"
                @click="seekToTime(record.video_start_sec, record.keyframe_frame, record.step_no)"
              >
                跳转此帧
              </a-button>
            </template>
          </template>

          <template #expandedRowRender="{ record }">
            <div class="detail-expanded">
              <a-alert
                v-if="record.error_message"
                type="error"
                show-icon
                :message="`失败现场排障信息: ${record.error_message}`"
                style="margin-bottom: 8px;"
              />
              <a-alert
                v-if="record.healing_details"
                type="warning"
                show-icon
                :message="`智能自愈诊断: ${record.healing_details}`"
              />
            </div>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  devicePlaybackApi,
  type PlaybackTimelineReport,
} from '@/api/devicePlayback'

const props = withDefaults(
  defineProps<{
    open: boolean
    sessionId?: string
    platform?: string
  }>(),
  {
    open: false,
    sessionId: 'pb_sess_sample_01',
    platform: 'android',
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const compiling = ref(false)
const report = ref<PlaybackTimelineReport | null>(null)
const currentSeekTime = ref(0.0)
const currentFrame = ref(0)
const activeStepNo = ref<number | null>(null)

const columns = [
  { title: '步骤序号', key: 'step_no', width: 95 },
  { title: '动作类型', key: 'action', width: 110 },
  { title: '视频时间区间', key: 'video_range', width: 140 },
  { title: '绝对帧号', key: 'keyframe', width: 100 },
  { title: '对齐高亮', key: 'highlight', width: 130 },
  { title: '视频定位', key: 'seek_action', width: 90 },
]

function handleClose() {
  emit('update:open', false)
}

function seekToTime(sec: number, frame: number, stepNo: number) {
  currentSeekTime.value = sec
  currentFrame.value = frame
  activeStepNo.value = stepNo
  message.info(`已对齐跳转至视频第 ${sec}s (绝对帧号 #${frame})`)
}

function loadSampleIncident() {
  currentSeekTime.value = 1.2
  currentFrame.value = 36
  message.success('已载入音画对齐典型异常现场！')
}

async function handleCompileReport() {
  compiling.value = true
  try {
    const sampleSteps = [
      {
        step_no: 1,
        action: 'click',
        params: { resource_id: 'btn_search' },
        status: 'passed',
        duration_ms: 150,
      },
      {
        step_no: 2,
        action: 'input_text',
        params: { text: '智能手表' },
        status: 'healed',
        duration_ms: 450,
        healed: true,
        healing_details: '组件定位由无障碍树模糊评分自愈补偿',
      },
      {
        step_no: 3,
        action: 'assert_text',
        params: { expected_text: '热卖爆款' },
        status: 'failed',
        duration_ms: 200,
        error_message: '断言失败: 未能在屏幕找到期望文本 "热卖爆款"',
      },
    ]

    const res = await devicePlaybackApi.compileRawTimelineReport({
      session_id: props.sessionId || 'pb_sess_sample_01',
      platform: props.platform || 'android',
      step_records: sampleSteps,
      video_duration_seconds: 30.0,
      fps: 30.0,
    })
    report.value = res
    message.success('音画逐帧对齐时间线报告生成成功！')
  } catch (err: any) {
    message.error(err.message || '生成时间线报告失败')
  } finally {
    compiling.value = false
  }
}
</script>

<style scoped>
.playback-keyframe-timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-card,
.track-card,
.steps-card {
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

.unit {
  font-size: 11px;
  color: #94a3b8;
  font-weight: normal;
}

.timeline-scrubber-box {
  padding: 10px 4px;
}

.time-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  margin-bottom: 10px;
}

.current-seek-badge {
  color: #2563eb;
}

.timeline-track-bar {
  position: relative;
  height: 28px;
  background: #0f172a;
  border-radius: 6px;
  border: 1px solid #334155;
  cursor: pointer;
}

.seek-marker-pin {
  position: absolute;
  top: 4px;
  width: 14px;
  height: 20px;
  border-radius: 3px;
  transform: translateX(-50%);
  cursor: pointer;
  box-shadow: 0 0 6px rgba(0, 0, 0, 0.4);
  transition: transform 0.2s;
}

.seek-marker-pin:hover {
  transform: translateX(-50%) scale(1.2);
}

.marker-tooltip {
  display: none;
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: #1e293b;
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  white-space: nowrap;
}

.seek-marker-pin:hover .marker-tooltip {
  display: block;
}

.playhead-line {
  position: absolute;
  top: 0;
  width: 2px;
  height: 100%;
  background: #38bdf8;
  box-shadow: 0 0 8px #38bdf8;
  pointer-events: none;
}

.range-code {
  font-family: monospace;
  font-size: 11px;
  color: #475569;
}

.active-step-row {
  color: #2563eb;
  font-weight: 600;
}

.detail-expanded {
  padding: 6px 0;
}
</style>
