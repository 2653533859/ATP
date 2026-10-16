<template>
  <a-modal
    :open="open"
    :width="1120"
    title="一阶语法变异算子注入生成与代码对比工作台"
    :footer="null"
    destroy-on-close
    class="mutation-generator-modal"
    @cancel="handleClose"
  >
    <div class="mutation-modal-content">
      <!-- 头部说明条 -->
      <div class="modal-banner">
        <div class="banner-title">
          <ThunderboltOutlined class="banner-icon" />
          <span>AST 一阶语法变异注入引擎 (First-Order Mutation Generator)</span>
        </div>
        <p class="banner-desc">
          基于 Python AST 抽象语法树解析，在代码关键决策节点注入微小的单一变异算子。用于检验单元测试集断言是否真正具备击毙缺陷的能力，杜绝「只跑代码无有效断言」的虚假覆盖率。
        </p>
      </div>

      <!-- 源码与算子配置区 -->
      <div class="config-grid">
        <!-- 源码输入区 -->
        <div class="config-card source-card">
          <div class="card-header">
            <span class="card-title"><CodeOutlined /> 待变异 Python 源码</span>
            <div class="card-actions">
              <a-button size="small" type="link" @click="loadSampleCode('discount')">
                示例: 折扣计算
              </a-button>
              <a-button size="small" type="link" @click="loadSampleCode('auth')">
                示例: 权限门禁
              </a-button>
            </div>
          </div>
          <div class="card-body">
            <a-textarea
              v-model:value="sourceCode"
              class="code-editor"
              :rows="9"
              placeholder="请输入或粘贴 Python 函数源码..."
            />
            <div class="source-meta-row">
              <span class="meta-item">文件路径: <a-input v-model:value="filePath" size="small" style="width: 140px" /></span>
              <span class="meta-item">限定行号 (可选): <a-input v-model:value="targetLinesInput" size="small" placeholder="如: 3, 5, 8" style="width: 120px" /></span>
              <span class="meta-item">变异体上限: <a-input-number v-model:value="maxMutants" size="small" :min="1" :max="100" style="width: 70px" /></span>
              <a-button type="primary" size="small" :loading="generating" @click="handleGenerate">
                <ThunderboltOutlined /> 生成一阶变异体
              </a-button>
            </div>
          </div>
        </div>

        <!-- 算子类型说明与筛选卡 -->
        <div class="config-card operator-card">
          <div class="card-header">
            <span class="card-title"><ExperimentOutlined /> 五大一阶变异算子配置</span>
            <a-tag color="blue">一阶精确变异</a-tag>
          </div>
          <div class="card-body operator-list">
            <div
              v-for="op in supportedOperators"
              :key="op.type"
              class="operator-item"
              :class="{ active: selectedOperators.includes(op.type) }"
              @click="toggleOperator(op.type)"
            >
              <div class="op-top">
                <a-tag :color="op.color" class="op-tag">{{ op.type }}</a-tag>
                <span class="op-name">{{ op.name }}</span>
                <span v-if="report?.operator_distribution?.[op.type]" class="op-count-badge">
                  {{ report.operator_distribution[op.type] }} 个
                </span>
              </div>
              <div class="op-desc">{{ op.desc }}</div>
              <div class="op-example">例: <code>{{ op.example }}</code></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 变异体生成结果看板 -->
      <a-spin :spinning="generating">
        <div v-if="report" class="result-section">
          <!-- KPI 概览指标 -->
          <div class="kpi-grid">
            <div class="kpi-card">
              <span class="kpi-label">已生成变异体总数</span>
              <span class="kpi-val text-primary">{{ report.total_mutants_generated }}</span>
              <span class="kpi-sub">上限 {{ maxMutants }} 个</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">涉及源码行号数</span>
              <span class="kpi-val text-info">{{ report.target_lines_count }}</span>
              <span class="kpi-sub">{{ report.file_path }}</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">已激活变异算子种数</span>
              <span class="kpi-val text-warning">{{ Object.keys(report.operator_distribution || {}).length }} / 5</span>
              <span class="kpi-sub">覆盖率 {{ Math.round((Object.keys(report.operator_distribution || {}).length / 5) * 100) }}%</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">当前选定变异体</span>
              <span class="kpi-val text-success">{{ selectedMutant ? '#' + selectedMutant.line_number + '行' : '-' }}</span>
              <span class="kpi-sub">{{ selectedMutant ? selectedMutant.operator_type : '点击列表比对' }}</span>
            </div>
          </div>

          <!-- 下半部分：变异体列表 + 双栏 Diff 对比区 -->
          <div class="diff-split-container">
            <!-- 左侧变异体列表 -->
            <div class="mutant-list-pane">
              <div class="pane-header">
                <span class="pane-title">变异体清单 ({{ filteredMutants.length }})</span>
                <a-tag v-if="selectedOperators.length < 5" color="orange" size="small">
                  已筛选 {{ selectedOperators.length }} 算子
                </a-tag>
              </div>
              <div class="mutant-items-scroll">
                <div
                  v-for="(mutant, index) in filteredMutants"
                  :key="mutant.mutant_id"
                  class="mutant-row-card"
                  :class="{ selected: selectedMutant?.mutant_id === mutant.mutant_id }"
                  @click="selectedMutant = mutant"
                >
                  <div class="mutant-row-top">
                    <span class="mutant-idx">#{{ index + 1 }}</span>
                    <a-tag :color="getOperatorColor(mutant.operator_type)" size="small">
                      {{ mutant.operator_type }}
                    </a-tag>
                    <span class="mutant-line">Line {{ mutant.line_number }}</span>
                  </div>
                  <div class="mutant-token-swap">
                    <code class="old-token">{{ mutant.original_token }}</code>
                    <span class="swap-arrow">→</span>
                    <code class="new-token">{{ mutant.mutated_token }}</code>
                  </div>
                  <div class="mutant-row-desc">{{ mutant.description }}</div>
                </div>
              </div>
            </div>

            <!-- 右侧双栏对比与代码明细 -->
            <div class="diff-viewer-pane">
              <template v-if="selectedMutant">
                <div class="pane-header">
                  <div class="diff-title-left">
                    <span class="pane-title">行级变异代码比对 (Line {{ selectedMutant.line_number }})</span>
                    <a-tag :color="getOperatorColor(selectedMutant.operator_type)">
                      {{ selectedMutant.operator_type }} - {{ selectedMutant.description }}
                    </a-tag>
                  </div>
                  <a-space>
                    <a-button size="small" @click="copyCode(selectedMutant.mutated_code)">
                      <CopyOutlined /> 复制完整变异代码
                    </a-button>
                  </a-space>
                </div>

                <!-- 行级双栏比对框 -->
                <div class="line-diff-box">
                  <div class="diff-col old-col">
                    <div class="col-tag">原始代码 (Original)</div>
                    <pre class="code-pre"><code>{{ selectedMutant.original_line }}</code></pre>
                  </div>
                  <div class="diff-col new-col">
                    <div class="col-tag">一阶变异代码 (Mutated)</div>
                    <pre class="code-pre"><code>{{ selectedMutant.mutated_line }}</code></pre>
                  </div>
                </div>

                <!-- 完整变异体预览 -->
                <div class="full-code-box">
                  <div class="full-code-header">
                    <span>完整变异体代码预览 (已注入变异体 ID: <code>{{ selectedMutant.mutant_id.slice(0, 8) }}...</code>)</span>
                  </div>
                  <pre class="full-code-content"><code>{{ selectedMutant.mutated_code }}</code></pre>
                </div>
              </template>
              <div v-else class="empty-diff-placeholder">
                <a-empty description="请从左侧列表点击选择一个变异体进行代码差异比对" />
              </div>
            </div>
          </div>
        </div>
      </a-spin>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  CodeOutlined,
  ExperimentOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type MutationOperatorType,
  type MutantItem,
  type MutationGenerationReport,
} from '@/api/ciImpact'

const props = defineProps<{
  open: boolean
  defaultSourceCode?: string
  defaultFilePath?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'mutants-generated', report: MutationGenerationReport): void
}>()

const DEFAULT_SAMPLE_DISCOUNT = `def calculate_discount(price: float, is_vip: bool, coupon_count: int) -> float:
    if price <= 0:
        return 0.0
    discount = 0.0
    if is_vip and coupon_count > 0:
        discount = price * 0.20
    elif is_vip or coupon_count >= 2:
        discount = price * 0.10
    else:
        discount = 0.0
    return price - discount
`

const DEFAULT_SAMPLE_AUTH = `def check_user_access(role: str, is_active: bool, retry_left: int) -> bool:
    if not is_active or retry_left <= 0:
        return False
    if role == "ADMIN" or role == "SECURITY_AUDITOR":
        return True
    return False
`

const sourceCode = ref(props.defaultSourceCode || DEFAULT_SAMPLE_DISCOUNT)
const filePath = ref(props.defaultFilePath || 'discount_service.py')
const targetLinesInput = ref('')
const maxMutants = ref(25)
const generating = ref(false)

const report = ref<MutationGenerationReport | null>(null)
const selectedMutant = ref<MutantItem | null>(null)

interface OperatorMeta {
  type: MutationOperatorType
  name: string
  color: string
  desc: string
  example: string
}

const supportedOperators: OperatorMeta[] = [
  {
    type: 'ROR',
    name: '关系运算符反转 (Relational)',
    color: 'magenta',
    desc: '反转比较算子，检查测试是否具备严格边界验证',
    example: 'price <= 0 -> price > 0, > -> <=',
  },
  {
    type: 'LCR',
    name: '逻辑连接符替换 (Logical)',
    color: 'purple',
    desc: '反转条件连接词，暴露多条件组合逻辑漏洞',
    example: 'is_vip and coupon > 0 -> is_vip or ...',
  },
  {
    type: 'AOR',
    name: '算术运算符替换 (Arithmetic)',
    color: 'blue',
    desc: '篡改数值计算逻辑，测试核心金额与量化公式',
    example: 'price * 0.2 -> price / 0.2, - -> +',
  },
  {
    type: 'RVO',
    name: '返回值篡改 (Return Value)',
    color: 'red',
    desc: '置空或布尔翻转函数出口，杜绝空跑用例',
    example: 'return price - discount -> return None',
  },
  {
    type: 'BVO',
    name: '常数边界值偏移 (Boundary)',
    color: 'orange',
    desc: '整数常数 ±1 偏移，检测临界值是否漏测',
    example: 'coupon_count >= 2 -> coupon_count >= 3',
  },
]

const selectedOperators = ref<MutationOperatorType[]>(['ROR', 'LCR', 'AOR', 'RVO', 'BVO'])

const toggleOperator = (type: MutationOperatorType) => {
  const idx = selectedOperators.value.indexOf(type)
  if (idx >= 0) {
    if (selectedOperators.value.length === 1) {
      message.warning('至少需要保留一种变异算子')
      return
    }
    selectedOperators.value.splice(idx, 1)
  } else {
    selectedOperators.value.push(type)
  }
}

const getOperatorColor = (type: MutationOperatorType) => {
  return supportedOperators.find(o => o.type === type)?.color || 'default'
}

const filteredMutants = computed(() => {
  if (!report.value?.mutants) return []
  return report.value.mutants.filter(m => selectedOperators.value.includes(m.operator_type))
})

const loadSampleCode = (type: 'discount' | 'auth') => {
  if (type === 'discount') {
    sourceCode.value = DEFAULT_SAMPLE_DISCOUNT
    filePath.value = 'discount_service.py'
  } else {
    sourceCode.value = DEFAULT_SAMPLE_AUTH
    filePath.value = 'auth_guard.py'
  }
  message.info(`已载入「${type === 'discount' ? '折扣计算' : '权限门禁'}」标准 Python 示例`)
}

const parseTargetLines = (): number[] | undefined => {
  if (!targetLinesInput.value.trim()) return undefined
  const parts = targetLinesInput.value.split(/[,，\s]+/)
  const lines: number[] = []
  for (const part of parts) {
    const num = parseInt(part, 10)
    if (!isNaN(num) && num > 0) {
      lines.push(num)
    }
  }
  return lines.length > 0 ? lines : undefined
}

const handleGenerate = async () => {
  if (!sourceCode.value.trim()) {
    message.warning('请输入待变异 Python 源代码')
    return
  }

  generating.value = true
  try {
    const targetLines = parseTargetLines()
    const res = await ciImpactApi.generateMutants({
      source_code: sourceCode.value,
      file_path: filePath.value || 'main.py',
      target_lines: targetLines,
      max_mutants: maxMutants.value,
    })

    report.value = res.report
    if (res.report.mutants && res.report.mutants.length > 0) {
      selectedMutant.value = res.report.mutants[0]
      message.success(res.message || `成功注入并生成 ${res.report.total_mutants_generated} 个一阶语法变异体`)
      emit('mutants-generated', res.report)
    } else {
      selectedMutant.value = null
      message.warning('未能从指定代码行识别出可变异的语法节点')
    }
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '变异体注入生成失败')
  } finally {
    generating.value = false
  }
}

const copyCode = (code: string) => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(code)
    message.success('已复制完整变异代码至剪贴板')
  } else {
    message.info('当前浏览器环境不支持自动剪贴板，请手动复制')
  }
}

const handleClose = () => {
  emit('update:open', false)
}

watch(
  () => props.open,
  (newVal) => {
    if (newVal && !report.value) {
      handleGenerate()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.mutation-modal-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-banner {
  background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%);
  border: 1px solid #bae6fd;
  border-radius: 8px;
  padding: 12px 16px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #0369a1;
  margin-bottom: 4px;
}

.banner-icon {
  font-size: 18px;
  color: #0284c7;
}

.banner-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin: 0;
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 14px;
}

.config-card {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  background: #f8fafc;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.card-body {
  padding: 12px;
  flex: 1;
}

.code-editor {
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  background: #1e293b;
  color: #f8fafc;
  border-radius: 6px;
}

.source-meta-row {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.operator-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 250px;
  overflow-y: auto;
}

.operator-item {
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fff;
}

.operator-item:hover {
  border-color: #38bdf8;
  background: #f0f9ff;
}

.operator-item.active {
  border-color: #0284c7;
  background: #f0fdf4;
}

.op-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.op-tag {
  font-weight: 600;
  margin-right: 0;
}

.op-name {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
}

.op-count-badge {
  margin-left: auto;
  font-size: 11px;
  font-weight: 600;
  color: #059669;
  background: #d1fae5;
  padding: 1px 6px;
  border-radius: 10px;
}

.op-desc {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 2px;
}

.op-example {
  font-size: 11px;
  color: #475569;
}

.op-example code {
  color: #d97706;
  background: #fef3c7;
  padding: 1px 4px;
  border-radius: 3px;
}

/* KPI 卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.kpi-card {
  padding: 10px 14px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
}

.kpi-label {
  font-size: 12px;
  color: #64748b;
}

.kpi-val {
  font-size: 20px;
  font-weight: 700;
  margin: 2px 0;
}

.kpi-sub {
  font-size: 11px;
  color: #94a3b8;
}

.text-primary { color: #0284c7; }
.text-info { color: #2563eb; }
.text-warning { color: #d97706; }
.text-success { color: #059669; }

/* 差异比对分栏 */
.diff-split-container {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 12px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  min-height: 320px;
}

.mutant-list-pane {
  border-right: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  flex-direction: column;
}

.pane-header {
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pane-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.mutant-items-scroll {
  flex: 1;
  max-height: 380px;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mutant-row-card {
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  background: #fff;
  transition: all 0.2s ease;
}

.mutant-row-card:hover {
  border-color: #38bdf8;
  background: #f0f9ff;
}

.mutant-row-card.selected {
  border-color: #0284c7;
  background: #e0f2fe;
}

.mutant-row-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.mutant-idx {
  font-weight: 700;
  font-size: 12px;
  color: #64748b;
}

.mutant-line {
  font-size: 11px;
  font-weight: 600;
  color: #0f172a;
  margin-left: auto;
}

.mutant-token-swap {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 12px;
}

.old-token {
  background: #fee2e2;
  color: #dc2626;
  padding: 1px 4px;
  border-radius: 3px;
}

.swap-arrow {
  color: #94a3b8;
}

.new-token {
  background: #dcfce7;
  color: #16a34a;
  padding: 1px 4px;
  border-radius: 3px;
}

.mutant-row-desc {
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 右侧比对区 */
.diff-viewer-pane {
  display: flex;
  flex-direction: column;
  padding: 12px;
  background: #fafafa;
}

.diff-title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.line-diff-box {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 12px 0;
}

.diff-col {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}

.old-col {
  border-left: 3px solid #ef4444;
}

.new-col {
  border-left: 3px solid #10b981;
}

.col-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 8px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
}

.old-col .col-tag { color: #b91c1c; }
.new-col .col-tag { color: #047857; }

.code-pre {
  margin: 0;
  padding: 10px;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-all;
}

.old-col .code-pre {
  background: #fff5f5;
  color: #991b1b;
}

.new-col .code-pre {
  background: #f0fdf4;
  color: #065f46;
}

.full-code-box {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
  background: #1e293b;
}

.full-code-header {
  padding: 6px 10px;
  background: #0f172a;
  color: #94a3b8;
  font-size: 11px;
  border-bottom: 1px solid #334155;
}

.full-code-header code {
  color: #38bdf8;
}

.full-code-content {
  margin: 0;
  padding: 10px;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.5;
  color: #f8fafc;
  max-height: 200px;
  overflow-y: auto;
}

.empty-diff-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
}
</style>
