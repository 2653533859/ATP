<template>
  <div class="page-shell remote-nodes-page">
    <header class="nodes-toolbar">
      <div>
        <h2 class="page-title">{{ t('remote_nodes.title') }}</h2>
        <p class="page-subtitle">{{ t('remote_nodes.subtitle') }}</p>
      </div>
      <a-button :loading="loading" @click="loadNodes">
        <ReloadOutlined :spin="loading" />
        {{ t('remote_nodes.refresh') }}
      </a-button>
    </header>

    <a-card :bordered="false" :loading="loading">
      <a-empty v-if="!nodes.length" :description="t('remote_nodes.empty')" />
      <a-table
        v-else
        row-key="client_id"
        :data-source="nodes"
        :columns="nodeColumns"
        :pagination="false"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'online' ? 'green' : 'default'">
              {{ record.status === 'online' ? t('remote_nodes.online') : t('remote_nodes.offline') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'last_seen_at'">
            {{ formatTime(record.last_seen_at) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button type="link" size="small" @click="openGrants(record as RemoteNodeItem)">
              <SafetyCertificateOutlined /> {{ t('remote_nodes.manage_grants') }}
            </a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-drawer v-model:open="drawerVisible" :title="drawerTitle" width="760" destroy-on-close>
      <div class="grants-toolbar">
        <a-space>
          <a-button type="primary" @click="openCreateModal">
            <UsergroupAddOutlined /> {{ t('remote_nodes.add_grant') }}
          </a-button>
          <a-checkbox v-model:checked="includeRevoked" @change="loadGrants">
            {{ t('remote_nodes.include_revoked') }}
          </a-checkbox>
        </a-space>
      </div>
      <a-table
        row-key="id"
        :data-source="grants"
        :columns="grantColumns"
        :pagination="false"
        size="small"
        :loading="grantsLoading"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'subject'">
            <span>{{ record.subject_name }}</span>
            <a-tag style="margin-left: 8px">
              {{ record.subject_type === 'user' ? t('remote_nodes.subject_user') : t('remote_nodes.subject_project') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'access_level'">
            <a-tag :color="record.access_level === 'read_write' ? 'red' : 'blue'">
              {{ record.access_level === 'read_write' ? t('remote_nodes.read_write') : t('remote_nodes.read_only') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'state'">
            <a-tag :color="record.revoked_at ? 'default' : 'green'">
              {{ record.revoked_at ? t('remote_nodes.status_revoked') : t('remote_nodes.status_active') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-popconfirm
              v-if="!record.revoked_at"
              :title="t('remote_nodes.revoke_confirm')"
              :ok-text="t('common.confirm')"
              :cancel-text="t('common.cancel')"
              @confirm="handleRevoke(record as RemoteNodeGrantItem)"
            >
              <a-button type="link" danger size="small">{{ t('remote_nodes.revoke') }}</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <a-modal v-model:open="createVisible" :title="t('remote_nodes.add_grant')" :confirm-loading="saving" @ok="submitCreate">
      <a-form layout="vertical">
        <a-form-item :label="t('remote_nodes.subject_type')">
          <a-radio-group v-model:value="createForm.subject_type" @change="handleSubjectTypeChange">
            <a-radio value="user">{{ t('remote_nodes.subject_user') }}</a-radio>
            <a-radio value="project">{{ t('remote_nodes.subject_project') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('remote_nodes.select_subject')">
          <a-select
            v-model:value="createForm.subject_id"
            show-search
            :options="subjectOptions"
            :filter-option="filterOption"
            :placeholder="t('remote_nodes.select_subject')"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item :label="t('remote_nodes.access_level')">
          <a-radio-group v-model:value="createForm.access_level">
            <a-radio value="read_only">{{ t('remote_nodes.read_only') }}</a-radio>
            <a-radio value="read_write">{{ t('remote_nodes.read_write') }}</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
      <p class="level-hint">{{ t('remote_nodes.level_hint') }}</p>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ReloadOutlined, SafetyCertificateOutlined, UsergroupAddOutlined } from '@ant-design/icons-vue'
import {
  projectApi,
  remoteNodesApi,
  userApi,
  type ProjectItem,
  type RemoteNodeGrantItem,
  type RemoteNodeItem,
} from '@/api'

const { t } = useI18n()

const loading = ref(false)
const nodes = ref<RemoteNodeItem[]>([])
const drawerVisible = ref(false)
const grantsLoading = ref(false)
const includeRevoked = ref(false)
const grants = ref<RemoteNodeGrantItem[]>([])
const activeNode = ref<RemoteNodeItem | null>(null)
const createVisible = ref(false)
const saving = ref(false)
const subjectOptionsLoaded = ref(false)
const userOptions = ref<{ label: string; value: number }[]>([])
const projectOptions = ref<{ label: string; value: number }[]>([])
const createForm = reactive({
  subject_type: 'user' as 'user' | 'project',
  subject_id: undefined as number | undefined,
  access_level: 'read_only' as 'read_only' | 'read_write',
})

const nodeColumns = computed(() => [
  { title: t('remote_nodes.node_name'), dataIndex: 'machine_name', key: 'machine_name' },
  { title: t('remote_nodes.node_id'), dataIndex: 'client_id', key: 'client_id' },
  { title: t('remote_nodes.node_status'), key: 'status' },
  { title: t('remote_nodes.last_seen'), dataIndex: 'last_seen_at', key: 'last_seen_at' },
  { title: t('remote_nodes.grants'), key: 'actions' },
])

const grantColumns = computed(() => [
  { title: t('remote_nodes.subject'), key: 'subject' },
  { title: t('remote_nodes.access_level'), key: 'access_level' },
  { title: t('remote_nodes.created_by'), dataIndex: 'created_by', key: 'created_by' },
  { title: t('remote_nodes.created_at'), dataIndex: 'created_at', key: 'created_at' },
  { title: t('remote_nodes.grant_state'), key: 'state' },
  { title: '', key: 'actions' },
])

const drawerTitle = computed(() =>
  activeNode.value
    ? `${t('remote_nodes.grant_list')} · ${activeNode.value.machine_name}`
    : t('remote_nodes.grant_list'),
)

const subjectOptions = computed(() => (createForm.subject_type === 'user' ? userOptions.value : projectOptions.value))

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function filterOption(input: string, option?: { label?: unknown }) {
  return String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
}

async function loadNodes() {
  loading.value = true
  try {
    nodes.value = await remoteNodesApi.list()
  } catch {
    message.error(t('remote_nodes.load_failed'))
  } finally {
    loading.value = false
  }
}

async function loadGrants() {
  if (!activeNode.value) return
  grantsLoading.value = true
  try {
    grants.value = await remoteNodesApi.grants(activeNode.value.client_id, includeRevoked.value)
  } catch {
    message.error(t('remote_nodes.grants_load_failed'))
  } finally {
    grantsLoading.value = false
  }
}

async function openGrants(node: RemoteNodeItem) {
  activeNode.value = node
  grants.value = []
  includeRevoked.value = false
  drawerVisible.value = true
  await loadGrants()
}

async function loadSubjectOptions() {
  try {
    const [users, projects] = await Promise.all([userApi.list(), projectApi.list()])
    userOptions.value = users.map((item) => ({ label: item.username, value: item.id }))
    projectOptions.value = projects.map((item: ProjectItem) => ({ label: item.name, value: item.id }))
    subjectOptionsLoaded.value = true
  } catch {
    message.error(t('remote_nodes.save_failed'))
  }
}

function openCreateModal() {
  createForm.subject_type = 'user'
  createForm.subject_id = undefined
  createForm.access_level = 'read_only'
  createVisible.value = true
  if (!subjectOptionsLoaded.value) {
    void loadSubjectOptions()
  }
}

function handleSubjectTypeChange() {
  createForm.subject_id = undefined
}

async function submitCreate() {
  if (!activeNode.value || createForm.subject_id === undefined) return
  saving.value = true
  try {
    await remoteNodesApi.createGrant(activeNode.value.client_id, {
      subject_type: createForm.subject_type,
      subject_id: createForm.subject_id,
      access_level: createForm.access_level,
    })
    message.success(t('remote_nodes.create_success'))
    createVisible.value = false
    await loadGrants()
  } catch {
    message.error(t('remote_nodes.save_failed'))
  } finally {
    saving.value = false
  }
}

async function handleRevoke(grant: RemoteNodeGrantItem) {
  if (!activeNode.value) return
  try {
    await remoteNodesApi.revokeGrant(activeNode.value.client_id, grant.id)
    message.success(t('remote_nodes.revoke_success'))
    await loadGrants()
  } catch {
    message.error(t('remote_nodes.save_failed'))
  }
}

onMounted(loadNodes)
</script>

<style scoped>
.nodes-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.page-subtitle {
  margin: 4px 0 0;
  color: var(--c-text-tertiary);
  font-size: 13px;
  max-width: 640px;
}

.grants-toolbar {
  margin-bottom: 12px;
}

.level-hint {
  margin: 0;
  color: var(--c-text-tertiary);
  font-size: 12px;
}
</style>
