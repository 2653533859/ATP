import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StartupConfigView from './StartupConfigView.vue'

const { messageSuccess } = vi.hoisted(() => ({ messageSuccess: vi.fn() }))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      return `${key}:${JSON.stringify(params)}`
    },
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: { success: messageSuccess },
}))

function mountPage() {
  return mount(StartupConfigView)
}

describe('StartupConfigView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('exposes the complete startup configuration and generates env content', () => {
    const wrapper = mountPage()
    const vm = wrapper.vm as any

    expect(vm.fieldCount).toBe(117)
    expect(vm.envContent).toContain('POSTGRES_HOST=postgres')
    expect(vm.envContent).toContain('POSTGRES_CONNECT_TIMEOUT_SECONDS=5')
    expect(vm.envContent).toContain('REDIS_CONNECT_TIMEOUT_SECONDS=5')
    expect(vm.envContent).toContain('MINIO_CONNECT_TIMEOUT_SECONDS=5')
    expect(vm.envContent).toContain('CELERY_QUEUES=default,android,mobile_special,ios,ai,maintenance,performance')
    expect(vm.envContent).toContain('ADB_SCAN_MODE=local')
    expect(vm.envContent).toContain('PERFORMANCE_EXECUTORS=k6,locust,grpc')
    expect(vm.envContent).toContain('WEB_RECORDER_MODE=local')
    expect(vm.envContent).toContain('WEB_RECORDER_WORKER_QUEUE_PREFIX=atp:web-recording:commands')
    expect(vm.envContent).toContain('WEB_RECORDER_SESSION_TTL_SECONDS=3600')
    expect(vm.envContent).toContain('AI_HEALING_APPLY_ENABLED=false')
    expect(vm.envContent).toContain('VITE_BACKEND_ORIGIN=')
    expect(vm.profileOptions).toHaveLength(4)
    expect(vm.isReady).toBe(false)
  })

  it('applies the Windows performance-agent startup profile', () => {
    const wrapper = mountPage()
    const vm = wrapper.vm as any

    vm.applyProfile('performance-agent')

    expect(vm.selectedProfile).toBe('performance-agent')
    expect(vm.config.POSTGRES_USER).toBe('<database-user>')
    expect(vm.config.MINIO_ROOT_USER).toBe('<minio-user>')
    expect(vm.config.CELERY_QUEUES).toBe('performance.worker-a')
    expect(vm.config.PERFORMANCE_NODE_ID).toBe('performance-win-worker-a')
    expect(vm.config.PERFORMANCE_NODE_QUEUE).toBe('performance.worker-a')
    expect(vm.config.PERFORMANCE_EXECUTORS).toBe('jmeter,grpc')
    expect(vm.config.ADB_SCAN_ENABLED).toBe(false)
    expect(vm.envContent).toContain('PERFORMANCE_NODE_ENABLED=true')
  })

  it('applies presets and saves a browser-local draft', () => {
    const wrapper = mountPage()
    const vm = wrapper.vm as any

    vm.applyPreset('remote')
    expect(vm.config.POSTGRES_HOST).toBe('<server-host>')
    expect(vm.config.POSTGRES_USER).toBe('<database-user>')
    expect(vm.config.REDIS_HOST).toBe('<server-host>')
    expect(vm.config.MINIO_HOST).toBe('<server-host>')
    expect(vm.config.MINIO_ROOT_USER).toBe('<minio-user>')
    expect(vm.missingRequired).toEqual(expect.arrayContaining(['POSTGRES_HOST', 'REDIS_HOST', 'MINIO_HOST']))
    expect(vm.missingRequired).toEqual(expect.arrayContaining(['POSTGRES_USER', 'MINIO_ROOT_USER']))
    expect(vm.isDirty).toBe(true)

    vm.saveDraft()
    const saved = JSON.parse(localStorage.getItem('atp-startup-config-draft-v1')!)
    expect(saved).toMatchObject({
      POSTGRES_HOST: '<server-host>',
      POSTGRES_USER: '<database-user>',
      REDIS_HOST: '<server-host>',
      MINIO_HOST: '<server-host>',
      MINIO_ROOT_USER: '<minio-user>',
    })
    expect(saved.POSTGRES_PASSWORD).toBeUndefined()
    expect(saved.APP_SECRET_KEY).toBeUndefined()
    expect(localStorage.getItem('atp-startup-profile-v1')).toBe('remote-infra')
    expect(vm.isDirty).toBe(false)
    expect(messageSuccess).toHaveBeenCalled()
  })

  it('flags missing required values and restores the example preset', () => {
    const wrapper = mountPage()
    const vm = wrapper.vm as any

    vm.config.POSTGRES_HOST = ''
    vm.config.APP_SECRET_KEY = 'short'
    expect(vm.missingRequired).toContain('POSTGRES_HOST')
    expect(vm.isReady).toBe(false)

    vm.resetDefaults()
    expect(vm.config.POSTGRES_HOST).toBe('postgres')
    expect(vm.config.APP_SECRET_KEY.length).toBeGreaterThanOrEqual(32)
    expect(vm.isReady).toBe(false)
  })

  it('removes secrets left by an older browser draft format', () => {
    localStorage.setItem('atp-startup-config-draft-v1', JSON.stringify({
      POSTGRES_HOST: 'db.example.com',
      POSTGRES_PASSWORD: 'old-secret',
      APP_SECRET_KEY: 'old-app-secret',
    }))

    const wrapper = mountPage()
    const vm = wrapper.vm as any
    const saved = JSON.parse(localStorage.getItem('atp-startup-config-draft-v1')!)

    expect(vm.config.POSTGRES_HOST).toBe('db.example.com')
    expect(saved.POSTGRES_PASSWORD).toBeUndefined()
    expect(saved.APP_SECRET_KEY).toBeUndefined()
  })
})
