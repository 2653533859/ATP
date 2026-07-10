export interface EnvironmentSummary {
  id: number
  name: string
}

export function buildRunPayload(environmentId: number | null | undefined): { env_id?: number } {
  return environmentId ? { env_id: environmentId } : {}
}

export function buildEnvironmentOptions(environments: EnvironmentSummary[]) {
  return environments.map((environment) => ({ label: environment.name, value: environment.id }))
}

// 命名路由：run-detail 的 path 只在 router/index.ts 定义一次，这里不重复字符串路径
export function buildRunDetailLocation(runId: number) {
  return { name: 'run-detail', params: { runId } }
}
