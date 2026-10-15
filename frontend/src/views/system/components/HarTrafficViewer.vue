<template>
  <div class="har-traffic-viewer">
    <!-- 顶部上传与示例控制栏 -->
    <div class="toolbar-box">
      <div class="toolbar-info">
        <h3 class="viewer-title">网络抓包 (HAR 1.2) 流量分析与慢请求诊断</h3>
        <p class="viewer-subtitle">支持上传标准 .har 抓包文件或粘贴 JSON 日志，全景透视接口耗时瀑布流与慢请求瓶颈。</p>
      </div>
      <div class="toolbar-actions">
        <a-upload
          :before-upload="handleFileUpload"
          :show-upload-list="false"
          accept=".har,.json"
        >
          <a-button type="primary">
            <UploadOutlined /> 上传 HAR 文件
          </a-button>
        </a-upload>
        <a-button @click="loadSampleHar">
          载入示例 HAR
        </a-button>
      </div>
    </div>

    <!-- 加载中状态 -->
    <a-spin :spinning="loading">
      <div v-if="parsedData" class="content-body">
        <!-- 核心统计 KPI 卡片 -->
        <a-row :gutter="16" class="kpi-row">
          <a-col :span="6">
            <a-card size="small" class="kpi-card">
              <a-statistic title="总请求数" :value="parsedData.total_requests" suffix="次" />
            </a-card>
          </a-col>
          <a-col :span="6">
            <a-card size="small" class="kpi-card">
              <a-statistic
                title="请求成功率"
                :value="parsedData.success_rate"
                suffix="%"
                :value-style="{ color: parsedData.success_rate >= 95 ? '#3f8600' : '#cf1322' }"
              />
            </a-card>
          </a-col>
          <a-col :span="6">
            <a-card size="small" class="kpi-card">
              <a-statistic title="平均响应耗时" :value="parsedData.avg_latency_ms" suffix="ms" :precision="1" />
            </a-card>
          </a-col>
          <a-col :span="6">
            <a-card size="small" class="kpi-card">
              <a-statistic
                title="传输总流量"
                :value="formatBytes(parsedData.total_bytes_transferred).value"
                :suffix="formatBytes(parsedData.total_bytes_transferred).unit"
              />
            </a-card>
          </a-col>
        </a-row>

        <!-- 慢请求 Top 5 诊断卡片 -->
        <div class="section-box">
          <div class="section-header">
            <span class="section-tag">瓶颈诊断</span>
            <span class="section-title">最慢请求 Top 5 (Slowest Endpoints)</span>
          </div>

          <div class="slowest-grid">
            <div
              v-for="(item, idx) in parsedData.slowest_requests"
              :key="item.index"
              class="slow-card"
            >
              <div class="slow-rank">#{{ idx + 1 }}</div>
              <div class="slow-main">
                <div class="slow-topline">
                  <a-tag :color="getMethodColor(item.method)">{{ item.method }}</a-tag>
                  <a-tag :color="item.status >= 200 && item.status < 400 ? 'green' : 'red'">
                    HTTP {{ item.status }}
                  </a-tag>
                  <span class="slow-duration">{{ item.duration_ms }} ms</span>
                  <span class="slow-size">{{ formatBytes(item.bytes).formatted }}</span>
                </div>
                <div class="slow-url" :title="item.url">{{ item.url }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 抓包请求耗时瀑布流表格 -->
        <div class="section-box">
          <div class="section-header">
            <span class="section-title">抓包请求明细与耗时分布 ({{ filteredEntries.length }} 项)</span>
            <div class="filter-controls">
              <a-radio-group v-model:value="statusFilter" size="small" button-style="solid">
                <a-radio-button value="all">全部 ({{ parsedData.entries_summary.length }})</a-radio-button>
                <a-radio-button value="failed">仅异常 ({{ parsedData.failed_requests }})</a-radio-button>
              </a-radio-group>
              <a-input
                v-model:value="searchKeyword"
                size="small"
                placeholder="搜索 URL 路径..."
                style="width: 220px; margin-left: 8px"
                allow-clear
              />
            </div>
          </div>

          <a-table
            :columns="columns"
            :data-source="filteredEntries"
            :pagination="{ pageSize: 10 }"
            size="small"
            row-key="index"
            class="waterfall-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'method'">
                <a-tag :color="getMethodColor(record.method)">{{ record.method }}</a-tag>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status >= 200 && record.status < 400 ? 'green' : 'red'">
                  {{ record.status }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'url'">
                <span class="table-url" :title="record.url">{{ record.url }}</span>
              </template>
              <template v-else-if="column.key === 'duration'">
                <div class="waterfall-bar-box">
                  <div
                    class="waterfall-bar"
                    :style="{ width: `${getDurationPercent(record.duration_ms)}%` }"
                  />
                  <span class="waterfall-time">{{ record.duration_ms }} ms</span>
                </div>
              </template>
              <template v-else-if="column.key === 'bytes'">
                <span>{{ formatBytes(record.bytes).formatted }}</span>
              </template>
            </template>
          </a-table>
        </div>
      </div>

      <!-- 尚未载入任何数据时的引导视图 -->
      <a-empty
        v-else
        description="请上传 .har 抓包文件或点击上方「载入示例 HAR」进行即时诊断"
        style="margin: 60px 0"
      />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import { networkSimulationApi, type HarParseResponse, type HarEntry } from '@/api/networkSimulation'

const loading = ref(false)
const parsedData = ref<HarParseResponse | null>(null)
const statusFilter = ref<'all' | 'failed'>('all')
const searchKeyword = ref('')

const columns = [
  { title: '#', dataIndex: 'index', width: 60 },
  { title: '方法', key: 'method', width: 80 },
  { title: '状态', key: 'status', width: 80 },
  { title: '请求 URL', key: 'url', ellipsis: true },
  { title: '耗时瀑布流', key: 'duration', width: 220 },
  { title: '数据大小', key: 'bytes', width: 100 },
]

const maxDuration = computed(() => {
  if (!parsedData.value?.entries_summary.length) return 1000
  return Math.max(...parsedData.value.entries_summary.map((e) => e.duration_ms), 100)
})

const getDurationPercent = (ms: number): number => {
  return Math.max(5, Math.min(100, (ms / maxDuration.value) * 100))
}

const formatBytes = (bytes: number): { value: number; unit: string; formatted: string } => {
  if (bytes >= 1024 * 1024) {
    const v = Number((bytes / (1024 * 1024)).toFixed(2))
    return { value: v, unit: 'MB', formatted: `${v} MB` }
  }
  const v = Number((bytes / 1024).toFixed(1))
  return { value: v, unit: 'KB', formatted: `${v} KB` }
}

const getMethodColor = (method: string): string => {
  switch (method?.toUpperCase()) {
    case 'GET':
      return 'blue'
    case 'POST':
      return 'green'
    case 'PUT':
      return 'orange'
    case 'DELETE':
      return 'red'
    default:
      return 'default'
  }
}

const filteredEntries = computed<HarEntry[]>(() => {
  if (!parsedData.value) return []
  return parsedData.value.entries_summary.filter((item) => {
    if (statusFilter.value === 'failed' && !item.is_failed) return false
    if (searchKeyword.value) {
      return item.url.toLowerCase().includes(searchKeyword.value.toLowerCase())
    }
    return true
  })
})

const parseHarObject = async (harContent: string | Record<string, unknown>) => {
  loading.value = true
  try {
    const res = await networkSimulationApi.parseHar(harContent)
    parsedData.value = res
    message.success(`成功解析 HAR 抓包日志，捕获 ${res.total_requests} 个 HTTP 请求`)
  } catch (err: unknown) {
    const errorMsg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '解析 HAR 数据失败'
    message.error(errorMsg)
  } finally {
    loading.value = false
  }
}

const handleFileUpload = (file: File): boolean => {
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target?.result
    if (typeof content === 'string') {
      try {
        const json = JSON.parse(content)
        parseHarObject(json)
      } catch {
        parseHarObject(content)
      }
    }
  }
  reader.readAsText(file)
  return false // Block automatic browser upload
}

const loadSampleHar = () => {
  const sample = {
    log: {
      version: '1.2',
      entries: [
        {
          request: { method: 'GET', url: 'https://api.atp.io/v1/auth/session' },
          response: { status: 200, bodySize: 1240, headersSize: 320 },
          time: 85.4,
        },
        {
          request: { method: 'POST', url: 'https://api.atp.io/v1/cases/batch-run' },
          response: { status: 200, bodySize: 45200, headersSize: 450 },
          time: 1420.0,
        },
        {
          request: { method: 'GET', url: 'https://api.atp.io/v1/devices/matrix' },
          response: { status: 200, bodySize: 12800, headersSize: 380 },
          time: 320.5,
        },
        {
          request: { method: 'GET', url: 'https://cdn.atp.io/assets/bundle.js' },
          response: { status: 200, bodySize: 524000, headersSize: 220 },
          time: 680.0,
        },
        {
          request: { method: 'POST', url: 'https://api.atp.io/v1/payments/verify' },
          response: { status: 504, bodySize: 210, headersSize: 300 },
          time: 3150.2,
        },
        {
          request: { method: 'GET', url: 'https://api.atp.io/v1/reports/summary' },
          response: { status: 200, bodySize: 8400, headersSize: 350 },
          time: 210.0,
        },
      ],
    },
  }
  parseHarObject(sample)
}
</script>

<style scoped>
.har-traffic-viewer {
  padding: 8px 0;
}
.toolbar-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
}
.viewer-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: var(--c-text-primary, #111827);
}
.viewer-subtitle {
  font-size: 13px;
  color: var(--c-text-secondary, #6b7280);
  margin: 0;
}
.toolbar-actions {
  display: flex;
  gap: 10px;
}
.kpi-row {
  margin-bottom: 20px;
}
.kpi-card {
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
.section-box {
  margin-bottom: 24px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  padding: 16px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.section-tag {
  font-size: 11px;
  background: #ff4d4f;
  color: #ffffff;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  margin-right: 8px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary, #1f2937);
}
.slowest-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.slow-card {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  background: var(--c-bg-page, #f9fafb);
  border-radius: 6px;
  border-left: 4px solid #ff4d4f;
}
.slow-rank {
  font-size: 16px;
  font-weight: 800;
  color: #ff4d4f;
  margin-right: 16px;
  min-width: 32px;
}
.slow-main {
  flex: 1;
  min-width: 0;
}
.slow-topline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.slow-duration {
  font-weight: 700;
  color: #cf1322;
  font-size: 13px;
}
.slow-size {
  font-size: 12px;
  color: var(--c-text-tertiary, #9ca3af);
  margin-left: auto;
}
.slow-url {
  font-size: 12px;
  font-family: monospace;
  color: var(--c-text-secondary, #4b5563);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.table-url {
  font-family: monospace;
  font-size: 12px;
}
.waterfall-bar-box {
  display: flex;
  align-items: center;
  gap: 8px;
}
.waterfall-bar {
  height: 10px;
  background: linear-gradient(90deg, #1890ff, #722ed1);
  border-radius: 4px;
  transition: width 0.3s ease;
}
.waterfall-time {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-secondary, #4b5563);
  min-width: 55px;
}
</style>
