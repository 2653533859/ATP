import { describe, expect, it } from 'vitest'

import {
  API_REQUEST_TEMPLATES,
  ASSERTION_PRESETS,
  COOKIE_PRESETS,
  DYNAMIC_VARIABLE_PRESETS,
  ENVIRONMENT_VARIABLE_PRESETS,
  EXTRACTION_PRESETS,
  HEADER_PRESETS,
  PARAM_PRESETS,
  SCENARIO_TEMPLATES,
} from './apiTemplates'
import { API_BODY_TEMPLATES } from './smartJson'

describe('apiTemplates library', () => {
  it('provides unique IDs and valid definitions across all preset groups', () => {
    const groups = [
      DYNAMIC_VARIABLE_PRESETS,
      HEADER_PRESETS,
      PARAM_PRESETS,
      COOKIE_PRESETS,
      API_REQUEST_TEMPLATES,
      ASSERTION_PRESETS,
      EXTRACTION_PRESETS,
      SCENARIO_TEMPLATES,
      ENVIRONMENT_VARIABLE_PRESETS,
      API_BODY_TEMPLATES,
    ]
    for (const group of groups) {
      expect(group.length).toBeGreaterThan(0)
      const ids = group.map((item) => item.id)
      expect(new Set(ids).size).toBe(ids.length)
    }
  })

  it('includes valid dynamic variable tokens matching backend syntax', () => {
    for (const preset of DYNAMIC_VARIABLE_PRESETS) {
      expect(preset.token).toMatch(/^\{\{\$[a-z_]+(?:\([^()]+\))?\}\}$/)
    }
  })

  it('provides valid JSON strings for all API body templates', () => {
    for (const tpl of API_BODY_TEMPLATES) {
      expect(() => JSON.parse(tpl.value)).not.toThrow()
    }
  })

  it('defines multi-step scenario skeletons with assertions and step data', () => {
    expect(SCENARIO_TEMPLATES.length).toBeGreaterThanOrEqual(3)
    for (const scenario of SCENARIO_TEMPLATES) {
      expect(scenario.steps.length).toBeGreaterThanOrEqual(2)
      for (const step of scenario.steps) {
        expect(step.name).toBeTruthy()
        expect(step.url).toContain('{{base_url}}')
      }
    }
  })

  it('defines curated environment variable packs with non-empty unique keys', () => {
    expect(ENVIRONMENT_VARIABLE_PRESETS.length).toBeGreaterThanOrEqual(5)
    for (const preset of ENVIRONMENT_VARIABLE_PRESETS) {
      expect(preset.variables.length).toBeGreaterThan(0)
      const keys = preset.variables.map((item) => item.key)
      expect(new Set(keys).size).toBe(keys.length)
    }
  })
})
