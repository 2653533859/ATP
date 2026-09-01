import type { RouteLocationRaw } from 'vue-router'

export type CaseNavigationReviewStatus = 'pending' | 'approved' | 'rejected'

type RouteValue = string | number | null | undefined | Array<string | null>

export type CaseRouteSelection = {
  projectId: number | null
  moduleId: number | null
  keyword: string | undefined
  reviewStatus: CaseNavigationReviewStatus | undefined
  aiGenerate: boolean
  aiDatasetId: number | null
  aiDatasetVersion: number | null
  aiMockRuleIds: number[]
}

export type CaseNavigationContext = {
  projectId?: number | null
  moduleId?: number | null
  keyword?: string
  reviewStatus?: CaseNavigationReviewStatus
  aiGenerate?: boolean
  aiDatasetId?: number | null
  aiDatasetVersion?: number | null
  aiMockRuleIds?: number[]
}

export function parsePositiveInt(value: RouteValue): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

export function parseReviewStatus(value: RouteValue): CaseNavigationReviewStatus | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  return raw === 'pending' || raw === 'approved' || raw === 'rejected' ? raw : undefined
}

export function parseRouteText(value: RouteValue): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  const text = typeof raw === 'string' ? raw.trim() : ''
  return text || undefined
}

export function parsePositiveIntList(value: RouteValue): number[] {
  const rawValues = Array.isArray(value) ? value : [value]
  return rawValues
    .flatMap((item) => String(item ?? '').split(','))
    .map((item) => Number(item.trim()))
    .filter((item, index, values) => Number.isInteger(item) && item > 0 && values.indexOf(item) === index)
}

export function buildCasesQuery(context: CaseNavigationContext): Record<string, string> {
  const query: Record<string, string> = {}
  if (context.projectId) {
    query.project_id = String(context.projectId)
  }
  if (context.moduleId) {
    query.module_id = String(context.moduleId)
  }
  if (context.keyword?.trim()) {
    query.keyword = context.keyword.trim()
  }
  if (context.reviewStatus) {
    query.review_status = context.reviewStatus
  }
  if (context.aiGenerate) {
    query.ai_generate = '1'
  }
  if (context.aiDatasetId) {
    query.ai_dataset_id = String(context.aiDatasetId)
  }
  if (context.aiDatasetVersion) {
    query.ai_dataset_version = String(context.aiDatasetVersion)
  }
  if (context.aiMockRuleIds?.length) {
    query.ai_mock_rule_ids = context.aiMockRuleIds.join(',')
  }
  return query
}

export function readCaseRouteSelection(route: {
  query: Record<string, RouteValue>
  params: Record<string, RouteValue>
}): CaseRouteSelection {
  return {
    projectId: parsePositiveInt(route.query.project_id) ?? parsePositiveInt(route.params.projectId),
    moduleId: parsePositiveInt(route.query.module_id),
    keyword: parseRouteText(route.query.keyword),
    reviewStatus: parseReviewStatus(route.query.review_status),
    aiGenerate: route.query.ai_generate === '1' || route.query.ai_generate === 'true',
    aiDatasetId: parsePositiveInt(route.query.ai_dataset_id),
    aiDatasetVersion: parsePositiveInt(route.query.ai_dataset_version),
    aiMockRuleIds: parsePositiveIntList(route.query.ai_mock_rule_ids),
  }
}

export function buildProjectCasesLocation(projectId: number): RouteLocationRaw {
  return {
    name: 'cases',
    query: buildCasesQuery({ projectId }),
  }
}

export function buildCaseDetailLocation(caseId: number, context: CaseNavigationContext): RouteLocationRaw {
  return {
    name: 'case-detail',
    params: { caseId: String(caseId) },
    query: buildCasesQuery(context),
  }
}
