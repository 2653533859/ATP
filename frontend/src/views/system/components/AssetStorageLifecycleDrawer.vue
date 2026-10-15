<template>
  <a-drawer
    :open="visible"
    title="测试资产 MinIO 存储生命周期与自动归档清理"
    width="820px"
    placement="right"
    @close="handleClose"
  >
    <div class="asset-lifecycle-drawer">
      <!-- 顶部空间释放概览 -->
      <div v-if="scanReport" class="reclaim-summary-card">
        <div class="summary-left">
          <div class="disk-badge">
            <span class="disk-val">{{ scanReport.total_reclaimable_mb.toFixed(1) }}</span>
            <span class="disk-unit">MB 待释放</span>
          </div>
          <div class="disk-copy">
            <div class="disk-topline">
              <span class="highlight-text">{{ scanReport.total_expired_count }} 个过期对象可安全清理</span>
              <a-tag color="blue">扫描总数: {{ scanReport.total_scanned_count }}</a-tag>
            </div>
            <p class="disk-desc">
              根据各分类资产保留周期策略扫描，清理后将同步清除数据库孤儿引用，杜绝 404 死链。
            </p>
          </div>
        </div>

        <div class="summary-actions">
          <a-button size="small" :loading="scanning" @click="runScan(true)">
            重新预演扫描
          </a-button>
          <a-popconfirm
            title="确认依据当前保留策略执行物理清理？不可撤销。"
            ok-text="确认清理"
            cancel-text="取消"
            @confirm="runScan(false)"
          >
            <a-button type="primary" danger size="small" :loading="cleaning" :disabled="scanReport.total_expired_count === 0">
              一键执行安全释放
            </a-button>
          </a-popconfirm>
        </div>
      </div>

      <!-- 分类保留天数与过期统计卡片网格 -->
      <div class="section-title">分级资产保留策略与待清理明细 (Asset Retention Categories)</div>
      <a-spin :spinning="scanning">
        <div class="category-grid">
          <div
            v-for="cat in (scanReport?.categories || defaultCategories)"
            :key="cat.category"
            class="category-card"
          >
            <div class="cat-header">
              <span class="cat-name">{{ getCategoryTitle(cat.category) }}</span>
              <a-tag :color="cat.expired_count > 0 ? 'red' : 'green'">
                {{ cat.expired_count }} / {{ cat.scanned_count }} 过期
              </a-tag>
            </div>

            <div class="cat-prefix">前缀路径: <code>{{ cat.prefix }}</code></div>

            <div class="retention-input-row">
              <span class="input-lbl">保留天数:</span>
              <a-input-number
                v-model:value="customRetention[cat.category]"
                :min="1"
                :max="365"
                size="small"
                style="width: 90px"
              />
              <span class="unit-lbl">天</span>
            </div>

            <div class="cat-space-row">
              <span class="space-lbl">可释放空间:</span>
              <strong class="space-val">{{ cat.reclaimable_mb.toFixed(2) }} MB</strong>
            </div>

            <!-- 抽样过期文件预览 -->
            <div v-if="cat.sample_expired_files && cat.sample_expired_files.length" class="sample-box">
              <span class="sample-lbl">抽样文件:</span>
              <div class="sample-list">
                <div v-for="file in cat.sample_expired_files.slice(0, 3)" :key="file" class="sample-file" :title="file">
                  {{ file.replace(cat.prefix, '') }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-spin>

      <!-- 清理成果与数据库引用修复清单 -->
      <div v-if="cleanupResult && !cleanupResult.dry_run" class="cleanup-result-banner">
        <div class="result-head">
          <span class="result-title">🎉 清理执行成果报告</span>
          <a-tag color="green">已物理删除 {{ cleanupResult.deleted_count }} 个对象</a-tag>
        </div>
        <div class="db-reconcile-info">
          <span>数据库孤儿引用清理:</span>
          <span>用例截图: <b>{{ cleanupResult.db_cleanup_summary?.step_results_cleared ?? 0 }}</b> 处</span>
          <span>异常现场: <b>{{ cleanupResult.db_cleanup_summary?.mobile_incidents_cleared ?? 0 }}</b> 处</span>
          <span>移动产物: <b>{{ cleanupResult.db_cleanup_summary?.mobile_artifacts_cleared ?? 0 }}</b> 处</span>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  storageApi,
  type AssetLifecycleScanResponse,
  type CategoryScanItem,
} from '@/api'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const scanning = ref(false)
const cleaning = ref(false)
const scanReport = ref<AssetLifecycleScanResponse | null>(null)
const cleanupResult = ref<AssetLifecycleScanResponse | null>(null)

const customRetention = ref<Record<string, number>>({
  videos: 7,
  screenshots: 14,
  traces: 14,
  reports: 30,
  logs: 30,
})

const defaultCategories: CategoryScanItem[] = [
  { category: 'videos', prefix: 'videos/', retention_days: 7, scanned_count: 0, expired_count: 0, reclaimable_bytes: 0, reclaimable_mb: 0, sample_expired_files: [] },
  { category: 'screenshots', prefix: 'screenshots/', retention_days: 14, scanned_count: 0, expired_count: 0, reclaimable_bytes: 0, reclaimable_mb: 0, sample_expired_files: [] },
  { category: 'traces', prefix: 'traces/', retention_days: 14, scanned_count: 0, expired_count: 0, reclaimable_bytes: 0, reclaimable_mb: 0, sample_expired_files: [] },
  { category: 'reports', prefix: 'reports/', retention_days: 30, scanned_count: 0, expired_count: 0, reclaimable_bytes: 0, reclaimable_mb: 0, sample_expired_files: [] },
  { category: 'logs', prefix: 'logs/', retention_days: 30, scanned_count: 0, expired_count: 0, reclaimable_bytes: 0, reclaimable_mb: 0, sample_expired_files: [] },
]

const getCategoryTitle = (cat: string): string => {
  switch (cat) {
    case 'videos':
      return 'MP4 录像视频 (videos/)'
    case 'screenshots':
      return '步骤与失败截图 (screenshots/)'
    case 'traces':
      return 'HAR抓包与Traces (traces/)'
    case 'reports':
      return '测试聚合报告 (reports/)'
    case 'logs':
      return '系统与Logcat日志 (logs/)'
    default:
      return `${cat}/`
  }
}

const runScan = async (dryRun = true) => {
  if (dryRun) {
    scanning.value = true
  } else {
    cleaning.value = true
  }
  try {
    const payload = {
      custom_retention_days: customRetention.value,
    }
    const res = dryRun
      ? await storageApi.scanLifecycle(payload)
      : await storageApi.executeLifecycleCleanup(payload)

    if (dryRun) {
      scanReport.value = res
      message.success(`生命周期预演完成！预计可释放 ${res.total_reclaimable_mb.toFixed(1)} MB`)
    } else {
      cleanupResult.value = res
      scanReport.value = res
      message.success(`安全清理执行完成！成功释放 ${res.deleted_count} 个过期资产`)
    }
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '执行生命周期扫描失败'
    message.error(msg)
  } finally {
    scanning.value = false
    cleaning.value = false
  }
}

const handleClose = () => {
  emit('update:visible', false)
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      runScan(true)
    }
  },
)

onMounted(() => {
  if (props.visible) {
    runScan(true)
  }
})
</script>

<style scoped>
.asset-lifecycle-drawer {
  padding: 4px 0;
}
.reclaim-summary-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 20px;
}
.summary-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.disk-badge {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 10px 16px;
  background: rgba(24, 144, 255, 0.1);
  border-radius: 8px;
}
.disk-val {
  font-size: 22px;
  font-weight: 800;
  color: #1890ff;
  line-height: 1;
}
.disk-unit {
  font-size: 11px;
  color: #1890ff;
  margin-top: 4px;
}
.disk-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.disk-topline {
  display: flex;
  align-items: center;
  gap: 10px;
}
.highlight-text {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.disk-desc {
  font-size: 12px;
  color: var(--c-text-tertiary, #6b7280);
  margin: 0;
}
.summary-actions {
  display: flex;
  gap: 10px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--c-text-primary, #1f2937);
}
.category-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}
.category-card {
  padding: 12px 14px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
}
.cat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.cat-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.cat-prefix {
  font-size: 11px;
  color: var(--c-text-tertiary, #9ca3af);
  margin-bottom: 8px;
}
.cat-prefix code {
  color: #1890ff;
}
.retention-input-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 12px;
}
.input-lbl {
  color: var(--c-text-secondary, #4b5563);
}
.unit-lbl {
  color: var(--c-text-tertiary, #9ca3af);
}
.cat-space-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
}
.space-lbl {
  color: var(--c-text-secondary, #4b5563);
}
.space-val {
  color: #cf1322;
  font-size: 14px;
}
.sample-box {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed var(--c-border-subtle, #f3f4f6);
}
.sample-lbl {
  font-size: 10px;
  color: var(--c-text-tertiary, #9ca3af);
}
.sample-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 2px;
}
.sample-file {
  font-family: monospace;
  font-size: 10px;
  color: var(--c-text-secondary, #6b7280);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cleanup-result-banner {
  padding: 14px 18px;
  background: rgba(82, 196, 26, 0.08);
  border: 1px solid rgba(82, 196, 26, 0.25);
  border-radius: 8px;
}
.result-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.result-title {
  font-size: 13px;
  font-weight: 700;
  color: #274916;
}
.db-reconcile-info {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #389e0d;
}
</style>
