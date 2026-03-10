<template>
  <div class="case-detail-page">
    <a-card class="header-card" :bordered="false">
      <div class="page-header">
        <div class="page-header-main">
          <div class="page-header-eyebrow">用例详情</div>
          <div class="page-header-title-row">
            <h2>{{ detailTitle }}</h2>
            <a-space v-if="caseDetail" wrap size="small">
              <a-tag :color="caseTypeColor(caseDetail.case_type)">{{ caseTypeLabel(caseDetail.case_type) }}</a-tag>
              <a-tag :color="reviewStatusColor(caseDetail.review_status)">{{ reviewStatusLabel(caseDetail.review_status) }}</a-tag>
              <a-tag :color="automationStatusColor(caseDetail.automation_status)">{{ automationStatusLabel(caseDetail.automation_status) }}</a-tag>
              <a-tag :color="statusColor(caseDetail.status)">{{ statusLabel(caseDetail.status) }}</a-tag>
            </a-space>
          </div>
          <p class="page-header-code">{{ detailCode }}</p>
          <p class="page-header-description">{{ detailDescription }}</p>
        </div>

        <div class="page-header-actions">
          <a-space wrap>
            <a-button @click="goBack">返回</a-button>
            <a-button @click="loadCase">刷新</a-button>
            <a-button :loading="copying" @click="handleCopy">复制</a-button>
            <a-button :disabled="!caseDetail" @click="openHistory">历史</a-button>
            <a-button v-if="canSubmitReview" @click="handleWorkflow('submitReview')">提交评审</a-button>
            <a-button v-if="canApprove" @click="handleWorkflow('approve')">审核通过</a-button>
            <a-button v-if="canReject" @click="handleWorkflow('reject')">审核驳回</a-button>
            <a-button v-if="canDeprecate" @click="handleWorkflow('deprecate')">废弃</a-button>
            <a-button v-if="canReactivate" @click="handleWorkflow('reactivate')">重新激活</a-button>
            <a-tooltip :title="caseDetail?.is_ready_for_execution ? '执行该用例' : '仅已评审通过的自动化或半自动化用例可执行'">
              <a-button type="primary" :disabled="!caseDetail?.is_ready_for_execution" @click="openRunModal">
                执行
              </a-button>
            </a-tooltip>
          </a-space>
        </div>
      </div>
    </a-card>

    <a-spin :spinning="loading">
      <template v-if="caseDetail">
        <div class="summary-grid">
          <a-card class="summary-card" :bordered="false">
            <div class="summary-label">项目</div>
            <div class="summary-value">{{ projectName }}</div>
            <div class="summary-hint">当前所属项目</div>
          </a-card>

          <a-card class="summary-card" :bordered="false">
            <div class="summary-label">模块</div>
            <div class="summary-value">{{ moduleName }}</div>
            <div class="summary-hint">当前所属模块</div>
          </a-card>

          <a-card class="summary-card" :bordered="false">
            <div class="summary-label">评审状态</div>
            <div class="summary-value">
              <a-tag :color="reviewStatusColor(caseDetail.review_status)">{{ reviewStatusLabel(caseDetail.review_status) }}</a-tag>
            </div>
            <div class="summary-hint">审核时间：{{ formatDateTime(caseDetail.reviewed_at) }}</div>
          </a-card>

          <a-card class="summary-card" :bordered="false">
            <div class="summary-label">执行状态</div>
            <div class="summary-value">
              <a-tag :color="executionStatusColor">{{ executionStatusLabel }}</a-tag>
            </div>
            <div class="summary-hint">{{ executionStatusHint }}</div>
          </a-card>
        </div>

        <a-row :gutter="[16, 16]" class="detail-grid">
          <a-col :xs="24" :xl="16">
            <a-card class="detail-card" title="基础信息" :bordered="false">
              <a-descriptions bordered size="small" :column="2">
                <a-descriptions-item label="编码">{{ caseDetail.case_code }}</a-descriptions-item>
                <a-descriptions-item label="类型">
                  <a-tag :color="caseTypeColor(caseDetail.case_type)">{{ caseTypeLabel(caseDetail.case_type) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="项目">{{ projectName }}</a-descriptions-item>
                <a-descriptions-item label="模块">{{ moduleName }}</a-descriptions-item>
                <a-descriptions-item label="优先级">
                  <a-tag :color="priorityColor(caseDetail.priority)">{{ caseDetail.priority }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="等级">{{ caseLevelLabel(caseDetail.case_level) }}</a-descriptions-item>
                <a-descriptions-item label="生命周期">
                  <a-tag :color="statusColor(caseDetail.status)">{{ statusLabel(caseDetail.status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="评审状态">
                  <a-tag :color="reviewStatusColor(caseDetail.review_status)">{{ reviewStatusLabel(caseDetail.review_status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="自动化状态">
                  <a-tag :color="automationStatusColor(caseDetail.automation_status)">{{ automationStatusLabel(caseDetail.automation_status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="可执行">
                  <a-tag :color="caseDetail.is_ready_for_execution ? 'success' : 'default'">
                    {{ caseDetail.is_ready_for_execution ? '是' : '否' }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="摘要" :span="2">{{ caseDetail.summary || '-' }}</a-descriptions-item>
                <a-descriptions-item label="描述" :span="2">{{ caseDetail.description || '-' }}</a-descriptions-item>
                <a-descriptions-item label="标签" :span="2">
                  <a-space wrap>
                    <a-tag v-for="tag in caseDetail.tags" :key="tag" color="blue">{{ tag }}</a-tag>
                    <span v-if="!caseDetail.tags.length">-</span>
                  </a-space>
                </a-descriptions-item>
                <a-descriptions-item label="创建时间">{{ formatDateTime(caseDetail.created_at) }}</a-descriptions-item>
                <a-descriptions-item label="更新时间">{{ formatDateTime(caseDetail.updated_at) }}</a-descriptions-item>
                <a-descriptions-item label="创建人 ID">{{ caseDetail.creator_id }}</a-descriptions-item>
                <a-descriptions-item label="负责人 ID">{{ caseDetail.owner_id ?? '-' }}</a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="8">
            <a-card class="detail-card" title="评审信息" :bordered="false">
              <a-descriptions bordered size="small" :column="1">
                <a-descriptions-item label="提交评审时间">{{ formatDateTime(caseDetail.submitted_at) }}</a-descriptions-item>
                <a-descriptions-item label="审核时间">{{ formatDateTime(caseDetail.reviewed_at) }}</a-descriptions-item>
                <a-descriptions-item label="审核人">{{ caseDetail.reviewed_by ?? '-' }}</a-descriptions-item>
                <a-descriptions-item label="备注">{{ caseDetail.review_comment || '-' }}</a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="12">
            <a-card class="detail-card detail-card--compact" title="前置条件" :bordered="false">
              <template v-if="caseDetail.preconditions.length">
                <div class="condition-tags">
                  <a-tag v-for="item in caseDetail.preconditions" :key="item">{{ item }}</a-tag>
                </div>
              </template>
              <a-empty v-else description="暂无前置条件" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="12">
            <a-card class="detail-card detail-card--compact" title="后置条件" :bordered="false">
              <template v-if="caseDetail.postconditions.length">
                <div class="condition-tags">
                  <a-tag v-for="item in caseDetail.postconditions" :key="item">{{ item }}</a-tag>
                </div>
              </template>
              <a-empty v-else description="暂无后置条件" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
            </a-card>
          </a-col>

          <a-col :span="24">
            <a-card class="detail-card table-card" title="标准步骤" :bordered="false">
              <a-table
                v-if="caseDetail.steps.length"
                :columns="stepColumns"
                :data-source="caseDetail.steps"
                row-key="id"
                size="small"
                :pagination="false"
                :scroll="{ x: 1000 }"
                :locale="{ emptyText: '暂无数据' }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'is_key_step'">
                    <a-tag :color="record.is_key_step ? 'red' : 'default'">
                      {{ record.is_key_step ? '关键步骤' : '普通步骤' }}
                    </a-tag>
                  </template>
                </template>
              </a-table>
              <a-empty
                v-else
                description="暂无标准步骤"
                :image="Empty.PRESENTED_IMAGE_SIMPLE"
              />
            </a-card>
          </a-col>

          <a-col :span="24">
            <a-card class="detail-card" title="执行配置" :bordered="false">
              <pre class="config-block">{{ prettyConfig }}</pre>
            </a-card>
          </a-col>
        </a-row>
      </template>

      <a-card v-else class="detail-card empty-card" :bordered="false">
        <a-empty description="未找到用例" />
      </a-card>
    </a-spin>

    <a-modal
      v-model:open="runModalOpen"
      title="选择执行环境"
      ok-text="执行"
      cancel-text="取消"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p class="run-tip">请选择本次执行使用的环境，不选择则按无环境方式执行。</p>
      <a-select
        v-model:value="runEnvId"
        placeholder="不选择环境"
        allow-clear
        style="width: 100%"
        :options="runEnvOptions"
        :loading="runEnvLoading"
      />
    </a-modal>

    <CaseHistoryDrawer
      :open="historyOpen"
      :case-id="caseId"
      @close="historyOpen = false"
      @rolled="handleRolled"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Empty, message } from 'ant-design-vue'
import { caseApi, environmentApi, projectApi } from '@/api'
import type {
  AutomationStatus,
  CaseDetailItem,
  CaseLevel,
  CasePriority,
  CaseStatus,
  CaseType,
  ModuleTreeItem,
  ProjectItem,
  ReviewStatus,
} from '@/api'
import CaseHistoryDrawer from '@/views/case/CaseHistoryDrawer.vue'

type WorkflowAction = 'submitReview' | 'approve' | 'reject' | 'deprecate' | 'reactivate'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const copying = ref(false)
const caseDetail = ref<CaseDetailItem | null>(null)
const projects = ref<ProjectItem[]>([])
const moduleNameMap = ref<Record<number, string>>({})
const historyOpen = ref(false)
const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)

const stepColumns = [
  { title: '#', dataIndex: 'step_no', key: 'step_no', width: 70 },
  { title: '操作', dataIndex: 'action', key: 'action', width: 220 },
  { title: '测试数据', dataIndex: 'test_data', key: 'test_data', width: 220 },
  { title: '预期结果', dataIndex: 'expected_result', key: 'expected_result', width: 260 },
  { title: '类型', key: 'is_key_step', width: 100 },
  { title: '备注', dataIndex: 'remarks', key: 'remarks', width: 180 },
]

const caseId = computed(() => parsePositiveInt(route.params.caseId))
const projectQueryId = computed(() => parsePositiveInt(route.query.project_id))
const moduleQueryId = computed(() => parsePositiveInt(route.query.module_id))
const backQuery = computed<Record<string, string>>(() => {
  const query: Record<string, string> = {}
  if (projectQueryId.value) {
    query.project_id = String(projectQueryId.value)
  }
  if (moduleQueryId.value) {
    query.module_id = String(moduleQueryId.value)
  }
  return query
})

const projectName = computed(() => {
  if (!projectQueryId.value) {
    return '-'
  }
  return projects.value.find((item) => item.id === projectQueryId.value)?.name ?? `项目 #${projectQueryId.value}`
})

const moduleName = computed(() => {
  if (!caseDetail.value) {
    return '-'
  }
  return moduleNameMap.value[caseDetail.value.module_id] ?? `模块 #${caseDetail.value.module_id}`
})

const detailTitle = computed(() => caseDetail.value?.name || '用例详情')
const detailCode = computed(() => caseDetail.value?.case_code || `用例 #${caseId.value ?? '-'}`)
const detailDescription = computed(() => {
  const parts: string[] = []
  if (projectName.value !== '-') {
    parts.push(`项目：${projectName.value}`)
  }
  if (moduleName.value !== '-') {
    parts.push(`模块：${moduleName.value}`)
  }
  if (caseDetail.value?.summary) {
    parts.push(caseDetail.value.summary)
  }
  return parts.length ? parts.join(' ｜ ' ) : '查看基础信息、评审信息、标准步骤与执行配置。'
})
const executionStatusLabel = computed(() => caseDetail.value?.is_ready_for_execution ? '可执行' : '不可执行')
const executionStatusColor = computed(() => caseDetail.value?.is_ready_for_execution ? 'success' : 'warning')
const executionStatusHint = computed(() => caseDetail.value?.is_ready_for_execution
  ? '满足执行前置校验，可直接发起执行。'
  : '仅已评审通过的自动化或半自动化用例可执行。'
)
const prettyConfig = computed(() => JSON.stringify(caseDetail.value?.config ?? {}, null, 2))
const canSubmitReview = computed(() => !!caseDetail.value && caseDetail.value.status !== 'deprecated' && caseDetail.value.review_status !== 'pending')
const canApprove = computed(() => !!caseDetail.value && caseDetail.value.status !== 'deprecated' && caseDetail.value.review_status === 'pending')
const canReject = computed(() => !!caseDetail.value && caseDetail.value.review_status === 'pending')
const canDeprecate = computed(() => !!caseDetail.value && caseDetail.value.status !== 'deprecated')
const canReactivate = computed(() => !!caseDetail.value && caseDetail.value.status === 'deprecated' && caseDetail.value.review_status === 'approved')

function parsePositiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function flattenModules(nodes: ModuleTreeItem[], acc: Record<number, string> = {}) {
  for (const node of nodes) {
    acc[node.id] = node.name
    if (Array.isArray(node.children) && node.children.length) {
      flattenModules(node.children, acc)
    }
  }
  return acc
}

function formatDateTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function caseTypeLabel(type: CaseType) {
  return {
    api: 'API',
    graphql: 'GraphQL',
    websocket: 'WebSocket',
    grpc: 'gRPC',
    web: 'Web 用例',
    android: 'Android 用例',
  }[type]
}

function caseTypeColor(type: CaseType) {
  return {
    api: 'geekblue',
    graphql: 'orange',
    websocket: 'cyan',
    grpc: 'red',
    web: 'purple',
    android: 'green',
  }[type] ?? 'default'
}

function caseLevelLabel(level: CaseLevel) {
  return {
    smoke: '冒烟',
    core: '核心',
    regression: '回归',
    extended: '扩展',
  }[level]
}

function priorityColor(priority: CasePriority) {
  return {
    P0: 'red',
    P1: 'orange',
    P2: 'gold',
    P3: 'default',
  }[priority]
}

function reviewStatusLabel(status: ReviewStatus) {
  return {
    pending: '待评审',
    approved: '已通过',
    rejected: '已驳回',
  }[status]
}

function reviewStatusColor(status: ReviewStatus) {
  return {
    pending: 'processing',
    approved: 'success',
    rejected: 'error',
  }[status]
}

function statusLabel(status: CaseStatus) {
  return {
    draft: '草稿',
    active: '启用',
    deprecated: '已废弃',
  }[status]
}

function statusColor(status: CaseStatus) {
  return {
    draft: 'default',
    active: 'success',
    deprecated: 'warning',
  }[status]
}

function automationStatusLabel(status: AutomationStatus) {
  return {
    manual: '手工',
    semi_auto: '半自动',
    auto: '自动',
  }[status]
}

function automationStatusColor(status: AutomationStatus) {
  return {
    manual: 'default',
    semi_auto: 'processing',
    auto: 'success',
  }[status]
}

async function loadMeta() {
  if (!projectQueryId.value) {
    projects.value = []
    moduleNameMap.value = {}
    return
  }

  try {
    const [projectList, modules] = await Promise.all([
      projectApi.list(),
      projectApi.getModules(projectQueryId.value),
    ])
    projects.value = projectList
    moduleNameMap.value = flattenModules(modules)
  } catch {
    projects.value = []
    moduleNameMap.value = {}
  }
}

async function loadCase() {
  if (!caseId.value) {
    caseDetail.value = null
    return
  }

  loading.value = true
  try {
    caseDetail.value = await caseApi.get(caseId.value)
  } catch (error: any) {
    caseDetail.value = null
    message.error(error ?? '加载用例详情失败')
  } finally {
    loading.value = false
  }
}

function goBack() {
  void router.push({ name: 'cases', query: backQuery.value })
}

async function handleCopy() {
  if (!caseId.value) {
    return
  }

  copying.value = true
  try {
    const copied = await caseApi.copy(caseId.value)
    message.success(`已复制用例 ${copied.case_code}`)
    void router.replace({ name: 'case-detail', params: { caseId: String(copied.id) }, query: backQuery.value })
    caseDetail.value = copied
  } catch (error: any) {
    message.error(error ?? '复制用例失败')
  } finally {
    copying.value = false
  }
}

async function handleWorkflow(action: WorkflowAction) {
  if (!caseId.value) {
    return
  }

  try {
    switch (action) {
      case 'submitReview':
        caseDetail.value = await caseApi.submitReview(caseId.value)
        message.success('已提交评审')
        break
      case 'approve':
        caseDetail.value = await caseApi.approve(caseId.value)
        message.success('用例已审核通过')
        break
      case 'reject':
        caseDetail.value = await caseApi.reject(caseId.value)
        message.success('用例已审核驳回')
        break
      case 'deprecate':
        caseDetail.value = await caseApi.deprecate(caseId.value)
        message.success('用例已废弃')
        break
      case 'reactivate':
        caseDetail.value = await caseApi.reactivate(caseId.value)
        message.success('用例已重新激活')
        break
    }
  } catch (error: any) {
    message.error(error ?? '流程操作失败')
  }
}

function openHistory() {
  historyOpen.value = true
}

async function openRunModal() {
  runEnvId.value = null
  runEnvOptions.value = []
  runModalOpen.value = true

  if (!projectQueryId.value) {
    return
  }

  runEnvLoading.value = true
  try {
    const environments = await environmentApi.list(projectQueryId.value)
    runEnvOptions.value = environments.map((item: any) => ({ label: item.name, value: item.id }))
  } catch {
    runEnvOptions.value = []
    message.warning('加载环境失败，将按无环境方式继续执行')
  } finally {
    runEnvLoading.value = false
  }
}

async function confirmRun() {
  if (!caseId.value) {
    return
  }

  runConfirming.value = true
  try {
    const payload: { env_id?: number } = {}
    if (runEnvId.value) {
      payload.env_id = runEnvId.value
    }
    const run = await caseApi.run(caseId.value, payload) as any
    runModalOpen.value = false
    message.success('已开始执行，正在打开报告')
    void router.push(`/runs/${run.id}`)
  } catch (error: any) {
    message.error(error ?? '启动执行失败')
  } finally {
    runConfirming.value = false
  }
}

async function handleRolled() {
  await loadCase()
}

onMounted(async () => {
  await Promise.all([loadMeta(), loadCase()])
})
</script>

<style scoped>
.case-detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-card,
.summary-card,
.detail-card {
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.header-card :deep(.ant-card-body) {
  padding: 20px 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-header-main {
  min-width: 0;
  flex: 1 1 auto;
}

.page-header-eyebrow {
  margin-bottom: 8px;
  color: #1677ff;
  font-size: 13px;
  font-weight: 600;
}

.page-header-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.page-header-title-row h2 {
  margin: 0;
  color: #1f1f1f;
}

.page-header-code {
  margin: 8px 0 0;
  color: #1f1f1f;
  font-size: 14px;
  font-weight: 600;
}

.page-header-description {
  margin: 8px 0 0;
  color: #666;
  line-height: 1.6;
}

.page-header-actions {
  flex: 0 0 auto;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card :deep(.ant-card-body) {
  padding: 18px 20px;
}

.summary-label {
  color: #667085;
  font-size: 13px;
}

.summary-value {
  margin-top: 10px;
  color: #1f1f1f;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
  word-break: break-word;
}

.summary-hint {
  margin-top: 8px;
  color: #8c8c8c;
  font-size: 12px;
  line-height: 1.5;
}

.detail-card :deep(.ant-card-head) {
  min-height: 54px;
  border-bottom: 1px solid #f0f0f0;
}

.detail-card :deep(.ant-card-head-title) {
  font-weight: 600;
}

.detail-card :deep(.ant-card-body) {
  padding: 18px 20px;
}

.detail-card--compact :deep(.ant-card-body) {
  min-height: 112px;
}

.table-card :deep(.ant-card-body) {
  padding: 0;
}

.table-card :deep(.ant-empty) {
  margin: 40px 0;
}

.condition-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.config-block {
  margin: 0;
  padding: 16px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  overflow-x: auto;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #1f2937;
}

.empty-card :deep(.ant-card-body) {
  padding: 40px 24px;
}

.run-tip {
  margin-bottom: 12px;
  color: #666;
}

@media (max-width: 1280px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header-actions {
    width: 100%;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
