import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AIGenerateDrawer from './AIGenerateDrawer.vue'
import zhCN from '@/locales/zh-CN'

vi.mock('@/api', () => ({
  aiCaseGenerationApi: {
    parseSchema: vi.fn(),
    generateDrafts: vi.fn(),
  },
  datasetApi: {
    list: vi.fn().mockResolvedValue([]),
    listVersions: vi.fn().mockResolvedValue([]),
  },
  mockRuleApi: {
    list: vi.fn().mockResolvedValue([]),
  },
  caseApi: {
    importCases: vi.fn(),
  },
}))

const passthrough = (name: string) => defineComponent({
  name,
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const drawerStub = defineComponent({
  name: 'ADrawer',
  setup(_props, { slots }) {
    return () => h('section', [slots.default?.(), slots.footer?.()])
  },
})

describe('AIGenerateDrawer', () => {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN },
  })

  it('renders and allows switching sourceType without throwing compilation error', async () => {
    const wrapper = mount(AIGenerateDrawer, {
      props: {
        open: true,
        projectId: 1,
        moduleId: 1,
      },
      global: {
        plugins: [i18n],
        stubs: {
          ADrawer: drawerStub,
          ACard: passthrough('ACard'),
          ARadioGroup: defineComponent({
            name: 'ARadioGroup',
            props: ['value'],
            emits: ['update:value'],
            setup(_props, { slots, emit }) {
              return () => h('div', { class: 'ant-radio-group', onClick: () => emit('update:value', 'curl') }, slots.default?.())
            },
          }),
          ARadio: passthrough('ARadio'),
          AAlert: passthrough('AAlert'),
          ATextarea: passthrough('ATextarea'),
          AButton: passthrough('AButton'),
          ASelect: passthrough('ASelect'),
          ASelectOption: passthrough('ASelectOption'),
          AForm: passthrough('AForm'),
          AFormItem: passthrough('AFormItem'),
          ARow: passthrough('ARow'),
          ACol: passthrough('ACol'),
        },
      },
    })

    expect(wrapper.exists()).toBe(true)

    const radioGroup = wrapper.findComponent({ name: 'ARadioGroup' })
    expect(radioGroup.exists()).toBe(true)

    // Verify switching to curl and sample works without throwing message compilation errors
    await radioGroup.vm.$emit('update:value', 'curl')
    expect(wrapper.text()).toContain('cURL 命令')

    await radioGroup.vm.$emit('update:value', 'sample')
    expect(wrapper.text()).toContain('接口样例')

    await radioGroup.vm.$emit('update:value', 'natural')
    expect(wrapper.text()).toContain('自然语言')
  })
})
