import type { LocationQueryValue } from 'vue-router'

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
