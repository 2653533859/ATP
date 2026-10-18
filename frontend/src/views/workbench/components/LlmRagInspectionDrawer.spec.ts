import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LlmRagInspectionDrawer from './LlmRagInspectionDrawer.vue'

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs-stub"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane-stub"><slot /></div>' },
  'a-progress': { template: '<div class="ant-progress-stub" />' },
  'a-table': {
    template: `
      <div class="ant-table-stub">
        <slot name="bodyCell" v-for="item in dataSource" :column="{ key: 'claim_text' }" :record="item" />
      </div>
    `,
    props: ['dataSource'],
  },
  'a-alert': { template: '<div class="ant-alert-stub"><slot /></div>' },
}

describe('LlmRagInspectionDrawer.vue', () => {
  it('renders hero bar with query title, model name, and RAG Triad scores', () => {
    const wrapper = mount(LlmRagInspectionDrawer, {
      props: {
        open: true,
        query: 'ATP 全链路压测如何保障数据隔离？',
        targetModel: 'DeepSeek-V3',
        compositeScore: 94.2,
        contextRelevance: 0.92,
        groundedness: 1.0,
        answerRelevance: 0.95,
        grade: 'EXCELLENT',
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('ATP 全链路压测如何保障数据隔离？')
    expect(wrapper.text()).toContain('DeepSeek-V3')
    expect(wrapper.text()).toContain('94.2')
    expect(wrapper.text()).toContain('92.0%')
    expect(wrapper.text()).toContain('100.0%')
    expect(wrapper.text()).toContain('95.0%')
    expect(wrapper.text()).toContain('EXCELLENT')
  })

  it('renders retrieved chunks and displays content with source docs', () => {
    const wrapper = mount(LlmRagInspectionDrawer, {
      props: {
        open: true,
        chunks: [
          {
            chunk_id: 'chk_101',
            content: '核心压测隔离由影子库表路由切面全自动拦截。',
            relevance_score: 0.89,
            source_doc: 'isolation-guide.md',
          },
        ],
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('#chk_101')
    expect(wrapper.text()).toContain('isolation-guide.md')
    expect(wrapper.text()).toContain('核心压测隔离由影子库表路由切面全自动拦截。')
    expect(wrapper.text()).toContain('89.0%')
  })

  it('renders claim attributions in answers tab', () => {
    const wrapper = mount(LlmRagInspectionDrawer, {
      props: {
        open: true,
        claimAttributions: [
          {
            claim_text: '所有写操作路由至 t_order_shadow 影子表',
            is_grounded: true,
            supporting_chunk_id: 'chk_01',
            evidence_snippet: '匹配片段 chk_01 (重合度 91%)',
          },
        ],
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('所有写操作路由至 t_order_shadow 影子表')
  })

  it('handles refresh button click and emits refresh event', async () => {
    const wrapper = mount(LlmRagInspectionDrawer, {
      props: { open: true },
      global: { stubs },
    })

    const refreshBtn = wrapper.findAll('.ant-btn-stub').find((b) => b.text().includes('刷新评测'))
    expect(refreshBtn).toBeDefined()
    await refreshBtn?.trigger('click')

    expect(wrapper.emitted('refresh')).toBeTruthy()
  })

  it('handles close event properly', () => {
    const wrapper = mount(LlmRagInspectionDrawer, {
      props: { open: true },
      global: { stubs },
    })

    // Call close handler
    ;(wrapper.vm as unknown as { handleClose: () => void }).handleClose()
    expect(wrapper.emitted('update:open')?.[0]).toEqual([false])
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
