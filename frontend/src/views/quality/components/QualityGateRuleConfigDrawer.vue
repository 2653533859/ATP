<template>
  <a-drawer
    :open="open"
    :width="960"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <div class="drawer-title-box">
        <span>CI/CD 智能流水线质量门禁策略配置与卡点决策中心</span>
        <a-tag v-if="evaluationResult?.passed" color="green">准予放行 (exit_code: 0)</a-tag>
        <a-tag v-else-if="evaluationResult" color="red">强制阻断 (exit_code: 1)</a-tag>
      </div>
    </template>

    <div class="quality-gate-drawer-body">
      <!-- 策略选择与预设控制栏 -->
      <a-card size="small" class="profile-card">
        <div class="profile-header">
          <div class="header-desc">
            <h4 class="title">质量门禁 Profile 策略配置</h4>
            <p class="subtitle">
              针对不同发版环境与 CI/CD 阶段，定义精准的量化拦截基线。若触碰 Blocker 级别规则，引擎自动输出非零退出码（exit_code: 1），物理切断自动化部署流水线。
            </p>
          </div>

          <div class="header-actions">
            <a-space size="small">
              <a-button size="small" @click="loadProdReleasePreset">
                载入生产发版阻断预设
              </a-button>
              <a-button size="small" @click="loadPrCheckPreset">
                载入 PR 冒烟准入预设
              </a-button>
              <a-button type="primary" size="small" :loading="saving" @click="handleSaveProfile">
                保存门禁策略
              </a-button>
            </a-space>
          </div>
        </div>

        <!-- 策略元数据表单 -->
        <a-form layout="inline" class="meta-form">
          <a-form-item label="策略 ID" required>
            <a-input v-model:value="profileId" size="small" style="width: 170px" />
          </a-form-item>

          <a-form-item label="策略名称" required>
            <a-input v-model:value="profileName" size="small" style="width: 220px" />
          </a-form-item>

          <a-form-item label="违约时阻塞 CI">
            <a-switch v-model:checked="blockOnFailure" size="small" />
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 规则矩阵配置表格 -->
      <a-card size="small" title="卡点规则表达式配置清单 (Rule Matrix)" class="rules-card">
        <template #extra>
          <a-button size="small" type="primary" ghost @click="handleAddRule">
            + 添加卡点规则
          </a-button>
        </template>

        <a-table
          :data-source="rules"
          :columns="ruleColumns"
          row-key="metric_key"
          size="small"
          :pagination="false"
        >
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'metric_key'">
              <a-input v-model:value="record.metric_key" size="small" placeholder="如 pass_rate_pct" />
            </template>

            <template v-if="column.key === 'operator'">
              <a-select v-model:value="record.operator" size="small" style="width: 80px">
                <a-select-option value="gte">≥</a-select-option>
                <a-select-option value="gt">&gt;</a-select-option>
                <a-select-option value="lte">≤</a-select-option>
                <a-select-option value="lt">&lt;</a-select-option>
                <a-select-option value="eq">=</a-select-option>
              </a-select>
            </template>

            <template v-if="column.key === 'threshold'">
              <a-input-number v-model:value="record.threshold" size="small" style="width: 90px" />
            </template>

            <template v-if="column.key === 'severity'">
              <a-select v-model:value="record.severity" size="small" style="width: 100px">
                <a-select-option value="blocker">Blocker 阻断</a-select-option>
                <a-select-option value="warning">Warning 警告</a-select-option>
              </a-select>
            </template>

            <template v-if="column.key === 'description'">
              <a-input v-model:value="record.description" size="small" placeholder="规则业务说明" />
            </template>

            <template v-if="column.key === 'action'">
              <a-button
                danger
                type="link"
                size="small"
                :disabled="rules.length <= 1"
                @click="handleRemoveRule(index)"
              >
                删除
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 在线卡点决策实测 -->
      <a-card size="small" title="CI/CD 在线实时卡点判定测试 (Gate Evaluation)" class="eval-card">
        <div class="eval-box">
          <div class="eval-input-block">
            <span class="eval-label">待判定流水线输入指标 (JSON):</span>
            <a-textarea
              v-model:value="metricsJsonText"
              :rows="4"
              class="metrics-textarea"
              placeholder="请输入当前流水线收集到的指标 JSON..."
            />
          </div>

          <div class="eval-action-bar">
            <a-space size="small">
              <a-button size="small" @click="loadSampleMetrics">
                载入达标样本
              </a-button>
              <a-button size="small" @click="loadBreachMetrics">
                载入违约阻断样本
              </a-button>
              <a-button
                type="primary"
                :danger="Boolean(evaluationResult && !evaluationResult.passed)"
                size="small"
                :loading="evaluating"
                @click="handleEvaluateGate"
              >
                执行卡点在线决策
              </a-button>
            </a-space>
          </div>
        </div>

        <!-- 判定决策横幅 -->
        <a-alert
          v-if="evaluationResult?.passed"
          type="success"
          show-icon
          class="eval-alert"
          message="[准予放行 PASSED] 所有质量门禁规则全部合规达标！"
          :description="`流水线已准予继续流转，最终退出码 exit_code: 0。未检测到任何阻塞性阻断项。`"
        />

        <a-alert
          v-else-if="evaluationResult"
          type="error"
          show-icon
          class="eval-alert"
          message="[卡点阻断 BLOCKED] 检测到阻塞性规则未达标，流水线已被强制终止！"
          :description="`阻断原因: ${evaluationResult.failed_blockers.join('；')}。最终退出码 exit_code: 1，已禁止部署流转。`"
        />

        <!-- 规则明细逐项判定结果流水 -->
        <div v-if="evaluationResult" class="rule-results-box">
          <h5 class="sub-title">逐项规则判定决策流水明细：</h5>
          <a-table
            :data-source="evaluationResult.rule_results"
            :columns="evalResultColumns"
            row-key="metric_key"
            size="small"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'metric_key'">
                <code>{{ record.metric_key }}</code>
              </template>

              <template v-if="column.key === 'operator'">
                <span>{{ record.operator }}</span>
              </template>

              <template v-if="column.key === 'threshold'">
                <strong>{{ record.threshold }}</strong>
              </template>

              <template v-if="column.key === 'actual_value'">
                <strong :class="record.passed ? 'text-green' : 'text-red'">
                  {{ record.actual_value }}
                </strong>
              </template>

              <template v-if="column.key === 'passed'">
                <a-tag :color="record.passed ? 'green' : 'red'">
                  {{ record.passed ? 'PASS 达标' : 'FAIL 违约' }}
                </a-tag>
              </template>

              <template v-if="column.key === 'severity'">
                <a-tag :color="record.severity === 'blocker' ? 'red' : 'orange'">
                  {{ record.severity.toUpperCase() }}
                </a-tag>
              </template>
            </template>
          </a-table>
        </div>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  qualityGovernanceApi,
  type QualityGateRuleItem,
  type GateEvaluationResponse,
} from '@/api/qualityGovernance'

const props = withDefaults(
  defineProps<{
    open: boolean
    defaultProfileId?: string
  }>(),
  {
    open: false,
    defaultProfileId: 'gate_prod_release',
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const saving = ref(false)
const evaluating = ref(false)

const profileId = ref('gate_prod_release')
const profileName = ref('生产发布阻断性质量门禁规则')
const blockOnFailure = ref(true)

const defaultProdRules: QualityGateRuleItem[] = [
  { metric_key: 'pass_rate_pct', operator: 'gte', threshold: 99.0, severity: 'blocker', description: '全量用例通过率 ≥ 99%' },
  { metric_key: 'p0_pass_rate_pct', operator: 'gte', threshold: 100.0, severity: 'blocker', description: 'P0 核心用例 100% 通过' },
  { metric_key: 'open_blocker_defects', operator: 'lte', threshold: 0, severity: 'blocker', description: '未解决阻塞性缺陷为 0' },
  { metric_key: 'composite_health_score', operator: 'gte', threshold: 80.0, severity: 'warning', description: '综合质量评分 ≥ 80' },
]

const rules = ref<QualityGateRuleItem[]>([...defaultProdRules])

const samplePassingMetrics = {
  pass_rate_pct: 99.5,
  p0_pass_rate_pct: 100.0,
  open_blocker_defects: 0,
  composite_health_score: 91.5,
}

const metricsJsonText = ref(JSON.stringify(samplePassingMetrics, null, 2))
const evaluationResult = ref<GateEvaluationResponse | null>(null)

const ruleColumns = [
  { title: '指标字段 (Metric Key)', key: 'metric_key', width: 170 },
  { title: '算子', key: 'operator', width: 90 },
  { title: '安全阈值', key: 'threshold', width: 100 },
  { title: '卡点等级', key: 'severity', width: 120 },
  { title: '规则说明', key: 'description' },
  { title: '操作', key: 'action', width: 70 },
]

const evalResultColumns = [
  { title: '指标字段', key: 'metric_key', width: 160 },
  { title: '算子', key: 'operator', width: 70 },
  { title: '安全阈值', key: 'threshold', width: 90 },
  { title: '检测实际值', key: 'actual_value', width: 100 },
  { title: '判定结论', key: 'passed', width: 110 },
  { title: '严重等级', key: 'severity', width: 110 },
  { title: '详细判定原因', dataIndex: 'reason', key: 'reason' },
]

function handleClose() {
  emit('update:open', false)
}

function handleAddRule() {
  rules.value.push({
    metric_key: 'flaky_ratio_pct',
    operator: 'lte',
    threshold: 5.0,
    severity: 'warning',
    description: 'Flaky 波动率 ≤ 5%',
  })
}

function handleRemoveRule(idx: number) {
  if (rules.value.length > 1) {
    rules.value.splice(idx, 1)
  }
}

function loadProdReleasePreset() {
  profileId.value = 'gate_prod_release'
  profileName.value = '生产发布阻断性质量门禁规则'
  blockOnFailure.value = true
  rules.value = [...defaultProdRules]
  message.info('已载入生产发布阻断门禁预设！')
}

function loadPrCheckPreset() {
  profileId.value = 'gate_pr_check'
  profileName.value = 'PR 代码合入快速冒烟门禁规则'
  blockOnFailure.value = true
  rules.value = [
    { metric_key: 'p0_pass_rate_pct', operator: 'gte', threshold: 100.0, severity: 'blocker', description: 'PR 冒烟 P0 用例 100% 通过' },
    { metric_key: 'open_blocker_defects', operator: 'lte', threshold: 0, severity: 'blocker', description: '无新增未修复阻断 Bug' },
  ]
  message.info('已载入 PR 冒烟门禁预设！')
}

function loadSampleMetrics() {
  metricsJsonText.value = JSON.stringify(samplePassingMetrics, null, 2)
  message.info('已载入达标测试样本！')
}

function loadBreachMetrics() {
  const breachMetrics = {
    pass_rate_pct: 95.0, // 违约
    p0_pass_rate_pct: 90.0, // 违约
    open_blocker_defects: 2, // 违约
    composite_health_score: 72.0,
  }
  metricsJsonText.value = JSON.stringify(breachMetrics, null, 2)
  message.warning('已载入阻塞性违约样本！')
}

async function handleSaveProfile() {
  saving.value = true
  try {
    await qualityGovernanceApi.registerGateProfile({
      profile_id: profileId.value,
      name: profileName.value,
      description: `CI/CD 智能门禁: ${profileName.value}`,
      rules: rules.value,
      block_on_failure: blockOnFailure.value,
    })
    message.success('质量门禁策略注册保存成功！')
  } catch (err: any) {
    message.error(err.message || '保存门禁策略失败')
  } finally {
    saving.value = false
  }
}

async function handleEvaluateGate() {
  evaluating.value = true
  try {
    let parsedMetrics: any
    try {
      parsedMetrics = JSON.parse(metricsJsonText.value)
    } catch {
      throw new Error('指标 JSON 格式不合法')
    }

    const res = await qualityGovernanceApi.evaluateQualityGate(profileId.value, parsedMetrics)
    evaluationResult.value = res
    if (res.passed) {
      message.success('门禁判定完成：全部达标，准予放行！')
    } else {
      message.error(`门禁判定完成：检测到 ${res.failed_blockers.length} 项阻塞违规，流水线阻断！`)
    }
  } catch (err: any) {
    message.error(err.message || '门禁卡点决策执行失败')
  } finally {
    evaluating.value = false
  }
}

onMounted(() => {
  if (props.defaultProfileId) {
    profileId.value = props.defaultProfileId
  }
})
</script>

<style scoped>
.quality-gate-drawer-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.profile-card,
.rules-card,
.eval-card {
  border-radius: 8px;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 10px;
}

.title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.meta-form {
  margin-top: 6px;
}

.eval-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.eval-input-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.eval-label {
  font-size: 11px;
  color: #64748b;
}

.metrics-textarea {
  font-family: monospace;
  font-size: 11px;
  background: var(--c-bg-subtle, #f8fafc);
}

.eval-action-bar {
  display: flex;
  justify-content: flex-end;
}

.eval-alert {
  border-radius: 6px;
  margin-top: 10px;
}

.rule-results-box {
  margin-top: 12px;
}

.sub-title {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px;
}

.text-green {
  color: #16a34a;
}

.text-red {
  color: #dc2626;
}
</style>
