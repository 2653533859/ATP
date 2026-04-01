<template>
  <div style="display: flex; flex-direction: column; height: 100%">
    <!-- Header -->
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <h2 style="margin: 0">专项测试任务</h2>
      <a-select
        v-model:value="selectedProjectId"
        placeholder="选择项目"
        style="width: 220px"
        :options="projectOptions"
        allow-clear
        @change="onProjectChange"
      />
      <a-select
        v-model:value="selectedTaskType"
        placeholder="任务类型"
        style="width: 140px"
        :options="taskTypeOptions"
        allow-clear
        @change="loadTasks"
      />
      <a-button type="primary" :disabled="!selectedProjectId" @click="openCreate">
        新建任务
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
            <a style="font-weight: 500" @click="openEdit(record)">{{ record.name }}</a>
          </template>
          <template v-else-if="column.key === 'task_type'">
            <a-tag :color="taskTypeColor(record.task_type)">{{ taskTypeLabel(record.task_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'schedule_enabled'">
            <a-tag :color="record.schedule_enabled ? 'green' : 'default'">
              {{ record.schedule_enabled ? '已启用' : '未启用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'last_run_at'">
            {{ record.last_run_at ? formatDate(record.last_run_at) : '-' }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="primary" size="small" @click="triggerRun(record)">执行</a-button>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm title="确认删除此任务？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-spin>

    <!-- Create/Edit Drawer -->
    <a-drawer
      v-model:open="drawerVisible"
      :title="editingTask ? '编辑专项任务' : '新建专项任务'"
      width="560"
      @close="resetForm"
    >
      <a-form :label-col="{ span: 6 }" layout="horizontal">
        <a-form-item label="任务名称" required>
          <a-input v-model:value="form.name" placeholder="如：性能摸底测试" />
        </a-form-item>

        <a-form-item label="任务类型" required>
          <a-select v-model:value="form.task_type" placeholder="选择任务类型" :options="taskTypeOptions" />
        </a-form-item>

        <a-form-item label="数据来源">
          <a-select v-model:value="form.source_type" :options="sourceTypeOptions" />
        </a-form-item>

        <a-divider>设备配置</a-divider>

        <a-form-item label="设备范围">
          <a-select v-model:value="form.device_scope_type" :options="deviceScopeOptions" />
        </a-form-item>

        <a-form-item v-if="form.device_scope_type === 'single_device'" label="选择设备">
          <a-select
            v-model:value="form.device_id"
            placeholder="选择设备"
            :options="deviceOptions"
            allow-clear
          />
        </a-form-item>

        <a-form-item v-if="form.device_scope_type === 'device_group'" label="设备标签">
          <a-input v-model:value="form.device_group_tag" placeholder="如 android-12" />
        </a-form-item>

        <a-divider>应用配置</a-divider>

        <a-form-item label="APK">
          <a-select
            v-model:value="form.apk_id"
            placeholder="选择 APK"
            :options="apkOptions"
            allow-clear
          />
        </a-form-item>

        <a-form-item label="应用包名">
          <a-input v-model:value="form.app_package" placeholder="如 com.example.app" />
        </a-form-item>

        <a-divider>执行配置</a-divider>

        <a-form-item label="采样间隔(秒)">
          <a-input-number v-model:value="form.config_interval" :min="1" :max="300" style="width: 100%" />
        </a-form-item>

        <a-form-item label="运行时长(秒)">
          <a-input-number v-model:value="form.config_duration" :min="10" :max="86400" style="width: 100%" />
        </a-form-item>

        <a-form-item label="自动启动应用">
          <a-switch v-model:checked="form.config_auto_start" />
        </a-form-item>

        <template v-if="form.task_type === 'stability'">
          <a-form-item label="操作间隔(ms)">
            <a-input-number v-model:value="form.config_operation_interval" :min="100" :max="5000" style="width: 100%" />
          </a-form-item>
        </template>

        <template v-if="form.task_type === 'fluency'">
          <a-form-item label="场景配置">
            <a-textarea
              v-model:value="form.config_stages"
              :rows="4"
              placeholder='JSON 格式，如 [{"name":"启动","action":"start_app"},{"name":"滑动列表","action":"swipe","coords":{"x1":540,"y1":1000,"x2":540,"y2":500}}]'
            />
          </a-form-item>
        </template>

        <a-divider>调度配置</a-divider>

        <a-form-item label="启用调度">
          <a-switch v-model:checked="form.schedule_enabled" />
        </a-form-item>

        <a-form-item v-if="form.schedule_enabled" label="Cron 表达式">
          <a-input v-model:value="form.cron_expression" placeholder="如 0 2 * * *" />
        </a-form-item>
      </a-form>

      <template #footer>
        <a-space>
          <a-button @click="drawerVisible = false">取消</a-button>
          <a-button type="primary" :loading="saving" @click="handleSave">{{ editingTask ? '保存' : '创建' }}</a-button>
        </a-space>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { projectApi, mobileSpecialApi, deviceApi, apkApi, type MobileSpecialTaskItem, type TaskType } from '@/api'

const loading = ref(false)
const saving = ref(false)
const tasks = ref<MobileSpecialTaskItem[]>([])
const projects = ref<any[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const deviceOptions = ref<Array<{ label: string; value: number }>>([])
const apkOptions = ref<Array<{ label: string; value: number }>>([])

const selectedProjectId = ref<number | null>(null)
const selectedTaskType = ref<TaskType | null>(null)

const taskTypeOptions = [
  { label: '性能测试', value: 'performance' },
  { label: '稳定性测试', value: 'stability' },
  { label: '流畅度测试', value: 'fluency' },
]

const sourceTypeOptions = [
  { label: '仅 APK', value: 'apk_only' },
  { label: '用例驱动', value: 'case' },
  { label: '套件驱动', value: 'suite' },
  { label: 'Monkey 探索', value: 'monkey' },
]

const deviceScopeOptions = [
  { label: '单设备', value: 'single_device' },
  { label: '设备组', value: 'device_group' },
  { label: '手动选择', value: 'manual_pick' },
]

const columns = [
  { title: '任务名称', key: 'name', dataIndex: 'name' },
  { title: '任务类型', key: 'task_type', dataIndex: 'task_type', width: 120 },
  { title: '包名', key: 'app_package', dataIndex: 'app_package', width: 180, ellipsis: true },
  { title: '调度', key: 'schedule_enabled', dataIndex: 'schedule_enabled', width: 100 },
  { title: '上次执行', key: 'last_run_at', dataIndex: 'last_run_at', width: 160 },
  { title: '操作', key: 'action', width: 180 },
]

// Drawer state
const drawerVisible = ref(false)
const editingTask = ref<MobileSpecialTaskItem | null>(null)
const form = ref({
  name: '',
  task_type: 'performance' as TaskType,
  source_type: 'apk_only' as any,
  device_scope_type: 'single_device' as any,
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
  config_operation_interval: 500,
  config_stages: '',
})

onMounted(async () => {
  try {
    const list = await projectApi.list()
    projects.value = list
    projectOptions.value = list.map((p: any) => ({ label: p.name, value: p.id }))
    // Load devices and APKs for first project
    if (list.length > 0) {
      selectedProjectId.value = list[0].id
      await Promise.all([loadDevices(), loadApks(), loadTasks()])
    }
  } catch (e: any) {
    message.error(e?.message || '加载失败')
  }
})

async function loadDevices() {
  if (!selectedProjectId.value) return
  try {
    deviceOptions.value = []
    const devs = await deviceApi.list({})
    deviceOptions.value = devs.map((d: any) => ({ label: `${d.name || d.serial} (${d.status})`, value: d.id }))
  } catch {}
}

async function loadApks() {
  if (!selectedProjectId.value) return
  try {
    apkOptions.value = []
    const apks = await apkApi.list({ project_id: selectedProjectId.value })
    apkOptions.value = apks.map((a: any) => ({ label: a.package_name || a.filename, value: a.id }))
  } catch {}
}

async function loadTasks() {
  if (!selectedProjectId.value) return
  loading.value = true
  try {
    const params: any = { project_id: selectedProjectId.value }
    if (selectedTaskType.value) {
      params.task_type = selectedTaskType.value
    }
    tasks.value = await mobileSpecialApi.listTasks(params)
  } catch (e: any) {
    message.error(e?.message || '加载任务失败')
  } finally {
    loading.value = false
  }
}

function onProjectChange() {
  loadTasks()
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString()
}

function taskTypeColor(type: string) {
  return { performance: 'blue', stability: 'orange', fluency: 'purple' }[type] || 'default'
}

function taskTypeLabel(type: string) {
  return { performance: '性能', stability: '稳定性', fluency: '流畅度' }[type] || type
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
    config_operation_interval: (config.operation_interval_ms as number) || 500,
    config_stages: config.stages ? JSON.stringify(config.stages, null, 2) : '',
  }
  drawerVisible.value = true
}

function resetForm() {
  editingTask.value = null
  drawerVisible.value = false
}

async function handleSave() {
  if (!form.value.name.trim()) {
    message.warning('请输入任务名称')
    return
  }
  if (!selectedProjectId.value) {
    message.warning('请先选择项目')
    return
  }

  saving.value = true
  try {
    let stages = undefined
    if (form.value.config_stages) {
      try {
        stages = JSON.parse(form.value.config_stages)
      } catch {
        message.warning('场景配置 JSON 格式错误')
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
        operation_interval_ms: form.value.config_operation_interval,
        stages,
      },
    }

    if (editingTask.value) {
      await mobileSpecialApi.updateTask(editingTask.value.id, data)
      message.success('任务已更新')
    } else {
      await mobileSpecialApi.createTask(data)
      message.success('任务已创建')
    }
    drawerVisible.value = false
    await loadTasks()
  } catch (e: any) {
    message.error(e?.message || '保存任务失败')
  } finally {
    saving.value = false
  }
}

async function triggerRun(task: MobileSpecialTaskItem) {
  try {
    const run = await mobileSpecialApi.triggerTask(task.id, {})
    message.success(`任务已开始执行 (Run #${run.id})`)
  } catch (e: any) {
    message.error(e?.message || '触发任务失败')
  }
}

async function handleDelete(id: number) {
  try {
    await mobileSpecialApi.deleteTask(id)
    message.success('任务已删除')
    await loadTasks()
  } catch (e: any) {
    message.error(e?.message || '删除任务失败')
  }
}
</script>
