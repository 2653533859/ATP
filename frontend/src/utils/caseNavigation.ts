import type { RouteLocationRaw } from 'vue-router'

export type CaseNavigationReviewStatus = 'pending' | 'approved' | 'rejected'

type RouteValue = string | number | null | undefined | Array<string | null>

export type CaseRouteSelection = {
  projectId: number | null
  moduleId: number | null
  reviewStatus: CaseNavigationReviewStatus | undefined
}

export type CaseNavigationContext = {
  projectId?: number | null
  moduleId?: number | null
  reviewStatus?: CaseNavigationReviewStatus
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

export function buildCasesQuery(context: CaseNavigationContext): Record<string, string> {
  const query: Record<string, string> = {}
  if (context.projectId) {
    query.project_id = String(context.projectId)
  }
  if (context.moduleId) {
    query.module_id = String(context.moduleId)
  }
  if (context.reviewStatus) {
    query.review_status = context.reviewStatus
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
    reviewStatus: parseReviewStatus(route.query.review_status),
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
