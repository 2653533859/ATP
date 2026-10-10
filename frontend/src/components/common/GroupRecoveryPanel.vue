<template>
  <section class="group-recovery-panel">
    <div class="recovery-heading">
      <strong>{{ t('executionRecovery.title') }}</strong>
      <a-space>
        <a-button size="small" :loading="loading" @click="load">{{ t('common.refresh') }}</a-button>
        <a-button v-if="state?.can_cancel && !error" size="small" danger :loading="cancelling" @click="confirmCancel">
          {{ t('common.cancel') }}
        </a-button>
      </a-space>
    </div>
    <a-alert v-if="error" type="warning" show-icon :message="error" />
    <template v-if="state">
      <a-alert :type="state.requires_reconciliation ? 'warning' : 'info'" show-icon
        :message="reasonText" :description="state.requires_reconciliation ? t('executionRecovery.verify_hint') : undefined" />
      <a-descriptions size="small" :column="2" class="recovery-metadata">
        <a-descriptions-item :label="t('executionRecovery.run_status')">{{ state.run_status }}</a-descriptions-item>
        <a-descriptions-item :label="t('executionRecovery.dispatch')">{{ state.dispatch?.status || t('executionRecovery.no_dispatch') }}</a-descriptions-item>
        <a-descriptions-item :label="t('executionRecovery.accepted')">{{ time(state.dispatch?.accepted_at) }}</a-descriptions-item>
        <a-descriptions-item :label="t('executionRecovery.cancel_time')">{{ time(state.cancel_requested_at) }}</a-descriptions-item>
        <a-descriptions-item :label="t('executionRecovery.lease')">{{ state.lease_status || '—' }}</a-descriptions-item>
        <a-descriptions-item :label="t('executionRecovery.lease_expiry')">{{ time(state.lease_expires_at) }}</a-descriptions-item>
      </a-descriptions>
      <p v-if="state.legacy_children_unverified" class="recovery-note">{{ t('executionRecovery.legacy_children') }}</p>
      <a-space v-if="state.children.length" wrap>
        <span>{{ t('executionRecovery.children', { count: state.child_count }) }}</span>
        <a-tag v-for="child in state.children" :key="`${child.kind}:${child.run_id}`" :color="child.verified && !child.execution_uncertain ? 'default' : 'orange'">
          {{ t(child.kind === 'case' ? 'executionRecovery.case' : 'executionRecovery.suite') }} #{{ child.run_id }} · {{ child.verified ? child.status : t('executionRecovery.unverified') }}
          <span v-if="child.execution_uncertain"> · {{ t('executionRecovery.result_uncertain') }}</span>
        </a-tag>
      </a-space>
      <p v-if="state.children_truncated" class="recovery-note">{{ t('executionRecovery.truncated') }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { groupExecutionApi, type GroupExecutionState } from '@/api'

const props = withDefaults(defineProps<{ kind: 'suite' | 'plan'; runId: number; active?: boolean }>(), { active: true })
const emit = defineEmits<{ changed: [] }>()
const { t, te } = useI18n()
const state = ref<GroupExecutionState | null>(null)
const loading = ref(false)
const cancelling = ref(false)
const error = ref('')
let generation = 0
let requestId = 0
let timer: ReturnType<typeof setInterval> | undefined
const reasonText = computed(() => {
  const key = `executionRecovery.reasons.${state.value?.reason}`
  return te(key) ? t(key) : t('executionRecovery.unknown')
})
function time(value?: string | null) { return value ? new Date(value).toLocaleString() : '—' }

async function load() {
  if (!props.active) return
  const epoch = generation
  const request = ++requestId
  loading.value = true
  try {
    const next = await groupExecutionApi.state(props.kind, props.runId)
    if (epoch !== generation || request !== requestId) return
    state.value = next
    error.value = ''
  } catch {
    if (epoch === generation && request === requestId) error.value = t('executionRecovery.load_failed')
  } finally {
    if (epoch === generation && request === requestId) loading.value = false
  }
}

function confirmCancel() {
  if (!state.value?.can_cancel || cancelling.value || error.value) return
  const snapshot = { kind: props.kind, id: props.runId, revision: state.value.revision, generation }
  Modal.confirm({
    title: t('executionRecovery.cancel_title', { id: snapshot.id }),
    content: t('executionRecovery.cancel_hint'),
    okText: t('executionRecovery.confirm_cancel'), cancelText: t('common.cancel'),
    async onOk() {
      if (snapshot.generation !== generation) return
      cancelling.value = true
      try {
        const result = await groupExecutionApi.cancel(snapshot.kind, snapshot.id, snapshot.revision)
        if (snapshot.generation !== generation) return
        message.success(t(result.pending ? 'executionRecovery.cancelled_pending' : 'executionRecovery.cancel_requested'))
        emit('changed')
        await load()
      } catch (cause: unknown) {
        message.error(cause instanceof Error ? cause.message : t('executionRecovery.cancel_failed'))
        throw cause
      } finally {
        cancelling.value = false
      }
    },
  })
}

watch(() => [props.kind, props.runId, props.active], () => {
  generation++
  state.value = null
  error.value = ''
  if (timer) clearInterval(timer)
  if (!props.active) { loading.value = false; return }
  void load()
  timer = setInterval(() => {
    if (!loading.value && (!state.value || ['pending', 'running'].includes(state.value.run_status) || state.value.requires_reconciliation)) void load()
  }, 3000)
}, { immediate: true })
onUnmounted(() => { generation++; if (timer) clearInterval(timer) })
</script>

<style scoped>
.group-recovery-panel { margin-bottom: 16px; padding: 12px; border: 1px solid var(--c-border); border-radius: 8px; background: var(--c-bg-elevated); }
.recovery-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.recovery-metadata { margin-top: 12px; }
.recovery-note { margin: 8px 0; color: var(--c-text-secondary); font-size: 12px; }
</style>
