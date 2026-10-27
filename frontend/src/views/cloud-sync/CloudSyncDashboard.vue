<template>
  <div class="cloud-sync-dashboard">
    <div class="dashboard-header">
      <div class="header-title-row">
        <h2 class="page-title">
          <CloudServerOutlined style="margin-right: 8px; color: var(--ant-primary-color)" />
          {{ t('cloud_sync.dashboard.title', '跨端结果汇总中心') }}
        </h2>
        <a-space>
          <a-tag v-if="localMode" color="blue">{{ t('cloud_sync.mode.local', '本地桌面节点') }}</a-tag>
          <a-tag v-else color="green">{{ t('cloud_sync.mode.cloud', '云端聚合服务') }}</a-tag>
          <a-button :loading="loading" @click="loadAllData">
            <ReloadOutlined /> {{ t('common.refresh', '刷新') }}
          </a-button>
          <a-button v-if="localMode" type="primary" :loading="syncing" @click="triggerManualSync">
            <SyncOutlined /> {{ t('cloud_sync.sync_now', '立即同步到云端') }}
          </a-button>
        </a-space>
      </div>
      <p class="header-desc">
        {{ localMode ? t('cloud_sync.local.description', '本机仅展示待同步队列；云端汇总结果请在云端 Web 端查看。') : t('cloud_sync.dashboard.desc', '汇集各 Windows 本地测试节点上报的脱敏结果摘要，统一统计通过率、运行时长及多机分布。') }}
      </p>
    </div>

    <a-card v-if="localMode" size="small" :title="t('cloud_sync.local.title', '本机同步状态')">
      <a-space wrap>
        <a-tag color="blue">{{ t('cloud_sync.local.pending', '待同步') }} {{ localStatus?.stats.pending ?? 0 }}</a-tag>
        <a-tag color="processing">{{ t('cloud_sync.local.syncing', '同步中') }} {{ localStatus?.stats.syncing ?? 0 }}</a-tag>
        <a-tag color="green">{{ t('cloud_sync.local.synced', '已同步') }} {{ localStatus?.stats.synced ?? 0 }}</a-tag>
        <a-tag color="red">{{ t('cloud_sync.local.failed', '失败待重试') }} {{ localStatus?.stats.failed ?? 0 }}</a-tag>
      </a-space>
    </a-card>

    <!-- 顶部核心指标看板 -->
    <a-row v-if="!localMode" :gutter="16" class="stats-row">
      <a-col :span="6">
        <a-card size="small" class="stat-card">
          <a-statistic
            :title="t('cloud_sync.stats.total_runs', '汇总运行总数')"
            :value="stats?.total_runs ?? 0"
          >
            <template #prefix><FileTextOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" class="stat-card">
          <a-statistic
            :title="t('cloud_sync.stats.pass_rate', '全局通过率')"
            :value="passRate"
            suffix="%"
            :value-style="{ color: passRate >= 90 ? '#52c41a' : (passRate >= 75 ? '#faad14' : '#ff4d4f') }"
          >
            <template #prefix><CheckCircleOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" class="stat-card">
          <a-statistic
            :title="t('cloud_sync.stats.connected_clients', '已连接电脑节点')"
            :value="stats?.connected_clients.length ?? 0"
            :value-style="{ color: '#1890ff' }"
          >
            <template #prefix><LaptopOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" class="stat-card">
          <a-statistic
            :title="t('cloud_sync.stats.failed_runs', '异常/失败用例')"
            :value="(stats?.status_distribution['failed'] ?? 0) + (stats?.status_distribution['error'] ?? 0)"
            :value-style="{ color: '#ff4d4f' }"
          >
            <template #prefix><CloseCircleOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- 连接电脑节点列表 -->
    <a-card
      v-if="!localMode && stats?.connected_clients && stats.connected_clients.length"
      size="small"
      :title="t('cloud_sync.clients.title', '上报客户端电脑清单')"
      style="margin-bottom: 16px"
    >
      <a-row :gutter="12">
        <a-col v-for="c in stats.connected_clients" :key="c.client_id" :span="8">
          <div class="client-box">
            <div class="client-header">
              <span class="client-name"><strong>{{ c.machine_name || 'Windows Desktop' }}</strong></span>
              <a-tag color="cyan">{{ c.runs_count }} 运行记录</a-tag>
            </div>
            <div class="client-id-text">
              <code>{{ c.client_id }}</code>
            </div>
          </div>
        </a-col>
      </a-row>
    </a-card>

    <!-- 汇总运行表格 -->
    <a-card v-if="!localMode" size="small" :title="t('cloud_sync.runs.title', '已上报运行列表')">
      <div class="table-toolbar">
        <a-space wrap>
          <a-select
            v-model:value="filterClientId"
            :placeholder="t('cloud_sync.filter.client', '按客户端电脑筛选')"
            allow-clear
            style="width: 220px"
            @change="handleFilterChange"
          >
            <a-select-option v-for="c in stats?.connected_clients" :key="c.client_id" :value="c.client_id">
              {{ c.machine_name }} ({{ c.client_id.slice(0, 10) }}...)
            </a-select-option>
          </a-select>

          <a-select
            v-model:value="filterRunType"
            :placeholder="t('cloud_sync.filter.type', '按类型筛选')"
            allow-clear
            style="width: 140px"
            @change="handleFilterChange"
          >
            <a-select-option value="case">API / 低代码</a-select-option>
            <a-select-option value="suite">测试套件</a-select-option>
            <a-select-option value="plan">测试计划</a-select-option>
            <a-select-option value="mobile_special">专项测试</a-select-option>
            <a-select-option value="performance">性能测试</a-select-option>
          </a-select>

          <a-select
            v-model:value="filterStatus"
            :placeholder="t('cloud_sync.filter.status', '按状态筛选')"
            allow-clear
            style="width: 130px"
            @change="handleFilterChange"
          >
            <a-select-option value="passed">Passed</a-select-option>
            <a-select-option value="failed">Failed</a-select-option>
            <a-select-option value="error">Error</a-select-option>
          </a-select>

          <a-button @click="resetFilters">{{ t('common.reset', '重置') }}</a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="runs"
        :loading="loading"
        :pagination="pagination"
        row-key="unique_key"
        size="middle"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'client'">
            <span><strong>{{ record.machine_name }}</strong></span>
            <div style="font-size: 11px; color: var(--c-text-tertiary)">{{ record.client_id.slice(0, 14) }}...</div>
          </template>

          <template v-else-if="column.key === 'title'">
            <div style="font-weight: 500">{{ record.title }}</div>
            <div style="font-size: 12px; color: var(--c-text-secondary)">{{ record.project_name }} ({{ record.project_code }})</div>
          </template>

          <template v-else-if="column.key === 'run_type'">
            <a-tag :color="typeTagColor(record.run_type)">{{ record.run_type }}</a-tag>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusTagColor(record.status)">{{ record.status }}</a-tag>
          </template>

          <template v-else-if="column.key === 'duration_ms'">
            <span>{{ record.duration_ms != null ? `${record.duration_ms} ms` : '-' }}</span>
          </template>

          <template v-else-if="column.key === 'reported_at'">
            <span style="font-size: 12px">{{ formatTimestamp(record.reported_at) }}</span>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-button type="link" size="small" @click="viewDetail(record.unique_key)">
              {{ t('common.view_detail', '查看详情') }}
            </a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:open="detailModalOpen"
      :title="selectedRun?.title || t('cloud_sync.modal.detail_title', '运行摘要详情')"
      width="780px"
      :footer="null"
    >
      <template v-if="selectedRun">
        <a-descriptions bordered size="small" :column="2" style="margin-bottom: 16px">
          <a-descriptions-item label="唯一键" :span="2"><code>{{ selectedRun.unique_key }}</code></a-descriptions-item>
          <a-descriptions-item label="来源电脑">{{ selectedRun.machine_name }} ({{ selectedRun.client_id }})</a-descriptions-item>
          <a-descriptions-item label="所属项目">{{ selectedRun.project_name }} ({{ selectedRun.project_code }})</a-descriptions-item>
          <a-descriptions-item label="运行类型"><a-tag :color="typeTagColor(selectedRun.run_type)">{{ selectedRun.run_type }}</a-tag></a-descriptions-item>
          <a-descriptions-item label="终态"><a-tag :color="statusTagColor(selectedRun.status)">{{ selectedRun.status }}</a-tag></a-descriptions-item>
          <a-descriptions-item label="耗时">{{ selectedRun.duration_ms ? `${selectedRun.duration_ms} ms` : '-' }}</a-descriptions-item>
          <a-descriptions-item label="上报时间">{{ formatTimestamp(selectedRun.reported_at) }}</a-descriptions-item>
          <a-descriptions-item v-if="selectedRun.error_summary" label="错误摘要" :span="2">
            <span style="color: #ff4d4f; word-break: break-all">{{ selectedRun.error_summary }}</span>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 步骤分解 -->
        <div v-if="selectedRun.steps && selectedRun.steps.length">
          <h4 style="margin-bottom: 8px; font-weight: 600">{{ t('cloud_sync.modal.steps', '步骤脱敏摘要') }} ({{ selectedRun.steps.length }})</h4>
          <a-table
            :columns="stepColumns"
            :data-source="selectedRun.steps"
            :pagination="false"
            row-key="step_index"
            size="small"
          >
            <template #bodyCell="{ column, record: st }">
              <template v-if="column.key === 'status'">
                <a-tag :color="statusTagColor(st.status)">{{ st.status }}</a-tag>
              </template>
              <template v-else-if="column.key === 'duration_ms'">
                <span>{{ st.duration_ms ? `${st.duration_ms} ms` : '-' }}</span>
              </template>
              <template v-else-if="column.key === 'error_summary'">
                <span v-if="st.error_summary" style="color: #ff4d4f; font-size: 12px">{{ st.error_summary }}</span>
                <span v-else style="color: var(--c-text-tertiary)">-</span>
              </template>
            </template>
          </a-table>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  CloudServerOutlined,
  ReloadOutlined,
  SyncOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LaptopOutlined,
} from '@ant-design/icons-vue'
import {
  cloudSyncApi,
  type CloudRunItem,
  type CloudRunDetail,
  type CloudSyncStats,
  type CloudSyncLocalStatus,
} from '@/api'
import { getRuntimeMode } from '@/runtimeMode'

const { t } = useI18n()
const localMode = computed(() => getRuntimeMode()?.mode === 'local')

const loading = ref(false)
const syncing = ref(false)
const stats = ref<CloudSyncStats | null>(null)
const localStatus = ref<CloudSyncLocalStatus | null>(null)
const runs = ref<CloudRunItem[]>([])

const filterClientId = ref<string | undefined>()
const filterRunType = ref<string | undefined>()
const filterStatus = ref<string | undefined>()

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
})

const detailModalOpen = ref(false)
const selectedRun = ref<CloudRunDetail | null>(null)

const columns = [
  { title: '来源客户端', key: 'client', width: 170 },
  { title: '项目与用例', key: 'title', minWidth: 220 },
  { title: '类型', key: 'run_type', width: 110 },
  { title: '状态', key: 'status', width: 95 },
  { title: '耗时', key: 'duration_ms', width: 95 },
  { title: '上报时间', key: 'reported_at', width: 165 },
  { title: '操作', key: 'actions', width: 95, align: 'center' as const },
]

const stepColumns = [
  { title: '#', dataIndex: 'step_index', width: 50 },
  { title: '步骤名称', dataIndex: 'name', width: 200 },
  { title: '状态', key: 'status', width: 90 },
  { title: '耗时', key: 'duration_ms', width: 90 },
  { title: '错误摘要', key: 'error_summary', ellipsis: true },
]

const passRate = computed(() => {
  if (!stats.value || stats.value.total_runs === 0) return 0
  const passed = stats.value.status_distribution['passed'] || 0
  return Math.round((passed / stats.value.total_runs) * 100)
})

function typeTagColor(type: string): string {
  switch (type) {
    case 'case': return 'blue'
    case 'suite': return 'purple'
    case 'plan': return 'cyan'
    case 'mobile_special': return 'orange'
    case 'performance': return 'magenta'
    default: return 'default'
  }
}

function statusTagColor(status: string): string {
  switch (status) {
    case 'passed': return 'green'
    case 'failed': return 'red'
    case 'error': return 'volcano'
    case 'running': return 'processing'
    default: return 'default'
  }
}

function formatTimestamp(ts?: string | null): string {
  if (!ts) return '-'
  return ts.slice(0, 19).replace('T', ' ')
}

async function loadStats() {
  try {
    stats.value = await cloudSyncApi.getStats()
  } catch (err) {
    console.error('Failed to load cloud sync stats:', err)
  }
}

async function loadRuns() {
  loading.value = true
  try {
    const res = await cloudSyncApi.listRuns({
      client_id: filterClientId.value,
      run_type: filterRunType.value,
      status: filterStatus.value,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })
    runs.value = res.items
    pagination.value.total = res.total
  } catch (err) {
    message.error(t('cloud_sync.msg.load_failed', '加载云端汇总数据失败'))
  } finally {
    loading.value = false
  }
}

async function loadAllData() {
  if (localMode.value) {
    try {
      localStatus.value = await cloudSyncApi.getLocalStatus()
    } catch (err) {
      message.error(t('cloud_sync.msg.load_failed', '加载同步状态失败'))
    }
  } else {
    await Promise.all([loadStats(), loadRuns()])
  }
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  void loadRuns()
}

function handleFilterChange() {
  pagination.value.current = 1
  void loadRuns()
}

function resetFilters() {
  filterClientId.value = undefined
  filterRunType.value = undefined
  filterStatus.value = undefined
  pagination.value.current = 1
  void loadRuns()
}

async function viewDetail(uniqueKey: string) {
  try {
    const detail = await cloudSyncApi.getRunDetail(uniqueKey)
    selectedRun.value = detail
    detailModalOpen.value = true
  } catch (err) {
    message.error(t('cloud_sync.msg.load_detail_failed', '加载详情失败'))
  }
}

async function triggerManualSync() {
  syncing.value = true
  try {
    const res = await cloudSyncApi.syncNow()
    message.success(`已完成同步：成功 ${res.synced} 条，失败 ${res.failed} 条`)
    await loadAllData()
  } catch (err) {
    message.error('触发同步失败，请检查网络和云端连接')
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  void loadAllData()
})
</script>

<style scoped>
.cloud-sync-dashboard {
  padding: 16px 20px;
}

.dashboard-header {
  margin-bottom: 16px;
}

.header-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-desc {
  margin-top: 4px;
  color: var(--c-text-secondary);
  font-size: 13px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 6px;
}

.client-box {
  background: var(--c-bg-layout, #f5f7fa);
  border: 1px solid var(--c-border, #e4e7ed);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.client-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.client-name {
  font-size: 13px;
}

.client-id-text {
  margin-top: 4px;
  font-size: 11px;
}

.table-toolbar {
  margin-bottom: 12px;
}
</style>
