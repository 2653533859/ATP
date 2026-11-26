import { describe, expect, it } from 'vitest'

import type { ApiContractAssetItem, ApiSchemaAssetItem } from '@/api'
import {
  buildSchemaDerivedTemplates,
  extractOpenApiRequestTemplates,
  generateSampleFromJsonSchema,
} from './schemaSampleGenerator'

describe('schemaSampleGenerator', () => {
  it('generates nested objects, arrays, $ref, allOf, oneOf, and respects hint precedence', () => {
    const schema = {
      $defs: {
        Tag: {
          type: 'object',
          properties: {
            code: { type: 'string', default: 'tag-default' },
            weight: { type: 'integer', minimum: 5 },
          },
        },
      },
      type: 'object',
      properties: {
        request_id: { type: 'string', format: 'uuid' },
        email: { type: 'string', format: 'email' },
        created_at: { type: 'string', format: 'date-time' },
        biz_date: { type: 'string', format: 'date' },
        phone: { type: 'string' },
        status: { type: 'string', enum: ['draft', 'published'] },
        example_field: { type: 'string', example: 'explicit-example', default: 'ignored-default' },
        tags: { type: 'array', items: { $ref: '#/$defs/Tag' } },
        composite: {
          allOf: [
            { type: 'object', properties: { a: { type: 'boolean' } } },
            { type: 'object', properties: { b: { type: 'number', minimum: 2.5 } } },
          ],
        },
        union: {
          oneOf: [{ type: 'null' }, { type: 'string', const: 'fixed-union' }],
        },
      },
    }

    const dynamicSample = generateSampleFromJsonSchema(schema) as Record<string, unknown>
    expect(dynamicSample).toEqual({
      request_id: '{{$uuid}}',
      email: '{{$random_email}}',
      created_at: '{{$iso_now}}',
      biz_date: '{{$date}}',
      phone: '{{$random_phone}}',
      status: 'draft',
      example_field: 'explicit-example',
      tags: [{ code: 'tag-default', weight: 5 }],
      composite: { a: true, b: 2.5 },
      union: 'fixed-union',
    })

    const staticSample = generateSampleFromJsonSchema(schema, { useDynamicVars: false }) as Record<string, unknown>
    expect(staticSample.email).toBe('user@example.com')
    expect(staticSample.request_id).toBe('550e8400-e29b-41d4-a716-446655440000')
  })

  it('guards against circular $ref without infinite recursion', () => {
    const circular = {
      $defs: {
        Node: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            next: { $ref: '#/$defs/Node' },
          },
        },
      },
      $ref: '#/$defs/Node',
    }

    const sample = generateSampleFromJsonSchema(circular) as Record<string, unknown>
    expect(sample.name).toBe('sample_name')
    expect(sample.next).toEqual({})
  })

  it('extracts request body templates from OpenAPI 3 and Swagger 2 contracts and merges with schema assets', () => {
    const openapiDef = {
      openapi: '3.0.3',
      components: {
        schemas: {
          CreateUser: {
            type: 'object',
            properties: {
              email: { type: 'string', format: 'email' },
              role: { type: 'string', enum: ['tester', 'admin'] },
            },
          },
        },
      },
      paths: {
        '/users': {
          get: { summary: 'Ignored GET' },
          post: {
            summary: 'Create User',
            requestBody: {
              content: {
                'application/json': {
                  schema: { $ref: '#/components/schemas/CreateUser' },
                },
              },
            },
          },
        },
      },
    }

    const openapiTemplates = extractOpenApiRequestTemplates('UserService', 'openapi', openapiDef)
    expect(openapiTemplates).toHaveLength(1)
    expect(openapiTemplates[0].group).toBe('contract')
    expect(openapiTemplates[0].label).toContain('POST /users')
    expect(JSON.parse(openapiTemplates[0].value)).toEqual({
      email: '{{$random_email}}',
      role: 'tester',
    })

    const swaggerDef = {
      swagger: '2.0',
      paths: {
        '/orders': {
          put: {
            summary: 'Update Order',
            parameters: [
              {
                in: 'body',
                name: 'body',
                schema: {
                  type: 'object',
                  properties: { amount: { type: 'number', minimum: 10 } },
                },
              },
            ],
          },
        },
      },
    }
    const swaggerTemplates = extractOpenApiRequestTemplates('OrderAPI', 'swagger', swaggerDef)
    expect(swaggerTemplates).toHaveLength(1)
    expect(JSON.parse(swaggerTemplates[0].value)).toEqual({ amount: 10 })

    const schemaAsset: ApiSchemaAssetItem = {
      id: 9,
      project_id: 1,
      name: 'AuthLoginPayload',
      definition: {
        type: 'object',
        properties: { username: { type: 'string', default: 'qa_bot' } },
      },
      version: 1,
      created_at: '',
      updated_at: '',
    }
    const contractAsset: ApiContractAssetItem = {
      id: 3,
      project_id: 1,
      name: 'UserService',
      role: 'provider',
      format: 'openapi',
      definition: openapiDef,
      version: 1,
      created_at: '',
      updated_at: '',
    }

    const combined = buildSchemaDerivedTemplates([schemaAsset], [contractAsset])
    expect(combined).toHaveLength(2)
    expect(combined[0].group).toBe('schema')
    expect(combined[0].label).toBe('Schema · AuthLoginPayload')
    expect(combined[1].group).toBe('contract')
  })

  it('keeps unique template IDs for Chinese contracts and preserves sibling properties inside allOf', () => {
    const schemaWithSiblingAllOf = {
      $defs: {
        Base: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
          },
        },
        Extra: {
          allOf: [
            { type: 'object', properties: { tag: { type: 'string', default: 'nested' } } },
          ],
        },
      },
      allOf: [{ $ref: '#/$defs/Base' }, { $ref: '#/$defs/Extra' }],
      properties: {
        remark: { type: 'string', example: 'sibling-ok' },
      },
    }

    expect(generateSampleFromJsonSchema(schemaWithSiblingAllOf)).toEqual({
      id: '{{$uuid}}',
      tag: 'nested',
      remark: 'sibling-ok',
    })

    const contracts: ApiContractAssetItem[] = [
      {
        id: 101,
        project_id: 1,
        name: '用户服务契约',
        role: 'provider',
        format: 'openapi',
        definition: {
          openapi: '3.0.3',
          paths: {
            '/users/{id}': {
              post: { requestBody: { content: { 'application/json': { schema: { type: 'object', properties: { a: { type: 'string' } } } } } } },
            },
            '/users/id': {
              post: { requestBody: { content: { 'application/json': { schema: { type: 'object', properties: { b: { type: 'string' } } } } } } },
            },
          },
        },
        version: 1,
        created_at: '',
        updated_at: '',
      },
      {
        id: 102,
        project_id: 1,
        name: '订单服务契约',
        role: 'consumer',
        format: 'openapi',
        definition: {
          openapi: '3.0.3',
          paths: {
            '/users/{id}': {
              post: { requestBody: { content: { 'application/json': { schema: { type: 'object', properties: { c: { type: 'string' } } } } } } },
            },
          },
        },
        version: 1,
        created_at: '',
        updated_at: '',
      },
    ]

    const derived = buildSchemaDerivedTemplates([], contracts)
    expect(derived).toHaveLength(3)
    const ids = derived.map((item) => item.id)
    expect(new Set(ids).size).toBe(3)
  })
})
