<template>
  <div class="case-detail-page">
    <a-page-header :title="caseDetail?.name || 'Case Detail'" @back="goBack">
      <template #subTitle>
        <span>{{ caseDetail?.case_code || `Case #${caseId ?? '-'}` }}</span>
      </template>
      <template #extra>
        <a-space wrap>
          <a-button @click="loadCase">Refresh</a-button>
          <a-button :loading="copying" @click="handleCopy">Copy</a-button>
          <a-button :disabled="!caseDetail" @click="openHistory">History</a-button>
          <a-button v-if="canSubmitReview" @click="handleWorkflow('submitReview')">Submit review</a-button>
          <a-button v-if="canApprove" @click="handleWorkflow('approve')">Approve</a-button>
          <a-button v-if="canReject" @click="handleWorkflow('reject')">Reject</a-button>
          <a-button v-if="canDeprecate" @click="handleWorkflow('deprecate')">Deprecate</a-button>
          <a-button v-if="canReactivate" @click="handleWorkflow('reactivate')">Reactivate</a-button>
          <a-tooltip :title="caseDetail?.is_ready_for_execution ? 'Run this case' : 'Only approved auto or semi-auto cases can run'">
            <a-button type="primary" :disabled="!caseDetail?.is_ready_for_execution" @click="openRunModal">
              Run
            </a-button>
          </a-tooltip>
        </a-space>
      </template>
    </a-page-header>

    <a-spin :spinning="loading">
      <template v-if="caseDetail">
        <a-row :gutter="[16, 16]">
          <a-col :xs="24" :xl="16">
            <a-card title="Basic Info">
              <a-descriptions bordered size="small" :column="2">
                <a-descriptions-item label="Code">{{ caseDetail.case_code }}</a-descriptions-item>
                <a-descriptions-item label="Type">
                  <a-tag :color="caseTypeColor(caseDetail.case_type)">{{ caseTypeLabel(caseDetail.case_type) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Project">{{ projectName }}</a-descriptions-item>
                <a-descriptions-item label="Module">{{ moduleName }}</a-descriptions-item>
                <a-descriptions-item label="Priority">
                  <a-tag :color="priorityColor(caseDetail.priority)">{{ caseDetail.priority }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Level">{{ caseDetail.case_level }}</a-descriptions-item>
                <a-descriptions-item label="Status">
                  <a-tag :color="statusColor(caseDetail.status)">{{ statusLabel(caseDetail.status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Review">
                  <a-tag :color="reviewStatusColor(caseDetail.review_status)">{{ reviewStatusLabel(caseDetail.review_status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Automation">
                  <a-tag :color="automationStatusColor(caseDetail.automation_status)">{{ caseDetail.automation_status }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Ready to run">
                  <a-tag :color="caseDetail.is_ready_for_execution ? 'success' : 'default'">
                    {{ caseDetail.is_ready_for_execution ? 'Yes' : 'No' }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Summary" :span="2">{{ caseDetail.summary || '-' }}</a-descriptions-item>
                <a-descriptions-item label="Description" :span="2">{{ caseDetail.description || '-' }}</a-descriptions-item>
                <a-descriptions-item label="Tags" :span="2">
                  <a-space wrap>
                    <a-tag v-for="tag in caseDetail.tags" :key="tag" color="blue">{{ tag }}</a-tag>
                    <span v-if="!caseDetail.tags.length">-</span>
                  </a-space>
                </a-descriptions-item>
                <a-descriptions-item label="Created at">{{ formatDateTime(caseDetail.created_at) }}</a-descriptions-item>
                <a-descriptions-item label="Updated at">{{ formatDateTime(caseDetail.updated_at) }}</a-descriptions-item>
                <a-descriptions-item label="Creator ID">{{ caseDetail.creator_id }}</a-descriptions-item>
                <a-descriptions-item label="Owner ID">{{ caseDetail.owner_id ?? '-' }}</a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="8">
            <a-card title="Review Info">
              <a-descriptions bordered size="small" :column="1">
                <a-descriptions-item label="Submitted at">{{ formatDateTime(caseDetail.submitted_at) }}</a-descriptions-item>
                <a-descriptions-item label="Reviewed at">{{ formatDateTime(caseDetail.reviewed_at) }}</a-descriptions-item>
                <a-descriptions-item label="Reviewed by">{{ caseDetail.reviewed_by ?? '-' }}</a-descriptions-item>
                <a-descriptions-item label="Comment">{{ caseDetail.review_comment || '-' }}</a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="12">
            <a-card title="Preconditions">
              <template v-if="caseDetail.preconditions.length">
                <a-space wrap>
                  <a-tag v-for="item in caseDetail.preconditions" :key="item">{{ item }}</a-tag>
                </a-space>
              </template>
              <a-empty v-else description="No preconditions" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="12">
            <a-card title="Postconditions">
              <template v-if="caseDetail.postconditions.length">
                <a-space wrap>
                  <a-tag v-for="item in caseDetail.postconditions" :key="item">{{ item }}</a-tag>
                </a-space>
              </template>
              <a-empty v-else description="No postconditions" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
            </a-card>
          </a-col>

          <a-col :span="24">
            <a-card title="Standard Steps">
              <a-table
                :columns="stepColumns"
                :data-source="caseDetail.steps"
                row-key="id"
                size="small"
                :pagination="false"
                :scroll="{ x: 1000 }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'is_key_step'">
                    <a-tag :color="record.is_key_step ? 'red' : 'default'">
                      {{ record.is_key_step ? 'Key' : 'Normal' }}
                    </a-tag>
                  </template>
                </template>
              </a-table>
              <a-empty
                v-if="!caseDetail.steps.length"
                description="No standard steps"
                :image="Empty.PRESENTED_IMAGE_SIMPLE"
              />
            </a-card>
          </a-col>

          <a-col :span="24">
            <a-card title="Execution Config">
              <pre class="config-block">{{ prettyConfig }}</pre>
            </a-card>
          </a-col>
        </a-row>
      </template>

      <a-empty v-else description="Case not found" />
    </a-spin>

    <a-modal
      v-model:open="runModalOpen"
      title="Select environment"
      ok-text="Run"
      cancel-text="Cancel"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p class="run-tip">Pick an environment or leave empty to run without one.</p>
      <a-select
        v-model:value="runEnvId"
        placeholder="No environment"
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
  { title: 'Action', dataIndex: 'action', key: 'action', width: 220 },
  { title: 'Test Data', dataIndex: 'test_data', key: 'test_data', width: 220 },
  { title: 'Expected Result', dataIndex: 'expected_result', key: 'expected_result', width: 260 },
  { title: 'Kind', key: 'is_key_step', width: 100 },
  { title: 'Remarks', dataIndex: 'remarks', key: 'remarks', width: 180 },
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
  return projects.value.find((item) => item.id === projectQueryId.value)?.name ?? `Project #${projectQueryId.value}`
})

const moduleName = computed(() => {
  if (!caseDetail.value) {
    return '-'
  }
  return moduleNameMap.value[caseDetail.value.module_id] ?? `Module #${caseDetail.value.module_id}`
})

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
    web: 'Web UI',
    android: 'Android UI',
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
    pending: 'Pending',
    approved: 'Approved',
    rejected: 'Rejected',
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
    draft: 'Draft',
    active: 'Active',
    deprecated: 'Deprecated',
  }[status]
}

function statusColor(status: CaseStatus) {
  return {
    draft: 'default',
    active: 'success',
    deprecated: 'warning',
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
    message.error(error ?? 'Failed to load case detail')
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
    message.success(`Copied case ${copied.case_code}`)
    void router.replace({ name: 'case-detail', params: { caseId: String(copied.id) }, query: backQuery.value })
    caseDetail.value = copied
  } catch (error: any) {
    message.error(error ?? 'Failed to copy case')
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
        message.success('Review submitted')
        break
      case 'approve':
        caseDetail.value = await caseApi.approve(caseId.value)
        message.success('Case approved')
        break
      case 'reject':
        caseDetail.value = await caseApi.reject(caseId.value)
        message.success('Case rejected')
        break
      case 'deprecate':
        caseDetail.value = await caseApi.deprecate(caseId.value)
        message.success('Case deprecated')
        break
      case 'reactivate':
        caseDetail.value = await caseApi.reactivate(caseId.value)
        message.success('Case reactivated')
        break
    }
  } catch (error: any) {
    message.error(error ?? 'Workflow action failed')
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
    message.warning('Failed to load environments, run will continue without one')
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
    message.success('Run started, opening the report')
    void router.push(`/runs/${run.id}`)
  } catch (error: any) {
    message.error(error ?? 'Failed to start run')
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

.config-block {
  margin: 0;
  padding: 16px;
  border-radius: 8px;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  overflow-x: auto;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.run-tip {
  margin-bottom: 12px;
  color: #666;
}
</style>
