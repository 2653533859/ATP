import type { LocationQueryValue, RouteLocationNormalizedLoaded, RouteLocationRaw } from 'vue-router'

export function projectIdFromQuery(value: LocationQueryValue | LocationQueryValue[]): number | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  if (!raw) return undefined
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

export function selectAvailableProjectId(
  requestedId: number | undefined,
  projects: Array<{ id: number }>,
): number | undefined {
  if (requestedId && projects.some((project) => project.id === requestedId)) return requestedId
  return projects[0]?.id
}

export function projectSelectionLocation(
  route: Pick<RouteLocationNormalizedLoaded, 'name' | 'params' | 'path' | 'query'>,
  projectId: number,
): RouteLocationRaw {
  const query = { ...route.query, project_id: String(projectId) }
  if (route.params.projectId && route.name) {
    return {
      name: route.name,
      params: { ...route.params, projectId: String(projectId) },
      query,
    }
  }
  return { path: route.path, query }
}

export function projectContextRenderKey(
  route: Pick<RouteLocationNormalizedLoaded, 'name' | 'params' | 'path' | 'query'>,
): string {
  const rawProjectId = route.query.project_id ?? route.params.projectId
  const projectId = Array.isArray(rawProjectId) ? rawProjectId[0] : rawProjectId
  return `${String(route.name ?? route.path)}:${projectId || 'none'}`
}
