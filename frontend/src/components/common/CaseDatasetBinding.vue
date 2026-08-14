<template>
  <a-divider orientation="left">{{ t('case_form.basic.dataset_section') }}</a-divider>
  <a-form-item :label="t('case_form.basic.dataset_label')">
    <a-select
      data-test="dataset-select"
      :value="modelValue.datasetId ?? undefined"
      :placeholder="t('case_form.basic.dataset_placeholder')"
      allow-clear
      :loading="datasetsLoading"
      :options="datasetOptions"
      @change="handleDatasetChange"
    />
    <div v-if="modelValue.datasetId" class="dataset-hint">
      {{ t('case_form.basic.dataset_hint') }}
    </div>
  </a-form-item>

  <template v-if="modelValue.datasetId">
    <a-form-item :label="t('case_form.basic.dataset_version_label')">
      <a-select
        data-test="dataset-version-select"
        :value="modelValue.datasetVersion ?? undefined"
        :placeholder="t('case_form.basic.dataset_version_placeholder')"
        allow-clear
        :loading="versionsLoading"
        :options="versionOptions"
        @change="handleVersionChange"
      />
      <div class="dataset-hint">
        {{ t('case_form.basic.dataset_version_hint') }}
      </div>
    </a-form-item>

    <a-form-item>
      <a-checkbox
        :checked="modelValue.strictSchema"
        @update:checked="updateBinding({ strictSchema: $event })"
      >
        {{ t('case_form.basic.dataset_strict_schema') }}
      </a-checkbox>
      <div class="dataset-hint">
        {{ t('case_form.basic.dataset_strict_schema_hint') }}
      </div>
    </a-form-item>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item :label="t('case_form.basic.dataset_strategy')">
          <a-select
            :value="modelValue.strategy"
            :options="strategyOptions"
            @change="handleStrategyChange"
          />
        </a-form-item>
      </a-col>
      <a-col v-if="['fixed_count', 'random', 'cartesian', 'pairwise'].includes(modelValue.strategy)" :span="8">
        <a-form-item :label="t('case_form.basic.dataset_fixed_count')">
          <a-input-number
            :value="modelValue.fixedCount ?? undefined"
            :min="1"
            style="width: 100%"
            @update:value="handleFixedCountChange"
          />
        </a-form-item>
      </a-col>
      <a-col :span="8">
        <a-form-item :label="t('case_form.basic.dataset_max_iterations')">
          <a-input-number
            :value="modelValue.maxIterations"
            :min="1"
            :max="1000"
            style="width: 100%"
            @update:value="handleMaxIterationsChange"
          />
        </a-form-item>
      </a-col>
    </a-row>

    <a-form-item v-if="['cartesian', 'pairwise'].includes(modelValue.strategy)" :label="t('case_form.basic.dataset_combination_fields')">
      <a-select
        mode="tags"
        :value="modelValue.combinationFields"
        :placeholder="t('case_form.basic.dataset_combination_fields_placeholder')"
        @update:value="handleCombinationFieldsChange"
      />
    </a-form-item>

    <a-row :gutter="12">
      <a-col :span="8">
        <a-form-item :label="t('case_form.basic.dataset_seed')">
          <a-input-number
            :value="modelValue.seed ?? undefined"
            style="width: 100%"
            @update:value="handleSeedChange"
          />
        </a-form-item>
      </a-col>
      <a-col :span="16">
        <a-form-item :label="t('case_form.basic.dataset_redact_fields')">
          <a-select
            mode="tags"
            :value="modelValue.redactFields"
            :placeholder="t('case_form.basic.dataset_redact_fields_placeholder')"
            @update:value="handleRedactFieldsChange"
          />
        </a-form-item>
      </a-col>
    </a-row>
  </template>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { datasetApi, type DatasetListItem, type DatasetVersionItem } from '@/api'
import type { CaseDatasetBinding } from '@/types/caseDataset'

const props = defineProps<{
  projectId?: number | null
  modelValue: CaseDatasetBinding
}>()

const emit = defineEmits<{ 'update:modelValue': [value: CaseDatasetBinding] }>()
const { t } = useI18n()

const datasetsLoading = ref(false)
const versionsLoading = ref(false)
const datasets = ref<DatasetListItem[]>([])
const versions = ref<DatasetVersionItem[]>([])
const datasetLoadSeq = ref(0)
const versionLoadSeq = ref(0)

const datasetOptions = computed(() => datasets.value.map((item) => ({
  label: `${item.name} (${item.row_count} ${t('case_form.basic.dataset_rows_suffix')})`,
  value: item.id,
})))
const versionOptions = computed(() => versions.value.map((item) => ({
  label: `v${item.version} (${item.row_count} ${t('case_form.basic.dataset_rows_suffix')})`,
  value: item.version,
})))
const strategyOptions = computed(() => [
  { label: t('case_form.basic.dataset_strategy_sequential'), value: 'sequential' },
  { label: t('case_form.basic.dataset_strategy_random'), value: 'random' },
  { label: t('case_form.basic.dataset_strategy_fixed'), value: 'fixed_count' },
  { label: t('case_form.basic.dataset_strategy_cartesian'), value: 'cartesian' },
  { label: t('case_form.basic.dataset_strategy_pairwise'), value: 'pairwise' },
])

function updateBinding(patch: Partial<CaseDatasetBinding>) {
  emit('update:modelValue', { ...props.modelValue, ...patch })
}

function handleStrategyChange(value: unknown) {
  const strategy = value === 'random' || value === 'fixed_count' || value === 'cartesian' || value === 'pairwise'
    ? value
    : 'sequential'
  updateBinding({ strategy })
}

function numberOrNull(value: unknown) {
  if (value == null || value === '') return null
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function handleFixedCountChange(value: unknown) {
  updateBinding({ fixedCount: numberOrNull(value) })
}

function handleMaxIterationsChange(value: unknown) {
  updateBinding({ maxIterations: numberOrNull(value) ?? 1000 })
}

function handleSeedChange(value: unknown) {
  updateBinding({ seed: numberOrNull(value) })
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.map(String) : []
}

function handleCombinationFieldsChange(value: unknown) {
  updateBinding({ combinationFields: stringArray(value) })
}

function handleRedactFieldsChange(value: unknown) {
  updateBinding({ redactFields: stringArray(value) })
}

async function loadDatasets() {
  const projectId = props.projectId
  const seq = ++datasetLoadSeq.value
  datasets.value = []
  if (projectId == null) {
    datasetsLoading.value = false
    return
  }
  datasetsLoading.value = true
  try {
    const items = await datasetApi.list(projectId)
    if (seq === datasetLoadSeq.value) datasets.value = items
  } catch {
    if (seq === datasetLoadSeq.value) datasets.value = []
  } finally {
    if (seq === datasetLoadSeq.value) datasetsLoading.value = false
  }
}

async function loadVersions(datasetId: number | null, initial: boolean) {
  const seq = ++versionLoadSeq.value
  versions.value = []
  if (datasetId == null) {
    versionsLoading.value = false
    if (props.modelValue.datasetVersion != null) updateBinding({ datasetVersion: null })
    return
  }
  versionsLoading.value = true
  try {
    const items = await datasetApi.listVersions(datasetId)
    if (seq !== versionLoadSeq.value) return
    versions.value = items
    const currentVersion = props.modelValue.datasetVersion
    const currentExists = currentVersion != null && items.some((item) => item.version === currentVersion)
    if ((!initial && !currentExists) || (initial && currentVersion != null && !currentExists)) {
      updateBinding({ datasetVersion: items[0]?.version ?? null })
    }
  } catch {
    if (seq === versionLoadSeq.value) versions.value = []
  } finally {
    if (seq === versionLoadSeq.value) versionsLoading.value = false
  }
}

function handleDatasetChange(value: unknown) {
  const datasetId = value == null || value === '' ? null : Number(value)
  updateBinding({ datasetId: Number.isFinite(datasetId) ? datasetId : null, datasetVersion: null })
}

function handleVersionChange(value: unknown) {
  const datasetVersion = value == null || value === '' ? null : Number(value)
  updateBinding({ datasetVersion: Number.isFinite(datasetVersion) ? datasetVersion : null })
}

watch(() => props.projectId, () => { void loadDatasets() }, { immediate: true })
watch(() => props.modelValue.datasetId, (datasetId, previousId) => {
  void loadVersions(datasetId ?? null, previousId === undefined)
}, { immediate: true })
</script>

<style scoped>
.dataset-hint {
  margin-top: 4px;
  color: #999;
  font-size: 12px;
}
</style>
