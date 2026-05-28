<template>
  <a-drawer
    :open="open"
    :title="t('case.history.title')"
    :width="680"
    @close="$emit('close')"
  >
    <a-empty v-if="!loading && snapshots.length === 0" :description="t('case.history.empty')" />

    <a-spin :spinning="loading">
      <div v-if="snapshots.length >= 2" style="margin-bottom: 12px">
        <a-button
          size="small"
          :disabled="compareSelection.length !== 2"
          @click="showCompare"
        >
          {{ t('case.history.compare_selected', { count: compareSelection.length }) }}
        </a-button>
        <a-button v-if="compareSelection.length > 0" type="link" size="small" @click="compareSelection = []">
          {{ t('case.history.clear_selection') }}
        </a-button>
      </div>

      <a-timeline>
        <a-timeline-item v-for="s in snapshots" :key="s.id">
          <div class="snapshot-card">
            <div class="snapshot-header">
              <a-checkbox
                v-if="snapshots.length >= 2"
                :checked="compareSelection.includes(s.id)"
                :disabled="compareSelection.length >= 2 && !compareSelection.includes(s.id)"
                @change="toggleCompare(s.id)"
                style="margin-right: 8px"
              />
              <span class="version-tag">v{{ s.version }}</span>
              <span class="snapshot-user">{{ s.updated_by_name || t('case.history.user_fallback', { id: s.updated_by }) }}</span>
              <span class="snapshot-time">{{ formatTime(s.created_at) }}</span>
            </div>
            <a-descriptions :column="1" size="small" bordered>
              <a-descriptions-item :label="t('common.name')">{{ s.name }}</a-descriptions-item>
              <a-descriptions-item :label="t('common.description')">{{ s.description || '-' }}</a-descriptions-item>
              <a-descriptions-item :label="t('case.detail.tags')">
                <a-tag v-for="t in s.tags" :key="t" color="blue">{{ t }}</a-tag>
                <span v-if="!s.tags?.length">-</span>
              </a-descriptions-item>
            </a-descriptions>

            <a-collapse :bordered="false" style="margin-top: 8px">
              <a-collapse-panel :header="t('case.history.config_detail')" :key="s.id">
                <pre class="config-json">{{ JSON.stringify(s.config, null, 2) }}</pre>
              </a-collapse-panel>
            </a-collapse>

            <div class="snapshot-actions">
              <a-popconfirm
                :title="t('case.history.rollback_confirm')"
                @confirm="handleRollback(s.id)"
              >
                <a-button size="small" type="primary" ghost :loading="rollingBack === s.id">
                  {{ t('case.history.rollback') }}
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </a-timeline-item>
      </a-timeline>

      <div v-if="total > pageSize" style="text-align: center; margin-top: 16px">
        <a-pagination
          v-model:current="currentPage"
          :total="total"
          :page-size="pageSize"
          size="small"
          show-less-items
          @change="loadSnapshots"
        />
      </div>
    </a-spin>

    <a-modal
      v-model:open="compareOpen"
      :title="t('case.history.compare_title')"
      width="800px"
      :footer="null"
    >
      <a-table
        v-if="compareLeft && compareRight"
        :columns="compareColumns"
        :data-source="compareData"
        :pagination="false"
        size="small"
        bordered
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'left'">
            <span :class="{ 'diff-highlight': record.isDiff }">{{ record.left }}</span>
          </template>
          <template v-if="column.key === 'right'">
            <span :class="{ 'diff-highlight': record.isDiff }">{{ record.right }}</span>
          </template>
        </template>
      </a-table>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { caseApi, type CaseSnapshotItem } from '@/api'

const props = defineProps<{
  open: boolean
  caseId: number | null
}>()

const emit = defineEmits<{
  close: []
  rolled: []
}>()

const { t } = useI18n()

const snapshots = ref<CaseSnapshotItem[]>([])
const loading = ref(false)
const rollingBack = ref<number | null>(null)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)

const compareSelection = ref<number[]>([])
const compareOpen = ref(false)

const compareLeft = computed(() => snapshots.value.find(s => s.id === compareSelection.value[0]))
const compareRight = computed(() => snapshots.value.find(s => s.id === compareSelection.value[1]))

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

const compareColumns = computed(() => [
  { title: t('case.history.field'), dataIndex: 'field', key: 'field', width: 100 },
  { title: compareLeft.value ? `v${compareLeft.value.version}` : t('case.history.version_a'), key: 'left' },
  { title: compareRight.value ? `v${compareRight.value.version}` : t('case.history.version_b'), key: 'right' },
])

const compareData = computed(() => {
  if (!compareLeft.value || !compareRight.value) return []
  const l = compareLeft.value
  const r = compareRight.value

  const fields = [
    { field: t('common.name'), left: l.name, right: r.name },
    { field: t('common.description'), left: l.description || '-', right: r.description || '-' },
    { field: t('case.detail.tags'), left: (l.tags || []).join(', ') || '-', right: (r.tags || []).join(', ') || '-' },
    { field: t('case.history.config'), left: JSON.stringify(l.config, null, 2), right: JSON.stringify(r.config, null, 2) },
  ]

  return fields.map(f => ({
    ...f,
    isDiff: f.left !== f.right,
    key: f.field,
  }))
})

function toggleCompare(id: number) {
  const idx = compareSelection.value.indexOf(id)
  if (idx >= 0) {
    compareSelection.value.splice(idx, 1)
  } else if (compareSelection.value.length < 2) {
    compareSelection.value.push(id)
  }
}

function showCompare() {
  if (compareSelection.value.length !== 2) return
  compareOpen.value = true
}

watch(() => props.open, async (val) => {
  if (val && props.caseId) {
    currentPage.value = 1
    compareSelection.value = []
    await loadSnapshots()
  } else {
    snapshots.value = []
    total.value = 0
  }
})

async function loadSnapshots() {
  if (!props.caseId) return
  loading.value = true
  try {
    const res = await caseApi.listSnapshots(props.caseId, {
      page: currentPage.value,
      page_size: pageSize,
    })
    snapshots.value = res.items
    total.value = res.total
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.history.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ') ?? ''
}

async function handleRollback(snapshotId: number) {
  if (!props.caseId) return
  rollingBack.value = snapshotId
  try {
    await caseApi.rollback(props.caseId, snapshotId)
    message.success(t('case.history.msg.rollback_success'))
    emit('rolled')
    emit('close')
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.history.msg.rollback_failed')))
  } finally {
    rollingBack.value = null
  }
}
</script>

<style scoped>
.snapshot-card {
  margin-bottom: 8px;
}
.snapshot-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.version-tag {
  font-weight: 600;
  color: #1677ff;
}
.snapshot-user {
  color: #666;
  font-size: 13px;
}
.snapshot-time {
  color: #999;
  font-size: 12px;
}
.snapshot-actions {
  margin-top: 8px;
}
.config-json {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  max-height: 300px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.diff-highlight {
  background-color: #fff7e6;
  font-weight: 600;
}
</style>
