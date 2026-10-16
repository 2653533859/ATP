<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="基础设施即代码 (IaC) 与网络策略安全合规巡检控制台"
    destroy-on-close
    class="iac-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制介绍 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <SecurityScanOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">云原生 IaC 清单与 NetworkPolicy 准入安全巡检引擎 (T2.3)</div>
          <div class="banner-desc">
            全面扫描 Kubernetes Pod / Deployment / DaemonSet / NetworkPolicy 与 Docker Compose 配置，精准阻断特权容器逃逸、敏感宿主机卷挂载、网络全通与资源缺失等高危漏洞，捍卫发布安全准入门禁。
          </div>
        </div>
      </div>

      <!-- 场景预设与快速扫描控制栏 -->
      <div class="config-section">
        <div class="section-title">IaC 清单扫描配置与演练预设</div>
        <div class="config-row">
          <div class="preset-group">
            <span class="label">清单场景预设:</span>
            <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
              <a-radio-button value="insecure_workload">高危违规清单 (特权逃逸/DockerSock)</a-radio-button>
              <a-radio-button value="unrestricted_netpol">网络策略全网段开放 (0.0.0.0/0)</a-radio-button>
              <a-radio-button value="secure_workload">安全合规黄金基准清单</a-radio-button>
            </a-radio-group>
          </div>
          <a-button type="primary" size="small" :loading="scanning" @click="handleScan">
            <ThunderboltOutlined /> 执行合规安全扫描
          </a-button>
        </div>
      </div>

      <!-- 准入裁决大横幅 -->
      <div v-if="latestReport" class="verdict-banner-wrap">
        <a-alert
          v-if="latestReport.verdict === 'BLOCKED'"
          type="error"
          show-icon
          :message="`发版准入阻断 (BLOCKED) - 发现 ${latestReport.critical_count} 个 CRITICAL 级逃逸高危违规！`"
          description="当前基础设施清单包含特权容器 (privileged: true) 或敏感目录挂载，存在严重节点越权逃逸隐患，禁止上线发布！"
          class="mb-3"
        />
        <a-alert
          v-else-if="latestReport.verdict === 'WARNING'"
          type="warning"
          show-icon
          :message="`发版准入预警 (WARNING) - 检测到 ${latestReport.high_count} 项 HIGH 级安全合规缺陷`"
          description="网络策略入向规则未受限或容器缺少必要安全上下文，建议修复后重新扫描核验。"
          class="mb-3"
        />
        <a-alert
          v-else
          type="success"
          show-icon
          message="发版准入通过 (PASS) - 基础设施清单 100% 满足安全基线要求"
          description="未检测到任何高危配置缺陷，所有容器均已配置受限权限、只读文件系统与合理资源限额。"
          class="mb-3"
        />
      </div>

      <!-- 4 大核心 KPI 统计卡片 -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">扫描 IaC 资源总数</div>
            <div class="stat-value text-primary">{{ latestReport?.total_resources_scanned ?? 0 }} <span class="unit">个</span></div>
            <div class="stat-trend">工作负载与网络策略</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">基础设施安全合规评分</div>
            <div class="stat-value" :class="getScoreColorClass(latestReport?.compliance_score_pct ?? 100)">
              {{ latestReport?.compliance_score_pct ?? 100 }}%
            </div>
            <div class="stat-trend">动态加权扣分模型</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">阻断级违规 (CRITICAL)</div>
            <div class="stat-value text-danger">{{ latestReport?.critical_count ?? 0 }} <span class="unit">处</span></div>
            <div class="stat-trend">特权逃逸与越权风险</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">高危缺陷 (HIGH/MEDIUM)</div>
            <div class="stat-value text-warning">
              {{ (latestReport?.high_count ?? 0) + (latestReport?.medium_count ?? 0) }} <span class="unit">处</span>
            </div>
            <div class="stat-trend">网络开放与限额缺失</div>
          </div>
        </a-col>
      </a-row>

      <!-- 合规违规明细表格 -->
      <div class="table-section">
        <div class="table-header">
          <div class="section-title">合规检查违规项与加固指引清单</div>
          <span class="text-xs text-muted">共 {{ latestReport?.violations.length ?? 0 }} 处违规</span>
        </div>

        <a-table
          :data-source="latestReport?.violations ?? []"
          :columns="columns"
          :row-key="(r: any) => `${r.rule_id}_${r.resource_name}`"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'rule_id'">
              <span class="rule-id-badge">{{ record.rule_id }}</span>
            </template>

            <template v-else-if="column.key === 'severity'">
              <a-tag :color="getSeverityTagColor(record.severity)">{{ record.severity }}</a-tag>
            </template>

            <template v-else-if="column.key === 'resource'">
              <div class="res-cell">
                <span class="res-kind">{{ record.resource_kind }}</span>
                <strong>{{ record.resource_name }}</strong>
              </div>
            </template>

            <template v-else-if="column.key === 'message'">
              <span class="text-xs">{{ record.violation_message }}</span>
            </template>

            <template v-else-if="column.key === 'remediation'">
              <span class="text-xs text-primary">{{ record.remediation_guidance }}</span>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SecurityScanOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  iacComplianceScannerApi,
  type IaCComplianceReport,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const scanning = ref(false)
const selectedPreset = ref<'insecure_workload' | 'unrestricted_netpol' | 'secure_workload'>('insecure_workload')
const latestReport = ref<IaCComplianceReport | null>(null)

const PRESET_MANIFESTS = {
  insecure_workload: [
    {
      kind: 'Deployment',
      metadata: { name: 'ci-runner-deployment' },
      spec: {
        template: {
          spec: {
            hostNetwork: true,
            volumes: [
              { name: 'docker-sock', hostPath: { path: '/var/run/docker.sock' } },
            ],
            containers: [
              {
                name: 'docker-builder',
                securityContext: { privileged: true },
                // 缺失 resources limits
              },
            ],
          },
        },
      },
    },
  ],
  unrestricted_netpol: [
    {
      kind: 'NetworkPolicy',
      metadata: { name: 'allow-all-ingress' },
      spec: {
        podSelector: {},
        ingress: [
          {
            from: [{ ipBlock: { cidr: '0.0.0.0/0' } }],
          },
        ],
      },
    },
  ],
  secure_workload: [
    {
      kind: 'Deployment',
      metadata: { name: 'hardened-microservice' },
      spec: {
        template: {
          spec: {
            securityContext: { runAsNonRoot: true },
            containers: [
              {
                name: 'app',
                securityContext: { privileged: false, runAsNonRoot: true },
                resources: {
                  requests: { cpu: '100m', memory: '128Mi' },
                  limits: { cpu: '500m', memory: '512Mi' },
                },
              },
            ],
          },
        },
      },
    },
  ],
}

const columns = [
  { title: '规则编号', key: 'rule_id', width: 90 },
  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', width: 160 },
  { title: '严重度', key: 'severity', width: 90 },
  { title: '违规资源', key: 'resource', width: 180 },
  { title: '违规说明', key: 'message', width: 260 },
  { title: '加固排查指引', key: 'remediation' },
]

function handleClose() {
  emit('update:open', false)
}

function handlePresetChange() {
  handleScan()
}

function getSeverityTagColor(sev: string) {
  switch (sev) {
    case 'CRITICAL': return 'red'
    case 'HIGH': return 'orange'
    case 'MEDIUM': return 'gold'
    case 'LOW': return 'default'
    default: return 'default'
  }
}

function getScoreColorClass(score: number) {
  if (score >= 90) return 'text-success'
  if (score >= 70) return 'text-warning'
  return 'text-danger'
}

async function handleScan() {
  scanning.value = true
  try {
    const manifests = PRESET_MANIFESTS[selectedPreset.value]
    const res = await iacComplianceScannerApi.scan({
      target_name: selectedPreset.value,
      manifests,
    })
    latestReport.value = res.report
    message.success(res.message || '合规扫描完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '扫描失败')
  } finally {
    scanning.value = false
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      handleScan()
    }
  }
)

onMounted(() => {
  if (props.open) {
    handleScan()
  }
})
</script>

<style scoped>
.iac-drawer :deep(.ant-drawer-body) {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
}

.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #dc2626;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #991b1b;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.5;
}

.config-section,
.table-section {
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
  margin-bottom: 10px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.preset-group {
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
.text-danger { color: #dc2626; }
.text-muted { color: #94a3b8; }

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.rule-id-badge {
  font-family: monospace;
  font-weight: 700;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.res-cell {
  display: flex;
  flex-direction: column;
  font-size: 11px;
}

.res-kind {
  font-size: 10px;
  color: #64748b;
}

.text-xs {
  font-size: 11px;
}

.mb-3 {
  margin-bottom: 12px;
}
</style>
