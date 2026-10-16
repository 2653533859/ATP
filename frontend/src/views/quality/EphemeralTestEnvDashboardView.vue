<template>
  <div class="page-shell ephemeral-dashboard-view">
    <!-- 顶部导航与操作栏 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <ClusterOutlined class="hero-icon" />
          <h2 class="page-title">临时沙箱测试环境生命周期拓扑与原子回收全景大盘</h2>
          <span class="live-dot" />
          <span class="muted-text text-xs">多租户隔离命名空间 · 动态 TTL 租约心跳 · 孤儿资源清道夫</span>
        </div>
        <p class="hero-subtitle">
          面向 PR/特性分支自动化拉起隔离容器环境，零污染双向回归，测试完成后优雅原子回收全量资源。
        </p>
      </div>
      <div class="hero-actions">
        <a-space>
          <a-button type="primary" @click="showProvisionModal = true">
            <PlusOutlined /> 快速拉起新测试沙箱
          </a-button>
          <a-button :loading="reclaiming" @click="handleReclaimExpired">
            <ClearOutlined /> 扫描并回收超期环境
          </a-button>
          <a-button :loading="loading" @click="fetchData">
            <ReloadOutlined /> 刷新大盘
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 机制说明 Banner -->
    <div class="mechanism-banner">
      <div class="banner-icon-col">
        <ApartmentOutlined class="banner-icon" />
      </div>
      <div class="banner-texts">
        <div class="banner-title">Kubernetes 多租户沙箱环境生命周期与租约治理体系 (T1.3)</div>
        <div class="banner-desc">
          每个沙箱分配独立的 Kubernetes 命名空间（<code>atp-eph-pr-xxx</code>）、路由隔离策略与虚拟中间件；默认绑定 3600 秒动态租约 TTL，支持心跳续期，并在超期或销毁后原子级释放计算与网络资源，杜绝资源泄漏。
        </div>
      </div>
    </div>

    <!-- 4 大核心 KPI 统计卡片 -->
    <a-row :gutter="[16, 16]" class="kpi-row">
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">活跃运行沙箱环境</div>
          <div class="stat-value text-primary">{{ activeEnvsCount }} <span class="unit">个</span></div>
          <div class="stat-trend">多分支独立隔离并发</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">已分配 CPU 核心配额</div>
          <div class="stat-value text-success">{{ totalAllocatedCpu }} <span class="unit">Cores</span></div>
          <div class="stat-trend">隔离计算资源限额</div>
        </div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-label">已分配内存容量配额</div>
        <div class="stat-value text-warning">{{ totalAllocatedMem }} <span class="unit">GiB</span></div>
        <div class="stat-trend">独立容器内存保障</div>
      </a-col>
      <a-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-label">累计历史回收沙箱数</div>
          <div class="stat-value text-purple">{{ destroyedCount }} <span class="unit">个</span></div>
          <div class="stat-trend">优雅销毁无孤儿残留</div>
        </div>
      </a-col>
    </a-row>

    <!-- 临时沙箱全景审计与生命周期控制大盘表格 -->
    <div class="table-section">
      <div class="table-header">
        <div class="section-title">临时沙箱测试环境列表与操作中心</div>
        <div class="table-filter">
          <a-checkbox v-model:checked="activeOnly" @change="fetchData">仅看活跃环境</a-checkbox>
        </div>
      </div>

      <a-table
        :data-source="environments"
        :columns="columns"
        :row-key="(r: any) => r.env_id"
        :loading="loading"
        size="middle"
        :pagination="{ pageSize: 6 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'env_name'">
            <div class="env-name-cell">
              <strong>{{ record.env_name }}</strong>
              <code class="ns-tag">{{ record.namespace }}</code>
            </div>
          </template>

          <template v-else-if="column.key === 'branch_or_pr'">
            <a-tag color="blue">{{ record.branch_or_pr }}</a-tag>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
          </template>

          <template v-else-if="column.key === 'resources'">
            <span>{{ record.cpu_limit_cores }}核 / {{ record.memory_limit_gib }}G</span>
          </template>

          <template v-else-if="column.key === 'ttl'">
            <div v-if="record.status !== 'DESTROYED'" class="ttl-cell">
              <span :class="record.is_expired ? 'text-danger' : 'text-primary'">
                {{ Math.floor(record.remaining_ttl_seconds / 60) }}m {{ record.remaining_ttl_seconds % 60 }}s
              </span>
              <a-button type="link" size="small" class="p-0 ml-1" @click="handleExtendLease(record.env_id)">
                续租30m
              </a-button>
            </div>
            <span v-else class="text-muted">已回收释放</span>
          </template>

          <template v-else-if="column.key === 'services'">
            <span class="text-xs">{{ record.services.join(', ') }}</span>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-popconfirm
                v-if="record.status !== 'DESTROYED'"
                title="确定优雅销毁并回收该沙箱测试环境吗？"
                @confirm="handleTeardown(record.env_id)"
              >
                <a-button size="small" danger type="link" :loading="tearingDownId === record.env_id">
                  原子销毁
                </a-button>
              </a-popconfirm>
              <span v-else class="text-xs text-muted">已清理</span>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 快速供给沙箱环境对话框 -->
    <a-modal
      v-model:open="showProvisionModal"
      title="快速供给拉起全新临时沙箱测试环境"
      destroy-on-close
      @ok="handleProvisionSubmit"
    >
      <div class="provision-form">
        <div class="form-item">
          <label class="form-label">代码分支或 PR 标识 (Branch / PR):</label>
          <a-input v-model:value="newBranchOrPr" placeholder="如 pr-2048-checkout 或 feat-order-split" />
        </div>
        <div class="form-item">
          <label class="form-label">CPU 核心配额 (Cores):</label>
          <a-input-number v-model:value="newCpuLimit" :min="1.0" :max="16.0" :step="0.5" class="w-full" />
        </div>
        <div class="form-item">
          <label class="form-label">内存容量配额 (GiB):</label>
          <a-input-number v-model:value="newMemLimit" :min="1.0" :max="32.0" :step="1.0" class="w-full" />
        </div>
        <div class="form-item">
          <label class="form-label">初始生存时间 TTL (秒):</label>
          <a-input-number v-model:value="newTtlSeconds" :min="300" :max="86400" :step="600" class="w-full" />
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ClusterOutlined,
  PlusOutlined,
  ClearOutlined,
  ReloadOutlined,
  ApartmentOutlined,
} from '@ant-design/icons-vue'
import {
  ephemeralTestEnvApi,
  type EphemeralEnvironment,
} from '@/api/cloudNativeCluster'

const loading = ref(false)
const reclaiming = ref(false)
const tearingDownId = ref<string | null>(null)
const activeOnly = ref(false)
const environments = ref<EphemeralEnvironment[]>([])

const showProvisionModal = ref(false)
const newBranchOrPr = ref('pr-1024-checkout')
const newCpuLimit = ref(2.0)
const newMemLimit = ref(4.0)
const newTtlSeconds = ref(3600)

const columns = [
  { title: '测试沙箱名称 / 命名空间', key: 'env_name', width: 280 },
  { title: '分支 / PR', key: 'branch_or_pr', width: 140 },
  { title: '状态', key: 'status', width: 110 },
  { title: '资源配额', key: 'resources', width: 120 },
  { title: '剩余租约 (TTL)', key: 'ttl', width: 140 },
  { title: '包含微服务', key: 'services' },
  { title: '操作', key: 'actions', width: 110 },
]

const activeEnvsCount = computed(() => {
  return environments.value.filter((e) => e.status !== 'DESTROYED').length
})

const destroyedCount = computed(() => {
  return environments.value.filter((e) => e.status === 'DESTROYED').length
})

const totalAllocatedCpu = computed(() => {
  const sum = environments.value
    .filter((e) => e.status !== 'DESTROYED')
    .reduce((acc, cur) => acc + (cur.cpu_limit_cores || 0), 0)
  return Math.round(sum * 10) / 10
})

const totalAllocatedMem = computed(() => {
  const sum = environments.value
    .filter((e) => e.status !== 'DESTROYED')
    .reduce((acc, cur) => acc + (cur.memory_limit_gib || 0), 0)
  return Math.round(sum * 10) / 10
})

function getStatusColor(status: string) {
  switch (status) {
    case 'READY': return 'success'
    case 'IN_USE': return 'processing'
    case 'PROVISIONING': return 'warning'
    case 'DESTROYED': return 'default'
    default: return 'default'
  }
}

async function fetchData() {
  loading.value = true
  try {
    const res = await ephemeralTestEnvApi.listEnvs({ active_only: activeOnly.value })
    environments.value = res.environments || []
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '获取沙箱列表失败')
  } finally {
    loading.value = false
  }
}

async function handleProvisionSubmit() {
  if (!newBranchOrPr.value) {
    message.warning('请填写分支或 PR 标识')
    return
  }
  try {
    const res = await ephemeralTestEnvApi.provision({
      branch_or_pr: newBranchOrPr.value,
      cpu_limit_cores: newCpuLimit.value,
      memory_limit_gib: newMemLimit.value,
      ttl_seconds: newTtlSeconds.value,
    })
    message.success(res.message || '沙箱测试环境已成功拉起')
    showProvisionModal.value = false
    await fetchData()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '供给失败')
  }
}

async function handleExtendLease(envId: string) {
  try {
    const res = await ephemeralTestEnvApi.extendLease(envId, { extra_seconds: 1800 })
    message.success(res.message || '租约已成功延长 30 分钟')
    await fetchData()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '续租失败')
  }
}

async function handleTeardown(envId: string) {
  tearingDownId.value = envId
  try {
    const res = await ephemeralTestEnvApi.teardown(envId)
    message.success(res.message || '沙箱环境已安全优雅销毁')
    await fetchData()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '销毁失败')
  } finally {
    tearingDownId.value = null
  }
}

async function handleReclaimExpired() {
  reclaiming.value = true
  try {
    const res = await ephemeralTestEnvApi.reclaimExpired()
    message.success(res.message || '已完成超期孤儿测试环境清理')
    await fetchData()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '回收失败')
  } finally {
    reclaiming.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.ephemeral-dashboard-view {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
  min-height: 100vh;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-icon {
  font-size: 22px;
  color: #2563eb;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.hero-subtitle {
  margin: 4px 0 0 0;
  color: var(--c-text-secondary, #64748b);
  font-size: 13px;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
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
  line-height: 1.5;
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
.text-purple { color: #7c3aed; }
.text-danger { color: #dc2626; }
.text-muted { color: #94a3b8; }

.table-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.env-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ns-tag {
  font-size: 10px;
  color: #64748b;
}

.ttl-cell {
  display: flex;
  align-items: center;
}

.p-0 { padding: 0; }
.ml-1 { margin-left: 4px; }
.w-full { width: 100%; }

.provision-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}
</style>
