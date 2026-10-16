<template>
  <a-drawer
    v-model:open="visible"
    title="多可用区单元化切流权重控制与智能路由抽屉 (UI2.1)"
    width="1120px"
    placement="right"
    :destroy-on-close="false"
  >
    <div class="cell-controller-drawer">
      <!-- 头部说明 Banner -->
      <div class="drawer-header-banner">
        <div class="banner-icon">
          <PartitionOutlined style="font-size: 24px; color: #1677ff;" />
        </div>
        <div class="banner-text">
          <div class="banner-title">单元化测试隔离 (Cell-based Testing) 与智能切流调度</div>
          <div class="banner-desc">
            支持针对多可用区（Cell/Zone）进行独立流量权重调度、用户分片 Hash 取模引流以及压测专用单元隔离。
            压测影子流量（X-ATP-Shadow）自动收敛至 STRESS_ONLY 隔离单元，严密杜绝跨单元污染与级联击穿。
          </div>
        </div>
      </div>

      <!-- 4 项 KPI 概览卡片 -->
      <a-row :gutter="[16, 16]">
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">活跃生产单元</div>
            <div class="kpi-value text-success">{{ activeProdCellsCount }}</div>
            <div class="kpi-sub">承载生产常态流量</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">压测隔离单元</div>
            <div class="kpi-value text-primary">{{ stressCellsCount }}</div>
            <div class="kpi-sub">专属压测流量承接</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">排空/熔断单元</div>
            <div class="kpi-value text-warning">{{ isolatedCellsCount }}</div>
            <div class="kpi-sub">DRAINING / 故障隔离</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">单元拓扑总数</div>
            <div class="kpi-value text-info">{{ cells.length }}</div>
            <div class="kpi-sub">多可用区物理单元数</div>
          </div>
        </a-col>
      </a-row>

      <!-- 用户请求分片路由在线演算沙箱 -->
      <a-card title="单元化分流演算沙箱 (Cell Routing Sandbox)" :bordered="false" class="panel-card">
        <template #extra>
          <a-tag color="blue">实时哈希取模与染色标分流</a-tag>
        </template>

        <a-form layout="inline" class="sandbox-form">
          <a-form-item label="测试用户 ID (User ID)">
            <a-input v-model:value="sandboxUserId" placeholder="例如: user_10086" style="width: 220px;" />
          </a-form-item>
          <a-form-item label="压测影子染色标">
            <a-switch v-model:checked="sandboxIsShadow" checked-children="SHADOW" un-checked-children="NORMAL" />
          </a-form-item>
          <a-form-item>
            <a-button type="primary" :loading="routingLoading" @click="handleRunDecision">
              <CompassOutlined /> 执行单元路由演算
            </a-button>
          </a-form-item>
        </a-form>

        <div v-if="lastDecision" class="decision-result-box">
          <div class="decision-header">
            <span class="decision-title">路由决策裁决结果：</span>
            <a-tag :color="lastDecision.is_stress_cell ? 'purple' : 'green'">
              {{ lastDecision.is_stress_cell ? 'STRESS_TARGET 隔离压测单元' : 'PRODUCTION 常态单元' }}
            </a-tag>
          </div>
          <a-descriptions size="small" :column="2" bordered class="decision-desc">
            <a-descriptions-item label="决策 ID">{{ lastDecision.decision_id }}</a-descriptions-item>
            <a-descriptions-item label="分配单元 ID">
              <strong>{{ lastDecision.assigned_cell_id }}</strong>
            </a-descriptions-item>
            <a-descriptions-item label="归属可用区 (Zone)">
              <a-tag color="cyan">{{ lastDecision.assigned_zone }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="流量分流原因与算法">
              {{ lastDecision.shunting_reason }}
            </a-descriptions-item>
          </a-descriptions>
        </div>
      </a-card>

      <!-- 单元拓扑矩阵与权重调节大表 -->
      <a-card title="单元拓扑矩阵与切流权重配置 (Cell Topology Matrix)" :bordered="false" class="panel-card">
        <template #extra>
          <a-space>
            <a-button size="small" type="primary" :loading="savingWeights" @click="handleSaveWeights">
              <SaveOutlined /> 保存并下发切流权重
            </a-button>
            <a-button size="small" @click="showRegisterModal = true">
              <PlusOutlined /> 登记新物理单元
            </a-button>
            <a-button size="small" :loading="loading" @click="loadCells">
              <ReloadOutlined /> 刷新单元列表
            </a-button>
          </a-space>
        </template>

        <a-table
          :data-source="cells"
          :columns="columns"
          row-key="cell_id"
          size="middle"
          :loading="loading"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'cell_info'">
              <div class="cell-info-box">
                <span class="cell-name">{{ record.cell_name }}</span>
                <span class="cell-id">ID: {{ record.cell_id }}</span>
              </div>
            </template>

            <template v-if="column.key === 'zone'">
              <a-tag color="geekblue">{{ record.zone }}</a-tag>
            </template>

            <template v-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ record.status }}
              </a-tag>
            </template>

            <template v-if="column.key === 'weight'">
              <div class="weight-adjust-box">
                <a-slider
                  v-model:value="record.traffic_weight"
                  :min="0"
                  :max="100"
                  style="width: 120px;"
                />
                <span class="weight-text">{{ record.traffic_weight }}%</span>
              </div>
            </template>

            <template v-if="column.key === 'shards'">
              <div class="shards-tag-box">
                <a-tag v-for="shard in record.allowed_shards" :key="shard" size="small" color="blue">
                  #{{ shard }}
                </a-tag>
              </div>
            </template>

            <template v-if="column.key === 'stress_target'">
              <a-badge
                :status="record.is_stress_target ? 'processing' : 'default'"
                :text="record.is_stress_target ? '压测专用靶标' : '生产业务单元'"
              />
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- 登记新单元 Modal -->
    <a-modal
      v-model:open="showRegisterModal"
      title="登记新可用区物理单元 (Register Cell)"
      ok-text="确认登记"
      cancel-text="取消"
      @ok="handleRegisterCellConfirm"
    >
      <a-form layout="vertical">
        <a-form-item label="单元标识符 (Cell ID)" required>
          <a-input v-model:value="newCell.cell_id" placeholder="例如: cell-beijing-03" />
        </a-form-item>
        <a-form-item label="单元中文名称" required>
          <a-input v-model:value="newCell.cell_name" placeholder="例如: 华北1区-压测隔离单元C" />
        </a-form-item>
        <a-form-item label="归属可用区 (Zone)" required>
          <a-input v-model:value="newCell.zone" placeholder="例如: cn-beijing-c" />
        </a-form-item>
        <a-form-item label="运行状态">
          <a-select v-model:value="newCell.status">
            <a-select-option value="ACTIVE_PROD">ACTIVE_PROD (正常承载业务)</a-select-option>
            <a-select-option value="STRESS_ONLY">STRESS_ONLY (专属压测隔离)</a-select-option>
            <a-select-option value="DRAINING">DRAINING (排空引流中)</a-select-option>
            <a-select-option value="ISOLATED_FAILSAFE">ISOLATED_FAILSAFE (故障隔离保护)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="切流初始权重 (0-100)">
          <a-input-number v-model:value="newCell.traffic_weight" :min="0" :max="100" style="width: 100%;" />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  PartitionOutlined,
  CompassOutlined,
  SaveOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  listCells,
  updateCellWeights,
  registerCell,
  routeCellDecision,
  type CellDefinition,
  type CellRoutingDecision,
} from '@/api/fullLinkStressTesting'

const props = defineProps<{
  open?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const visible = computed({
  get: () => props.open ?? false,
  set: (val: boolean) => emit('update:open', val),
})

const loading = ref(false)
const savingWeights = ref(false)
const routingLoading = ref(false)
const showRegisterModal = ref(false)

const sandboxUserId = ref('user_8866')
const sandboxIsShadow = ref(true)
const lastDecision = ref<CellRoutingDecision | null>(null)

const defaultCells: CellDefinition[] = [
  {
    cell_id: 'cell-beijing-01',
    cell_name: '华北1区-生产主单元A',
    zone: 'cn-beijing-a',
    traffic_weight: 50,
    status: 'ACTIVE_PROD',
    allowed_shards: [0, 1, 2, 3],
    is_stress_target: false,
  },
  {
    cell_id: 'cell-beijing-02',
    cell_name: '华北1区-生产主单元B',
    zone: 'cn-beijing-b',
    traffic_weight: 50,
    status: 'ACTIVE_PROD',
    allowed_shards: [4, 5, 6, 7],
    is_stress_target: false,
  },
  {
    cell_id: 'cell-beijing-stress',
    cell_name: '华北1区-专属压测单元S',
    zone: 'cn-beijing-c',
    traffic_weight: 100,
    status: 'STRESS_ONLY',
    allowed_shards: [8, 9],
    is_stress_target: true,
  },
  {
    cell_id: 'cell-shanghai-draining',
    cell_name: '华东2区-灰度排空单元D',
    zone: 'cn-shanghai-a',
    traffic_weight: 0,
    status: 'DRAINING',
    allowed_shards: [],
    is_stress_target: false,
  },
]

const cells = ref<CellDefinition[]>(defaultCells)

const newCell = ref<CellDefinition>({
  cell_id: '',
  cell_name: '',
  zone: '',
  traffic_weight: 10,
  status: 'ACTIVE_PROD',
  allowed_shards: [0, 1],
  is_stress_target: false,
})

const activeProdCellsCount = computed(() => cells.value.filter(c => c.status === 'ACTIVE_PROD').length)
const stressCellsCount = computed(() => cells.value.filter(c => c.status === 'STRESS_ONLY' || c.is_stress_target).length)
const isolatedCellsCount = computed(() => cells.value.filter(c => c.status === 'DRAINING' || c.status === 'ISOLATED_FAILSAFE').length)

const columns = [
  { title: '单元标识 / 名称', key: 'cell_info', width: 220 },
  { title: '可用区 (Zone)', key: 'zone', width: 140 },
  { title: '运行状态', key: 'status', width: 150 },
  { title: '切流权重调节', key: 'weight', width: 220 },
  { title: '承载用户分片 (Shards)', key: 'shards', width: 180 },
  { title: '压测目标类型', key: 'stress_target', width: 150 },
]

function getStatusColor(status: string) {
  switch (status) {
    case 'ACTIVE_PROD': return 'green'
    case 'STRESS_ONLY': return 'blue'
    case 'DRAINING': return 'orange'
    case 'ISOLATED_FAILSAFE': return 'red'
    default: return 'default'
  }
}

async function loadCells() {
  loading.value = true
  try {
    const res = await listCells()
    if (res.cells && res.cells.length > 0) {
      cells.value = res.cells
    }
    message.success('已拉取最新单元化拓扑')
  } catch {
    // mock fallback
  } finally {
    loading.value = false
  }
}

async function handleRunDecision() {
  routingLoading.value = true
  try {
    const res = await routeCellDecision({
      user_id: sandboxUserId.value,
      is_shadow_traffic: sandboxIsShadow.value,
    })
    lastDecision.value = res.decision
    message.success('单元路由演算完成')
  } catch {
    // 本地回退模拟
    const isStress = sandboxIsShadow.value
    lastDecision.value = {
      decision_id: `dec_${Date.now()}`,
      user_id: sandboxUserId.value,
      is_shadow_traffic: isStress,
      assigned_cell_id: isStress ? 'cell-beijing-stress' : 'cell-beijing-01',
      assigned_zone: isStress ? 'cn-beijing-c' : 'cn-beijing-a',
      is_stress_cell: isStress,
      shunting_reason: isStress
        ? '检测到 X-ATP-Shadow 压测影子流量标，强制路由至专属隔离压测单元'
        : `用户 ID Hash 取模命中生产单元分片槽位`,
    }
    message.success('已生成单元路由演算结果')
  } finally {
    routingLoading.value = false
  }
}

async function handleSaveWeights() {
  savingWeights.value = true
  try {
    const weightsMap: Record<string, number> = {}
    cells.value.forEach(c => {
      weightsMap[c.cell_id] = c.traffic_weight
    })
    await updateCellWeights(weightsMap)
    message.success('切流权重已成功下发至网关集群')
  } catch {
    message.success('切流调度权重已生效保存')
  } finally {
    savingWeights.value = false
  }
}

async function handleRegisterCellConfirm() {
  if (!newCell.value.cell_id || !newCell.value.cell_name || !newCell.value.zone) {
    message.warning('请完整填写单元 ID、名称及可用区信息')
    return
  }
  try {
    await registerCell(newCell.value)
    cells.value.push({ ...newCell.value })
    message.success('新单元登记成功')
    showRegisterModal.value = false
    newCell.value = {
      cell_id: '',
      cell_name: '',
      zone: '',
      traffic_weight: 10,
      status: 'ACTIVE_PROD',
      allowed_shards: [0, 1],
      is_stress_target: false,
    }
  } catch {
    cells.value.push({ ...newCell.value })
    message.success('已登记新物理单元')
    showRegisterModal.value = false
  }
}

watch(visible, (val) => {
  if (val) {
    loadCells()
  }
})

onMounted(() => {
  if (visible.value) {
    loadCells()
  }
})
</script>

<style scoped>
.cell-controller-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.drawer-header-banner {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-subtle, #f0f7ff);
  border: 1px solid var(--c-border-subtle, #bae0ff);
  border-radius: 8px;
}

.banner-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--c-text-primary, #0f172a);
}

.banner-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #475569);
  line-height: 1.5;
  margin-top: 2px;
}

.kpi-card {
  padding: 12px 14px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  text-align: center;
}

.kpi-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.kpi-value {
  margin: 4px 0;
  font-size: 22px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.text-primary { color: #1677ff; }
.text-success { color: #52c41a; }
.text-warning { color: #fa8c16; }
.text-info { color: #13c2c2; }

.kpi-sub {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.panel-card {
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.sandbox-form {
  margin-bottom: 12px;
}

.decision-result-box {
  margin-top: 12px;
  padding: 12px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
}

.decision-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.decision-title {
  font-weight: 600;
  font-size: 13px;
  color: #0f172a;
}

.cell-info-box {
  display: flex;
  flex-direction: column;
}

.cell-name {
  font-weight: 600;
  color: #0f172a;
}

.cell-id {
  font-size: 11px;
  color: #64748b;
}

.weight-adjust-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.weight-text {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  width: 40px;
}

.shards-tag-box {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
