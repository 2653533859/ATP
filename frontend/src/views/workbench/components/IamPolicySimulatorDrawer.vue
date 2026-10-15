<template>
  <a-drawer
    :open="open"
    :width="920"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <span>细粒度资源操作 RBAC 策略模拟器与 Anti-IDOR 诊断</span>
    </template>

    <div class="iam-policy-simulator-drawer">
      <!-- 顶部诊断简介与快速测试场景 -->
      <a-card size="small" class="intro-card">
        <div class="intro-header">
          <div class="intro-desc">
            <h4 class="title">企业级策略决策点 (PDP) 在线动态模拟与越权防线</h4>
            <p class="subtitle">
              遵循显式拒绝优先 (Explicit Deny Precedence) 与最小特权原则。支持针对特定资产类型与细粒度动作进行策略推演，并具备 Anti-IDOR 跨项目边界横向越权拦截能力。
            </p>
          </div>
          <a-space class="preset-scenarios">
            <a-button size="small" @click="loadScenario('viewer_mutate')">
              测试员修改用例 (显式拒绝)
            </a-button>
            <a-button size="small" @click="loadScenario('engineer_secret')">
              工程师删密钥 (显式拒绝)
            </a-button>
            <a-button size="small" danger @click="loadScenario('cross_project_idor')">
              跨项目越权 (Anti-IDOR)
            </a-button>
            <a-button size="small" type="primary" ghost @click="loadScenario('normal_modify')">
              正常用例维护 (允许)
            </a-button>
          </a-space>
        </div>

        <!-- 模拟器配置表单 -->
        <a-form layout="vertical" class="sim-form">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="目标资源类型 (Resource Kind)" required>
                <a-select v-model:value="simForm.resource_kind" style="width: 100%">
                  <a-select-option value="case">测试用例 (case)</a-select-option>
                  <a-select-option value="suite">测试套件 (suite)</a-select-option>
                  <a-select-option value="plan">测试计划 (plan)</a-select-option>
                  <a-select-option value="device">真机设备 (device)</a-select-option>
                  <a-select-option value="secret">企业敏感密钥 (secret)</a-select-option>
                  <a-select-option value="dataset">数据集 (dataset)</a-select-option>
                  <a-select-option value="mesh_chaos">网关混沌故障 (mesh_chaos)</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>

            <a-col :span="12">
              <a-form-item label="拟执行操作动作 (Action)" required>
                <a-select v-model:value="simForm.action" style="width: 100%">
                  <a-select-option value="read">只读查询 (read)</a-select-option>
                  <a-select-option value="execute">触发执行 (execute)</a-select-option>
                  <a-select-option value="create">新建录入 (create)</a-select-option>
                  <a-select-option value="modify">修改配置 (modify)</a-select-option>
                  <a-select-option value="delete">数据删除 (delete)</a-select-option>
                  <a-select-option value="manage_permissions">权限委派分配 (manage_permissions)</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="当前请求项目上下文 ID (Context Project ID)">
                <a-input-number v-model:value="simForm.project_id" :min="1" style="width: 100%" />
              </a-form-item>
            </a-col>

            <a-col :span="12">
              <a-form-item label="目标资产所属项目 ID (Target Resource Project ID)">
                <a-input-number v-model:value="simForm.resource_project_id" :min="1" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>

          <div class="submit-btn-row">
            <a-button type="primary" :loading="evaluating" block @click="handleRunEvaluate">
              执行策略决策点 (PDP) 在线判定
            </a-button>
          </div>
        </a-form>
      </a-card>

      <!-- 诊断判定结果展示区 -->
      <a-card size="small" title="策略判定决策报告 (Policy Evaluation Result)" class="result-card">
        <div v-if="result" class="decision-display">
          <a-alert
            v-if="result.allowed"
            type="success"
            show-icon
            class="decision-alert"
            :message="`[策略允许 (Explicit Allow)] 允许执行操作: ${result.resource_kind}:${result.action}`"
            :description="result.decision_reason"
          />
          <a-alert
            v-else
            type="error"
            show-icon
            class="decision-alert"
            :message="`[策略拒绝 (Access Denied)] 拦截操作: ${result.resource_kind}:${result.action}`"
            :description="result.decision_reason"
          />

          <div class="detail-grid">
            <div class="detail-item">
              <span class="lbl">目标资源分类:</span>
              <a-tag color="blue">{{ result.resource_kind }}</a-tag>
            </div>
            <div class="detail-item">
              <span class="lbl">申请操作动作:</span>
              <a-tag color="purple">{{ result.action }}</a-tag>
            </div>
            <div class="detail-item">
              <span class="lbl">命中策略规则:</span>
              <code>{{ result.matched_rule || '无匹配 (Default Deny)' }}</code>
            </div>
            <div class="detail-item">
              <span class="lbl">Anti-IDOR 越权状态:</span>
              <a-tag :color="isIdorDetected ? 'red' : 'green'">
                {{ isIdorDetected ? '拦截跨项目平行越权' : '同项目边界安全' }}
              </a-tag>
            </div>
          </div>
        </div>

        <a-empty v-else description="点击上方按钮即可启动 PDP 策略决策判定" class="empty-holder" />
      </a-card>

      <!-- 平台当前生效的策略基线清单 -->
      <a-card size="small" title="平台当前生效的细粒度 RBAC 规则基线 (Active Policies)" class="policies-card">
        <template #extra>
          <a-button size="small" :loading="loadingPolicies" @click="loadPolicies">
            刷新规则列表
          </a-button>
        </template>

        <a-table
          :data-source="policies"
          :columns="policyColumns"
          row-key="rule_id"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'effect'">
              <a-tag :color="record.effect === 'allow' ? 'green' : 'red'">
                {{ record.effect === 'allow' ? '允许 (Allow)' : '显式拒绝 (Deny)' }}
              </a-tag>
            </template>

            <template v-if="column.key === 'principals'">
              <a-space size="small" class="tag-wrap">
                <a-tag v-for="p in record.principals" :key="p" color="blue" class="mono-tag">
                  {{ p }}
                </a-tag>
              </a-space>
            </template>

            <template v-if="column.key === 'resources'">
              <a-space size="small" class="tag-wrap">
                <a-tag v-for="r in record.resources" :key="r" color="cyan" class="mono-tag">
                  {{ r }}
                </a-tag>
              </a-space>
            </template>

            <template v-if="column.key === 'actions'">
              <a-space size="small" class="tag-wrap">
                <a-tag v-for="a in record.actions" :key="a" color="purple" class="mono-tag">
                  {{ a }}
                </a-tag>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  iamPolicyApi,
  type IamResourceKind,
  type IamAction,
  type IamPolicyRule,
  type IamEvaluationResult,
} from '@/api/iamPolicy'

const props = withDefaults(
  defineProps<{
    open: boolean
  }>(),
  {
    open: false,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const evaluating = ref(false)
const loadingPolicies = ref(false)
const result = ref<IamEvaluationResult | null>(null)
const policies = ref<IamPolicyRule[]>([])

const simForm = reactive<{
  resource_kind: IamResourceKind
  action: IamAction
  project_id: number
  resource_project_id: number
}>({
  resource_kind: 'case',
  action: 'modify',
  project_id: 1,
  resource_project_id: 1,
})

const policyColumns = [
  { title: '规则标识', dataIndex: 'rule_id', key: 'rule_id', width: 180 },
  { title: '策略效力', key: 'effect', width: 110 },
  { title: '主体角色 (Principals)', key: 'principals', width: 170 },
  { title: '资源范围', key: 'resources', width: 140 },
  { title: '动作权限', key: 'actions', width: 130 },
  { title: '规则描述', dataIndex: 'description', key: 'description', ellipsis: true },
]

const isIdorDetected = computed(() => {
  return (
    simForm.project_id &&
    simForm.resource_project_id &&
    simForm.project_id !== simForm.resource_project_id
  )
})

function handleClose() {
  emit('update:open', false)
}

function loadScenario(type: string) {
  switch (type) {
    case 'viewer_mutate':
      simForm.resource_kind = 'case'
      simForm.action = 'delete'
      simForm.project_id = 1
      simForm.resource_project_id = 1
      message.info('已配置: 访客/测试员执行核心资产删除 (预期显式拒绝)')
      break
    case 'engineer_secret':
      simForm.resource_kind = 'secret'
      simForm.action = 'delete'
      simForm.project_id = 1
      simForm.resource_project_id = 1
      message.info('已配置: 工程师擅自销毁企业密钥 (预期显式拒绝)')
      break
    case 'cross_project_idor':
      simForm.resource_kind = 'case'
      simForm.action = 'read'
      simForm.project_id = 10
      simForm.resource_project_id = 20
      message.warning('已配置: 跨项目平行越权请求 (预期 Anti-IDOR 隔离阻断)')
      break
    case 'normal_modify':
      simForm.resource_kind = 'case'
      simForm.action = 'modify'
      simForm.project_id = 1
      simForm.resource_project_id = 1
      message.success('已配置: 研发工程师维护项目用例 (预期显式允许)')
      break
  }
  handleRunEvaluate()
}

async function loadPolicies() {
  loadingPolicies.value = true
  try {
    const res = await iamPolicyApi.listPolicies()
    policies.value = res.policies
  } catch (err: any) {
    message.error(err.message || '获取策略规则失败')
  } finally {
    loadingPolicies.value = false
  }
}

async function handleRunEvaluate() {
  evaluating.value = true
  try {
    const res = await iamPolicyApi.evaluatePolicy({
      resource_kind: simForm.resource_kind,
      action: simForm.action,
      project_id: simForm.project_id,
      resource_project_id: simForm.resource_project_id,
    })
    result.value = res
    if (res.allowed) {
      message.success('策略判定: 显式允许访问！')
    } else {
      message.warning(`策略判定: 拒绝访问 - ${res.decision_reason}`)
    }
  } catch (err: any) {
    message.error(err.message || '策略判定失败')
  } finally {
    evaluating.value = false
  }
}

onMounted(() => {
  loadPolicies()
  handleRunEvaluate()
})
</script>

<style scoped>
.iam-policy-simulator-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.intro-card,
.result-card,
.policies-card {
  border-radius: 8px;
}

.intro-header {
  margin-bottom: 14px;
}

.title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.preset-scenarios {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sim-form {
  padding-top: 14px;
  border-top: 1px solid var(--c-border, #f1f5f9);
}

.submit-btn-row {
  margin-top: 4px;
}

.decision-display {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.decision-alert {
  border-radius: 6px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 10px 14px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.detail-item .lbl {
  color: var(--c-text-secondary, #64748b);
  min-width: 100px;
}

.detail-item code {
  color: #2563eb;
  font-size: 11px;
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mono-tag {
  font-family: monospace;
  font-size: 10px;
  padding: 0 4px;
}

.empty-holder {
  padding: 20px 0;
}
</style>
