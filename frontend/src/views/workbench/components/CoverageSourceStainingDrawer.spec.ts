import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CoverageSourceStainingDrawer from './CoverageSourceStainingDrawer.vue'

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub" @click="$emit(\'click\')"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-card': { template: '<div class="ant-card-stub"><slot /></div>' },
  'a-radio-group': {
    template: '<div class="ant-radio-group-stub"><slot /></div>',
    props: ['value'],
  },
  'a-radio-button': {
    template: '<button class="ant-radio-button-stub" :data-value="value"><slot /></button>',
    props: ['value'],
  },
}

describe('CoverageSourceStainingDrawer.vue', () => {
  const sampleStainedLines = [
    { line_number: 1, content: 'def add(a, b):', is_changed_in_diff: true, status: 'COVERED' as const, hits: 3 },
    { line_number: 2, content: '    if a < 0:', is_changed_in_diff: true, status: 'PARTIAL' as const, hits: 1, branches_covered: 1, branches_total: 2 },
    { line_number: 3, content: '        return 0', is_changed_in_diff: true, status: 'UNCOVERED' as const, hits: 0 },
  ]

  it('renders drawer header, file path, and line statistics', () => {
    const wrapper = mount(CoverageSourceStainingDrawer, {
      props: {
        open: true,
        filePath: 'app/services/calc.py',
        diffLineCoveragePct: 66.7,
        stainedLines: sampleStainedLines,
      },
      global: { stubs },
    })

    expect(wrapper.find('.staining-hero-bar').exists()).toBe(true)
    expect(wrapper.text()).toContain('app/services/calc.py')
    expect(wrapper.text()).toContain('66.7%')
    expect(wrapper.text()).toContain('已覆盖行: 1')
    expect(wrapper.text()).toContain('未覆盖红行: 1')
    expect(wrapper.text()).toContain('部分分支: 1')
  })

  it('renders quick jump pill for red uncovered lines and emits jumpToLine on click', async () => {
    // mock scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn()

    const wrapper = mount(CoverageSourceStainingDrawer, {
      props: {
        open: true,
        filePath: 'app/services/calc.py',
        stainedLines: sampleStainedLines,
      },
      global: { stubs },
    })

    const jumpBar = wrapper.find('.quick-jump-bar')
    expect(jumpBar.exists()).toBe(true)
    expect(jumpBar.text()).toContain('Line 3')

    const linePills = jumpBar.findAll('.ant-tag-stub')
    const line3Pill = linePills.find(p => p.text().includes('Line 3'))
    expect(line3Pill).toBeDefined()
    await line3Pill!.trigger('click')

    expect(wrapper.emitted('jumpToLine')).toBeTruthy()
    expect(wrapper.emitted('jumpToLine')![0]).toEqual([3])
  })

  it('emits requestSynthesizeTest when clicking generate test button on uncovered line', async () => {
    const wrapper = mount(CoverageSourceStainingDrawer, {
      props: {
        open: true,
        filePath: 'app/services/calc.py',
        stainedLines: sampleStainedLines,
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.action-btn')
    expect(buttons.length).toBeGreaterThan(0)
    await buttons[0].trigger('click')

    expect(wrapper.emitted('requestSynthesizeTest')).toBeTruthy()
    expect(wrapper.emitted('requestSynthesizeTest')![0]).toEqual([3])
  })

  it('emits close event when clicking close button', async () => {
    const wrapper = mount(CoverageSourceStainingDrawer, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const closeBtn = buttons.find(b => b.text().includes('关闭'))
    expect(closeBtn).toBeDefined()
    await closeBtn!.trigger('click')

    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
