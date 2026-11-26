import { beforeEach, describe, expect, it } from 'vitest'

import {
  deleteCustomRequestTemplate,
  loadCustomRequestTemplates,
  saveCustomRequestTemplate,
} from './customApiTemplates'

describe('customApiTemplates storage helper', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('saves, loads, and deletes project-scoped custom request templates', () => {
    expect(loadCustomRequestTemplates(12)).toEqual([])

    const afterFirst = saveCustomRequestTemplate(12, {
      label: '创建订单调试模板',
      description: 'POST /orders + Bearer',
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer {{token}}' },
      bodyType: 'json',
      jsonBody: { order_id: '{{$uuid}}' },
    })

    expect(afterFirst).toHaveLength(1)
    expect(afterFirst[0].id).toMatch(/^custom_/)
    expect(loadCustomRequestTemplates(12)).toHaveLength(1)
    expect(loadCustomRequestTemplates(99)).toEqual([])

    const afterDelete = deleteCustomRequestTemplate(12, afterFirst[0].id)
    expect(afterDelete).toEqual([])
    expect(loadCustomRequestTemplates(12)).toEqual([])
  })

  it('preserves HEAD/OPTIONS methods and xml bodyType round-trips', () => {
    const saved = saveCustomRequestTemplate(8, {
      label: 'XML 报文与 HEAD 探活',
      description: 'HEAD / XML',
      method: 'HEAD',
      bodyType: 'xml',
      rawBody: '<ping>{{$uuid}}</ping>',
    })

    expect(saved[0].method).toBe('HEAD')
    expect(saved[0].bodyType).toBe('xml')
    expect(saved[0].rawBody).toBe('<ping>{{$uuid}}</ping>')

    const reloaded = loadCustomRequestTemplates(8)
    expect(reloaded[0]).toMatchObject({
      method: 'HEAD',
      bodyType: 'xml',
      rawBody: '<ping>{{$uuid}}</ping>',
    })
  })
})
