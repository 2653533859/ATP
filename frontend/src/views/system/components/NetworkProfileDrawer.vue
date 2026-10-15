<template>
  <a-drawer
    :open="visible"
    title="移动端弱网仿真档案与参数试算"
    width="720px"
    placement="right"
    @close="handleClose"
  >
    <div class="network-profile-drawer">
      <!-- 预设档案概览 -->
      <div class="section-title">预设仿真网络档案</div>
      <a-spin :spinning="loading">
        <div class="profile-grid">
          <div
            v-for="(profile, key) in profiles"
            :key="key"
            class="profile-card"
            :class="{ active: selectedProfileId === key }"
            @click="selectProfile(String(key))"
          >
            <div class="profile-header">
              <span class="profile-name">{{ profile.name }}</span>
              <a-tag :color="profile.offline ? 'red' : profile.packet_loss_percent > 10 ? 'orange' : 'blue'">
                {{ profile.offline ? '断网' : `${profile.download_kbps} kbps` }}
              </a-tag>
            </div>
            <div class="profile-details">
              <div>延迟: <strong>{{ profile.latency_ms }} ms</strong></div>
              <div>丢包率: <strong>{{ profile.packet_loss_percent }}%</strong></div>
              <div>上行: <strong>{{ profile.upload_kbps }} kbps</strong></div>
            </div>
            <div v-if="profile.description" class="profile-desc">
              {{ profile.description }}
            </div>
          </div>
        </div>
      </a-spin>

      <a-divider />

      <!-- 交互试算器 -->
      <div class="section-title">弱网传输参数模拟试算</div>
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="模拟数据包大小 (Bytes)">
              <a-input-number
                v-model:value="payloadBytes"
                :min="0"
                :step="1024"
                style="width: 100%"
                placeholder="例如 65536 (64KB)"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="当前选定弱网模式">
              <a-select v-model:value="selectedProfileId" style="width: 100%" @change="onProfileChange">
                <a-select-option v-for="(p, k) in profiles" :key="k" :value="String(k)">
                  {{ p.name }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-button type="primary" :loading="evaluating" @click="runEvaluation">
          执行参数试算
        </a-button>
      </a-form>

      <!-- 试算结果卡片 -->
      <div v-if="evaluationResult" class="evaluation-result-panel">
        <div class="section-title">预期传输指标与底层注入指令</div>
        <a-row :gutter="16" class="metric-row">
          <a-col :span="8">
            <a-statistic
              title="预计传输延迟"
              :value="evaluationResult.estimated_delay_seconds"
              suffix="秒"
              :precision="3"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic
              title="丢包判定状态"
              :value="evaluationResult.is_dropped ? '随机触发丢包' : '正常通过'"
              :value-style="{ color: evaluationResult.is_dropped ? '#cf1322' : '#3f8600' }"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic
              title="离线断网状态"
              :value="evaluationResult.offline ? '离线 (OFFLINE)' : '在线受限'"
            />
          </a-col>
        </a-row>

        <div class="code-block-title">Web 端 CDP 网络条件 (Network.emulateNetworkConditions):</div>
        <pre class="code-preview">{{ JSON.stringify(evaluationResult.cdp_conditions, null, 2) }}</pre>

        <div class="code-block-title">移动端 Android ADB tc netem 指令:</div>
        <div class="adb-commands">
          <div v-for="(cmd, idx) in evaluationResult.adb_commands" :key="idx" class="cmd-line">
            $ {{ cmd.join(' ') }}
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import {
  networkSimulationApi,
  type NetworkProfile,
  type NetworkEvaluateResponse,
} from '@/api/networkSimulation'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const loading = ref(false)
const evaluating = ref(false)
const profiles = ref<Record<string, NetworkProfile>>({})
const selectedProfileId = ref('2g_edge')
const payloadBytes = ref(65536)
const evaluationResult = ref<NetworkEvaluateResponse | null>(null)

const fetchProfiles = async () => {
  loading.value = true
  try {
    const res = await networkSimulationApi.getProfiles()
    profiles.value = res || {}
    if (profiles.value && !profiles.value[selectedProfileId.value]) {
      const keys = Object.keys(profiles.value)
      if (keys.length > 0) {
        selectedProfileId.value = keys[0]
      }
    }
  } catch (err) {
    // Graceful fallback
    profiles.value = {
      '2g_edge': {
        name: '2G (EDGE 良好)',
        latency_ms: 300,
        download_kbps: 250,
        upload_kbps: 200,
        packet_loss_percent: 2.0,
        offline: false,
        description: '高延迟与窄带宽移动环境',
      },
      '4g_lte': {
        name: '4G (LTE 城市)',
        latency_ms: 50,
        download_kbps: 30000,
        upload_kbps: 15000,
        packet_loss_percent: 0.5,
        offline: false,
        description: '常规移动蜂窝网络',
      },
    }
  } finally {
    loading.value = false
  }
}

const selectProfile = (id: string) => {
  selectedProfileId.value = id
  runEvaluation()
}

const onProfileChange = () => {
  runEvaluation()
}

const runEvaluation = async () => {
  evaluating.value = true
  try {
    const res = await networkSimulationApi.evaluate({
      profile_id: selectedProfileId.value,
      payload_bytes: payloadBytes.value,
    })
    evaluationResult.value = res
  } catch {
    // Local fallback calculation for preview
    const prof = profiles.value[selectedProfileId.value]
    if (prof) {
      evaluationResult.value = {
        profile_id: selectedProfileId.value,
        is_dropped: prof.packet_loss_percent > 10,
        estimated_delay_seconds: prof.offline ? 999.0 : Number(((prof.latency_ms / 1000) + (payloadBytes.value * 8 / (prof.download_kbps * 1024))).toFixed(3)),
        offline: prof.offline,
        cdp_conditions: {
          offline: prof.offline,
          latency: prof.latency_ms,
          downloadThroughput: (prof.download_kbps * 1024) / 8,
          uploadThroughput: (prof.upload_kbps * 1024) / 8,
        },
        adb_commands: [
          ['adb', 'shell', 'tc', 'qdisc', 'add', 'dev', 'wlan0', 'root', 'netem', 'delay', `${prof.latency_ms}ms`],
        ],
      }
    }
  } finally {
    evaluating.value = false
  }
}

const handleClose = () => {
  emit('update:visible', false)
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      fetchProfiles()
      runEvaluation()
    }
  },
)

onMounted(() => {
  if (props.visible) {
    fetchProfiles()
  }
})
</script>

<style scoped>
.network-profile-drawer {
  padding: 4px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--c-text-primary, #1f2937);
}
.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.profile-card {
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--c-bg-surface, #ffffff);
}
.profile-card:hover {
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.15);
}
.profile-card.active {
  border-color: #1890ff;
  background: rgba(24, 144, 255, 0.05);
}
.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.profile-name {
  font-weight: 600;
  font-size: 13px;
}
.profile-details {
  font-size: 12px;
  color: var(--c-text-secondary, #6b7280);
  line-height: 1.6;
}
.profile-desc {
  font-size: 11px;
  color: var(--c-text-tertiary, #9ca3af);
  margin-top: 6px;
}
.evaluation-result-panel {
  margin-top: 20px;
  padding: 16px;
  background: var(--c-bg-page, #f9fafb);
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle, #e5e7eb);
}
.metric-row {
  margin-bottom: 16px;
}
.code-block-title {
  font-size: 12px;
  font-weight: 600;
  margin-top: 12px;
  margin-bottom: 6px;
  color: var(--c-text-secondary, #4b5563);
}
.code-preview {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 10px;
  border-radius: 6px;
  font-size: 11px;
  overflow-x: auto;
  max-height: 160px;
}
.adb-commands {
  background: #282c34;
  color: #98c379;
  padding: 10px;
  border-radius: 6px;
  font-family: monospace;
  font-size: 12px;
}
.cmd-line {
  margin-bottom: 4px;
}
</style>
