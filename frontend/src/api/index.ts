import http from './http'

export const authApi = {
  login: (username: string, password: string) =>
    http.post<any, { access_token: string; refresh_token: string }>('/auth/login', { username, password }),

  me: () => http.get<any, { id: number; username: string; email: string; role: string }>('/auth/me'),
}

export const projectApi = {
  list: () => http.get<any, any[]>('/projects'),
  create: (data: { name: string; description?: string }) => http.post('/projects', data),
  update: (id: number, data: object) => http.patch(`/projects/${id}`, data),
  delete: (id: number) => http.delete(`/projects/${id}`),
  getModules: (projectId: number) => http.get<any, any[]>(`/projects/${projectId}/modules`),
}

export const moduleApi = {
  create: (data: object) => http.post('/modules', data),
  update: (id: number, data: object) => http.patch(`/modules/${id}`, data),
  delete: (id: number) => http.delete(`/modules/${id}`),
}

export const caseApi = {
  list: (params?: { module_id?: number; case_type?: string; tag?: string }) =>
    http.get<any, any[]>('/cases', { params }),
  create: (data: object) => http.post('/cases', data),
  get: (id: number) => http.get(`/cases/${id}`),
  update: (id: number, data: object) => http.patch(`/cases/${id}`, data),
  delete: (id: number) => http.delete(`/cases/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post(`/cases/${id}/run`, data ?? {}),
}

export const runApi = {
  list: (params?: { case_id?: number }) => http.get<any, any[]>('/runs', { params }),
  get: (id: number) => http.get(`/runs/${id}`),
}

export const scriptApi = {
  upload: (caseId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post(`/cases/${caseId}/script`, form)
  },
  get: (caseId: number) =>
    http.get<any, { content: string; exists: boolean; script_path?: string }>(`/cases/${caseId}/script`),
  saveContent: (caseId: number, content: string) => {
    const blob = new Blob([content], { type: 'text/x-python' })
    const file = new File([blob], 'test_case.py', { type: 'text/x-python' })
    const form = new FormData()
    form.append('file', file)
    return http.post(`/cases/${caseId}/script`, form)
  },
  delete: (caseId: number) => http.delete(`/cases/${caseId}/script`),
}

export const environmentApi = {
  list: (projectId: number) =>
    http.get<any, any[]>('/environments', { params: { project_id: projectId } }),
  create: (data: { name: string; description?: string; project_id: number }) =>
    http.post('/environments', data),
  update: (id: number, data: { name?: string; description?: string }) =>
    http.patch(`/environments/${id}`, data),
  delete: (id: number) => http.delete(`/environments/${id}`),
  getVariables: (id: number) => http.get<any, any[]>(`/environments/${id}/variables`),
  saveVariables: (id: number, data: { variables: Array<{ key: string; value: string; is_secret: boolean }> }) =>
    http.put(`/environments/${id}/variables`, data),
}

export const deviceApi = {
  list: (params?: { status_filter?: string }) =>
    http.get<any, any[]>('/devices', { params }),
  scan: () => http.post<any, any[]>('/devices/scan'),
  get: (id: number) => http.get('/devices/' + id),
  update: (id: number, data: { name?: string; description?: string }) =>
    http.patch(`/devices/${id}`, data),
  delete: (id: number) => http.delete(`/devices/${id}`),
  screenshot: (id: number) =>
    http.get<any, Blob>(`/devices/${id}/screenshot`, { responseType: 'blob' }),
  screenshotUrl: (id: number) => `/api/v1/devices/${id}/screenshot`,
  screenStreamUrl: (id: number, fps?: number) =>
    `/api/v1/devices/${id}/screen${fps ? `?fps=${fps}` : ''}`,
}

export const apkApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/apks', { params }),
  get: (id: number) => http.get('/apks/' + id),
  upload: (data: FormData) => http.post('/apks', data),
  update: (id: number, data: { description?: string; package_name?: string; version_name?: string; version_code?: number }) =>
    http.patch(`/apks/${id}`, data),
  delete: (id: number) => http.delete(`/apks/${id}`),
  download: (id: number) =>
    http.get<any, { url: string; filename: string }>(`/apks/${id}/download`),
}

export const suiteApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/suites', { params }),
  get: (id: number) => http.get('/suites/' + id),
  create: (data: object) => http.post('/suites', data),
  update: (id: number, data: object) => http.patch(`/suites/${id}`, data),
  delete: (id: number) => http.delete(`/suites/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post(`/suites/${id}/run`, data ?? {}),
  listRuns: (params?: { suite_id?: number }) =>
    http.get<any, any[]>('/suite-runs', { params }),
  getRun: (id: number) => http.get('/suite-runs/' + id),
}

export const planApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/plans', { params }),
  get: (id: number) => http.get('/plans/' + id),
  create: (data: object) => http.post('/plans', data),
  update: (id: number, data: object) => http.patch(`/plans/${id}`, data),
  delete: (id: number) => http.delete(`/plans/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post(`/plans/${id}/run`, data ?? {}),
  listRuns: (params?: { plan_id?: number }) =>
    http.get<any, any[]>('/plan-runs', { params }),
  getRun: (id: number) => http.get('/plan-runs/' + id),
}
