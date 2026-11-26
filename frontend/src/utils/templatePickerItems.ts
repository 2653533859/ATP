import {
  DYNAMIC_VARIABLE_PRESETS,
  type ApiRequestTemplate,
  type EnvironmentVariablePreset,
  type KvPresetOption,
} from '@/utils/apiTemplates'
import type { JsonTemplateOption } from '@/utils/smartJson'

export interface TemplatePickerItem {
  id: string
  label: string
  preview?: string
  description?: string
  badge?: string
  badgeTone?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger'
  group?: string
  deletable?: boolean
}

const METHOD_BADGE_TONE: Record<string, TemplatePickerItem['badgeTone']> = {
  GET: 'primary',
  POST: 'success',
  PUT: 'warning',
  PATCH: 'warning',
  DELETE: 'danger',
  HEAD: 'neutral',
  OPTIONS: 'neutral',
}

export function toDynamicVarPickerItems(groupLabels: {
  id: string
  time: string
  random: string
}): TemplatePickerItem[] {
  return DYNAMIC_VARIABLE_PRESETS.map((dv) => ({
    id: dv.id,
    label: dv.label,
    preview: dv.token,
    badge: dv.suggestedKey,
    badgeTone: 'neutral',
    group: groupLabels[dv.category],
  }))
}

export function toBodyTemplatePickerItems(
  templates: readonly JsonTemplateOption[],
  groupLabels: { builtin: string; schema: string },
): TemplatePickerItem[] {
  return templates.map((tpl) => ({
    id: tpl.id,
    label: tpl.label,
    preview: tpl.preview,
    badge: tpl.group === 'contract' ? 'OpenAPI' : tpl.group === 'schema' ? 'Schema' : undefined,
    badgeTone: tpl.group === 'contract' ? 'success' : tpl.group === 'schema' ? 'primary' : 'neutral',
    group: tpl.group === 'schema' || tpl.group === 'contract' ? groupLabels.schema : groupLabels.builtin,
  }))
}

export function toRequestTemplatePickerItems(
  builtinTemplates: readonly ApiRequestTemplate[],
  customTemplates: readonly ApiRequestTemplate[],
  groupLabels: { builtin: string; custom: string },
  canDeleteCustom: boolean,
): TemplatePickerItem[] {
  const builtin = builtinTemplates.map((tpl) => ({
    id: tpl.id,
    label: tpl.label,
    description: tpl.description,
    badge: tpl.method,
    badgeTone: METHOD_BADGE_TONE[tpl.method] || 'neutral',
    group: groupLabels.builtin,
  }))
  const custom = customTemplates.map((tpl) => ({
    id: tpl.id,
    label: tpl.label,
    description: tpl.description,
    badge: tpl.method,
    badgeTone: METHOD_BADGE_TONE[tpl.method] || 'neutral',
    group: groupLabels.custom,
    deletable: canDeleteCustom,
  }))
  return [...builtin, ...custom]
}

export function toKvPresetPickerItems(presets: readonly KvPresetOption[]): TemplatePickerItem[] {
  return presets.map((item) => ({
    id: item.id,
    label: item.label,
    preview: item.preview,
    badge: `+${Object.keys(item.entries).length}`,
    badgeTone: 'neutral',
  }))
}

export function toEnvPresetPickerItems(presets: readonly EnvironmentVariablePreset[]): TemplatePickerItem[] {
  return presets.map((preset) => ({
    id: preset.id,
    label: preset.label,
    description: preset.description,
    preview: preset.variables.map((v) => v.key).join(', '),
    badge: `+${preset.variables.length}`,
    badgeTone: 'primary',
  }))
}
