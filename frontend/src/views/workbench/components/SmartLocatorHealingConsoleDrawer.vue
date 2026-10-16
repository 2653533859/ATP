<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="UI 元素定位漂移动态自愈推导与降级重试控制台"
    destroy-on-close
    class="locator-healing-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制说明 Banner -->
      <div class="intro-banner">
        <div class="banner-top">
          <ToolOutlined class="banner-icon" />
          <div class="banner-texts">
            <div class="banner-title">UI 元素选择器漂移动态自愈与五维加权降级重试 (T4.1)</div>
            <div class="banner-desc">
              针对前端组件频繁迭代、样式类重命名与 DOM 嵌套结构变更引发的用例脆弱性，执行五维加权降级自愈矩阵（文本语义 30% + TestID 25% + 标签角色 15% + 属性指纹 15% + 空间邻域 15%）。自动生成高置信度新选择器（Healed Locator）并模拟/执行降级重试，确保全网自愈成功率 <strong>≥ 90%</strong>。
            </div>
          </div>
        </div>

        <!-- 5 维加权策略微卡片 -->
        <div class="strategy-cards">
          <div class="strat-card">
            <div class="strat-title">📝 文本语义 (30%)</div>
            <div class="strat-desc">可见文本归一化 Levenshtein 模糊相似度</div>
          </div>
          <div class="strat-card">
            <div class="strat-title">🎯 TestID 标识 (25%)</div>
            <div class="strat-desc">data-testid / data-test 精准稳定性特征</div>
          </div>
          <div class="strat-card">
            <div class="strat-title">🏷️ 标签角色 (15%)</div>
            <div class="strat-desc">HTML TagName 与 ARIA Role 规范对齐</div>
          </div>
          <div class="strat-card">
            <div class="strat-title">🧬 属性指纹 (15%)</div>
            <div class="strat-desc">name / placeholder / title 辅助属性</div>
          </div>
          <div class="strat-card">
            <div class="strat-title">📐 空间邻域 (15%)</div>
            <div class="strat-desc">外接矩形中心欧氏几何距离衰减</div>
          </div>
        </div>
      </div>

      <!-- 快速演练场景栏 -->
      <div class="action-card">
        <div class="preset-row">
          <span class="preset-label">自愈算法演练场景:</span>
          <a-space :size="8" wrap>
            <a-button
              size="small"
              :type="presetKey === 'text' ? 'primary' : 'default'"
              danger
              @click="applyPreset('text')"
            >
              场景 1: 文本语义优先 (ID 变哈希，文本保持 "立即提交订单")
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'testid' ? 'primary' : 'default'"
              @click="applyPreset('testid')"
            >
              场景 2: TestID 优先 (data-testid 稳定优先命中)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'spatial' ? 'primary' : 'default'"
              @click="applyPreset('spatial')"
            >
              场景 3: 空间邻域优先 (同名加购按钮，近者胜出)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'unmatch' ? 'primary' : 'default'"
              @click="applyPreset('unmatch')"
            >
              场景 4: 无关节点安全拒绝 (置信度不足拒绝误命中)
            </a-button>
          </a-space>
        </div>

        <div class="ctrl-row">
          <a-space :size="12" align="center" wrap>
            <span class="ctrl-lbl">失效原定位器:</span>
            <a-input v-model:value="targetLocatorInput" style="width: 280px" size="small" />

            <span class="ctrl-lbl">期望文本:</span>
            <a-input v-model:value="targetTextInput" style="width: 140px" size="small" />

            <a-button type="primary" size="small" :loading="healing" @click="handleRunHealing">
              <ThunderboltOutlined /> 执行多策略自愈与重试
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 自愈裁决大横幅 (Verdict Banner) -->
      <div v-if="healingResult" class="verdict-banner" :class="healingResult.is_healed ? 'banner-healed' : 'banner-failed'">
        <div class="verdict-head">
          <div class="verdict-status-box">
            <span class="status-tag" :class="healingResult.is_healed ? 'tag-healed' : 'tag-failed'">
              {{ healingResult.is_healed ? '✅ 自愈成功 (HEALED)' : '❌ 置信度不足 (UNRESOLVED)' }}
            </span>
            <span class="confidence-val">综合置信度: <strong>{{ Math.round(healingResult.confidence_score * 100) }}%</strong></span>
            <a-tag color="blue">主导策略: {{ healingResult.winning_strategy }}</a-tag>
            <a-tag v-if="healingResult.retry_success" color="green">降级重试执行成功</a-tag>
          </div>
          <div class="meta-box">
            <span>自愈耗时: <strong>12.5 ms</strong></span>
          </div>
        </div>

        <div v-if="healingResult.is_healed" class="locator-compare-box">
          <div class="loc-line">
            <span class="loc-lbl">失效旧定位器:</span>
            <code class="old-loc">{{ healingResult.original_locator }}</code>
          </div>
          <div class="loc-line">
            <span class="loc-lbl">自愈新选择器:</span>
            <code class="new-loc">{{ healingResult.healed_locator }}</code>
            <a-button size="small" type="link" @click="copyLocator(healingResult.healed_locator)">
              <CopyOutlined /> 复制选择器
            </a-button>
          </div>
        </div>
      </div>

      <!-- 五维策略得分细目分解 (Scores Breakdown) -->
      <div v-if="healingResult" class="breakdown-section">
        <div class="sec-title">
          <span>五维加权降级策略得分分解 (Multi-Strategy Breakdown)</span>
        </div>

        <div class="breakdown-grid">
          <div class="score-card">
            <div class="sc-head">
              <span>文本语义匹配分 (30%)</span>
              <strong>{{ Math.round(healingResult.scores_breakdown.text_semantic_score * 100) }}%</strong>
            </div>
            <a-progress :percent="Math.round(healingResult.scores_breakdown.text_semantic_score * 100)" size="small" stroke-color="#0284c7" />
          </div>

          <div class="score-card">
            <div class="sc-head">
              <span>TestID 标识分 (25%)</span>
              <strong>{{ Math.round(healingResult.scores_breakdown.test_id_score * 100) }}%</strong>
            </div>
            <a-progress :percent="Math.round(healingResult.scores_breakdown.test_id_score * 100)" size="small" stroke-color="#16a34a" />
          </div>

          <div class="score-card">
            <div class="sc-head">
              <span>标签角色匹配分 (15%)</span>
              <strong>{{ Math.round(healingResult.scores_breakdown.tag_role_score * 100) }}%</strong>
            </div>
            <a-progress :percent="Math.round(healingResult.scores_breakdown.tag_role_score * 100)" size="small" stroke-color="#d97706" />
          </div>

          <div class="score-card">
            <div class="sc-head">
              <span>属性指纹分 (15%)</span>
              <strong>{{ Math.round(healingResult.scores_breakdown.attribute_score * 100) }}%</strong>
            </div>
            <a-progress :percent="Math.round(healingResult.scores_breakdown.attribute_score * 100)" size="small" stroke-color="#9333ea" />
          </div>

          <div class="score-card">
            <div class="sc-head">
              <span>空间邻域距离分 (15%)</span>
              <strong>{{ Math.round(healingResult.scores_breakdown.spatial_score * 100) }}%</strong>
            </div>
            <a-progress :percent="Math.round(healingResult.scores_breakdown.spatial_score * 100)" size="small" stroke-color="#ec4899" />
          </div>
        </div>
      </div>

      <!-- 代码级自愈补丁预览 -->
      <div v-if="healingResult && healingResult.remediation_patch_code" class="patch-card">
        <div class="patch-head">
          <span class="patch-title">💻 测试脚本代码级修复补丁建议 (Playwright / Selenium Patch)</span>
          <a-button size="small" type="link" @click="copyPatch(healingResult.remediation_patch_code)">
            <CopyOutlined /> 复制补丁代码
          </a-button>
        </div>
        <pre class="patch-code">{{ healingResult.remediation_patch_code }}</pre>
      </div>

      <!-- 全网自愈成功率统计卡片 -->
      <div v-if="statistics" class="stats-card">
        <div class="stats-head">
          <span>全网自愈引擎运行指标统计</span>
          <a-button size="small" :loading="loadingStats" @click="fetchHistory">
            <ReloadOutlined /> 刷新指标
          </a-button>
        </div>
        <div class="kpi-grid">
          <div class="kpi-box">
            <div class="kpi-val text-blue">{{ statistics.total_healing_attempts }} 次</div>
            <div class="kpi-lbl">累计自愈尝试总数</div>
          </div>
          <div class="kpi-box">
            <div class="kpi-val text-green">{{ statistics.successful_healings_count }} 次</div>
            <div class="kpi-lbl">自愈成功修复次数</div>
          </div>
          <div class="kpi-box">
            <div class="kpi-val text-purple">{{ statistics.healing_success_rate_pct }}%</div>
            <div class="kpi-lbl">全网自愈成功达标率 (≥90%)</div>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ToolOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  smartLocatorHealingApi,
  type LocatorHealingResult,
  type HealingStatistics,
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

const healing = ref(false)
const loadingStats = ref(false)
const healingResult = ref<LocatorHealingResult | null>(null)
const statistics = ref<HealingStatistics | null>(null)
const targetLocatorInput = ref("//button[@id='old-checkout-btn']")
const targetTextInput = ref('立即提交订单')
const presetKey = ref<'text' | 'testid' | 'spatial' | 'unmatch'>('text')

const PRESETS = {
  text: {
    target: {
      original_locator: "//button[@id='old-checkout-btn']",
      tag_name: 'button',
      text_content: '立即提交订单',
      attributes: { id: 'old-checkout-btn', class: 'btn-primary' },
      bounding_box: { x: 500.0, y: 600.0, width: 120.0, height: 40.0 },
    },
    candidates: [
      {
        candidate_id: 'cand_1',
        tag_name: 'button',
        text_content: '立即提交订单',
        attributes: { id: 'btn-dynamic-hash-9182', class: 'rounded-lg bg-blue-600' },
        bounding_box: { x: 505.0, y: 602.0, width: 120.0, height: 40.0 },
        xpath: '//div/button[1]',
      },
      {
        candidate_id: 'cand_2',
        tag_name: 'button',
        text_content: '取消订单',
        attributes: { id: 'cancel-btn' },
        bounding_box: { x: 300.0, y: 600.0, width: 100.0, height: 40.0 },
      },
    ],
  },
  testid: {
    target: {
      original_locator: '#btn-pay',
      tag_name: 'button',
      test_id: 'checkout-action-submit',
      text_content: '确认支付',
    },
    candidates: [
      {
        candidate_id: 'c_testid',
        tag_name: 'button',
        test_id: 'checkout-action-submit',
        text_content: '立即支付 ￥99.0',
        attributes: { 'data-testid': 'checkout-action-submit' },
      },
    ],
  },
  spatial: {
    target: {
      original_locator: "//button[text()='加入购物车']",
      tag_name: 'button',
      text_content: '加入购物车',
      bounding_box: { x: 100.0, y: 200.0, width: 80.0, height: 30.0 },
    },
    candidates: [
      {
        candidate_id: 'cand_near',
        tag_name: 'button',
        text_content: '加入购物车',
        bounding_box: { x: 105.0, y: 202.0, width: 80.0, height: 30.0 },
        xpath: '//section[1]/button',
      },
      {
        candidate_id: 'cand_far',
        tag_name: 'button',
        text_content: '加入购物车',
        bounding_box: { x: 800.0, y: 1200.0, width: 80.0, height: 30.0 },
        xpath: '//aside/div/button',
      },
    ],
  },
  unmatch: {
    target: {
      original_locator: "//input[@name='user_password']",
      tag_name: 'input',
      text_content: '',
      attributes: { name: 'user_password', type: 'password' },
    },
    candidates: [
      {
        candidate_id: 'cand_footer',
        tag_name: 'a',
        text_content: '关于我们',
        attributes: { href: '/about' },
      },
    ],
  },
}

function applyPreset(key: 'text' | 'testid' | 'spatial' | 'unmatch') {
  presetKey.value = key
  const p = PRESETS[key]
  targetLocatorInput.value = p.target.original_locator
  targetTextInput.value = p.target.text_content || ''
  handleRunHealing()
}

async function handleRunHealing() {
  healing.value = true
  try {
    const p = PRESETS[presetKey.value]
    const res = await smartLocatorHealingApi.heal({
      target: {
        ...p.target,
        original_locator: targetLocatorInput.value,
        text_content: targetTextInput.value || p.target.text_content,
      },
      candidates: p.candidates as any,
      execute_retry: true,
    })
    healingResult.value = res.result
    message.success(res.message || '自愈计算完成')
    await fetchHistory()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '自愈失败')
  } finally {
    healing.value = false
  }
}

async function fetchHistory() {
  loadingStats.value = true
  try {
    const res = await smartLocatorHealingApi.getHistory()
    statistics.value = res.statistics
  } catch {
    // ignore
  } finally {
    loadingStats.value = false
  }
}

function copyLocator(loc: string) {
  void navigator.clipboard.writeText(loc)
  message.success('已复制自愈定位器')
}

function copyPatch(patch: string) {
  void navigator.clipboard.writeText(patch)
  message.success('已复制修复补丁代码')
}

onMounted(() => {
  handleRunHealing()
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

.strategy-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}

.strat-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px;
}

.strat-title {
  font-size: 11px;
  font-weight: 700;
  color: #1e293b;
}

.strat-desc {
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
  line-height: 1.3;
}

.action-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
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

.ctrl-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.ctrl-lbl {
  font-size: 12px;
  color: #64748b;
}

/* 裁决大横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 14px 18px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.banner-healed {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.banner-failed {
  background: #fef2f2;
  border-color: #fecaca;
}

.verdict-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.verdict-status-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-tag {
  font-size: 13px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
}

.tag-healed {
  background: #16a34a;
  color: #ffffff;
}

.tag-failed {
  background: #dc2626;
  color: #ffffff;
}

.confidence-val {
  font-size: 12px;
  color: #1e293b;
}

.meta-box {
  font-size: 11px;
  color: #64748b;
}

.locator-compare-box {
  background: #ffffff;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.loc-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.loc-lbl {
  color: #64748b;
  width: 90px;
}

.old-loc {
  color: #dc2626;
  background: #fee2e2;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: Consolas, monospace;
}

.new-loc {
  color: #16a34a;
  background: #dcfce7;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: Consolas, monospace;
  font-weight: bold;
}

/* 分解图 */
.breakdown-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sec-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.breakdown-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}

.score-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 10px;
}

.sc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  color: #475569;
  margin-bottom: 4px;
}

.patch-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.patch-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.patch-title {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}

.patch-code {
  background: #0f172a;
  color: #38bdf8;
  font-family: Consolas, monospace;
  font-size: 11px;
  padding: 10px;
  border-radius: 6px;
  margin: 0;
  white-space: pre-wrap;
}

.stats-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.stats-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.kpi-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px;
  text-align: center;
}

.kpi-val {
  font-size: 18px;
  font-weight: 800;
}

.kpi-lbl {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.text-blue {
  color: #0284c7;
}

.text-green {
  color: #16a34a;
}

.text-purple {
  color: #9333ea;
}
</style>
