import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TargetedRegressionWizard from './TargetedRegressionWizard.vue'
import { assetGraphApi } from '@/api/assetGraph'

const mockSynthesisResult = {
  synthesis_id: 'synth_test_001',
  suite_id: 88,
  suite_name: '智能契约变更精准回归套件',
  project_id: 1,
  total_cases_count: 2,
  included_case_ids: [101, 102],
  task_priority: 'P0',
  auto_triggered: true,
  dispatched_task_id: 'task_sched_p0_999',
  task_preempted: true,
  created_at: '2026-10-16T12:00:00Z',
  message: '精准回归套件合成成功，已触发 P0 弹性抢占调度！',
}

vi.mock('@/api/assetGraph', () => ({
  assetGraphApi: {
    synthesizeAndTriggerRegression: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  },
}))

describe('TargetedRegressionWizard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders Step 0 with deduplicated test cases table', async () => {
    const wrapper = mount(TargetedRegressionWizard, {
      props: {
        open: true,
        projectId: 1,
        initialCaseIds: [101, 102, 101], // 测试去重
        isBreakingChange: true,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-steps': { template: '<div class="ant-steps"><slot /></div>' },
          'a-step': { template: '<div class="ant-step" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.id" class="row">
                  <slot name="bodyCell" :column="{ key: 'id' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'name' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('变更影响用例自动化精准回归套件合成向导')
    expect(wrapper.text()).toContain('P0 紧急抢占回归')
    expect(wrapper.text()).toContain('待回归用例：2 个') // 101, 102 去重后为 2 个
    expect(wrapper.text()).toContain('#101')
    expect(wrapper.text()).toContain('#102')
  })

  it('navigates from Step 0 to Step 1 and configures suite scheduling strategy', async () => {
    const wrapper = mount(TargetedRegressionWizard, {
      props: {
        open: true,
        projectId: 1,
        initialCaseIds: [101, 102],
        isBreakingChange: true,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-steps': { template: '<div class="ant-steps"><slot /></div>' },
          'a-step': { template: '<div class="ant-step" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div class="ant-form-item">{{ label }}<slot /></div>', props: ['label'] },
          'a-input': { template: '<input />' },
          'a-checkbox': { template: '<label><input type="checkbox" /><slot /></label>' },
          'a-switch': { template: '<input type="checkbox" />' },
        },
      },
    })

    await flushPromises()

    // 点击下一步进入 Step 1
    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('下一步：配置调度策略'))
    expect(nextBtn).toBeDefined()
    await nextBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('测试套件名称')
    expect(wrapper.text()).toContain('包含 Breaking 破坏性字段变更')
    expect(wrapper.text()).toContain('套件持久化落库 (Persist to Suite)')
    expect(wrapper.text()).toContain('立即自动触发调度执行 (Auto Trigger)')
  })

  it('triggers synthesis and displays Step 2 delivery credentials', async () => {
    vi.mocked(assetGraphApi.synthesizeAndTriggerRegression).mockResolvedValue(mockSynthesisResult)

    const wrapper = mount(TargetedRegressionWizard, {
      props: {
        open: true,
        projectId: 1,
        initialCaseIds: [101, 102],
        isBreakingChange: true,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-steps': { template: '<div class="ant-steps"><slot /></div>' },
          'a-step': { template: '<div class="ant-step" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div class="ant-form-item">{{ label }}<slot /></div>', props: ['label'] },
          'a-input': { template: '<input />' },
          'a-checkbox': { template: '<label><slot /></label>' },
          'a-switch': { template: '<div />' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
        },
      },
    })

    await flushPromises()

    // 进入 Step 1
    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('下一步：配置调度策略'))
    await nextBtn!.trigger('click')
    await flushPromises()

    // 点击一键合成并触发调度
    const triggerBtn = wrapper.findAll('button').find((b) => b.text().includes('一键合成并触发调度'))
    expect(triggerBtn).toBeDefined()
    await triggerBtn!.trigger('click')
    await flushPromises()

    expect(assetGraphApi.synthesizeAndTriggerRegression).toHaveBeenCalledWith({
      impacted_case_ids: [101, 102],
      project_id: 1,
      suite_name: '智能契约变更精准回归套件',
      is_breaking_change: true,
      persist: true,
      auto_trigger: true,
    })

    // 验证 Step 2 结果
    expect(wrapper.text()).toContain('精准回归测试套件合成成功！')
    expect(wrapper.text()).toContain('#88')
    expect(wrapper.text()).toContain('P0')
    expect(wrapper.text()).toContain('task_sched_p0_999')
    expect(wrapper.text()).toContain('[P0 弹性抢占生效]')

    // 点击完成并关闭
    const finishBtn = wrapper.findAll('button').find((b) => b.text().includes('完成并关闭'))
    expect(finishBtn).toBeDefined()
    await finishBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('succeeded')).toBeDefined()
    expect(wrapper.emitted('succeeded')![0]).toEqual([mockSynthesisResult])
  })
})
