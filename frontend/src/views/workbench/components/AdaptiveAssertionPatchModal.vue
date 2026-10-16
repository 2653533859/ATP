<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="接口响应格式变迁自适应断言推导与代码 Diff 补丁控制台"
    destroy-on-close
    class="assertion-patch-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制介绍 Banner -->
      <div class="intro-banner">
        <div class="banner-top">
          <CodeOutlined class="banner-icon" />
          <div class="banner-texts">
            <div class="banner-title">API 响应结构变迁自适应断言推导与自动化补丁引擎 (T4.2)</div>
            <div class="banner-desc">
              当微服务接口重构引入外层数据包装（Envelope Unwrap）、驼峰/下划线命名演化或数组下钻时，传统用例断言往往全量误报失败。本引擎通过 JSONPath 递归逆向探查算法自动定位迁移字段，生成高置信度新断言表达式与 Python 代码 Diff，支持一键持久化应用落地。
            </div>
          </div>
        </div>

        <!-- 3 大变迁模式卡片 -->
        <div class="mode-cards">
          <div class="mode-card">
            <div class="mode-title">📦 外层包装拆包 (ENVELOPE)</div>
            <div class="mode-desc">$.order_id → $.data.order_id 自动感知</div>
          </div>
          <div class="mode-card">
            <div class="mode-title">🔤 命名规范演变 (RENAME)</div>
            <div class="mode-desc">user_id ⇄ userId 驼峰下划线智能互转</div>
          </div>
          <div class="mode-card">
            <div class="mode-title">📊 数组下钻深入 (EXPANSION)</div>
            <div class="mode-desc">$.item_id → $.items[0].item_id 列表探查</div>
          </div>
        </div>
      </div>

      <!-- 选项卡 -->
      <a-tabs v-model:activeKey="activeTab" size="small" class="patch-tabs">
        <!-- Tab 1: 在线推导自适应新断言 -->
        <a-tab-pane key="derive" tab="🧪 在线推导自适应新断言">
          <div class="tab-box">
            <!-- 快速演练预设 -->
            <div class="preset-row">
              <span class="preset-label">接口变迁演练预设:</span>
              <a-space :size="8" wrap>
                <a-button
                  size="small"
                  :type="presetKey === 'envelope' ? 'primary' : 'default'"
                  danger
                  @click="applyPreset('envelope')"
                >
                  场景 1: 外层数据包装拆包 ($.data.order_id)
                </a-button>
                <a-button
                  size="small"
                  :type="presetKey === 'camel' ? 'primary' : 'default'"
                  @click="applyPreset('camel')"
                >
                  场景 2: 驼峰下划线重命名 (user_id -> userId)
                </a-button>
                <a-button
                  size="small"
                  :type="presetKey === 'expansion' ? 'primary' : 'default'"
                  @click="applyPreset('expansion')"
                >
                  场景 3: 数组下钻深入 (items[0].item_id)
                </a-button>
              </a-space>
            </div>

            <!-- 推导参数输入表单 -->
            <div class="derive-form">
              <div class="form-row">
                <a-space :size="12" align="center" wrap>
                  <span class="f-lbl">接口端点:</span>
                  <a-input v-model:value="deriveForm.endpoint" style="width: 260px" size="small" />

                  <span class="f-lbl">失效原断言:</span>
                  <a-input v-model:value="deriveForm.original_assertion" style="width: 240px" size="small" />

                  <span class="f-lbl">期望比对值:</span>
                  <a-input v-model:value="deriveForm.expected_value_str" placeholder="如 1001" style="width: 100px" size="small" />

                  <a-button type="primary" size="small" :loading="deriving" @click="handleRunDerive">
                    <ThunderboltOutlined /> 执行自适应新断言推导
                  </a-button>
                </a-space>
              </div>

              <div class="payload-block">
                <span class="block-lbl">实测最新响应体 (JSON Payload):</span>
                <a-textarea v-model:value="deriveForm.response_payload_str" :rows="3" size="small" class="payload-text" />
              </div>
            </div>

            <!-- 推导补丁裁决大卡片 (Patch Verdict Card) -->
            <div v-if="currentPatch" class="patch-result-card" :class="`card-type-${currentPatch.patch_type.toLowerCase()}`">
              <div class="res-head">
                <div class="res-title-box">
                  <a-tag :color="getPatchTypeColor(currentPatch.patch_type)" class="type-tag">
                    {{ currentPatch.patch_type }}
                  </a-tag>
                  <span class="confidence-text">置信度: <strong>{{ Math.round(currentPatch.confidence_score * 100) }}%</strong></span>
                  <span class="res-summary">{{ currentPatch.explanation }}</span>
                </div>
                <a-space>
                  <a-button
                    size="small"
                    type="primary"
                    :disabled="currentPatch.is_applied"
                    :loading="applying"
                    @click="handleApplyPatch(currentPatch.patch_id)"
                  >
                    <CheckOutlined /> {{ currentPatch.is_applied ? '已持久化生效' : '一键应用补丁' }}
                  </a-button>
                  <a-button size="small" type="link" @click="copyDiff(currentPatch.python_code_diff)">
                    <CopyOutlined /> 复制 Diff
                  </a-button>
                </a-space>
              </div>

              <!-- 断言路径对比框 -->
              <div class="assertion-compare-box">
                <div class="cmp-row">
                  <span class="cmp-lbl">失效原断言:</span>
                  <code class="old-ast">{{ currentPatch.original_assertion }}</code>
                </div>
                <div class="cmp-row">
                  <span class="cmp-lbl">自适应新断言:</span>
                  <code class="new-ast">{{ currentPatch.patched_assertion }}</code>
                </div>
              </div>

              <!-- Python Code Diff 渲染 -->
              <div class="diff-block">
                <div class="diff-title">Python 自动化测试脚本变更补丁 (Code Diff):</div>
                <pre class="diff-code">{{ currentPatch.python_code_diff }}</pre>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- Tab 2: 已推导断言补丁清单 -->
        <a-tab-pane key="history" tab="📋 已推导断言自愈补丁清单">
          <div class="tab-box">
            <div class="tab-actions">
              <a-space>
                <a-button size="small" :loading="loadingPatches" @click="fetchPatches">
                  <ReloadOutlined /> 刷新补丁清单
                </a-button>
                <span class="patches-count">共登记 <strong>{{ patches.length }}</strong> 条自愈断言补丁</span>
              </a-space>
            </div>

            <a-table
              :data-source="patches"
              :columns="tableColumns"
              row-key="patch_id"
              size="small"
              :pagination="false"
              bordered
              class="patches-table"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'patch_id'">
                  <code>{{ record.patch_id }}</code>
                </template>

                <template v-if="column.key === 'patch_type'">
                  <a-tag :color="getPatchTypeColor(record.patch_type)">{{ record.patch_type }}</a-tag>
                </template>

                <template v-if="column.key === 'assertions'">
                  <div class="ast-cell">
                    <span class="old-ast-sub">旧: <code>{{ record.original_assertion }}</code></span>
                    <span class="new-ast-sub">新: <code>{{ record.patched_assertion }}</code></span>
                  </div>
                </template>

                <template v-if="column.key === 'confidence'">
                  <span class="text-green font-bold">{{ Math.round(record.confidence_score * 100) }}%</span>
                </template>

                <template v-if="column.key === 'status'">
                  <a-tag :color="record.is_applied ? 'green' : 'orange'">
                    {{ record.is_applied ? '已应用生效' : '待应用' }}
                  </a-tag>
                </template>

                <template v-if="column.key === 'action'">
                  <a-button
                    v-if="!record.is_applied"
                    size="small"
                    type="link"
                    @click="handleApplyPatch(record.patch_id)"
                  >
                    应用
                  </a-button>
                  <span v-else class="text-green text-xs">已生效</span>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  CodeOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  CheckOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  adaptiveAssertionPatchApi,
  type AssertionPatchItem,
} from '@/api/testSelfHealing'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

function handleClose() {
  emit('update:open', false)
}

const activeTab = ref<'derive' | 'history'>('derive')
const deriving = ref(false)
const applying = ref(false)
const loadingPatches = ref(false)
const currentPatch = ref<AssertionPatchItem | null>(null)
const patches = ref<AssertionPatchItem[]>([])
const presetKey = ref<'envelope' | 'camel' | 'expansion'>('envelope')

const deriveForm = reactive({
  endpoint: 'POST /api/v1/orders/checkout',
  original_assertion: '$.order_id == 1001',
  expected_value_str: '1001',
  response_payload_str: '{"code": 0, "message": "success", "data": {"order_id": 1001, "status": "PAID"}}',
})

const tableColumns = [
  { title: '补丁 ID', key: 'patch_id', width: 140 },
  { title: '变迁模式', key: 'patch_type', width: 160 },
  { title: '原断言 vs 自愈断言', key: 'assertions' },
  { title: '置信度', key: 'confidence', width: 90 },
  { title: '状态', key: 'status', width: 100 },
  { title: '操作', key: 'action', width: 80 },
]

function getPatchTypeColor(t: string): string {
  switch (t) {
    case 'ENVELOPE_UNWRAP': return 'green'
    case 'FIELD_RENAME': return 'blue'
    case 'PATH_EXPANSION': return 'purple'
    case 'TYPE_COERCION': return 'orange'
    default: return 'default'
  }
}

// 演练预设
const PRESETS = {
  envelope: {
    endpoint: 'POST /api/v1/orders/checkout',
    original_assertion: '$.order_id == 1001',
    expected_value_str: '1001',
    response_payload_str: JSON.stringify(
      { code: 0, message: 'success', data: { order_id: 1001, status: 'PAID' } },
      null,
      2
    ),
  },
  camel: {
    endpoint: 'GET /api/v1/users/profile',
    original_assertion: "response['user_id'] == 888",
    expected_value_str: '888',
    response_payload_str: JSON.stringify({ userId: 888, userName: 'Alice' }, null, 2),
  },
  expansion: {
    endpoint: 'GET /api/v1/items/search',
    original_assertion: '$.item_id == 55',
    expected_value_str: '55',
    response_payload_str: JSON.stringify(
      { total: 1, items: [{ item_id: 55, name: 'MacBook Pro' }] },
      null,
      2
    ),
  },
}

function applyPreset(key: 'envelope' | 'camel' | 'expansion') {
  presetKey.value = key
  const p = PRESETS[key]
  deriveForm.endpoint = p.endpoint
  deriveForm.original_assertion = p.original_assertion
  deriveForm.expected_value_str = p.expected_value_str
  deriveForm.response_payload_str = p.response_payload_str
  handleRunDerive()
}

async function handleRunDerive() {
  deriving.value = true
  try {
    let parsedPayload: any
    try {
      parsedPayload = JSON.parse(deriveForm.response_payload_str)
    } catch {
      parsedPayload = deriveForm.response_payload_str
    }

    let expectedVal: any = deriveForm.expected_value_str
    if (!isNaN(Number(deriveForm.expected_value_str))) {
      expectedVal = Number(deriveForm.expected_value_str)
    }

    const res = await adaptiveAssertionPatchApi.derive({
      case_id: 'case_api_auto_patch',
      endpoint: deriveForm.endpoint,
      original_assertion: deriveForm.original_assertion,
      actual_response_payload: parsedPayload,
      expected_value: expectedVal,
    })
    currentPatch.value = res.patch
    message.success(res.message || '自适应断言补丁推导成功')
    await fetchPatches()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '推导失败')
  } finally {
    deriving.value = false
  }
}

async function handleApplyPatch(patchId: string) {
  applying.value = true
  try {
    await adaptiveAssertionPatchApi.apply(patchId)
    message.success('断言补丁已持久化应用生效')
    if (currentPatch.value && currentPatch.value.patch_id === patchId) {
      currentPatch.value.is_applied = true
    }
    await fetchPatches()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '应用失败')
  } finally {
    applying.value = false
  }
}

async function fetchPatches() {
  loadingPatches.value = true
  try {
    const res = await adaptiveAssertionPatchApi.listPatches()
    patches.value = res.patches
  } catch {
    // ignore
  } finally {
    loadingPatches.value = false
  }
}

function copyDiff(diff: string) {
  void navigator.clipboard.writeText(diff)
  message.success('已复制 Python 代码补丁')
}

onMounted(() => {
  handleRunDerive()
  fetchPatches()
})
</script>

<style scoped>
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.intro-banner {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.banner-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.banner-icon {
  font-size: 22px;
  color: #0284c7;
  margin-top: 2px;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.banner-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
  margin-top: 4px;
}

.mode-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.mode-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 12px;
}

.mode-title {
  font-size: 11px;
  font-weight: 700;
  color: #1e293b;
}

.mode-desc {
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
}

.patch-tabs {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
}

.tab-box {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 6px;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.derive-form {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.f-lbl {
  font-size: 12px;
  color: #64748b;
}

.payload-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.block-lbl {
  font-size: 11px;
  color: #475569;
  font-weight: 500;
}

.payload-text {
  font-family: Consolas, monospace;
  font-size: 11px;
}

/* 补丁裁决卡片 */
.patch-result-card {
  border-radius: 8px;
  padding: 14px 18px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card-type-envelope_unwrap {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.card-type-field_rename {
  background: #f0f9ff;
  border-color: #bae6fd;
}

.card-type-path_expansion {
  background: #faf5ff;
  border-color: #e9d5ff;
}

.res-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.res-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.type-tag {
  font-weight: 800;
}

.confidence-text {
  font-size: 12px;
  color: #0f172a;
}

.res-summary {
  font-size: 12px;
  color: #334155;
  font-weight: 500;
}

.assertion-compare-box {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cmp-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.cmp-lbl {
  color: #64748b;
  width: 90px;
}

.old-ast {
  color: #dc2626;
  background: #fee2e2;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: Consolas, monospace;
}

.new-ast {
  color: #16a34a;
  background: #dcfce7;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: Consolas, monospace;
  font-weight: bold;
}

.diff-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.diff-title {
  font-size: 11px;
  font-weight: 600;
  color: #475569;
}

.diff-code {
  background: #0f172a;
  color: #38bdf8;
  font-family: Consolas, monospace;
  font-size: 11px;
  line-height: 1.4;
  padding: 10px;
  border-radius: 6px;
  margin: 0;
  white-space: pre-wrap;
}

.tab-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.patches-count {
  font-size: 12px;
  color: #64748b;
}

.patches-table {
  background: #ffffff;
}

.ast-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}

.old-ast-sub {
  color: #dc2626;
}

.new-ast-sub {
  color: #16a34a;
  font-weight: 600;
}

.text-green {
  color: #16a34a;
}

.font-bold {
  font-weight: 700;
}

.text-xs {
  font-size: 11px;
}
</style>
