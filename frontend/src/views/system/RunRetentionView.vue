<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.run_retention.title') }}</h2>
        <div class="page-subtitle">{{ t('system_pages.run_retention.subtitle') }}</div>
      </div>
    </div>

    <a-card class="filter-card" :bordered="false" style="margin-bottom: 16px">
      <a-form layout="inline" :model="filter">
        <a-form-item :label="t('system_pages.run_retention.retention_days')">
          <a-input-number
            v-model:value="filter.days"
            :min="1"
            :max="3650"
            style="width: 160px"
            :placeholder="t('system_pages.run_retention.days_placeholder')"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" :loading="previewLoading" @click="loadPreview">
            {{ t('system_pages.run_retention.generate_preview') }}
          </a-button>
          <a-button style="margin-left: 8px" :loading="perProjectLoading" @click="loadPerProjectPreview">
            {{ t('system_pages.run_retention.per_project_preview') }}
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :xs="24" :md="12">
        <a-card :title="t('system_pages.run_retention.preview_title')" :loading="previewLoading">
          <a-empty
            v-if="!preview"
            :description="t('system_pages.run_retention.no_preview')"
          />
          <a-descriptions v-else :column="1" size="small">
            <a-descriptions-item :label="t('system_pages.run_retention.retention_days')">
              {{ preview.retention_days }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.run_retention.cutoff')">
              {{ formatTime(preview.cutoff) }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.run_retention.plan_runs')">
              {{ preview.plan_runs }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.run_retention.suite_runs')">
              {{ preview.suite_runs }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.run_retention.test_runs')">
              {{ preview.test_runs }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.run_retention.mobile_runs')">
              {{ preview.mobile_runs }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.run_retention.estimated_objects')">
              {{ preview.estimated_objects }}
            </a-descriptions-item>
          </a-descriptions>
          <div style="margin-top: 16px">
            <a-popconfirm
              :title="t('system_pages.run_retention.confirm_execute', {
                total: totalToDelete,
                objects: preview?.estimated_objects ?? 0,
              })"
              :ok-text="t('common.confirm')"
              :cancel-text="t('common.cancel')"
              :disabled="!preview || totalToDelete === 0"
              @confirm="handleExecute"
            >
              <a-button
                danger
                type="primary"
                :loading="executeLoading"
                :disabled="!preview || totalToDelete === 0"
              >
                {{ t('system_pages.run_retention.execute_cleanup') }}
              </a-button>
            </a-popconfirm>
            <span style="margin-left: 12px; color: var(--c-text-tertiary); font-size: 12px">
              {{ t('system_pages.run_retention.execute_hint') }}
            </span>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :md="12">
        <a-card :title="t('system_pages.run_retention.per_project_title')" :loading="perProjectLoading">
          <a-empty
            v-if="!perProject"
            :description="t('system_pages.run_retention.no_per_project')"
          />
          <template v-else>
            <a-alert
              :message="t('system_pages.run_retention.per_project_note')"
              type="info"
              show-icon
              style="margin-bottom: 12px"
            />
            <a-table
              :columns="projectColumns"
              :data-source="perProject.projects"
              :pagination="false"
              row-key="project_id"
              size="small"
              :locale="{ emptyText: t('system_pages.run_retention.no_overrides') }"
            />
            <a-descriptions :column="1" size="small" style="margin-top: 16px">
              <a-descriptions-item :label="t('system_pages.run_retention.global_days')">
                {{ perProject.global.retention_days }}
              </a-descriptions-item>
              <a-descriptions-item :label="t('system_pages.run_retention.global_test_runs')">
                {{ perProject.global.test_runs }}
              </a-descriptions-item>
              <a-descriptions-item :label="t('system_pages.run_retention.global_mobile_runs')">
                {{ perProject.global.mobile_runs }}
              </a-descriptions-item>
            </a-descriptions>
          </template>
        </a-card>
      </a-col>
    </a-row>

    <a-card v-if="lastResult" :title="t('system_pages.run_retention.last_result_title')" :bordered="false">
      <a-descriptions :column="2" size="small">
        <a-descriptions-item :label="t('system_pages.run_retention.retention_days')">
          {{ lastResult.retention_days }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.run_retention.cutoff')">
          {{ formatTime(lastResult.cutoff) }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.run_retention.plan_runs')">
          {{ lastResult.plan_runs }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.run_retention.suite_runs')">
          {{ lastResult.suite_runs }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.run_retention.test_runs')">
          {{ lastResult.test_runs }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.run_retention.mobile_runs')">
          {{ lastResult.mobile_runs }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.run_retention.deleted_objects')">
          {{ lastResult.deleted_objects }}
        </a-descriptions-item>
      </a-descriptions>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  adminRunRetentionApi,
  type RunRetentionExecuteResult,
  type RunRetentionPerProjectPreview,
  type RunRetentionPreview,
} from '@/api'

const { t } = useI18n()

const filter = reactive<{ days?: number }>({ days: undefined })
const preview = ref<RunRetentionPreview | null>(null)
const perProject = ref<RunRetentionPerProjectPreview | null>(null)
const lastResult = ref<RunRetentionExecuteResult | null>(null)

const previewLoading = ref(false)
const perProjectLoading = ref(false)
const executeLoading = ref(false)

type ErrorLike = {
  response?: {
    data?: {
      detail?: unknown
    }
  }
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
  }
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return fallback
}

const totalToDelete = computed(() => {
  if (!preview.value) return 0
  return preview.value.plan_runs + preview.value.suite_runs + preview.value.test_runs + preview.value.mobile_runs
})

const projectColumns = computed(() => [
  { title: t('system_pages.run_retention.col.project_id'), dataIndex: 'project_id', key: 'project_id', width: 80 },
  { title: t('system_pages.run_retention.col.project_name'), dataIndex: 'project_name', key: 'project_name' },
  { title: t('system_pages.run_retention.col.retention_days'), dataIndex: 'retention_days', key: 'retention_days', width: 100 },
  { title: t('system_pages.run_retention.col.plan_runs'), dataIndex: 'plan_runs', key: 'plan_runs', width: 100 },
  { title: t('system_pages.run_retention.col.suite_runs'), dataIndex: 'suite_runs', key: 'suite_runs', width: 100 },
])

function formatTime(value: string | undefined | null): string {
  if (!value) return '-'
  return value.slice(0, 19).replace('T', ' ')
}

async function loadPreview() {
  previewLoading.value = true
  try {
    preview.value = await adminRunRetentionApi.preview(filter.days)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.run_retention.preview_failed')))
  } finally {
    previewLoading.value = false
  }
}

async function loadPerProjectPreview() {
  perProjectLoading.value = true
  try {
    perProject.value = await adminRunRetentionApi.perProjectPreview()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.run_retention.preview_failed')))
  } finally {
    perProjectLoading.value = false
  }
}

async function handleExecute() {
  executeLoading.value = true
  try {
    lastResult.value = await adminRunRetentionApi.run(filter.days)
    message.success(t('system_pages.run_retention.execute_success'))
    // 重新刷新预览，反映清理后的余量
    await loadPreview()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.run_retention.execute_failed')))
  } finally {
    executeLoading.value = false
  }
}
</script>

<style scoped>
.filter-card {
  background: var(--c-bg-subtle);
}
</style>
