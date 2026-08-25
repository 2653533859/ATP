<template>
  <div style="display: flex; flex-direction: column; height: 100%">
    <!-- Header -->
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <h2 style="margin: 0">{{ t('mobile_special.tasks_title') }}</h2>
      <a-select
        v-model:value="(selectedProjectId as number | undefined)"
        :placeholder="t('mobile_special.select_project')"
        style="width: 220px"
        :options="projectOptions"
        allow-clear
        @change="onProjectChange"
      />
      <a-select
        v-model:value="(selectedTaskType as TaskType | undefined)"
        :placeholder="t('mobile_special.task_type')"
        style="width: 140px"
        :options="taskTypeOptions"
        allow-clear
        @change="loadTasks"
      />
      <a-button type="primary" :disabled="!selectedProjectId" @click="openCreate">
        {{ t('mobile_special.new_task') }}
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <a-table
        :data-source="tasks"
        :columns="columns"
        :pagination="{ pageSize: 20 }"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <a style="font-weight: 500" @click="openEdit(asTask(record))">{{ record.name }}</a>
          </template>
          <template v-else-if="column.key === 'task_type'">
            <a-tag :color="taskTypeColor(record.task_type)">{{ taskTypeLabel(record.task_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'schedule_enabled'">
            <a-tag :color="record.schedule_enabled ? 'green' : 'default'">
              {{ record.schedule_enabled ? t('mobile_special.enabled') : t('mobile_special.not_enabled') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'last_run_at'">
            {{ record.last_run_at ? formatDate(record.last_run_at) : '-' }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="primary" size="small" @click="triggerRun(asTask(record))">{{ t('mobile_special.execute') }}</a-button>
            <a-button type="link" size="small" @click="openEdit(asTask(record))">{{ t('common.edit') }}</a-button>
            <a-popconfirm :title="t('mobile_special.confirm_delete_task')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-spin>

    <!-- Create/Edit Drawer -->
    <a-drawer
      v-model:open="drawerVisible"
      :title="editingTask ? t('mobile_special.edit_task') : t('mobile_special.new_task_full')"
      width="560"
      @close="resetForm"
    >
      <a-form :label-col="{ span: 6 }" layout="horizontal">
        <a-form-item :label="t('mobile_special.form.name')" required>
          <a-input v-model:value="form.name" :placeholder="t('mobile_special.form.name_placeholder')" />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.task_type')" required>
          <a-select v-model:value="form.task_type" :placeholder="t('mobile_special.form.select_task_type')" :options="taskTypeOptions" />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.source_type')">
          <a-select v-model:value="form.source_type" :options="sourceTypeOptions" />
        </a-form-item>

        <a-divider>{{ t('mobile_special.form.device_config') }}</a-divider>

        <a-form-item :label="t('mobile_special.form.device_scope')">
          <a-select v-model:value="form.device_scope_type" :options="deviceScopeOptions" />
        </a-form-item>

        <a-form-item v-if="form.device_scope_type === 'single_device'" :label="t('mobile_special.form.select_device')">
          <a-select
            v-model:value="(form.device_id as number | undefined)"
            :placeholder="t('mobile_special.form.select_device')"
            :options="deviceOptions"
            allow-clear
          />
        </a-form-item>

        <a-form-item v-if="form.device_scope_type === 'device_group'" :label="t('mobile_special.form.device_tag')">
          <a-input v-model:value="form.device_group_tag" :placeholder="t('mobile_special.form.device_tag_placeholder')" />
        </a-form-item>

        <a-divider>{{ t('mobile_special.form.app_config') }}</a-divider>

        <a-form-item :label="t('mobile_special.form.apk')">
          <a-select
            v-model:value="(form.apk_id as number | undefined)"
            :placeholder="t('mobile_special.form.select_apk')"
            :options="apkOptions"
            allow-clear
            @change="handleApkChange"
          />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.app_package')">
          <a-input
            v-model:value="form.app_package"
            :placeholder="t('mobile_special.form.app_package_placeholder')"
            :disabled="Boolean(form.apk_id && selectedApkPackage)"
          />
          <span class="form-hint">{{ t('mobile_special.form.app_package_hint') }}</span>
        </a-form-item>

        <a-divider>{{ t('mobile_special.form.standard_setup') }}</a-divider>

        <a-form-item :label="t('mobile_special.form.install_apk')">
          <a-switch v-model:checked="form.config_install_apk" />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.uninstall_before')">
          <a-switch v-model:checked="form.config_uninstall_before" />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.clear_data_before')">
          <a-switch v-model:checked="form.config_clear_data_before" />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.uninstall_after')">
          <a-switch v-model:checked="form.config_uninstall_after" />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.launch_before')">
          <a-switch v-model:checked="form.config_launch_before" />
        </a-form-item>

        <a-form-item v-if="form.config_launch_before" :label="t('mobile_special.form.launch_activity')">
          <a-input v-model:value="form.config_launch_activity" :placeholder="t('mobile_special.form.launch_activity_placeholder')" />
        </a-form-item>

        <a-divider>{{ t('mobile_special.form.execution_config') }}</a-divider>

        <a-form-item :label="t('mobile_special.form.sample_interval')">
          <a-input-number v-model:value="form.config_interval" :min="1" :max="300" style="width: 100%" />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.duration')">
          <a-input-number v-model:value="form.config_duration" :min="10" :max="86400" style="width: 100%" />
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.auto_start')">
          <a-switch v-model:checked="form.config_auto_start" />
        </a-form-item>

        <a-divider>{{ t('mobile_special.form.monitoring_config') }}</a-divider>

        <a-form-item :label="t('mobile_special.form.performance_monitoring')">
          <a-switch v-model:checked="form.config_collect_performance" />
          <span class="form-hint">{{ t('mobile_special.form.performance_monitoring_hint') }}</span>
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.jank_monitoring')">
          <a-switch v-model:checked="form.config_collect_jank" />
          <span class="form-hint">{{ t('mobile_special.form.jank_monitoring_hint') }}</span>
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.incident_monitoring')">
          <a-switch v-model:checked="form.config_collect_incidents" />
          <span class="form-hint">{{ t('mobile_special.form.incident_monitoring_hint') }}</span>
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.incident_replay')">
          <a-switch v-model:checked="form.config_capture_replay" />
          <span class="form-hint">{{ t('mobile_special.form.incident_replay_hint') }}</span>
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.device_log_artifact')">
          <a-switch v-model:checked="form.config_capture_device_logs" />
          <span class="form-hint">{{ t('mobile_special.form.device_log_artifact_hint') }}</span>
        </a-form-item>

        <a-form-item :label="t('mobile_special.form.screenshot_artifact')">
          <a-switch v-model:checked="form.config_capture_screenshot" />
          <span class="form-hint">{{ t('mobile_special.form.screenshot_artifact_hint') }}</span>
        </a-form-item>

        <a-form-item v-if="form.config_capture_replay" :label="t('mobile_special.form.replay_seconds')">
          <a-input-number v-model:value="form.config_replay_seconds" :min="5" :max="1800" style="width: 100%" />
        </a-form-item>

        <template v-if="form.task_type === 'stability'">
          <a-form-item :label="t('mobile_special.form.operation_interval')">
            <a-input-number v-model:value="form.config_operation_interval" :min="100" :max="5000" style="width: 100%" />
          </a-form-item>
        </template>

        <template v-if="form.task_type === 'fluency'">
          <a-form-item :label="t('mobile_special.form.stages')">
            <a-textarea
              v-model:value="form.config_stages"
              :rows="4"
              :placeholder="t('mobile_special.form.stages_placeholder')"
            />
          </a-form-item>
        </template>

        <a-divider>{{ t('mobile_special.form.schedule_config') }}</a-divider>

        <a-form-item :label="t('mobile_special.form.schedule_enabled')">
          <a-switch v-model:checked="form.schedule_enabled" />
        </a-form-item>

        <a-form-item v-if="form.schedule_enabled" :label="t('mobile_special.form.cron')">
          <a-input v-model:value="form.cron_expression" :placeholder="t('mobile_special.form.cron_placeholder')" />
        </a-form-item>
      </a-form>

      <template #footer>
        <a-space>
          <a-button @click="drawerVisible = false">{{ t('common.cancel') }}</a-button>
          <a-button type="primary" :loading="saving" @click="handleSave">{{ editingTask ? t('common.save') : t('common.create') }}</a-button>
        </a-space>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  projectApi,
  mobileSpecialApi,
  deviceApi,
  apkApi,
  type MobileSpecialTaskItem,
  type ProjectItem,
  type TaskType,
  type SourceType,
  type DeviceScopeType,
} from '@/api'
import { buildMobileApkOptions, findMobileApkPackage, type MobileApkOption } from '@/utils/mobileSpecialForm'

// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asTask = (record: unknown) => record as MobileSpecialTaskItem

const { t } = useI18n()
const router = useRouter()

type SelectOption<T extends string | number> = {
  label: string
  value: T
}

type ApkOption = SelectOption<number> & MobileApkOption

type TaskForm = {
  name: string
  task_type: TaskType
  source_type: SourceType
  device_scope_type: DeviceScopeType
  device_id: number | null
  device_group_tag: string
  apk_id: number | null
  app_package: string
  schedule_enabled: boolean
  cron_expression: string
  config_interval: number
  config_duration: number
  config_auto_start: boolean
  config_collect_performance: boolean
  config_collect_jank: boolean
  config_collect_incidents: boolean
  config_capture_replay: boolean
  config_capture_device_logs: boolean
  config_capture_screenshot: boolean
  config_replay_seconds: number
  config_install_apk: boolean
  config_uninstall_before: boolean
  config_clear_data_before: boolean
  config_uninstall_after: boolean
  config_launch_before: boolean
  config_launch_activity: string
  config_operation_interval: number
  config_stages: string
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

const loading = ref(false)
const saving = ref(false)
const tasks = ref<MobileSpecialTaskItem[]>([])
const projects = ref<ProjectItem[]>([])
const projectOptions = ref<SelectOption<number>[]>([])
const deviceOptions = ref<SelectOption<number>[]>([])
const apkOptions = ref<ApkOption[]>([])

const selectedProjectId = ref<number | null>(null)
const selectedTaskType = ref<TaskType | null>(null)

const taskTypeOptions = computed(() => [
  { label: t('mobile_special.task_types.performance'), value: 'performance' },
  { label: t('mobile_special.task_types.stability'), value: 'stability' },
  { label: t('mobile_special.task_types.fluency'), value: 'fluency' },
])

const sourceTypeOptions = computed(() => [
  { label: t('mobile_special.source_types.apk_only'), value: 'apk_only' },
  { label: t('mobile_special.source_types.case'), value: 'case' },
  { label: t('mobile_special.source_types.suite'), value: 'suite' },
  { label: t('mobile_special.source_types.monkey'), value: 'monkey' },
])

const deviceScopeOptions = computed(() => [
  { label: t('mobile_special.device_scopes.single_device'), value: 'single_device' },
  { label: t('mobile_special.device_scopes.device_group'), value: 'device_group' },
  { label: t('mobile_special.device_scopes.manual_pick'), value: 'manual_pick' },
])

const columns = computed(() => [
  { title: t('mobile_special.columns.name'), key: 'name', dataIndex: 'name' },
  { title: t('mobile_special.columns.task_type'), key: 'task_type', dataIndex: 'task_type', width: 120 },
  { title: t('mobile_special.columns.app_package'), key: 'app_package', dataIndex: 'app_package', width: 180, ellipsis: true },
  { title: t('mobile_special.columns.schedule'), key: 'schedule_enabled', dataIndex: 'schedule_enabled', width: 100 },
  { title: t('mobile_special.columns.last_run_at'), key: 'last_run_at', dataIndex: 'last_run_at', width: 160 },
  { title: t('mobile_special.columns.action'), key: 'action', width: 180 },
])

// Drawer state
const drawerVisible = ref(false)
const editingTask = ref<MobileSpecialTaskItem | null>(null)
const form = ref<TaskForm>({
  name: '',
  task_type: 'performance' as TaskType,
  source_type: 'apk_only',
  device_scope_type: 'single_device',
  device_id: null as number | null,
  device_group_tag: '',
  apk_id: null as number | null,
  app_package: '',
  schedule_enabled: false,
  cron_expression: '',
  // config fields flattened
  config_interval: 5,
  config_duration: 300,
  config_auto_start: true,
  config_collect_performance: true,
  config_collect_jank: true,
  config_collect_incidents: true,
  config_capture_replay: true,
  config_capture_device_logs: true,
  config_capture_screenshot: true,
  config_replay_seconds: 30,
  config_install_apk: false,
  config_uninstall_before: false,
  config_clear_data_before: false,
  config_uninstall_after: false,
  config_launch_before: false,
  config_launch_activity: '.MainActivity',
  config_operation_interval: 500,
  config_stages: '',
})
const selectedApkPackage = computed(() => findMobileApkPackage(apkOptions.value, form.value.apk_id))

onMounted(async () => {
  try {
    const list = await projectApi.list()
    projects.value = list
    projectOptions.value = list.map((p) => ({ label: p.name, value: p.id }))
    // Load devices and APKs for first project
    if (list.length > 0) {
      selectedProjectId.value = list[0].id
      await Promise.all([loadDevices(), loadApks(), loadTasks()])
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.msg.load_failed')))
  }
})

async function loadDevices() {
  if (!selectedProjectId.value) return
  try {
    deviceOptions.value = []
    const devs = await deviceApi.list({})
    deviceOptions.value = devs.map((d) => ({ label: `${d.name || d.serial} (${d.status})`, value: d.id }))
  } catch {}
}

async function loadApks() {
  if (!selectedProjectId.value) return
  try {
    apkOptions.value = []
    const apks = await apkApi.list({ project_id: selectedProjectId.value })
    apkOptions.value = buildMobileApkOptions(apks)
  } catch {}
}

function handleApkChange(apkId: unknown) {
  form.value.app_package = typeof apkId === 'number'
    ? findMobileApkPackage(apkOptions.value, apkId)
    : ''
}

async function loadTasks() {
  if (!selectedProjectId.value) return
  loading.value = true
  try {
    const params: { project_id: number; task_type?: TaskType } = { project_id: selectedProjectId.value }
    if (selectedTaskType.value) {
      params.task_type = selectedTaskType.value
    }
    tasks.value = await mobileSpecialApi.listTasks(params)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

function onProjectChange() {
  Promise.all([loadApks(), loadTasks()])
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString()
}

function taskTypeColor(type: TaskType) {
  return { performance: 'blue', stability: 'orange', fluency: 'purple' }[type] || 'default'
}

function taskTypeLabel(type: TaskType) {
  return {
    performance: t('mobile_special.task_types.performance'),
    stability: t('mobile_special.task_types.stability'),
    fluency: t('mobile_special.task_types.fluency'),
  }[type] || type
}

function openCreate() {
  editingTask.value = null
  form.value = {
    name: '',
    task_type: 'performance',
    source_type: 'apk_only',
    device_scope_type: 'single_device',
    device_id: null,
    device_group_tag: '',
    apk_id: null,
    app_package: '',
    schedule_enabled: false,
    cron_expression: '',
    config_interval: 5,
    config_duration: 300,
    config_auto_start: true,
    config_collect_performance: true,
    config_collect_jank: true,
    config_collect_incidents: true,
    config_capture_replay: true,
    config_capture_device_logs: true,
    config_capture_screenshot: true,
    config_replay_seconds: 30,
    config_install_apk: false,
    config_uninstall_before: false,
    config_clear_data_before: false,
    config_uninstall_after: false,
    config_launch_before: false,
    config_launch_activity: '.MainActivity',
    config_operation_interval: 500,
    config_stages: '',
  }
  drawerVisible.value = true
}

function openEdit(task: MobileSpecialTaskItem) {
  editingTask.value = task
  const config = task.config_json || {}
  form.value = {
    name: task.name,
    task_type: task.task_type,
    source_type: task.source_type,
    device_scope_type: task.device_scope_type,
    device_id: task.device_id ?? null,
    device_group_tag: task.device_group_tag || '',
    apk_id: task.apk_id ?? null,
    app_package: task.app_package || '',
    schedule_enabled: task.schedule_enabled,
    cron_expression: task.cron_expression || '',
    config_interval: (config.interval_seconds as number) || 5,
    config_duration: (config.duration_seconds as number) || 300,
    config_auto_start: config.auto_start !== false,
    config_collect_performance: config.collect_performance !== false,
    config_collect_jank: config.collect_jank !== false,
    config_collect_incidents: config.collect_incidents !== false,
    config_capture_replay: config.capture_replay !== false,
    config_capture_device_logs: config.capture_device_logs !== false,
    config_capture_screenshot: config.capture_screenshot !== false,
    config_replay_seconds: (config.replay_seconds as number) || 30,
    config_install_apk: config.install_apk === true || config.install_before === true,
    config_uninstall_before: config.uninstall_before === true,
    config_clear_data_before: config.clear_data_before === true,
    config_uninstall_after: config.uninstall_after === true,
    config_launch_before: config.launch_before === true,
    config_launch_activity: (config.launch_activity as string) || '.MainActivity',
    config_operation_interval: (config.operation_interval_ms as number) || 500,
    config_stages: config.stages ? JSON.stringify(config.stages, null, 2) : '',
  }
  if (!form.value.app_package) {
    handleApkChange(form.value.apk_id)
  }
  drawerVisible.value = true
}

function resetForm() {
  editingTask.value = null
  drawerVisible.value = false
}

async function handleSave() {
  if (!form.value.name.trim()) {
    message.warning(t('mobile_special.form.name'))
    return
  }
  if (!selectedProjectId.value) {
    message.warning(t('mobile_special.select_project'))
    return
  }

  saving.value = true
  try {
    let stages: unknown = undefined
    if (form.value.config_stages) {
      try {
        stages = JSON.parse(form.value.config_stages)
      } catch {
        message.warning(t('mobile_special.msg.save_failed'))
        saving.value = false
        return
      }
    }

    const data = {
      name: form.value.name.trim(),
      project_id: selectedProjectId.value!,
      task_type: form.value.task_type,
      source_type: form.value.source_type,
      device_scope_type: form.value.device_scope_type,
      device_id: form.value.device_id,
      device_group_tag: form.value.device_group_tag || undefined,
      apk_id: form.value.apk_id,
      app_package: form.value.app_package || undefined,
      schedule_enabled: form.value.schedule_enabled,
      cron_expression: form.value.cron_expression || undefined,
      config_json: {
        interval_seconds: form.value.config_interval,
        duration_seconds: form.value.config_duration,
        auto_start: form.value.config_auto_start,
        collect_performance: form.value.config_collect_performance,
        collect_jank: form.value.config_collect_jank,
        collect_incidents: form.value.config_collect_incidents,
        capture_replay: form.value.config_capture_replay,
        capture_device_logs: form.value.config_capture_device_logs,
        capture_screenshot: form.value.config_capture_screenshot,
        capture_on_incident: true,
        replay_seconds: form.value.config_replay_seconds,
        install_apk: form.value.config_install_apk,
        uninstall_before: form.value.config_uninstall_before,
        clear_data_before: form.value.config_clear_data_before,
        uninstall_after: form.value.config_uninstall_after,
        launch_before: form.value.config_launch_before,
        launch_activity: form.value.config_launch_activity.trim() || '.MainActivity',
        operation_interval_ms: form.value.config_operation_interval,
        stages,
      },
    }

    if (editingTask.value) {
      await mobileSpecialApi.updateTask(editingTask.value.id, data)
      message.success(t('mobile_special.msg.save_success'))
    } else {
      await mobileSpecialApi.createTask(data)
      message.success(t('mobile_special.msg.create_success'))
    }
    drawerVisible.value = false
    await loadTasks()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

async function triggerRun(task: MobileSpecialTaskItem) {
  try {
    const run = await mobileSpecialApi.triggerTask(task.id, {})
    message.success(`${t('mobile_special.msg.run_started')} (Run #${run.id})`)
    await router.push(`/mobile-special/reports/${run.id}`)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.msg.run_failed')))
  }
}

async function handleDelete(id: number) {
  try {
    await mobileSpecialApi.deleteTask(id)
    message.success(t('mobile_special.msg.delete_success'))
    await loadTasks()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.msg.delete_failed')))
  }
}
</script>

<style scoped>
.form-hint {
  margin-left: 10px;
  color: #8c8c8c;
  font-size: 12px;
}
</style>
