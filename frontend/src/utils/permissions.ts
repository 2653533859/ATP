export type UserRole = 'admin' | 'engineer' | 'tester' | 'viewer'

const EDITOR_ROLES: UserRole[] = ['admin', 'engineer']
const ADMIN_ROLES: UserRole[] = ['admin']

export function normalizeRole(role?: string | null): UserRole | null {
  if (role === 'admin' || role === 'engineer' || role === 'tester' || role === 'viewer') {
    return role
  }
  return null
}

export function hasAnyRole(role: string | null | undefined, allowedRoles?: readonly UserRole[]) {
  if (!allowedRoles?.length) return true
  const normalized = normalizeRole(role)
  return Boolean(normalized && allowedRoles.includes(normalized))
}

export function canManageSystem(role: string | null | undefined) {
  return hasAnyRole(role, ADMIN_ROLES)
}

export function canEditProjectAssets(role: string | null | undefined) {
  return hasAnyRole(role, EDITOR_ROLES)
}
