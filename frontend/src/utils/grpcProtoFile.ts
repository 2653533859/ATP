export const MAX_GRPC_PROTO_FILE_SIZE = 1024 * 1024
export const MAX_GRPC_PROTO_FILES = 64
export const MAX_GRPC_PROTO_BUNDLE_SIZE = 8 * 1024 * 1024

export type GrpcProtoFileErrorReason = 'extension' | 'size' | 'empty' | 'bundle_size'

export class GrpcProtoFileError extends Error {
  constructor(public readonly reason: GrpcProtoFileErrorReason) {
    super(`Invalid gRPC Proto file: ${reason}`)
    this.name = 'GrpcProtoFileError'
  }
}

export async function readGrpcProtoFile(
  file: Pick<File, 'name' | 'size' | 'text'>,
): Promise<string> {
  if (!file.name.toLowerCase().endsWith('.proto')) {
    throw new GrpcProtoFileError('extension')
  }
  if (file.size > MAX_GRPC_PROTO_FILE_SIZE) {
    throw new GrpcProtoFileError('size')
  }
  const content = await file.text()
  if (!content.trim()) {
    throw new GrpcProtoFileError('empty')
  }
  return content
}

export function validateGrpcProtoBundle(files: Record<string, string>, entryContent = ''): void {
  const auxiliaryFiles = Object.keys(files).filter((name) => name !== 'service.proto')
  if (auxiliaryFiles.length + (entryContent.trim() ? 1 : 0) > MAX_GRPC_PROTO_FILES) {
    throw new GrpcProtoFileError('bundle_size')
  }
  const size = new Blob([...Object.values(files), entryContent]).size
  if (size > MAX_GRPC_PROTO_BUNDLE_SIZE) {
    throw new GrpcProtoFileError('bundle_size')
  }
}
