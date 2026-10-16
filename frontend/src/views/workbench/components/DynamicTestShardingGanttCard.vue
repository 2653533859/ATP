<template>
  <div class="dynamic-test-sharding-gantt-card">
    <a-card size="small" class="sharding-panel" :bordered="false">
      <!-- 头部控制栏 -->
      <template #title>
        <div class="panel-header-row">
          <div class="header-left">
            <AppstoreOutlined class="panel-icon" />
            <span class="panel-title">多容器 Worker 负载均衡动态测试切片甘特图</span>
            <a-tag color="processing">LPT 贪心装箱算法</a-tag>
          </div>

          <div class="header-right">
            <a-space size="small">
              <span class="ctrl-lbl">目标容器分片数:</span>
              <a-radio-group v-model:value="targetShards" size="small" button-style="solid" @change="handleRunPartition">
                <a-radio-button :value="2">2 Shards</a-radio-button>
                <a-radio-button :value="4">4 Shards</a-radio-button>
                <a-radio-button :value="8">8 Shards</a-radio-button>
              </a-radio-group>

              <a-button size="small" :loading="loading" @click="handleRunPartition">
                <ReloadOutlined /> 重新试算
              </a-button>
            </a-space>
          </div>
        </div>
      </template>

      <a-spin :spinning="loading">
        <template v-if="currentReport">
          <!-- 核心性能收益 KPI 指标卡 -->
          <div class="metrics-grid">
            <div class="metric-box highlight-green">
              <span class="m-lbl">理论并发加速比</span>
              <div class="m-val-row">
                <span class="m-val text-success">{{ currentReport.theoretical_speedup_ratio }}x</span>
              </div>
              <span class="m-sub">相比单机串行执行提速</span>
            </div>

            <div class="metric-box">
              <span class="m-lbl">木桶瓶颈上限 (Max Shard)</span>
              <div class="m-val-row">
                <span class="m-val text-blue">{{ currentReport.max_shard_duration_sec }}</span>
                <span class="m-unit">秒</span>
              </div>
              <span class="m-sub">决定全流水线交付时间</span>
            </div>

            <div class="metric-box">
              <span class="m-lbl">分片耗时极小方差</span>
              <div class="m-val-row">
                <span class="m-val text-purple">{{ currentReport.duration_variance }}</span>
              </div>
              <span class="m-sub">数值越小负载越均匀</span>
            </div>

            <div class="metric-box">
              <span class="m-lbl">切片装箱用例总数</span>
              <div class="m-val-row">
                <span class="m-val text-orange">{{ currentReport.total_cases_count }}</span>
                <span class="m-unit">用例 ({{ currentReport.actual_shards_count }} 桶)</span>
              </div>
              <span class="m-sub">单机等效总耗时 ~{{ currentReport.total_estimated_duration_sec }}s</span>
            </div>
          </div>

          <!-- 甘特图横向切片负载可视化区 -->
          <div class="gantt-chart-section">
            <div class="gantt-header-row">
              <span class="gantt-title">分片执行负载分布甘特视图 (Shards Gantt Distribution)</span>
              <div class="gantt-legend">
                <span class="leg-item"><span class="dot bottleneck-dot" /> 木桶瓶颈分片 (Max Time)</span>
                <span class="leg-item"><span class="dot normal-dot" /> 均衡装箱分片</span>
              </div>
            </div>

            <div class="gantt-rows-container">
              <div
                v-for="shard in currentReport.shards || []"
                :key="shard.shard_index"
                class="gantt-shard-row"
                :class="{ 'shard-bottleneck': shard.estimated_duration_sec === currentReport.max_shard_duration_sec }"
              >
                <div class="shard-info-col">
                  <span class="shard-name font-bold">Shard #{{ shard.shard_index }}</span>
                  <small class="shard-pod-id mono">{{ shard.worker_assigned_id }}</small>
                </div>

                <div class="shard-track-col">
                  <div
                    class="shard-bar"
                    :style="{ width: `${getBarWidthPercentage(shard.estimated_duration_sec)}%` }"
                  >
                    <span class="shard-bar-time font-bold">{{ shard.estimated_duration_sec }}s</span>
                    <span class="shard-bar-cases">({{ shard.cases_count }} 用例)</span>
                  </div>
                </div>

                <div class="shard-cases-col">
                  <a-space :size="3" wrap>
                    <a-tag
                      v-for="cid in shard.case_ids.slice(0, 4)"
                      :key="cid"
                      size="small"
                      color="blue"
                    >
                      #{{ cid }}
                    </a-tag>
                    <span v-if="shard.case_ids.length > 4" class="more-cases-tag">
                      +{{ shard.case_ids.length - 4 }}
                    </span>
                  </a-space>
                </div>
              </div>
            </div>
          </div>

          <!-- 分片详细数据表格 -->
          <div class="shards-table-section">
            <a-table
              :data-source="currentReport.shards || []"
              :columns="tableColumns"
              row-key="shard_index"
              size="small"
              :pagination="false"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'shard_index'">
                  <div class="shard-tag-box">
                    <a-tag :color="record.estimated_duration_sec === currentReport.max_shard_duration_sec ? 'error' : 'processing'">
                      分片 #{{ record.shard_index }}
                    </a-tag>
                    <span v-if="record.estimated_duration_sec === currentReport.max_shard_duration_sec" class="bottleneck-tag">
                      木桶上限
                    </span>
                  </div>
                </template>

                <template v-else-if="column.key === 'worker_assigned_id'">
                  <span class="mono-text">{{ record.worker_assigned_id }}</span>
                </template>

                <template v-else-if="column.key === 'estimated_duration_sec'">
                  <span class="mono-text font-bold" :class="record.estimated_duration_sec === currentReport.max_shard_duration_sec ? 'text-danger' : 'text-success'">
                    {{ record.estimated_duration_sec }} 秒
                  </span>
                </template>

                <template v-else-if="column.key === 'case_ids'">
                  <a-space :size="2" wrap>
                    <a-tag v-for="cid in record.case_ids" :key="cid" size="small">
                      #{{ cid }}
                    </a-tag>
                  </a-space>
                </template>
              </template>
            </a-table>
          </div>
        </template>

        <a-empty v-else description="暂无动态分片数据，请点击「重新试算」" />
      </a-spin>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  AppstoreOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type DynamicShardingReportItem,
} from '@/api/ciImpact'

const props = withDefaults(
  defineProps<{
    initialCaseIds?: number[]
  }>(),
  {
    initialCaseIds: () => [101, 102, 103, 104, 105, 106, 107, 108],
  }
)

const loading = ref(false)
const targetShards = ref(4)
const currentReport = ref<DynamicShardingReportItem | null>(null)

// 模拟用例历史执行耗时 (秒)
const sampleDurationHistory: Record<number, number> = {
  101: 14.5,
  102: 12.0,
  103: 9.5,
  104: 8.0,
  105: 6.5,
  106: 5.0,
  107: 4.2,
  108: 2.8,
}

const tableColumns = [
  { title: '分片编号', key: 'shard_index', width: 140 },
  { title: '调度 Worker 容器', key: 'worker_assigned_id', width: 220 },
  { title: '装箱用例数', dataIndex: 'cases_count', width: 100 },
  { title: '预估分片总耗时', key: 'estimated_duration_sec', width: 140 },
  { title: '分配执行的用例列表', key: 'case_ids' },
]

function getBarWidthPercentage(duration: number): number {
  if (!currentReport.value || !currentReport.value.max_shard_duration_sec) return 50
  const max = currentReport.value.max_shard_duration_sec
  return Math.max(15, Math.min(100, Math.round((duration / max) * 100)))
}

async function handleRunPartition() {
  loading.value = true
  try {
    const res = await ciImpactApi.partitionShards({
      case_ids: props.initialCaseIds,
      target_shards_count: targetShards.value,
      case_duration_history: sampleDurationHistory,
      default_case_duration_sec: 3.5,
    })
    currentReport.value = res.report
    message.success(res.message || 'LPT 动态切片装箱完成')
  } catch (err: any) {
    message.error(`分片失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  handleRunPartition()
})
</script>

<style scoped>
.dynamic-test-sharding-gantt-card {
  margin-top: 14px;
}

.sharding-panel {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  background: var(--c-bg-card, #ffffff);
}

.panel-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-icon {
  font-size: 16px;
  color: #2563eb;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.ctrl-lbl {
  font-size: 12px;
  color: #64748b;
}

/* 核心 KPI 卡片网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.metric-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
}

.highlight-green {
  background: #ecfdf5;
  border-color: #a7f3d0;
}

.m-lbl {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.m-val-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.m-val {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
  color: #0f172a;
}

.m-unit {
  font-size: 11px;
  color: #64748b;
}

.m-sub {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 4px;
}

.text-success {
  color: #10b981;
}

.text-blue {
  color: #2563eb;
}

.text-purple {
  color: #8b5cf6;
}

.text-orange {
  color: #f59e0b;
}

.text-danger {
  color: #ef4444;
}

/* 甘特图区 */
.gantt-chart-section {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 14px;
}

.gantt-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 12px;
}

.gantt-title {
  font-weight: 600;
  color: #1e293b;
}

.gantt-legend {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #64748b;
}

.leg-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.bottleneck-dot {
  background: #ef4444;
}

.normal-dot {
  background: #3b82f6;
}

.gantt-rows-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gantt-shard-row {
  display: grid;
  grid-template-columns: 180px 1fr 180px;
  align-items: center;
  gap: 12px;
  background: #ffffff;
  padding: 6px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
}

.shard-bottleneck {
  border-color: #fca5a5;
  background: #fff5f5;
}

.shard-info-col {
  display: flex;
  flex-direction: column;
}

.shard-name {
  font-size: 12px;
  color: #0f172a;
}

.shard-pod-id {
  font-size: 10px;
  color: #94a3b8;
}

.shard-track-col {
  display: flex;
  align-items: center;
}

.shard-bar {
  background: linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%);
  height: 22px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  color: #ffffff;
  gap: 6px;
  transition: width 0.3s ease;
}

.shard-bottleneck .shard-bar {
  background: linear-gradient(90deg, #ef4444 0%, #f87171 100%);
}

.shard-bar-time {
  font-size: 11px;
  font-family: monospace;
}

.shard-bar-cases {
  font-size: 10px;
  opacity: 0.9;
}

.shard-cases-col {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.more-cases-tag {
  font-size: 10px;
  color: #94a3b8;
}

.font-bold {
  font-weight: 700;
}

.mono {
  font-family: monospace;
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}

.shard-tag-box {
  display: flex;
  align-items: center;
  gap: 4px;
}

.bottleneck-tag {
  font-size: 10px;
  color: #dc2626;
  background: #fee2e2;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 600;
}
</style>
