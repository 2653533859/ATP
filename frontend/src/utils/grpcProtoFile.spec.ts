import { describe, expect, it } from 'vitest'
import {
  GrpcProtoFileError,
  MAX_GRPC_PROTO_FILE_SIZE,
  MAX_GRPC_PROTO_FILES,
  readGrpcProtoFile,
  validateGrpcProtoBundle,
} from './grpcProtoFile'

function file(name: string, size: number, content: string | Promise<string>) {
  return { name, size, text: () => Promise.resolve(content) }
}

describe('readGrpcProtoFile', () => {
  it('reads a valid proto source file', async () => {
    await expect(readGrpcProtoFile(file('user.PROTO', 20, 'syntax = "proto3";')))
      .resolves.toBe('syntax = "proto3";')
  })

  it('rejects a non-proto file', async () => {
    await expect(readGrpcProtoFile(file('user.txt', 20, 'syntax = "proto3";')))
      .rejects.toMatchObject({ reason: 'extension' })
  })

  it('rejects files over the browser-side size limit', async () => {
    await expect(readGrpcProtoFile(file('user.proto', MAX_GRPC_PROTO_FILE_SIZE + 1, 'source')))
      .rejects.toMatchObject({ reason: 'size' })
  })

  it('rejects an empty proto source file', async () => {
    await expect(readGrpcProtoFile(file('user.proto', 0, ' \n\t')))
      .rejects.toBeInstanceOf(GrpcProtoFileError)
  })

  it('rejects an oversized or over-populated proto bundle', () => {
    expect(() => validateGrpcProtoBundle({
      'one.proto': 'source',
      'two.proto': 'source',
    })).not.toThrow()
    const tooMany = Object.fromEntries(Array.from({ length: MAX_GRPC_PROTO_FILES + 1 }, (_, index) => [`${index}.proto`, 'x']))
    expect(() => validateGrpcProtoBundle(tooMany)).toThrowError(GrpcProtoFileError)
    expect(() => validateGrpcProtoBundle({ 'large.proto': 'x'.repeat(8 * 1024 * 1024 + 1) }))
      .toThrowError(GrpcProtoFileError)
  })
})
