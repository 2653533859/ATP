<template>
  <div class="contract-drift-card">
    <!-- 头部规则与机制 Banner -->
    <div class="rule-banner">
      <div class="banner-header">
        <SafetyCertificateOutlined class="banner-icon" />
        <div class="banner-text">
          <div class="banner-title">接口契约非对称破坏性变更 Breaking 评级仲裁引擎</div>
          <div class="banner-desc">
            严格践行伯斯塔尔健壮性法则（Postel's Law）：请求体新增必填项或类型漂移判定为 <strong>BREAKING</strong>（客户端拒绝）；响应体删除既有字段判定为 <strong>BREAKING</strong>（下游解析空指针）；响应体扩展新属性判定为 <strong>COMPATIBLE</strong>。
          </div>
        </div>
      </div>

      <!-- 快速预设场景 -->
      <div class="preset-bar">
        <span class="preset-label">评级仲裁演示预设：</span>
        <a-space :size="8" wrap>
          <a-button
            size="small"
            :type="currentPresetKey === 'breaking' ? 'primary' : 'default'"
            danger
            @click="applyPreset('breaking')"
          >
            预设 1: 严重破坏性变更 (新增必填+删除响应)
          </a-button>
          <a-button
            size="small"
            :type="currentPresetKey === 'warning' ? 'primary' : 'default'"
            @click="applyPreset('warning')"
          >
            预设 2: 潜在风险告警 (响应枚举缩减)
          </a-button>
          <a-button
            size="small"
            :type="currentPresetKey === 'compatible' ? 'primary' : 'default'"
            @click="applyPreset('compatible')"
          >
            预设 3: 安全向下兼容 (仅响应新增字段)
          </a-button>
        </a-space>
      </div>

      <!-- 控制操作栏 -->
      <div class="action-bar">
        <a-space :size="12" style="width: 100%" align="center">
          <span class="input-label">接口端点:</span>
          <a-input
            v-model:value="endpointInput"
            placeholder="例如: POST /api/v1/orders/checkout"
            style="width: 320px"
            size="small"
          />
          <a-button
            type="primary"
            size="small"
            :loading="evaluating"
            @click="runEvaluation"
          >
            <ThunderboltOutlined /> 执行契约破坏性评级仲裁
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 仲裁结果评定大横幅 (Verdict Banner) -->
    <div v-if="report" class="verdict-banner" :class="`verdict-${report.overall_breaking_level.toLowerCase()}`">
      <div class="verdict-top">
        <div class="verdict-status-box">
          <span class="verdict-tag" :class="`tag-${report.overall_breaking_level.toLowerCase()}`">
            {{ report.overall_breaking_level }}
          </span>
          <span class="verdict-summary-text">{{ report.verdict_summary }}</span>
        </div>
        <div class="score-box">
          <div class="score-title">契约兼容性健康得分</div>
          <div class="score-value" :class="`score-${report.overall_breaking_level.toLowerCase()}`">
            {{ report.compatibility_score_pct }}%
          </div>
        </div>
      </div>

      <!-- 3 项指标统计微卡片 -->
      <div class="metric-cards">
        <div class="metric-card metric-breaking">
          <div class="metric-num">{{ report.breaking_changes_count }}</div>
          <div class="metric-title">阻断性破坏变更 (Breaking)</div>
        </div>
        <div class="metric-card metric-warning">
          <div class="metric-num">{{ report.warning_changes_count }}</div>
          <div class="metric-title">潜在风险告警 (Warning)</div>
        </div>
        <div class="metric-card metric-compatible">
          <div class="metric-num">{{ report.compatible_changes_count }}</div>
          <div class="metric-title">安全兼容变动 (Compatible)</div>
        </div>
      </div>
    </div>

    <!-- 差异明细表格 -->
    <div v-if="report" class="drift-section">
      <div class="section-title">
        <span>契约字段级漂移与非对称仲裁清单</span>
        <a-tag color="blue">共 {{ report.drift_items.length }} 处漂移比对项</a-tag>
      </div>

      <a-table
        :data-source="report.drift_items"
        :columns="tableColumns"
        row-key="field_path"
        size="small"
        :pagination="false"
        bordered
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'field_path'">
            <code class="code-path">{{ record.field_path }}</code>
          </template>

          <template v-if="column.key === 'target'">
            <a-tag :color="record.target.includes('REQUEST') ? 'cyan' : 'purple'">
              {{ record.target }}
            </a-tag>
          </template>

          <template v-if="column.key === 'change_type'">
            <a-tag>{{ record.change_type }}</a-tag>
          </template>

          <template v-if="column.key === 'breaking_level'">
            <a-tag
              :color="
                record.breaking_level === 'BREAKING'
                  ? 'red'
                  : record.breaking_level === 'WARNING'
                    ? 'orange'
                    : 'green'
              "
            >
              {{ record.breaking_level }}
            </a-tag>
          </template>

          <template v-if="column.key === 'values'">
            <div class="values-diff">
              <div class="val-line"><strong>基准:</strong> <code>{{ formatVal(record.design_value) }}</code></div>
              <div class="val-line"><strong>现网:</strong> <code>{{ formatVal(record.live_value) }}</code></div>
            </div>
          </template>

          <template v-if="column.key === 'impact'">
            <div class="impact-text">
              <div>{{ record.description }}</div>
              <small class="impact-sub">{{ record.impact_summary }}</small>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 阻断修复行动建议 (Action Recommendations) -->
    <div v-if="report && report.overall_breaking_level === 'BREAKING'" class="action-recommendation">
      <div class="rec-title">🚨 生产发布阻断与修复指引 (Pipeline Action Items)</div>
      <ul class="rec-list">
        <li><strong>请求体新增必填修复:</strong> 若向客户端强制要求新参数，必须先配置默认值或设为可选，否则旧版 App 或集成方将遭遇 HTTP 400 批量失败。</li>
        <li><strong>响应体删除字段修复:</strong> 必须保留已发布字段或提供向前兼容别名，严禁直接删除已被下游服务消费的核心字段。</li>
        <li><strong>主版本号升级:</strong> 若该破坏性变更为核心业务重构所必须，请通过 <code>/api/v2/...</code> 路径开展灰度平滑演进。</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  contractBreakingApi,
  type ContractDriftEvaluationReport,
} from '@/api/trafficGateway'

const endpointInput = ref('POST /api/v1/orders/checkout')
const evaluating = ref(false)
const report = ref<ContractDriftEvaluationReport | null>(null)
const currentPresetKey = ref<'breaking' | 'warning' | 'compatible'>('breaking')

const tableColumns = [
  { title: '字段路径', key: 'field_path', width: 220 },
  { title: '作用域', key: 'target', width: 140 },
  { title: '变动类型', key: 'change_type', width: 160 },
  { title: '破坏评级', key: 'breaking_level', width: 120 },
  { title: '期望基准 vs 现网实测', key: 'values', width: 220 },
  { title: '判定理由与影响分析', key: 'impact' },
]

function formatVal(v: any): string {
  if (v === undefined) return '<undefined>'
  if (v === null) return 'null'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

// 预设定义
const PRESETS = {
  breaking: {
    endpoint: 'POST /api/v1/orders/checkout',
    design: {
      type: 'object',
      properties: {
        order_id: { type: 'integer' },
        amount: { type: 'number' },
      },
      required: ['order_id'],
      response_schemas: {
        '200': {
          type: 'object',
          properties: {
            code: { type: 'integer' },
            status: { type: 'string' },
            pay_token: { type: 'string' },
          },
          required: ['code', 'pay_token'],
        },
      },
    },
    live: {
      type: 'object',
      properties: {
        order_id: { type: 'integer' },
        amount: { type: 'number' },
        coupon_id: { type: 'string' }, // 请求新增必填 -> BREAKING
      },
      required: ['order_id', 'coupon_id'],
      response_schemas: {
        '200': {
          type: 'object',
          properties: {
            code: { type: 'integer' },
            status: { type: 'string' },
            // pay_token 被删除 -> BREAKING
          },
          required: ['code'],
        },
      },
    },
  },
  warning: {
    endpoint: 'POST /api/v1/orders/checkout',
    design: {
      type: 'object',
      properties: {
        channel: { type: 'string', enum: ['APP', 'H5', 'WEB', 'MINI_APP'] },
      },
    },
    live: {
      type: 'object',
      properties: {
        channel: { type: 'string', enum: ['APP', 'H5'] }, // 枚举收缩 -> WARNING
      },
    },
  },
  compatible: {
    endpoint: 'GET /api/v1/users/profile',
    design: {
      type: 'object',
      properties: {
        user_id: { type: 'string' },
      },
      response_schemas: {
        '200': {
          type: 'object',
          properties: {
            user_id: { type: 'string' },
            nickname: { type: 'string' },
          },
        },
      },
    },
    live: {
      type: 'object',
      properties: {
        user_id: { type: 'string' },
      },
      response_schemas: {
        '200': {
          type: 'object',
          properties: {
            user_id: { type: 'string' },
            nickname: { type: 'string' },
            avatar_url: { type: 'string' }, // 响应新增字段 -> COMPATIBLE
          },
        },
      },
    },
  },
}

function applyPreset(key: 'breaking' | 'warning' | 'compatible') {
  currentPresetKey.value = key
  const p = PRESETS[key]
  endpointInput.value = p.endpoint
  runEvaluation()
}

async function runEvaluation() {
  evaluating.value = true
  try {
    const p = PRESETS[currentPresetKey.value]
    const res = await contractBreakingApi.compare({
      endpoint: endpointInput.value,
      design_contract: p.design,
      live_contract: p.live,
    })
    report.value = res.report
    message.success(res.message || '契约兼容性评估完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '评级计算失败')
  } finally {
    evaluating.value = false
  }
}

onMounted(() => {
  runEvaluation()
})
</script>

<style scoped>
.contract-drift-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rule-banner {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.banner-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.banner-icon {
  font-size: 24px;
  color: #0284c7;
  margin-top: 2px;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.banner-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
  margin-top: 4px;
}

.preset-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--c-border-subtle, #e2e8f0);
}

.preset-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  white-space: nowrap;
}

.action-bar {
  padding-top: 8px;
  border-top: 1px dashed var(--c-border-subtle, #e2e8f0);
}

.input-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

/* 裁决大横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 16px;
  border: 1px solid transparent;
}

.verdict-breaking {
  background: #fef2f2;
  border-color: #fecaca;
}

.verdict-warning {
  background: #fffbeb;
  border-color: #fde68a;
}

.verdict-compatible {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.verdict-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.verdict-status-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.verdict-tag {
  font-size: 14px;
  font-weight: 800;
  padding: 4px 12px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.tag-breaking {
  background: #ef4444;
  color: #fff;
}

.tag-warning {
  background: #f59e0b;
  color: #fff;
}

.tag-compatible {
  background: #10b981;
  color: #fff;
}

.verdict-summary-text {
  font-size: 13px;
  color: #1e293b;
  font-weight: 500;
}

.score-box {
  text-align: right;
}

.score-title {
  font-size: 11px;
  color: #64748b;
}

.score-value {
  font-size: 24px;
  font-weight: 800;
  line-height: 1.2;
}

.score-breaking {
  color: #dc2626;
}

.score-warning {
  color: #d97706;
}

.score-compatible {
  color: #16a34a;
}

.metric-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.metric-card {
  background: #ffffff;
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 6px;
  padding: 12px;
  text-align: center;
}

.metric-num {
  font-size: 20px;
  font-weight: 800;
}

.metric-title {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.metric-breaking .metric-num {
  color: #dc2626;
}

.metric-warning .metric-num {
  color: #d97706;
}

.metric-compatible .metric-num {
  color: #16a34a;
}

.drift-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.code-path {
  background: #f1f5f9;
  color: #0369a1;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: Consolas, monospace;
  font-size: 11px;
}

.values-diff {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}

.values-diff code {
  background: #f8fafc;
  padding: 1px 4px;
  border-radius: 3px;
  font-family: Consolas, monospace;
}

.impact-text {
  font-size: 12px;
  line-height: 1.4;
}

.impact-sub {
  color: #64748b;
  display: block;
  margin-top: 2px;
}

.action-recommendation {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 12px 16px;
}

.rec-title {
  font-size: 13px;
  font-weight: 700;
  color: #991b1b;
  margin-bottom: 6px;
}

.rec-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #7f1d1d;
  line-height: 1.6;
}
</style>
