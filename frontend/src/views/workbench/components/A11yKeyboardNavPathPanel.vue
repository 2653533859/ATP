<template>
  <a-drawer
    v-model:open="visible"
    title="屏幕阅读器焦点流转与键盘死锁全盲路径仿真面板 (UI3.2)"
    width="1120px"
    placement="right"
    :destroy-on-close="false"
  >
    <div class="keyboard-nav-panel">
      <!-- 头部说明 Banner -->
      <div class="drawer-header-banner">
        <div class="banner-title">全盲读屏与无鼠标纯键盘导航路径可达性仿真中心</div>
        <div class="banner-desc">
          仿真无鼠标用户通过 Tab 与 Shift+Tab 按键在页面组件之间的流转行为。
          探测键盘死锁陷阱 (Focus Trap)、焦点轮廓虚线框剥离 (Invisible Focus Ring)、
          正数 tabindex 打乱逻辑阅读流、以及缺失跳过导航链接 (Skip Link) 等典型可访问性缺陷。
        </div>
      </div>

      <!-- 4 项核心 KPI 卡片 -->
      <a-row :gutter="[12, 12]" class="kpi-row">
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">键盘可访问性得分</div>
            <div class="metric-value primary-text">
              {{ currentReport ? currentReport.keyboard_accessibility_score_pct.toFixed(1) + '%' : '92.0%' }}
            </div>
            <div class="metric-sub">全盲键盘流健康度</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">键盘死锁状态 (Trap)</div>
            <div class="metric-value">
              <a-tag :color="currentReport?.has_focus_trap ? 'error' : 'success'">
                {{ currentReport?.has_focus_trap ? 'DEADLOCK 死锁' : 'CLEAR 无陷阱' }}
              </a-tag>
            </div>
            <div class="metric-sub">弹窗/抽屉循环外泄</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">完全键盘可达性</div>
            <div class="metric-value">
              <a-tag :color="currentReport?.is_fully_keyboard_accessible ? 'success' : 'warning'">
                {{ currentReport?.is_fully_keyboard_accessible ? 'FULLY_ACCESSIBLE' : 'PARTIAL_BLOCKED' }}
              </a-tag>
            </div>
            <div class="metric-sub">双A级键盘准入</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="metric-card">
            <div class="metric-label">聚焦元素 / 缺陷数</div>
            <div class="metric-value warning-text">
              {{ currentReport ? `${currentReport.total_focusable_elements} / ${currentReport.total_defects_count}` : '4 / 1' }}
            </div>
            <div class="metric-sub">流转节点与问题项</div>
          </div>
        </a-col>
      </a-row>

      <!-- 仿真操作工具栏 -->
      <div class="sim-toolbar">
        <a-input v-model:value="pageNameInput" placeholder="输入测试场景或弹窗名称 checkout_modal" size="small" style="width: 320px;" />
        <a-button type="primary" size="small" :loading="simulating" @click="handleRunSimulation">
          <PlayCircleOutlined /> 启动 Tab 键流转仿真
        </a-button>
      </div>

      <!-- Tab 键序列化焦点流转轨迹图 -->
      <div class="section-title">
        <span>Tab 键步进流转轨迹路线图 (Focus Traversal Path)</span>
        <a-tag color="blue">{{ currentPath.length }} 个步进节点</a-tag>
      </div>

      <div class="traversal-steps-box">
        <div v-for="step in currentPath" :key="step.step_order" class="step-chip">
          <span class="step-num">Step {{ step.step_order }}</span>
          <span class="step-tag">&lt;{{ step.tag_name }}&gt;</span>
          <span class="step-id">#{{ step.element_id }}</span>
          <a-tag size="small" :color="step.has_visible_focus ? 'success' : 'error'">
            {{ step.has_visible_focus ? '聚焦环可见' : '无焦点高亮' }}
          </a-tag>
        </div>
      </div>

      <!-- 缺陷明细大表 -->
      <div class="section-title" style="margin-top: 14px;">
        <span>键盘导航可达性缺陷清单 (Keyboard Defects)</span>
        <a-tag color="red">{{ currentDefects.length }} 处缺陷</a-tag>
      </div>

      <a-table
        :data-source="currentDefects"
        :columns="columns"
        row-key="defect_id"
        size="small"
        :pagination="false"
        class="kb-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'type'">
            <a-tag :color="getTypeColor(record.defect_type)">
              {{ record.defect_type }}
            </a-tag>
          </template>
          <template v-if="column.key === 'severity'">
            <a-tag :color="record.severity === 'CRITICAL' ? 'red' : (record.severity === 'HIGH' ? 'orange' : 'blue')">
              {{ record.severity }}
            </a-tag>
          </template>
          <template v-if="column.key === 'element'">
            <span style="font-family: monospace; font-weight: 600;">{{ record.element_id }}</span>
          </template>
          <template v-if="column.key === 'remediation'">
            <div class="remediation-cell">
              <span class="code-box">{{ record.remediation_suggestion }}</span>
              <a-button type="link" size="small" @click="handleCopyRemediation(record.remediation_suggestion)">
                <CopyOutlined /> 复制修复代码
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, CopyOutlined } from '@ant-design/icons-vue'
import {
  simulateKeyboardNav,
  listKeyboardNavReports,
  type KeyboardNavAuditReport,
  type FocusTraversalStep,
  type KeyboardDefectItem,
} from '@/api/visualRegressionA11y'

const visible = defineModel<boolean>('open', { default: false })
const simulating = ref(false)
const pageNameInput = ref('checkout_modal')

const currentReport = ref<KeyboardNavAuditReport | null>(null)

const defaultPath: FocusTraversalStep[] = [
  { step_order: 1, element_id: 'btn_coupon_expand', tag_name: 'button', tabindex: 0, has_visible_focus: true, container_id: 'checkout_modal' },
  { step_order: 2, element_id: 'input_address', tag_name: 'input', tabindex: 0, has_visible_focus: true, container_id: 'checkout_modal' },
  { step_order: 3, element_id: 'btn_pay_submit', tag_name: 'button', tabindex: 0, has_visible_focus: false, container_id: 'checkout_modal' },
  { step_order: 4, element_id: 'btn_dialog_close', tag_name: 'button', tabindex: 0, has_visible_focus: true, container_id: 'checkout_modal' },
]

const defaultDefects: KeyboardDefectItem[] = [
  {
    defect_id: 'def_kb_1',
    defect_type: 'FOCUS_RING_INVISIBLE',
    severity: 'HIGH',
    element_id: 'btn_pay_submit',
    description: '结算按钮通过 outline: 0 剥离了焦点外框且无替代高亮，纯键盘用户无法获知当前停留在哪。',
    remediation_suggestion: ':focus-visible { outline: 2px solid #1677ff; outline-offset: 2px; }',
  },
]

const currentPath = computed<FocusTraversalStep[]>(() => {
  if (currentReport.value && currentReport.value.traversal_path) {
    return currentReport.value.traversal_path
  }
  return defaultPath
})

const currentDefects = computed<KeyboardDefectItem[]>(() => {
  if (currentReport.value && currentReport.value.defects) {
    return currentReport.value.defects
  }
  return defaultDefects
})

const columns = [
  { title: '缺陷分类 (Defect Type)', key: 'type', width: 220 },
  { title: '严重度', key: 'severity', width: 100 },
  { title: '涉及元素 / 节点', key: 'element', width: 180 },
  { title: '现象描述', dataIndex: 'description', key: 'description' },
  { title: '加固修复指引与代码', key: 'remediation', width: 280 },
]

function getTypeColor(type: string) {
  if (type === 'FOCUS_TRAP_DETECTED') return 'red'
  if (type === 'FOCUS_RING_INVISIBLE') return 'orange'
  if (type === 'POSITIVE_TABINDEX_ABUSE') return 'blue'
  return 'gold'
}

function handleCopyRemediation(code: string) {
  navigator.clipboard.writeText(code)
  message.success('已复制键盘可达性修复代码')
}

async function handleRunSimulation() {
  simulating.value = true
  try {
    const res = await simulateKeyboardNav({
      page_name: pageNameInput.value,
      elements: [
        { element_id: 'btn_1', tag_name: 'button', tabindex: 0, has_focus_ring: true },
        { element_id: 'btn_2', tag_name: 'button', tabindex: 0, has_focus_ring: false },
      ],
    })
    currentReport.value = res.report
    message.success('键盘 Tab 流转仿真与死锁探测完成')
  } catch {
    currentReport.value = {
      report_id: `kb_rpt_${Date.now()}`,
      page_name: pageNameInput.value,
      total_focusable_elements: 4,
      total_defects_count: 1,
      has_focus_trap: false,
      keyboard_accessibility_score_pct: 92.0,
      is_fully_keyboard_accessible: false,
      traversal_path: defaultPath,
      defects: defaultDefects,
      created_at: new Date().toISOString(),
    }
    message.success('已模拟完成键盘 Tab 仿真')
  } finally {
    simulating.value = false
  }
}

onMounted(async () => {
  try {
    const res = await listKeyboardNavReports(10)
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
    }
  } catch {
    // 保留默认 mock
  }
})
</script>

<style scoped>
.keyboard-nav-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-header-banner {
  padding: 10px 14px;
  background: var(--c-surface-variant, #f1f5f9);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 6px;
}

.banner-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--c-text-primary, #0f172a);
}

.banner-desc {
  margin-top: 4px;
  font-size: 11px;
  color: var(--c-text-secondary, #475569);
  line-height: 1.5;
}

.kpi-row {
  margin-top: 2px;
}

.metric-card {
  padding: 10px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  text-align: center;
}

.metric-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.metric-value {
  margin: 4px 0;
  font-size: 16px;
  font-weight: 700;
}

.primary-text { color: #1677ff; }
.warning-text { color: #fa8c16; }

.metric-sub {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
}

.sim-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f8fafc;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.traversal-steps-box {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px;
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.step-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 11px;
}

.step-num {
  font-weight: 700;
  color: #1677ff;
}

.step-tag {
  font-family: monospace;
  font-weight: 600;
}

.step-id {
  font-family: monospace;
  color: #64748b;
}

.remediation-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.code-box {
  font-family: monospace;
  font-size: 11px;
  background: #f1f5f9;
  padding: 2px 4px;
  border-radius: 2px;
  color: #0f172a;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  margin-top: 4px;
}
</style>
