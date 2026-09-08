<template>
  <section class="node-strip">
    <div class="node-strip-header">
      <div>
        <div class="section-label">{{ t('performance.nodes') }}</div>
        <div class="field-hint">{{ t('performance.node_hint') }}</div>
      </div>
      <a-space>
        <a-button size="small" :loading="loading" @click="emit('refresh')">
          <template #icon><ReloadOutlined /></template>
          {{ t('performance.node_refresh') }}
        </a-button>
        <a-button size="small" type="primary" @click="emit('create')">
          <template #icon><PlusOutlined /></template>
          {{ t('performance.node_register') }}
        </a-button>
      </a-space>
    </div>
    <a-empty v-if="nodes.length === 0" :image="false" :description="t('performance.no_nodes')" />
    <div v-else class="node-grid">
      <div v-for="node in nodes" :key="node.id" class="node-card" :class="`node-card-${node.status}`">
        <div class="node-card-title">
          <a-badge :status="badgeStatus(node.status)" />
          <strong>{{ node.name }}</strong>
          <a-tag>{{ statusLabel(node.status) }}</a-tag>
        </div>
        <div class="muted mono">{{ node.node_id }} · {{ node.queue_name }}</div>
        <div class="muted node-executors">{{ t('performance.node_executors') }}：{{ executorLabel(node) }}</div>
        <div class="node-card-meta">
          <span>{{ t('performance.node_capacity') }}</span>
          <strong>{{ capacityLabel(node) }}</strong>
        </div>
        <div class="muted node-heartbeat">
          {{ node.last_heartbeat_at ? t('performance.node_last_heartbeat', { value: formatDate(node.last_heartbeat_at) }) : t('performance.node_waiting_heartbeat') }}
        </div>
        <div v-if="node.last_error" class="node-error">
          <span>{{ t('performance.node_error') }}：</span>{{ node.last_error }}
        </div>
        <div class="node-card-actions">
          <a-button size="small" @click="emit('edit', node)">
            <template #icon><EditOutlined /></template>
            {{ t('common.edit') }}
          </a-button>
          <a-popconfirm :title="t('performance.node_delete_confirm')" @confirm="emit('delete', node)">
            <a-button size="small" danger>
              <template #icon><DeleteOutlined /></template>
              {{ t('common.delete') }}
            </a-button>
          </a-popconfirm>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import type { PerformanceNodeItem } from '@/api'

defineProps<{ nodes: PerformanceNodeItem[]; loading: boolean }>()
const emit = defineEmits<{
  refresh: []
  create: []
  edit: [node: PerformanceNodeItem]
  delete: [node: PerformanceNodeItem]
}>()
const { t } = useI18n()

function statusLabel(status: string) {
  return t(`performance.node_status.${status}`, status)
}

function badgeStatus(status: string): 'success' | 'default' | 'error' | 'warning' {
  if (status === 'online') return 'success'
  if (status === 'draining') return 'warning'
  if (status === 'disabled') return 'default'
  return 'error'
}

function executorNames(node: PerformanceNodeItem): string[] {
  const declared = node.capabilities?.executors
  if (Array.isArray(declared)) {
    const values = declared.map((value) => String(value).trim()).filter(Boolean)
    if (values.length) return values
  }
  if (typeof declared === 'string') {
    const values = declared.split(',').map((value) => value.trim()).filter(Boolean)
    if (values.length) return values
  }
  const legacy = node.capabilities?.executor
  return typeof legacy === 'string' && legacy.trim() ? [legacy.trim()] : ['k6']
}

function executorLabel(node: PerformanceNodeItem) {
  return executorNames(node).join(', ')
}

function capacityLabel(node: PerformanceNodeItem) {
  const vus = t('performance.node_vus_limit', { value: node.max_vus ?? '∞' })
  const concurrency = t('performance.node_concurrency_limit', { value: node.max_concurrency ?? '∞' })
  return `${vus} · ${concurrency}`
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.node-strip { margin-bottom: 20px; padding: 14px 16px; border: 1px solid #e8e8e8; border-radius: 8px; background: #fafafa; }
.node-strip-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.section-label { margin-bottom: 6px; color: #595959; font-weight: 600; }
.field-hint { margin-top: 6px; color: #8c8c8c; font-size: 12px; }
.node-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; }
.node-card { min-width: 0; padding: 10px 12px; border: 1px solid #e8e8e8; border-radius: 6px; background: #fff; }
.node-card-online { border-color: #b7eb8f; }
.node-card-title { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }
.node-card-title strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-card-title :deep(.ant-tag) { margin-inline-start: auto; margin-inline-end: 0; font-size: 11px; }
.muted { color: #8c8c8c; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }
.node-card-meta { display: flex; justify-content: space-between; gap: 8px; margin-top: 10px; color: #595959; font-size: 12px; }
.node-heartbeat { margin-top: 6px; font-size: 11px; }
.node-error { margin-top: 8px; padding: 6px 8px; color: #d46b08; font-size: 11px; line-height: 1.5; word-break: break-word; border: 1px solid #ffd591; border-radius: 4px; background: #fff7e6; }
.node-executors { margin-top: 5px; overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.node-card-actions { display: flex; gap: 6px; margin-top: 10px; }
</style>
