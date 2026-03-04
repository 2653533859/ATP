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
