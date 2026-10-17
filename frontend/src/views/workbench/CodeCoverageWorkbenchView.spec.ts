import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CodeCoverageWorkbenchView from './CodeCoverageWorkbenchView.vue'

const stubs = {
  'a-button': {
    template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>',
  },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-card': { template: '<div class="ant-card-stub"><slot /><slot name="extra" /></div>' },
  'a-progress': { template: '<div class="ant-progress-stub" :data-percent="percent"></div>', props: ['percent'] },
  'a-table': {
    template: '<div class="ant-table-stub"><slot /><div v-for="item in dataSource" :key="item.file_path" class="table-row">{{ item.file_path }} - {{ item.diff_line_coverage_pct }}%</div></div>',
    props: ['dataSource'],
  },
  'a-input-search': {
    template: '<input class="ant-search-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'CoverageSourceStainingDrawer': {
    template: '<div class="staining-drawer-stub" :data-open="open"><slot /></div>',
    props: ['open', 'filePath', 'diffLineCoveragePct'],
  },
  'CoverageGateConfigModal': {
    template: '<div class="gate-modal-stub" :data-open="open"><slot /></div>',
    props: ['open'],
  },
}

describe('CodeCoverageWorkbenchView.vue', () => {
  it('renders page hero title and 4 Bento KPI cards', () => {
    const wrapper = mount(CodeCoverageWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.page-hero').exists()).toBe(true)
    expect(wrapper.text()).toContain('全链路代码覆盖率动态染色与增量发布准入中台')
    expect(wrapper.text()).toContain('v5.9.0 动态代码染色在线')

    // 4 Bento cards
    const bentoCards = wrapper.findAll('.bento-card')
    expect(bentoCards.length).toBe(4)
    expect(wrapper.text()).toContain('增量代码行覆盖率 (Diff Line)')
    expect(wrapper.text()).toContain('88.5%')
    expect(wrapper.text()).toContain('增量条件分支覆盖率 (Branch)')
    expect(wrapper.text()).toContain('82.0%')
    expect(wrapper.text()).toContain('发布门禁准入裁决')
    expect(wrapper.text()).toContain('PASSED')
    expect(wrapper.text()).toContain('未覆盖高危分支数 (P0)')
    expect(wrapper.text()).toContain('0 处')
  })

  it('renders files coverage table with seed changed files', () => {
    const wrapper = mount(CodeCoverageWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.coverage-table-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('backend/app/services/payment.py')
    expect(wrapper.text()).toContain('90%')
    expect(wrapper.text()).toContain('backend/app/services/order.py')
    expect(wrapper.text()).toContain('100%')
  })

  it('opens staining drawer when clicking header view button', async () => {
    const wrapper = mount(CodeCoverageWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const viewBtn = buttons.find((b) => b.text().includes('源码逐行染色透视'))
    expect(viewBtn).toBeDefined()
    await viewBtn!.trigger('click')
    await flushPromises()

    const drawer = wrapper.find('.staining-drawer-stub')
    expect(drawer.attributes('data-open')).toBe('true')
  })

  it('opens gate config modal when clicking header config button', async () => {
    const wrapper = mount(CodeCoverageWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const configBtn = buttons.find((b) => b.text().includes('发布门禁与补测中枢'))
    expect(configBtn).toBeDefined()
    await configBtn!.trigger('click')
    await flushPromises()

    const modal = wrapper.find('.gate-modal-stub')
    expect(modal.attributes('data-open')).toBe('true')
  })
})
