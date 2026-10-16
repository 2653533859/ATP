import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReportBundlerExportModal from './ReportBundlerExportModal.vue'
import { reportBundlerApi } from '@/api/reportBundler'

const mockArtifact = {
  bundle_id: 'bundle_xyz_123',
  run_id: 101,
  format: 'multi_modal_zip',
  filename: 'ATP_TestReport_Run_101_20261016.zip',
  content_type: 'application/zip',
  file_size_bytes: 245890,
  created_at: '2026-10-16T10:00:00Z',
  download_url: '/api/v1/reporting/exports/download/bundle_xyz_123',
}

vi.mock('@/api/reportBundler', () => ({
  reportBundlerApi: {
    exportBundle: vi.fn(),
    listArtifacts: vi.fn(),
    getDownloadUrl: vi.fn((id: string) => `/api/v1/reporting/exports/download/${id}`),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  FileZipOutlined: { template: '<span>Zip</span>' },
  Html5Outlined: { template: '<span>Html5</span>' },
  FileExcelOutlined: { template: '<span>Excel</span>' },
  FilePdfOutlined: { template: '<span>Pdf</span>' },
  CloudDownloadOutlined: { template: '<span>CloudDownload</span>' },
  CheckCircleFilled: { template: '<span>CheckCircle</span>' },
  DownloadOutlined: { template: '<span>Download</span>' },
}))

describe('ReportBundlerExportModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(reportBundlerApi.listArtifacts).mockResolvedValue({
      total: 1,
      artifacts: [mockArtifact as any],
    })
    vi.mocked(reportBundlerApi.exportBundle).mockResolvedValue({
      message: '多模态报告打包生成成功',
      artifact: mockArtifact as any,
    })
  })

  it('renders modal content, 4 format cards and pre-fills form', async () => {
    const wrapper = mount(ReportBundlerExportModal, {
      props: {
        open: true,
        defaultRunId: 101,
        defaultProjectName: 'ATP-Platform',
      },
      global: {
        stubs: {
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    // 验证多模态格式选项卡
    expect(wrapper.text()).toContain('独立单文件 HTML5')
    expect(wrapper.text()).toContain('详细 Excel / CSV 表格')
    expect(wrapper.text()).toContain('企业合规 PDF 凭证')
    expect(wrapper.text()).toContain('多模态多合一 ZIP')

    // 验证历史产物查询
    expect(reportBundlerApi.listArtifacts).toHaveBeenCalled()
  })

  it('triggers export bundle and renders download card', async () => {
    const wrapper = mount(ReportBundlerExportModal, {
      props: {
        open: true,
        defaultRunId: 101,
        defaultProjectName: 'ATP-Platform',
      },
      global: {
        stubs: {
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleExportBundle()

    expect(reportBundlerApi.exportBundle).toHaveBeenCalledWith(expect.objectContaining({
      run_id: 101,
      format: 'multi_modal_zip',
    }))

    await flushPromises()

    expect(wrapper.text()).toContain('ATP_TestReport_Run_101_20261016.zip')
    expect(wrapper.text()).toContain('240.1 KB')
    expect(wrapper.text()).toContain('立即下载归档文件')
  })
})
