<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="大规模测试套件智能动态分片装箱矩阵与掉队重平衡控制台"
    destroy-on-close
    class="sharding-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制说明 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <ApartmentOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">LPT 贪心装箱算法与跨节点多分片负载均衡引擎 (T1.2)</div>
          <div class="banner-desc">
            基于用例历史执行耗时与优先级权重加权降序排序，始终将长耗时任务分配至当前累计负载最低的分片节点，彻底消除“一慢拖全盘”的长尾效应，实现集群执行总时长 (Makespan) 极小化。
          </div>
        </div>
      </div>

      <!-- 预设套件与分片配置控制栏 -->
      <div class="config-section">
        <div class="section-title">分片参数与测试套件配置</div>
        <div class="config-row">
          <div class="preset-group">
            <span class="label">测试套件场景预设:</span>
            <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
              <a-radio-button value="ecom_e2e">电商端到端全链路 (8用例)</a-radio-button>
              <a-radio-button value="api_regression">核心业务 API 矩阵 (12用例)</a-radio-button>
              <a-radio-button value="mixed_chaos">混合高并发混沌套件 (16用例)</a-radio-button>
            </a-radio-group>
          </div>
          <div class="shard-count-control">
            <span class="label">目标切分分片数:</span>
            <a-input-number v-model:value="shardCount" :min="2" :max="8" size="small" class="w-20" />
            <a-button type="primary" size="small" :loading="calculating" @click="handleCalculatePlan">
              <ThunderboltOutlined /> 计算 LPT 最优分片
            </a-button>
          </div>
        </div>
      </div>

      <!-- KPI 统计卡片 -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">待调度测试用例总数</div>
            <div class="stat-value text-primary">{{ currentPlan?.total_cases ?? 0 }} <span class="unit">个</span></div>
            <div class="stat-trend">多优先级任务全覆盖</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">目标执行分片节点数</div>
            <div class="stat-value text-success">{{ currentPlan?.total_shards ?? shardCount }} <span class="unit">节点</span></div>
            <div class="stat-trend">动态 Worker 槽位调度</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">长尾耗时上限 (Makespan)</div>
            <div class="stat-value text-warning">{{ currentPlan?.makespan_ms ?? 0 }} <span class="unit">ms</span></div>
            <div class="stat-trend">整体最慢节点完工耗时</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">分片耗时均衡度评分</div>
            <div class="stat-value text-purple">{{ currentPlan?.balance_score_pct ?? 100 }}%</div>
            <div class="stat-trend">≥ 80% 黄金负载均衡线</div>
          </div>
        </a-col>
      </a-row>

      <!-- 各节点分片装箱矩阵网格 -->
      <div v-if="currentPlan" class="matrix-section">
        <div class="section-title">各 Worker 节点分片分配与耗时负载矩阵</div>
        <div class="shards-grid">
          <div
            v-for="shard in currentPlan.shards"
            :key="shard.shard_index"
            class="shard-card"
          >
            <div class="shard-header">
              <div class="shard-title">
                <span class="shard-badge">Shard {{ shard.shard_index + 1 }}</span>
                <span class="node-name">{{ shard.assigned_node_id }}</span>
              </div>
              <span class="shard-count">{{ shard.case_count }} 个用例</span>
            </div>

            <div class="shard-duration-row">
              <span class="dur-label">预估耗时:</span>
              <span class="dur-val">{{ shard.estimated_duration_ms }} ms</span>
            </div>

            <a-progress
              :percent="Math.round((shard.estimated_duration_ms / (currentPlan.makespan_ms || 1)) * 100)"
              size="small"
              stroke-color="#2563eb"
            />

            <!-- 包含用例列表 -->
            <div class="cases-box">
              <div class="cases-title">分片执行用例:</div>
              <div class="cases-tags">
                <a-tag v-for="cid in shard.case_ids" :key="cid" class="case-tag">
                  {{ cid }}
                </a-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 掉队节点实时检测与重平衡建议 -->
      <div class="straggler-section">
        <div class="straggler-header">
          <div class="section-title"><ClockCircleOutlined /> 运行期长尾掉队节点探测与动态再平衡</div>
          <a-button size="small" :loading="detecting" @click="handleDetectStraggler">
            <RadarChartOutlined /> 扫描掉队节点
          </a-button>
        </div>

        <div v-if="stragglerResult" class="straggler-body">
          <a-alert
            v-if="stragglerResult.has_straggler"
            type="warning"
            show-icon
            :message="`检测到 ${stragglerResult.stragglers.length} 个执行掉队节点，建议触发动态再平衡`"
            :description="stragglerResult.recommendation"
            class="mb-3"
          />
          <a-alert
            v-else
            type="success"
            show-icon
            message="各分片节点运行平稳均衡"
            :description="stragglerResult.recommendation"
            class="mb-3"
          />

          <div v-if="stragglerResult.stragglers.length > 0" class="stragglers-list">
            <div
              v-for="st in stragglerResult.stragglers"
              :key="st.shard_index"
              class="straggler-item"
            >
              <div class="st-header">
                <span class="st-badge">Shard {{ st.shard_index + 1 }} ({{ st.node_id }})</span>
                <span class="st-elapsed">已耗时: {{ st.elapsed_ms }} ms</span>
              </div>
              <div class="st-desc">{{ st.reason }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  RadarChartOutlined,
} from '@ant-design/icons-vue'
import {
  testSuiteShardingApi,
  type ShardingPlanResult,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const PRESETS = {
  ecom_e2e: [
    { case_id: 'ecom_login', case_name: '用户认证登录', historical_duration_ms: 1500.0, priority: 'P0' },
    { case_id: 'ecom_browse_cart', case_name: '商品加购浏览', historical_duration_ms: 4500.0, priority: 'P0' },
    { case_id: 'ecom_checkout', case_name: '订单结算流程', historical_duration_ms: 6000.0, priority: 'P0' },
    { case_id: 'ecom_pay', case_name: '收银台第三方支付', historical_duration_ms: 3500.0, priority: 'P1' },
    { case_id: 'ecom_inventory', case_name: '库存扣减核对', historical_duration_ms: 2200.0, priority: 'P1' },
    { case_id: 'ecom_coupon', case_name: '优惠券满减计算', historical_duration_ms: 1800.0, priority: 'P2' },
    { case_id: 'ecom_points', case_name: '积分账户变动', historical_duration_ms: 1200.0, priority: 'P2' },
    { case_id: 'ecom_logistics', case_name: '物流发货跟踪', historical_duration_ms: 2000.0, priority: 'P3' },
  ],
  api_regression: [
    { case_id: 'api_user_get', case_name: '查询用户档案', historical_duration_ms: 300.0, priority: 'P1' },
    { case_id: 'api_user_update', case_name: '更新用户密码', historical_duration_ms: 800.0, priority: 'P1' },
    { case_id: 'api_order_list', case_name: '历史订单分页查询', historical_duration_ms: 1200.0, priority: 'P1' },
    { case_id: 'api_order_cancel', case_name: '超时未支付取消', historical_duration_ms: 2100.0, priority: 'P0' },
    { case_id: 'api_product_detail', case_name: '商品详情页大查询', historical_duration_ms: 4000.0, priority: 'P0' },
    { case_id: 'api_search_filter', case_name: '多条件搜索高亮', historical_duration_ms: 3200.0, priority: 'P0' },
    { case_id: 'api_category_tree', case_name: '全量类目树递归加载', historical_duration_ms: 2800.0, priority: 'P1' },
    { case_id: 'api_comment_post', case_name: '用户评价发表', historical_duration_ms: 1500.0, priority: 'P2' },
    { case_id: 'api_refund_apply', case_name: '售后退款流程发起', historical_duration_ms: 3900.0, priority: 'P0' },
    { case_id: 'api_invoice_gen', case_name: '电子发票生成', historical_duration_ms: 2400.0, priority: 'P2' },
    { case_id: 'api_health_check', case_name: '全链路探针巡检', historical_duration_ms: 400.0, priority: 'P3' },
    { case_id: 'api_metrics_scrape', case_name: '指标采集上报', historical_duration_ms: 600.0, priority: 'P3' },
  ],
  mixed_chaos: [
    { case_id: 'chaos_db_failover', case_name: '主备数据库倒换压测', historical_duration_ms: 8000.0, priority: 'P0' },
    { case_id: 'chaos_redis_evict', case_name: '缓存大面积雪崩击穿', historical_duration_ms: 7200.0, priority: 'P0' },
    { case_id: 'chaos_net_drop', case_name: '网络丢包率20%容错', historical_duration_ms: 6500.0, priority: 'P0' },
    { case_id: 'chaos_cpu_spike', case_name: '节点CPU 90%压测', historical_duration_ms: 5000.0, priority: 'P1' },
    { case_id: 'chaos_mem_leak', case_name: '内存泄露慢消耗模拟', historical_duration_ms: 4800.0, priority: 'P1' },
    { case_id: 'chaos_disk_full', case_name: '日志磁盘满故障恢复', historical_duration_ms: 4200.0, priority: 'P1' },
    { case_id: 'chaos_mq_delay', case_name: '消息总线积压30万条', historical_duration_ms: 3900.0, priority: 'P1' },
    { case_id: 'chaos_dns_timeout', case_name: 'DNS超时降级走备用IP', historical_duration_ms: 3500.0, priority: 'P2' },
  ],
}

const selectedPreset = ref<'ecom_e2e' | 'api_regression' | 'mixed_chaos'>('ecom_e2e')
const shardCount = ref(3)
const calculating = ref(false)
const detecting = ref(false)
const currentPlan = ref<ShardingPlanResult | null>(null)
const stragglerResult = ref<any | null>(null)

function handleClose() {
  emit('update:open', false)
}

function handlePresetChange() {
  handleCalculatePlan()
}

async function handleCalculatePlan() {
  calculating.value = true
  try {
    const cases = PRESETS[selectedPreset.value]
    const res = await testSuiteShardingApi.calculatePlan({
      cases,
      total_shards: shardCount.value,
    })
    currentPlan.value = res.plan
    message.success(res.message || '分片方案生成成功')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '计算分片方案失败')
  } finally {
    calculating.value = false
  }
}

async function handleDetectStraggler() {
  detecting.value = true
  try {
    // 构造模拟运行中分片进度进行掉队检测
    const res = await testSuiteShardingApi.rebalanceDetect({
      shard_progress: [
        { shard_index: 0, node_id: 'worker-node-1', elapsed_ms: 12500.0, remaining_cases: 12, total_cases: 16 },
        { shard_index: 1, node_id: 'worker-node-2', elapsed_ms: 3200.0, remaining_cases: 1, total_cases: 12 },
        { shard_index: 2, node_id: 'worker-node-3', elapsed_ms: 3800.0, remaining_cases: 0, total_cases: 14 },
      ],
    })
    stragglerResult.value = res
    message.success('掉队节点扫描完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '扫描失败')
  } finally {
    detecting.value = false
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      handleCalculatePlan()
      handleDetectStraggler()
    }
  }
)

onMounted(() => {
  if (props.open) {
    handleCalculatePlan()
    handleDetectStraggler()
  }
})
</script>

<style scoped>
.sharding-drawer :deep(.ant-drawer-body) {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
}

.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #16a34a;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #14532d;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #15803d;
  line-height: 1.5;
}

.config-section,
.matrix-section,
.straggler-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 12px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.preset-group,
.shard-count-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.kpi-row {
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
}

.stat-label {
  font-size: 11px;
  color: #64748b;
}

.stat-value {
  font-size: 22px;
  font-weight: 800;
  margin: 4px 0;
}

.stat-value .unit {
  font-size: 12px;
  font-weight: normal;
  color: #94a3b8;
}

.stat-trend {
  font-size: 11px;
  color: #94a3b8;
}

.text-primary { color: #2563eb; }
.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-purple { color: #7c3aed; }

.shards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.shard-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px 14px;
}

.shard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.shard-badge {
  background: #2563eb;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  margin-right: 6px;
}

.node-name {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.shard-count {
  font-size: 11px;
  color: #64748b;
}

.shard-duration-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  margin-bottom: 4px;
}

.dur-label {
  color: #64748b;
}

.dur-val {
  font-weight: 700;
  color: #1e293b;
}

.cases-box {
  margin-top: 10px;
  border-top: 1px dashed #cbd5e1;
  padding-top: 8px;
}

.cases-title {
  font-size: 10px;
  color: #64748b;
  margin-bottom: 4px;
}

.cases-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.case-tag {
  font-size: 10px;
  margin: 0;
}

.straggler-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.stragglers-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.straggler-item {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 4px;
  padding: 8px 12px;
}

.st-header {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 2px;
}

.st-badge {
  color: #b45309;
}

.st-elapsed {
  color: #d97706;
}

.st-desc {
  font-size: 11px;
  color: #78350f;
}

.mb-3 {
  margin-bottom: 12px;
}

.w-20 {
  width: 70px;
}
</style>
