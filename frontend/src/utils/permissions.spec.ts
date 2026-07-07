import { describe, expect, it } from 'vitest'

import {
  canEditProjectAssets,
  canManageSystem,
  hasAnyRole,
  normalizeRole,
  type UserRole,
} from './permissions'

describe('permissions utilities', () => {
  it('normalizes known roles and rejects unknown values', () => {
    expect(normalizeRole('admin')).toBe('admin')
    expect(normalizeRole('engineer')).toBe('engineer')
    expect(normalizeRole('tester')).toBe('tester')
    expect(normalizeRole('viewer')).toBe('viewer')
    expect(normalizeRole('owner')).toBeNull()
    expect(normalizeRole(null)).toBeNull()
  })

  it('allows unrestricted checks when no allowed roles are provided', () => {
    expect(hasAnyRole(null)).toBe(true)
    expect(hasAnyRole('viewer', [])).toBe(true)
  })

  it('checks role-specific capabilities', () => {
    const editorRoles: UserRole[] = ['admin', 'engineer']

    expect(hasAnyRole('engineer', editorRoles)).toBe(true)
    expect(hasAnyRole('viewer', editorRoles)).toBe(false)
    expect(canManageSystem('admin')).toBe(true)
    expect(canManageSystem('engineer')).toBe(false)
    expect(canEditProjectAssets('engineer')).toBe(true)
    expect(canEditProjectAssets('tester')).toBe(false)
  })
})
