import { computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { HermesSource } from '../components/hermesPanelTypes'

export type DraftModule = { id: number; name: string; selected: boolean; path: string }
export type DraftCase = { id: number; title: string; expected: string; selected: boolean; path: string }
export type DraftRegressionItem = { taskId: string; name: string; reason: string; selected: boolean; path: string }

export type PlanDraftSnapshot = {
  name: string
  objective: string
  testPoints: string[]
  moduleNames: string[]
  caseTitles: string[]
  regressionTaskIds: string[]
  regressionTaskNames: string[]
}

export type PlanDraft = {
  name: string
  objective: string
  testPoints: string[]
  scopeModules: DraftModule[]
  caseDrafts: DraftCase[]
  regressionScope: DraftRegressionItem[]
  sources: HermesSource[]
  baseline: PlanDraftSnapshot
}

export type HermesPlanDraftHandoff = {
  projectId: number
  name: string
  objective: string
  testPoints: string[]
  moduleIds: number[]
  caseIds: number[]
  regressionTaskIds: string[]
}

export type PlanDraftDiffRow = {
  key: string
  label: string
  before: string
  after: string
  changed: boolean
}

export function useHermesPlanDraft(planDraft: Ref<PlanDraft | null>) {
  const { t } = useI18n()

  const selectedModuleCount = computed(() => planDraft.value?.scopeModules.filter((item) => item.selected).length ?? 0)
  const selectedCaseCount = computed(() => planDraft.value?.caseDrafts.filter((item) => item.selected).length ?? 0)
  const selectedRegressionCount = computed(() => planDraft.value?.regressionScope.filter((item) => item.selected).length ?? 0)
  const diffRows = computed<PlanDraftDiffRow[]>(() => {
    const draft = planDraft.value
    if (!draft) return []
    const current = {
      name: draft.name,
      objective: draft.objective,
      testPoints: draft.testPoints,
      moduleNames: draft.scopeModules.filter((item) => item.selected).map((item) => item.name),
      caseTitles: draft.caseDrafts.filter((item) => item.selected).map((item) => item.title.trim()).filter(Boolean),
      regressionTaskIds: draft.regressionScope.filter((item) => item.selected).map((item) => item.taskId),
      regressionTaskNames: draft.regressionScope.filter((item) => item.selected).map((item) => item.name),
    }
    const display = (value: string | string[]) => Array.isArray(value)
      ? value.join('、') || t('hermes.plan_none_selected')
      : value.trim() || t('hermes.plan_not_filled')
    return [
      { key: 'name', label: t('hermes.plan_diff_name'), before: display(draft.baseline.name), after: display(current.name), changed: draft.baseline.name !== current.name },
      { key: 'objective', label: t('hermes.plan_diff_objective'), before: display(draft.baseline.objective), after: display(current.objective), changed: draft.baseline.objective !== current.objective },
      { key: 'testPoints', label: t('hermes.plan_diff_points'), before: display(draft.baseline.testPoints), after: display(current.testPoints), changed: JSON.stringify(draft.baseline.testPoints) !== JSON.stringify(current.testPoints) },
      { key: 'modules', label: t('hermes.plan_diff_modules'), before: display(draft.baseline.moduleNames), after: display(current.moduleNames), changed: JSON.stringify(draft.baseline.moduleNames) !== JSON.stringify(current.moduleNames) },
      { key: 'cases', label: t('hermes.plan_diff_cases'), before: display(draft.baseline.caseTitles), after: display(current.caseTitles), changed: JSON.stringify(draft.baseline.caseTitles) !== JSON.stringify(current.caseTitles) },
      { key: 'regression', label: t('hermes.plan_diff_regression'), before: display(draft.baseline.regressionTaskNames), after: display(current.regressionTaskNames), changed: JSON.stringify(draft.baseline.regressionTaskIds) !== JSON.stringify(current.regressionTaskIds) },
    ]
  })
  const changedCount = computed(() => diffRows.value.filter((row) => row.changed).length)

  function addPoint() {
    planDraft.value?.testPoints.push(t('hermes.default_plan_point'))
  }

  function removePoint(index: number) {
    if (planDraft.value && planDraft.value.testPoints.length > 1) planDraft.value.testPoints.splice(index, 1)
  }

  function buildHandoff(projectId: number): HermesPlanDraftHandoff | null {
    const draft = planDraft.value
    if (!draft) return null
    return {
      projectId,
      name: draft.name.trim().slice(0, 256),
      objective: draft.objective.trim().slice(0, 2000),
      testPoints: draft.testPoints.map((point) => point.trim().slice(0, 512)).filter(Boolean).slice(0, 16),
      moduleIds: draft.scopeModules.filter((item) => item.selected).map((item) => item.id).slice(0, 16),
      caseIds: draft.caseDrafts.filter((item) => item.selected).map((item) => item.id).slice(0, 16),
      regressionTaskIds: draft.regressionScope.filter((item) => item.selected).map((item) => item.taskId).slice(0, 16),
    }
  }

  return {
    addPoint,
    buildHandoff,
    changedCount,
    diffRows,
    removePoint,
    selectedCaseCount,
    selectedModuleCount,
    selectedRegressionCount,
  }
}
