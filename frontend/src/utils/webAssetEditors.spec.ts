import { describe, expect, it } from 'vitest'

import {
  parseElementRefsText,
  parseFallbackLocatorsText,
  parseIgnoreRegionsText,
  parseLocatorText,
  parsePageActionsText,
  serializeElementRefs,
  serializeFallbackLocators,
  serializeIgnoreRegions,
  serializeLocator,
  serializePageActions,
} from './webAssetEditors'

describe('webAssetEditors helpers', () => {
  it('parses and serializes locators and fallbacks while preserving extra properties', () => {
    const loc = parseLocatorText('{"strategy":"role","value":"button","name":"登录","exact":true,"frame":"main"}')
    expect(loc.valid).toBe(true)
    expect(loc.row).toEqual({ strategy: 'role', value: 'button', name: '登录', exact: true, extra: { frame: 'main' } })
    expect(JSON.parse(serializeLocator(loc.row))).toEqual({
      strategy: 'role',
      value: 'button',
      name: '登录',
      exact: true,
      frame: 'main',
    })

    const fallbacks = parseFallbackLocatorsText('[{"strategy":"css","value":"#submit"}]')
    expect(fallbacks.valid).toBe(true)
    expect(JSON.parse(serializeFallbackLocators(fallbacks.rows))).toEqual([{ strategy: 'css', value: '#submit' }])
  })

  it('parses and serializes page object element refs, actions, and visual ignore regions', () => {
    const refs = parseElementRefsText('[{"asset_id":5,"alias":"submitBtn"}]')
    expect(refs.valid).toBe(true)
    expect(JSON.parse(serializeElementRefs(refs.rows))).toEqual([{ asset_id: 5, alias: 'submitBtn' }])

    const actions = parsePageActionsText(
      '[{"name":"submit","step":"click","alias":"submitBtn"},{"name":"fillUser","step":"fill","alias":"userInput","params":{"text":"alice","delay":10}}]',
    )
    expect(actions.valid).toBe(true)
    expect(actions.rows[1].value).toBe('alice')
    expect(JSON.parse(serializePageActions(actions.rows))).toEqual([
      { name: 'submit', step: 'click', alias: 'submitBtn' },
      { name: 'fillUser', step: 'fill', alias: 'userInput', params: { text: 'alice', delay: 10 } },
    ])

    const regions = parseIgnoreRegionsText('[{"selector":".timestamp"},{"x":10,"y":20,"width":100,"height":40}]')
    expect(regions.valid).toBe(true)
    expect(regions.rows[0].mode).toBe('selector')
    expect(regions.rows[1].mode).toBe('box')
    expect(JSON.parse(serializeIgnoreRegions(regions.rows))).toEqual([
      { selector: '.timestamp' },
      { x: 10, y: 20, width: 100, height: 40 },
    ])
  })

  it('rejects invalid JSON structures cleanly', () => {
    expect(parseLocatorText('[]').valid).toBe(false)
    expect(parseFallbackLocatorsText('{}').valid).toBe(false)
    expect(parseElementRefsText('{bad').valid).toBe(false)
    expect(parsePageActionsText('"text"').valid).toBe(false)
    expect(parseIgnoreRegionsText('123').valid).toBe(false)
  })
})
