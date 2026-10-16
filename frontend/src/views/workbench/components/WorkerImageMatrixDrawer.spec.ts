import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import WorkerImageMatrixDrawer from './WorkerImageMatrixDrawer.vue'
import { workerImageMatrixApi } from '@/api/cloudNativeWorkers'

const mockImages = [
  {
    image_id: 'img_py312_core',
    name: 'ATP Python 3.12 核心执行环境',
    image_url: 'registry.internal/atp/worker-python:3.12-v1',
    category: 'python' as const,
    tags: ['python:3.12', 'pytest', 'playwright', 'x86_64'],
    is_default: true,
    weight: 1.2,
    min_cpu_cores: 1.0,
    min_memory_mb: 1024,
    created_at: '2026-10-16T12:00:00Z',
  },
  {
    image_id: 'img_node20_playwright',
    name: 'ATP Node.js 20 Web UI 自动化执行环境',
    image_url: 'registry.internal/atp/worker-node:20-playwright',
    category: 'browser' as const,
    tags: ['node:20', 'playwright:chromium', 'ui_test'],
    is_default: true,
    weight: 1.5,
    min_cpu_cores: 2.0,
    min_memory_mb: 2048,
    created_at: '2026-10-16T12:00:00Z',
  },
]

const mockMatchResult = {
  matched: true,
  selected_image: mockImages[0],
  match_score: 24.0,
  matched_tags: ['python:3.12', 'playwright'],
  unmatched_tags: [],
  is_fallback: false,
  reason: '精准命中镜像 [ATP Python 3.12 核心执行环境]，匹配标签 2 个，得分 24.0',
}

vi.mock('@/api/cloudNativeWorkers', () => ({
  workerImageMatrixApi: {
    listImages: vi.fn(),
    registerImage: vi.fn(),
    deleteImage: vi.fn(),
    resolveImage: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('WorkerImageMatrixDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, registration form, and images table on mount', async () => {
    vi.mocked(workerImageMatrixApi.listImages).mockResolvedValue({
      total: mockImages.length,
      images: mockImages,
    })

    const wrapper = mount(WorkerImageMatrixDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.image_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'name' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'category' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'tags' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'min_resources' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'actions' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('容器执行环境镜像版本矩阵与标签路由解析')
    expect(wrapper.text()).toContain('多语言 / 多 SDK 执行矩阵')
    expect(wrapper.text()).toContain('ATP Python 3.12 核心执行环境')
    expect(wrapper.text()).toContain('默认兜底')
    expect(wrapper.text()).toContain('ATP Node.js 20 Web UI 自动化执行环境')
  })

  it('registers new worker image and refreshes images list', async () => {
    vi.mocked(workerImageMatrixApi.listImages).mockResolvedValue({
      total: 0,
      images: [],
    })
    vi.mocked(workerImageMatrixApi.registerImage).mockResolvedValue({
      message: '镜像注册成功',
      image: mockImages[0],
    })

    const wrapper = mount(WorkerImageMatrixDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    // 填写镜像表单
    ;(wrapper.vm as any).newImageId = 'img_go122'
    ;(wrapper.vm as any).newName = 'Go 1.22 镜像'
    ;(wrapper.vm as any).newImageUrl = 'registry.internal/atp/go:1.22'
    ;(wrapper.vm as any).newTagsStr = 'go:1.22, grpc'
    const regBtn = wrapper.findAll('button').find((b) => b.text().includes('注册镜像'))
    expect(regBtn).toBeDefined()
    await regBtn!.trigger('click')
    await flushPromises()

    expect(workerImageMatrixApi.registerImage).toHaveBeenCalledWith({
      image_id: 'img_go122',
      name: 'Go 1.22 镜像',
      image_url: 'registry.internal/atp/go:1.22',
      category: 'python',
      tags: ['go:1.22', 'grpc'],
    })
    expect(workerImageMatrixApi.listImages).toHaveBeenCalledTimes(2)
  })

  it('resolves best worker image by required tags and displays match alert', async () => {
    vi.mocked(workerImageMatrixApi.listImages).mockResolvedValue({
      total: mockImages.length,
      images: mockImages,
    })
    vi.mocked(workerImageMatrixApi.resolveImage).mockResolvedValue(mockMatchResult)

    const wrapper = mount(WorkerImageMatrixDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const resolveBtn = wrapper.findAll('button').find((b) => b.text().includes('推演命中镜像'))
    expect(resolveBtn).toBeDefined()
    await resolveBtn!.trigger('click')
    await flushPromises()

    expect(workerImageMatrixApi.resolveImage).toHaveBeenCalledWith({
      required_tags: ['python:3.12', 'playwright'],
      category: undefined,
    })

    // 验证匹配结果渲染
    expect(wrapper.text()).toContain('[精准命中]')
    expect(wrapper.text()).toContain('ATP Python 3.12 核心执行环境')
    expect(wrapper.text()).toContain('得分: 24')
  })
})
