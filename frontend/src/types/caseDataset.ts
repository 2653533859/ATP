export type DatasetExecutionStrategy = 'sequential' | 'random' | 'fixed_count' | 'cartesian' | 'pairwise'

export interface CaseDatasetBinding {
  datasetId: number | null
  datasetVersion: number | null
  strictSchema: boolean
  strategy: DatasetExecutionStrategy
  fixedCount: number | null
  seed: number | null
  maxIterations: number
  combinationFields: string[]
  redactFields: string[]
}

export function createCaseDatasetBinding(): CaseDatasetBinding {
  return {
    datasetId: null,
    datasetVersion: null,
    strictSchema: false,
    strategy: 'sequential',
    fixedCount: null,
    seed: null,
    maxIterations: 1000,
    combinationFields: [],
    redactFields: [],
  }
}

export function buildCaseDatasetConfig(binding: CaseDatasetBinding): Record<string, unknown> {
  if (binding.datasetId == null) return {}
  return {
    dataset_strict_schema: binding.strictSchema,
    dataset_strategy: binding.strategy,
    dataset_fixed_count: binding.fixedCount,
    dataset_seed: binding.seed,
    dataset_max_iterations: binding.maxIterations,
    dataset_combination_fields: binding.combinationFields,
    dataset_redact_fields: binding.redactFields,
    dataset_prepare_actions: [],
  }
}
