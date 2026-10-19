import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LlmEvalWorkbenchView from './LlmEvalWorkbenchView.vue'

const stubs = {
  'a-button': { template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-radio-group': { template: '<div class="ant-radio-group-stub"><slot /></div>', props: ['value'] },
  'a-radio-button': { template: '<button class="ant-radio-button-stub"><slot /></button>', props: ['value'] },
  'a-progress': { template: '<div class="ant-progress-stub" />' },
  'a-table': {
    template: `
      <div class="ant-table-stub">
        <div v-for="item in dataSource" :key="item.model_name" class="table-row-item">
          <slot name="bodyCell" :column="{ key: 'model_name' }" :record="item" />
          <slot name="bodyCell" :column="{ key: 'rag_score' }" :record="item" />
          <slot name="bodyCell" :column="{ key: 'actions' }" :record="item" />
        </div>
      </div>
    `,
    props: ['dataSource'],
  },
  'a-form': { template: '<form class="ant-form-stub"><slot /></form>' },
  'a-form-item': { template: '<div class="ant-form-item-stub"><slot /></div>' },
  'a-input': { template: '<input class="ant-input-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />', props: ['value'] },
  'a-textarea': { template: '<textarea class="ant-textarea-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />', props: ['value'] },
  'LlmRagInspectionDrawer': {
    template: '<div class="rag-drawer-stub" :data-open="open" />',
    props: ['open'],
  },
  'LlmRedTeamConfigModal': {
    template: '<div class="redteam-modal-stub" :data-open="open" />',
    props: ['open'],
  },
}

describe('LlmEvalWorkbenchView.vue', () => {
  it('renders page hero title and 4 Bento KPI cards', () => {
    const wrapper = mount(LlmEvalWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.text()).toContain('企业级大模型与 RAG 智能体综合评测工作台中枢')
    expect(wrapper.text()).toContain('92.4')
    expect(wrapper.text()).toContain('93.2')
    expect(wrapper.text()).toContain('97.5%')
    expect(wrapper.text()).toContain('118.5')
  })

  it('renders model benchmark leaderboard items', () => {
    const wrapper = mount(LlmEvalWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.text()).toContain('deepseek-v3')
    expect(wrapper.text()).toContain('qwen-2.5-72b')
    expect(wrapper.text()).toContain('gpt-4o')
    expect(wrapper.text()).toContain('llama-3.3-70b')
  })

  it('opens RAG inspection drawer when clicking header action', async () => {
    const wrapper = mount(LlmEvalWorkbenchView, {
      global: { stubs },
    })

    const drawerBtn = wrapper.findAll('.ant-btn-stub').find((b) => b.text().includes('RAG 三元组透视'))
    expect(drawerBtn).toBeDefined()
    await drawerBtn?.trigger('click')

    const vm = wrapper.vm as unknown as { ragDrawerVisible: boolean }
    expect(vm.ragDrawerVisible).toBe(true)
  })

  it('opens red team config modal when clicking header action', async () => {
    const wrapper = mount(LlmEvalWorkbenchView, {
      global: { stubs },
    })

    const modalBtn = wrapper.findAll('.ant-btn-stub').find((b) => b.text().includes('红蓝对抗与护栏'))
    expect(modalBtn).toBeDefined()
    await modalBtn?.trigger('click')

    const vm = wrapper.vm as unknown as { redTeamModalVisible: boolean }
    expect(vm.redTeamModalVisible).toBe(true)
  })
})
