import { describe, expect, it } from 'vitest'

import {
  asStringMap,
  getFirstStep,
  getProtocolConfigError,
  isRecord,
  normalizeWsMessage,
  parseFormBody,
  parseGraphqlVariables,
  resolveRequestBody,
} from './caseFormConfig'

describe('case form config helpers', () => {
  it('guards records and coerces string maps', () => {
    expect(isRecord({ a: 1 })).toBe(true)
    expect(isRecord([1, 2])).toBe(false)
    expect(isRecord(null)).toBe(false)
    expect(asStringMap({ Authorization: 'Bearer x' })).toEqual({ Authorization: 'Bearer x' })
    expect(asStringMap('nope')).toEqual({})
  })

  it('extracts the first step from steps[] or a bare single-step config', () => {
    expect(getFirstStep({ steps: [{ url: 'a' }, { url: 'b' }] })).toEqual({ url: 'a' })
    expect(getFirstStep({ url: 'single' })).toEqual({ url: 'single' })
    expect(getFirstStep({ steps: [] })).toEqual({ steps: [] })
    expect(getFirstStep(undefined)).toEqual({})
  })

  it('parses form body from object, json string, or falls back to empty', () => {
    expect(parseFormBody({ a: '1' })).toEqual({ a: '1' })
    expect(parseFormBody('{"b":"2"}')).toEqual({ b: '2' })
    expect(parseFormBody('not json')).toEqual({})
    expect(parseFormBody(42)).toEqual({})
    expect(parseFormBody('   ')).toEqual({})
  })

  it('resolves the request body by body_type', () => {
    expect(resolveRequestBody('none', 'anything', {})).toBeNull()
    expect(resolveRequestBody('form', 'ignored', { k: 'v' })).toEqual({ k: 'v' })
    expect(resolveRequestBody('json', '{"a":1}', {})).toEqual({ a: 1 })
    expect(resolveRequestBody('json', 'bad json', {})).toBe('bad json')
    expect(resolveRequestBody('json', { already: 'object' }, {})).toEqual({ already: 'object' })
    expect(resolveRequestBody('raw', 'raw text', {})).toBe('raw text')
  })

  it('parses graphql variables, defaulting to empty object', () => {
    expect(parseGraphqlVariables('{"id":1}')).toEqual({ id: 1 })
    expect(parseGraphqlVariables('')).toEqual({})
    expect(parseGraphqlVariables('   ')).toEqual({})
    expect(parseGraphqlVariables('{bad')).toEqual({})
  })

  it('validates required graphql, websocket, and grpc config fields', () => {
    expect(getProtocolConfigError('graphql', {})).toBe('graphql_endpoint_required')
    expect(getProtocolConfigError('graphql', { endpoint: '/graphql', query: '  ' })).toBe('graphql_query_required')
    expect(getProtocolConfigError('graphql', { endpoint: '/graphql', query: ' query { health } ' })).toBeNull()

    expect(getProtocolConfigError('websocket', {})).toBe('ws_url_required')
    expect(getProtocolConfigError('websocket', { url: 'ws://localhost' })).toBe('ws_messages_required')
    expect(getProtocolConfigError('websocket', { url: 'ws://localhost', messages: [{}] })).toBeNull()

    expect(getProtocolConfigError('grpc', {})).toBe('grpc_target_required')
    expect(getProtocolConfigError('grpc', { target: 'localhost:50051' })).toBe('grpc_proto_required')
    expect(getProtocolConfigError('grpc', { target: 'localhost:50051', proto_content: 'syntax = "proto3";' })).toBe('grpc_service_required')
    expect(getProtocolConfigError('grpc', {
      target: 'localhost:50051',
      proto_content: 'syntax = "proto3";',
      service: 'Health',
    })).toBe('grpc_method_required')
    expect(getProtocolConfigError('grpc', {
      target: 'localhost:50051',
      proto_content: 'syntax = "proto3";',
      service: 'Health',
      method: 'Check',
    })).toBeNull()
  })

  it('ignores protocol validation for other case types', () => {
    expect(getProtocolConfigError('api', {})).toBeNull()
    expect(getProtocolConfigError('unknown', { messages: [] })).toBeNull()
  })

  it('normalizes websocket messages by action', () => {
    expect(normalizeWsMessage({ action: 'send', data: 'hi', data_type: 'json' })).toEqual({
      action: 'send',
      data: 'hi',
      data_type: 'json',
    })
    expect(normalizeWsMessage({ action: 'receive', timeout: 5, assertions: [{ a: 1 }], extractions: [] })).toEqual({
      action: 'receive',
      timeout: 5,
      assertions: [{ a: 1 }],
      extractions: [],
    })
    expect(normalizeWsMessage({ action: 'disconnect' })).toEqual({ action: 'disconnect' })
  })
})
