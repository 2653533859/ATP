import type { ApiContractAssetItem, ApiSchemaAssetItem } from '@/api'
import type { JsonTemplateOption } from '@/utils/smartJson'

export interface GenerateSchemaSampleOptions {
  rootDoc?: Record<string, unknown>
  useDynamicVars?: boolean
  maxDepth?: number
}

const DEFAULT_MAX_DEPTH = 6
const MAX_OBJECT_PROPERTIES = 50
const MAX_CONTRACT_OPS = 20
const HTTP_BODY_METHODS = ['post', 'put', 'patch', 'delete'] as const

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function resolveJsonPointer(doc: Record<string, unknown>, ref: string): unknown {
  if (!ref.startsWith('#/')) return null
  const parts = ref
    .slice(2)
    .split('/')
    .map((part) => part.replace(/~1/g, '/').replace(/~0/g, '~'))
  let cursor: unknown = doc
  for (const part of parts) {
    if (!isPlainObject(cursor)) return null
    cursor = cursor[part]
  }
  return cursor
}

function resolveSchemaNode(
  node: Record<string, unknown>,
  rootDoc: Record<string, unknown>,
  visitedRefs: Set<string>,
): Record<string, unknown> | null {
  let current: Record<string, unknown> = node
  while (typeof current.$ref === 'string') {
    const ref = current.$ref
    if (!ref.startsWith('#/') || visitedRefs.has(ref)) {
      return null
    }
    visitedRefs.add(ref)
    const target = resolveJsonPointer(rootDoc, ref)
    if (!isPlainObject(target)) {
      return null
    }
    const { $ref: _ignored, ...rest } = current
    current = { ...target, ...rest }
  }
  return current
}

function collectAllOfParts(
  schemas: unknown[],
  rootDoc: Record<string, unknown>,
  visitedRefs: Set<string>,
  mergedProps: Record<string, unknown>,
  mergedRequired: string[],
  state: { baseType: unknown },
): void {
  for (const rawItem of schemas) {
    if (!isPlainObject(rawItem)) continue
    const branchRefs = new Set(visitedRefs)
    const resolved = resolveSchemaNode(rawItem, rootDoc, branchRefs)
    if (!resolved) continue
    if (Array.isArray(resolved.allOf) && resolved.allOf.length > 0) {
      collectAllOfParts(resolved.allOf, rootDoc, branchRefs, mergedProps, mergedRequired, state)
    }
    if (resolved.type && !state.baseType) {
      state.baseType = resolved.type
    }
    if (isPlainObject(resolved.properties)) {
      Object.assign(mergedProps, resolved.properties)
    }
    if (Array.isArray(resolved.required)) {
      for (const req of resolved.required) {
        if (typeof req === 'string' && !mergedRequired.includes(req)) {
          mergedRequired.push(req)
        }
      }
    }
  }
}

function mergeAllOfSchemas(
  schemas: unknown[],
  rootDoc: Record<string, unknown>,
  visitedRefs: Set<string>,
  parentSchema?: Record<string, unknown>,
): Record<string, unknown> {
  const mergedProps: Record<string, unknown> = {}
  const mergedRequired: string[] = []
  const state: { baseType: unknown } = { baseType: undefined }

  collectAllOfParts(schemas, rootDoc, visitedRefs, mergedProps, mergedRequired, state)

  if (parentSchema) {
    if (isPlainObject(parentSchema.properties)) {
      Object.assign(mergedProps, parentSchema.properties)
    }
    if (Array.isArray(parentSchema.required)) {
      for (const req of parentSchema.required) {
        if (typeof req === 'string' && !mergedRequired.includes(req)) {
          mergedRequired.push(req)
        }
      }
    }
    if (parentSchema.type && !state.baseType) {
      state.baseType = parentSchema.type
    }
  }

  return {
    type: state.baseType ?? 'object',
    properties: mergedProps,
    ...(mergedRequired.length ? { required: mergedRequired } : {}),
  }
}

function pickNonNullBranch(variants: unknown[]): Record<string, unknown> | null {
  for (const item of variants) {
    if (!isPlainObject(item)) continue
    if (item.type === 'null') continue
    return item
  }
  const first = variants.find(isPlainObject)
  return first ?? null
}

function pickStringSample(
  schema: Record<string, unknown>,
  fieldName: string,
  useDynamicVars: boolean,
): string {
  const format = typeof schema.format === 'string' ? schema.format.toLowerCase() : ''
  const lowerKey = fieldName.toLowerCase()

  if (useDynamicVars) {
    if (format === 'uuid' || /(?:uuid|request_id|trace_id)/.test(lowerKey)) {
      return '{{$uuid}}'
    }
    if (format === 'email' || lowerKey.includes('email')) {
      return '{{$random_email}}'
    }
    if (format === 'date-time' || /(?:created|updated|occurred)_at$/.test(lowerKey)) {
      return '{{$iso_now}}'
    }
    if (format === 'date' || /date$/.test(lowerKey)) {
      return '{{$date}}'
    }
    if (/phone|mobile/.test(lowerKey)) {
      return '{{$random_phone}}'
    }
  } else {
    if (format === 'uuid') return '550e8400-e29b-41d4-a716-446655440000'
    if (format === 'email') return 'user@example.com'
    if (format === 'date-time') return '2026-01-01T00:00:00Z'
    if (format === 'date') return '2026-01-01'
  }

  if (format === 'uri' || format === 'url') return 'https://example.com'
  if (format === 'ipv4') return '127.0.0.1'
  if (format === 'ipv6') return '::1'
  return fieldName ? `sample_${fieldName}` : 'sample'
}

function generateNode(
  rawNode: unknown,
  fieldName: string,
  rootDoc: Record<string, unknown>,
  useDynamicVars: boolean,
  depth: number,
  maxDepth: number,
  visitedRefs: Set<string>,
): unknown {
  if (depth > maxDepth || !isPlainObject(rawNode)) {
    return {}
  }

  const branchRefs = new Set(visitedRefs)
  const resolved = resolveSchemaNode(rawNode, rootDoc, branchRefs)
  if (!resolved) {
    return {}
  }

  if (Object.prototype.hasOwnProperty.call(resolved, 'example')) return resolved.example
  if (Array.isArray(resolved.examples) && resolved.examples.length > 0) return resolved.examples[0]
  if (Object.prototype.hasOwnProperty.call(resolved, 'default')) return resolved.default
  if (Object.prototype.hasOwnProperty.call(resolved, 'const')) return resolved.const
  if (Array.isArray(resolved.enum) && resolved.enum.length > 0) return resolved.enum[0]

  if (Array.isArray(resolved.allOf) && resolved.allOf.length > 0) {
    const merged = mergeAllOfSchemas(resolved.allOf, rootDoc, branchRefs, resolved)
    return generateNode(merged, fieldName, rootDoc, useDynamicVars, depth, maxDepth, branchRefs)
  }

  const unionList = Array.isArray(resolved.oneOf)
    ? resolved.oneOf
    : Array.isArray(resolved.anyOf)
      ? resolved.anyOf
      : null
  if (unionList && unionList.length > 0) {
    const picked = pickNonNullBranch(unionList)
    if (picked) {
      return generateNode(picked, fieldName, rootDoc, useDynamicVars, depth, maxDepth, branchRefs)
    }
  }

  let primaryType = resolved.type
  if (Array.isArray(primaryType)) {
    primaryType = primaryType.find((item) => item !== 'null') ?? primaryType[0]
  }

  if (primaryType === 'object' || (!primaryType && isPlainObject(resolved.properties))) {
    const out: Record<string, unknown> = {}
    if (isPlainObject(resolved.properties)) {
      const entries = Object.entries(resolved.properties).slice(0, MAX_OBJECT_PROPERTIES)
      for (const [propKey, propSchema] of entries) {
        out[propKey] = generateNode(propSchema, propKey, rootDoc, useDynamicVars, depth + 1, maxDepth, branchRefs)
      }
      return out
    }
    if (isPlainObject(resolved.additionalProperties)) {
      out.key = generateNode(
        resolved.additionalProperties,
        'key',
        rootDoc,
        useDynamicVars,
        depth + 1,
        maxDepth,
        branchRefs,
      )
    }
    return out
  }

  if (primaryType === 'array') {
    if (isPlainObject(resolved.items)) {
      return [generateNode(resolved.items, fieldName, rootDoc, useDynamicVars, depth + 1, maxDepth, branchRefs)]
    }
    return []
  }

  if (primaryType === 'integer') {
    const minVal = typeof resolved.minimum === 'number' ? Math.ceil(resolved.minimum) : 1
    const maxVal = typeof resolved.maximum === 'number' ? Math.floor(resolved.maximum) : minVal + 100
    let candidate = Math.min(minVal, maxVal)
    if (typeof resolved.multipleOf === 'number' && resolved.multipleOf > 0) {
      candidate = Math.ceil(candidate / resolved.multipleOf) * resolved.multipleOf
    }
    return candidate
  }

  if (primaryType === 'number') {
    if (typeof resolved.minimum === 'number') return resolved.minimum
    if (typeof resolved.maximum === 'number') return Math.min(1.5, resolved.maximum)
    return 1.5
  }

  if (primaryType === 'boolean') return true
  if (primaryType === 'null') return null
  if (primaryType === 'string' || typeof resolved.format === 'string') {
    return pickStringSample(resolved, fieldName, useDynamicVars)
  }

  return {}
}

export function generateSampleFromJsonSchema(
  schema: Record<string, unknown>,
  options: GenerateSchemaSampleOptions = {},
): unknown {
  if (!isPlainObject(schema)) return {}
  const rootDoc = options.rootDoc ?? schema
  const useDynamicVars = options.useDynamicVars ?? true
  const maxDepth = options.maxDepth ?? DEFAULT_MAX_DEPTH
  return generateNode(schema, '', rootDoc, useDynamicVars, 0, maxDepth, new Set<string>())
}

function makeCompactPreview(sample: unknown): string {
  const compact = JSON.stringify(sample) ?? '{}'
  return compact.length > 80 ? `${compact.slice(0, 77)}...` : compact
}

function slugifyId(raw: string): string {
  return raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function findRequestBodySchema(
  operation: Record<string, unknown>,
  rootDoc: Record<string, unknown>,
): Record<string, unknown> | null {
  // OpenAPI 3 requestBody
  if (isPlainObject(operation.requestBody)) {
    const bodyObj = resolveSchemaNode(operation.requestBody, rootDoc, new Set()) ?? operation.requestBody
    if (isPlainObject(bodyObj.content)) {
      const jsonContent = isPlainObject(bodyObj.content['application/json'])
        ? bodyObj.content['application/json']
        : Object.entries(bodyObj.content).find(([ct, val]) => ct.includes('json') && isPlainObject(val))?.[1]
      if (isPlainObject(jsonContent) && isPlainObject(jsonContent.schema)) {
        return jsonContent.schema
      }
    }
  }

  // Swagger 2 body parameter
  if (Array.isArray(operation.parameters)) {
    for (const rawParam of operation.parameters) {
      if (!isPlainObject(rawParam)) continue
      const param = resolveSchemaNode(rawParam, rootDoc, new Set()) ?? rawParam
      if (param.in === 'body' && isPlainObject(param.schema)) {
        return param.schema
      }
    }
  }

  return null
}

export function extractOpenApiRequestTemplates(
  contractName: string,
  format: string,
  definition: Record<string, unknown>,
  contractId?: number | string,
): JsonTemplateOption[] {
  if (!isPlainObject(definition)) return []
  const idPrefix = contractId !== undefined ? `contract_${contractId}` : `contract_${slugifyId(contractName) || 'doc'}`

  if (format === 'json_schema' || !isPlainObject(definition.paths)) {
    const sample = generateSampleFromJsonSchema(definition, { rootDoc: definition, useDynamicVars: true })
    return [
      {
        id: `${idPrefix}_schema`,
        label: `[${contractName}] Schema 示例`,
        preview: makeCompactPreview(sample),
        value: JSON.stringify(sample, null, 2),
        group: 'schema',
      },
    ]
  }

  const results: JsonTemplateOption[] = []
  for (const [pathKey, rawPathItem] of Object.entries(definition.paths)) {
    if (!isPlainObject(rawPathItem)) continue
    const pathItem = resolveSchemaNode(rawPathItem, definition, new Set()) ?? rawPathItem
    for (const method of HTTP_BODY_METHODS) {
      const rawOp = pathItem[method]
      if (!isPlainObject(rawOp)) continue
      const operation = resolveSchemaNode(rawOp, definition, new Set()) ?? rawOp
      const schema = findRequestBodySchema(operation, definition)
      if (!schema) continue

      const sample = generateSampleFromJsonSchema(schema, { rootDoc: definition, useDynamicVars: true })
      const summary = typeof operation.summary === 'string' && operation.summary.trim()
        ? ` · ${operation.summary.trim()}`
        : ''
      const opIndex = results.length
      results.push({
        id: `${idPrefix}_op_${opIndex}_${method}_${slugifyId(pathKey) || 'path'}`,
        label: `[${contractName}] ${method.toUpperCase()} ${pathKey}${summary}`,
        preview: makeCompactPreview(sample),
        value: JSON.stringify(sample, null, 2),
        group: 'contract',
      })
      if (results.length >= MAX_CONTRACT_OPS) {
        return results
      }
    }
  }

  return results
}

export function buildSchemaDerivedTemplates(
  schemaAssets: readonly ApiSchemaAssetItem[] = [],
  contractAssets: readonly ApiContractAssetItem[] = [],
): JsonTemplateOption[] {
  const templates: JsonTemplateOption[] = []

  for (const asset of schemaAssets) {
    if (!isPlainObject(asset.definition) || Object.keys(asset.definition).length === 0) continue
    const sample = generateSampleFromJsonSchema(asset.definition, {
      rootDoc: asset.definition,
      useDynamicVars: true,
    })
    templates.push({
      id: `schema_asset_${asset.id}`,
      label: `Schema · ${asset.name}`,
      preview: makeCompactPreview(sample),
      value: JSON.stringify(sample, null, 2),
      group: 'schema',
    })
  }

  for (const contract of contractAssets) {
    templates.push(
      ...extractOpenApiRequestTemplates(contract.name, contract.format, contract.definition, contract.id),
    )
  }

  return templates
}
