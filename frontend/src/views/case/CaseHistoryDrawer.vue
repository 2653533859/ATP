<template>
  <a-drawer
    :open="open"
    title="版本历史"
    :width="680"
    @close="$emit('close')"
  >
    <a-empty v-if="!loading && snapshots.length === 0" description="暂无修改历史" />

    <a-spin :spinning="loading">
      <!-- 版本对比按钮 -->
      <div v-if="snapshots.length >= 2" style="margin-bottom: 12px">
        <a-button
          size="small"
          :disabled="compareSelection.length !== 2"
          @click="showCompare"
        >
          对比选中版本 ({{ compareSelection.length }}/2)
        </a-button>
        <a-button v-if="compareSelection.length > 0" type="link" size="small" @click="compareSelection = []">
          清除选择
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
              <span class="snapshot-user">{{ s.updated_by_name || `用户#${s.updated_by}` }}</span>
              <span class="snapshot-time">{{ formatTime(s.created_at) }}</span>
            </div>
            <a-descriptions :column="1" size="small" bordered>
              <a-descriptions-item label="名称">{{ s.name }}</a-descriptions-item>
              <a-descriptions-item label="描述">{{ s.description || '-' }}</a-descriptions-item>
              <a-descriptions-item label="标签">
                <a-tag v-for="t in s.tags" :key="t" color="blue">{{ t }}</a-tag>
                <span v-if="!s.tags?.length">-</span>
              </a-descriptions-item>
            </a-descriptions>

            <!-- config 折叠展示 -->
            <a-collapse :bordered="false" style="margin-top: 8px">
              <a-collapse-panel header="配置详情 (config)" :key="s.id">
                <pre class="config-json">{{ JSON.stringify(s.config, null, 2) }}</pre>
              </a-collapse-panel>
            </a-collapse>

            <div class="snapshot-actions">
              <a-popconfirm
                title="确认回滚到此版本？当前内容会被保存为新快照。"
                @confirm="handleRollback(s.id)"
              >
                <a-button size="small" type="primary" ghost :loading="rollingBack === s.id">
                  回滚到此版本
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </a-timeline-item>
      </a-timeline>

      <!-- 分页 -->
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

    <!-- 版本对比 Modal -->
    <a-modal
      v-model:open="compareOpen"
      title="版本对比"
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
import { caseApi } from '@/api'

const props = defineProps<{
  open: boolean
  caseId: number | null
}>()

const emit = defineEmits<{
  close: []
  rolled: []
}>()

const snapshots = ref<any[]>([])
const loading = ref(false)
const rollingBack = ref<number | null>(null)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)

// 版本对比
const compareSelection = ref<number[]>([])
const compareOpen = ref(false)

const compareLeft = computed(() => snapshots.value.find(s => s.id === compareSelection.value[0]))
const compareRight = computed(() => snapshots.value.find(s => s.id === compareSelection.value[1]))

const compareColumns = computed(() => [
  { title: '字段', dataIndex: 'field', key: 'field', width: 100 },
  { title: compareLeft.value ? `v${compareLeft.value.version}` : '版本A', key: 'left' },
  { title: compareRight.value ? `v${compareRight.value.version}` : '版本B', key: 'right' },
])

const compareData = computed(() => {
  if (!compareLeft.value || !compareRight.value) return []
  const l = compareLeft.value
  const r = compareRight.value

  const fields = [
    { field: '名称', left: l.name, right: r.name },
    { field: '描述', left: l.description || '-', right: r.description || '-' },
    { field: '标签', left: (l.tags || []).join(', ') || '-', right: (r.tags || []).join(', ') || '-' },
    { field: '配置', left: JSON.stringify(l.config, null, 2), right: JSON.stringify(r.config, null, 2) },
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
  } catch (e: any) {
    message.error(e ?? '加载版本历史失败')
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
    message.success('已回滚')
    emit('rolled')
    emit('close')
  } catch (e: any) {
    message.error(e ?? '回滚失败')
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
