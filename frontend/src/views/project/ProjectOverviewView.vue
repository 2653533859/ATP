<template>
  <div class="page-shell project-overview-page">
    <div class="page-hero">
      <div>
        <a-button type="link" class="back-link" @click="router.push('/projects')">← {{ t('project.overview.back') }}</a-button>
        <div class="overview-title-row">
          <h2 class="page-title">{{ project?.name || t('project.overview.title') }}</h2>
          <a-tag v-if="project" :color="project.status === 'active' ? 'green' : 'default'">
            {{ project.status === 'active' ? t('project.status.active') : t('project.status.archived') }}
          </a-tag>
        </div>
        <div class="page-subtitle">{{ project?.description || t('project.overview.subtitle') }}</div>
      </div>
      <a-space>
        <a-button @click="router.push({ name: 'cases', query: { project_id: String(projectId) } })">
          {{ t('project.overview.open_cases') }}
        </a-button>
        <a-button type="primary" @click="router.push('/projects')">{{ t('project.overview.project_list') }}</a-button>
      </a-space>
    </div>

    <a-alert
      v-if="project?.status === 'archived'"
      type="warning"
      show-icon
      :message="t('project.overview.archived_hint')"
      style="margin-bottom: 16px"
    />

    <a-spin :spinning="loading">
      <a-row :gutter="[16, 16]" class="page-summary">
        <a-col v-for="item in summaryItems" :key="item.key" :span="6">
          <a-card size="small">
            <a-statistic :title="t(item.label)" :value="item.value" />
          </a-card>
        </a-col>
      </a-row>

      <a-row :gutter="16" style="margin-top: 16px">
        <a-col :span="16">
          <a-card :title="t('project.overview.config_title')" class="config-card">
            <template #extra>{{ t('project.overview.config_hint') }}</template>
            <a-row :gutter="[12, 12]">
              <a-col v-for="resource in resources" :key="resource.key" :span="8">
                <a-card size="small" hoverable @click="openResource(resource)">
                  <div class="resource-card">
                    <div>
                      <div class="resource-title">{{ t(resource.label) }}</div>
                      <div class="resource-description">{{ t(resource.description) }}</div>
                    </div>
                    <a-statistic :value="counts[resource.key]" />
                  </div>
                </a-card>
              </a-col>
            </a-row>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card :title="t('project.overview.info_title')" class="info-card">
            <a-descriptions :column="1" size="small">
              <a-descriptions-item :label="t('project.overview.project_code')">
                {{ project?.project_code || t('project.unbound') }}
              </a-descriptions-item>
              <a-descriptions-item :label="t('project.overview.ai_model')">
                {{ project ? llmConfigLabel(project.ai_llm_config_id) : '-' }}
              </a-descriptions-item>
              <a-descriptions-item :label="t('project.overview.created_at')">
                {{ formatDate(project?.created_at) }}
              </a-descriptions-item>
              <a-descriptions-item :label="t('project.overview.updated_at')">
                {{ formatDate(project?.updated_at) }}
              </a-descriptions-item>
            </a-descriptions>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  apiContractAssetApi,
  apiSchemaAssetApi,
  caseApi,
  datasetApi,
  environmentApi,
  globalVariableApi,
  mockRuleApi,
  planApi,
  projectApi,
  statisticsApi,
  suiteApi,
  webAssetsApi,
  webVisualApi,
  type AILLMConfigItem,
  type ProjectItem,
} from '@/api'
import { aiLLMConfigApi } from '@/api'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const projectId = computed(() => Number(route.params.projectId))
const project = ref<ProjectItem | null>(null)
const llmConfigs = ref<AILLMConfigItem[]>([])
const loading = ref(false)
const overview = ref({ total_cases: 0, total_runs: 0, pass_rate: 0, recent_runs_7d: 0 })

type ResourceKey = 'cases' | 'environments' | 'datasets' | 'mock_rules' | 'suites' | 'plans' | 'web_assets' | 'api_assets' | 'variables'
const counts = reactive<Record<ResourceKey, number>>({
  cases: 0,
  environments: 0,
  datasets: 0,
  mock_rules: 0,
  suites: 0,
  plans: 0,
  web_assets: 0,
  api_assets: 0,
  variables: 0,
})

const resources = [
  { key: 'cases' as const, label: 'project.overview.resources.cases', description: 'project.overview.resources.cases_hint', path: '/cases' },
  { key: 'environments' as const, label: 'project.overview.resources.environments', description: 'project.overview.resources.environments_hint', path: '/system/environments' },
  { key: 'datasets' as const, label: 'project.overview.resources.datasets', description: 'project.overview.resources.datasets_hint', path: '/system/datasets' },
  { key: 'variables' as const, label: 'project.overview.resources.variables', description: 'project.overview.resources.variables_hint', path: '/system/global-variables' },
  { key: 'mock_rules' as const, label: 'project.overview.resources.mock_rules', description: 'project.overview.resources.mock_rules_hint', path: '/mock-rules' },
  { key: 'suites' as const, label: 'project.overview.resources.suites', description: 'project.overview.resources.suites_hint', path: '/suites' },
  { key: 'plans' as const, label: 'project.overview.resources.plans', description: 'project.overview.resources.plans_hint', path: '/plans' },
  { key: 'web_assets' as const, label: 'project.overview.resources.web_assets', description: 'project.overview.resources.web_assets_hint', path: '/system/web-assets' },
  { key: 'api_assets' as const, label: 'project.overview.resources.api_assets', description: 'project.overview.resources.api_assets_hint', path: '/system/api-contract-assets' },
]

const summaryItems = computed(() => [
  { key: 'cases', label: 'project.overview.stats.cases', value: overview.value.total_cases },
  { key: 'runs', label: 'project.overview.stats.runs', value: overview.value.total_runs },
  { key: 'pass_rate', label: 'project.overview.stats.pass_rate', value: `${overview.value.pass_rate}%` },
  { key: 'recent', label: 'project.overview.stats.recent_runs', value: overview.value.recent_runs_7d },
])

const llmNameMap = computed(() => new Map(llmConfigs.value.map((config) => [config.id, config.name])))

function llmConfigLabel(id?: number | null) {
  return id == null ? t('project.unbound') : llmNameMap.value.get(id) ?? `#${id}`
}

function formatDate(value?: string) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function openResource(resource: (typeof resources)[number]) {
  router.push({ path: resource.path, query: { project_id: String(projectId.value) } })
}

async function loadOverview() {
  if (!projectId.value) return
  loading.value = true
  try {
    const [projectResult, overviewResult, llmResult] = await Promise.allSettled([
      projectApi.get(projectId.value),
      statisticsApi.overview({ project_id: projectId.value }),
      aiLLMConfigApi.list(),
    ])
    if (projectResult.status === 'fulfilled') project.value = projectResult.value
    if (overviewResult.status === 'fulfilled') overview.value = overviewResult.value
    if (llmResult.status === 'fulfilled') llmConfigs.value = llmResult.value

    const resourceTasks: Array<[ResourceKey, () => Promise<unknown[]>]> = [
      ['cases', async () => caseApi.list({ project_id: projectId.value })],
      ['environments', async () => environmentApi.list(projectId.value)],
      ['datasets', async () => datasetApi.list(projectId.value)],
      ['mock_rules', async () => mockRuleApi.list({ project_id: projectId.value })],
      ['suites', async () => suiteApi.list({ project_id: projectId.value })],
      ['plans', async () => planApi.list({ project_id: projectId.value })],
      ['web_assets', async () => {
        const [elements, pageObjects, baselines] = await Promise.all([
          webAssetsApi.listElements(projectId.value),
          webAssetsApi.listPageObjects(projectId.value),
          webVisualApi.listBaselines(projectId.value),
        ])
        return [...elements, ...pageObjects, ...baselines]
      }],
      ['api_assets', async () => {
        const [contracts, schemas] = await Promise.all([
          apiContractAssetApi.list(projectId.value),
          apiSchemaAssetApi.list(projectId.value),
        ])
        return [...contracts, ...schemas]
      }],
      ['variables', async () => globalVariableApi.list({ project_id: projectId.value })],
    ]
    const resourceResults = await Promise.allSettled(resourceTasks.map(([, task]) => task()))
    resourceResults.forEach((result, index) => {
      counts[resourceTasks[index][0]] = result.status === 'fulfilled' ? result.value.length : 0
    })
  } catch {
    message.error(t('project.overview.load_failed'))
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)
</script>

<style scoped>
.back-link {
  padding: 0;
  margin-bottom: 4px;
}

.overview-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.resource-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 58px;
}

.resource-title {
  font-weight: 600;
}

.resource-description {
  margin-top: 4px;
  color: var(--c-text-tertiary);
  font-size: 12px;
}
</style>
