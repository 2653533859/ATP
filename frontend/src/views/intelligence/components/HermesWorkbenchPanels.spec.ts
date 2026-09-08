import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { WorkbenchTaskItem } from '@/api'

import HermesConversationPanel from './HermesConversationPanel.vue'
import HermesDiagnosisPanel from './HermesDiagnosisPanel.vue'
import HermesEvidencePanel from './HermesEvidencePanel.vue'
import HermesPlanDraftPanel from './HermesPlanDraftPanel.vue'
import { useHermesPlanDraft, type PlanDraft } from '../composables/useHermesPlanDraft'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@ant-design/icons-vue', () => {
  const iconStub = { setup: () => () => null }
  return {
    ArrowRightOutlined: iconStub,
    BulbOutlined: iconStub,
    CheckCircleOutlined: iconStub,
    CloseOutlined: iconStub,
    ExclamationCircleOutlined: iconStub,
    PlusOutlined: iconStub,
  }
})

const passthrough = defineComponent({
  emits: ['click'],
  setup: (_props, { emit, slots }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
})

const globalStubs = {
  AButton: passthrough,
  AEmpty: true,
  ASpace: defineComponent({ setup: (_props, { slots }) => () => h('div', slots.default?.()) }),
  ATag: defineComponent({ setup: (_props, { slots }) => () => h('span', slots.default?.()) }),
}

const failedTask: WorkbenchTaskItem = {
  id: 'case:5',
  task_type: 'case',
  run_id: 77,
  source_id: 5,
  project_id: 1,
  name: '登录失败',
  status: 'failed',
  created_at: '2026-09-08T10:00:00Z',
  detail_path: '/runs/77',
  can_retry: true,
  can_stop: false,
  metadata: {},
  error_message: 'status 500',
}

function createPlanDraft(): PlanDraft {
  return {
    name: ' 回归计划 ',
    objective: ' 验证登录 ',
    testPoints: [' 登录成功 ', ' 登录失败 '],
    scopeModules: [{ id: 10, name: '登录', selected: true, path: '/cases?module_id=10' }],
    caseDrafts: [{ id: 5, title: '登录失败', expected: '显示错误', selected: true, path: '/cases?case_id=5' }],
    regressionScope: [{ taskId: 'case:5', name: '登录失败', reason: 'status 500', selected: true, path: '/runs/77' }],
    sources: [{ label: '运行报告', path: '/reports' }],
    baseline: {
      name: '原计划',
      objective: '验证登录',
      testPoints: ['登录成功'],
      moduleNames: ['登录'],
      caseTitles: ['登录失败'],
      regressionTaskIds: ['case:5'],
      regressionTaskNames: ['登录失败'],
    },
  }
}

describe('Hermes workbench panels', () => {
  it('forwards message, source, feedback, prompt and composer actions', async () => {
    const wrapper = mount(HermesConversationPanel, {
      props: {
        inputText: '排查失败',
        messages: [{
          id: 1,
          role: 'assistant',
          text: '发现失败任务',
          createdAt: '2026-09-08T10:00:00Z',
          taskIds: ['case:5'],
          sources: [{ label: '运行详情', path: '/runs/77' }],
          mode: 'project_retrieval',
          toolSteps: [{ tool: 'failed_tasks', status: 'ok' }],
          backendIndex: 3,
        }],
        promptOptions: [{ key: 'quality', mark: '%', title: '质量分析', description: '查看趋势' }],
        taskNames: { 'case:5': '登录失败' },
        loading: false,
        diagnosing: false,
        querying: false,
      },
      global: { stubs: globalStubs },
    })

    expect(wrapper.text()).toContain('发现失败任务')
    expect(wrapper.text()).toContain('登录失败')
    expect(wrapper.text()).toContain('hermes.modes.project_retrieval')
    expect(wrapper.text()).toContain('hermes.tool_labels.failed_tasks')

    await wrapper.find('.message-task').trigger('click')
    await wrapper.find('.source-link').trigger('click')
    await wrapper.findAllComponents(passthrough)[0].trigger('click')
    await wrapper.find('.prompt-card').trigger('click')
    await wrapper.find('form').trigger('submit')

    expect(wrapper.emitted('select-task')?.[0]).toEqual(['case:5'])
    expect(wrapper.emitted('open-source')?.[0]).toEqual([{ label: '运行详情', path: '/runs/77' }])
    expect(wrapper.emitted('rate-message')?.[0]?.[1]).toBe('helpful')
    expect(wrapper.emitted('ask-prompt')?.[0]).toEqual(['quality'])
    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('renders quality and failures and forwards evidence actions', async () => {
    const wrapper = mount(HermesEvidencePanel, {
      props: {
        qualityScore: 78,
        passRate: 85,
        totalRuns: 20,
        coverageRate: 83,
        openDefects: 2,
        failedTasks: [failedTask],
        selectedTaskId: 'case:5',
        diagnosing: false,
      },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('.quality-score').text()).toContain('78')
    expect(wrapper.find('.failure-row.selected').text()).toContain('登录失败')
    await wrapper.find('.text-action').trigger('click')
    await wrapper.find('.failure-main').trigger('click')
    await wrapper.find('.diagnose-action').trigger('click')
    const footerButtons = wrapper.find('.failure-footer').findAllComponents(passthrough)
    await footerButtons[0].trigger('click')
    await footerButtons[1].trigger('click')

    expect(wrapper.emitted('ask-quality')).toHaveLength(1)
    expect(wrapper.emitted('select-task')?.[0]).toEqual(['case:5'])
    expect(wrapper.emitted('explain-failure')?.[0]).toEqual([failedTask])
    expect(wrapper.emitted('open-task-center')).toHaveLength(1)
    expect(wrapper.emitted('open-runs')).toHaveLength(1)
  })

  it('renders diagnosis evidence and forwards the run-detail action', async () => {
    const wrapper = mount(HermesDiagnosisPanel, {
      props: {
        diagnosis: {
          taskId: 'case:5',
          result: {
            status: 'done',
            source: 'rule',
            summary: '服务返回 500',
            at: '2026-09-08T10:00:00Z',
            failed_step_count: 1,
            screenshot_count: 0,
            repair_suggestions: [{
              step_index: 0,
              step_name: '请求登录接口',
              suggestion_type: 'update_request',
              target: 'status',
              suggested_change: '检查服务状态',
              evidence: 'HTTP 500',
              confidence: 0.9,
            }],
            error_samples: [],
          },
        },
      },
      global: { stubs: globalStubs },
    })

    expect(wrapper.text()).toContain('服务返回 500')
    expect(wrapper.text()).toContain('检查服务状态')
    await wrapper.find('.source-link').trigger('click')
    expect(wrapper.emitted('open-task')?.[0]).toEqual(['case:5'])
  })

  it('computes draft changes and builds a bounded handoff payload', () => {
    const draft = ref<PlanDraft | null>(createPlanDraft())
    const state = useHermesPlanDraft(draft)

    expect(state.selectedModuleCount.value).toBe(1)
    expect(state.selectedCaseCount.value).toBe(1)
    expect(state.selectedRegressionCount.value).toBe(1)
    expect(state.changedCount.value).toBe(3)

    state.addPoint()
    expect(draft.value?.testPoints).toHaveLength(3)
    state.removePoint(2)
    expect(draft.value?.testPoints).toHaveLength(2)
    const handoff = state.buildHandoff(1)
    expect(handoff).toEqual({
      projectId: 1,
      name: '回归计划',
      objective: '验证登录',
      testPoints: ['登录成功', '登录失败'],
      moduleIds: [10],
      caseIds: [5],
      regressionTaskIds: ['case:5'],
    })
  })

  it('forwards plan draft persistence, editing and navigation actions', async () => {
    const draft = createPlanDraft()
    const wrapper = mount(HermesPlanDraftPanel, {
      props: {
        draft,
        saving: false,
        confirmed: false,
        changedCount: 3,
        selectedModuleCount: 1,
        selectedCaseCount: 1,
        selectedRegressionCount: 1,
        failedTaskCount: 1,
        diffRows: [{ key: 'name', label: '名称', before: '原计划', after: '回归计划', changed: true }],
      },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('.draft-diff-row.changed').text()).toContain('回归计划')
    const headingButtons = wrapper.find('.plan-draft-heading').findAllComponents(passthrough)
    await headingButtons[0].trigger('click')
    await headingButtons[1].trigger('click')
    await wrapper.find('.points-heading .text-action').trigger('click')
    await wrapper.find('.icon-action').trigger('click')
    await wrapper.find('.draft-item-link').trigger('click')
    await wrapper.find('.draft-sources .source-link').trigger('click')

    expect(wrapper.emitted('save')).toHaveLength(1)
    expect(wrapper.emitted('confirm')).toHaveLength(1)
    expect(wrapper.emitted('add-point')).toHaveLength(1)
    expect(wrapper.emitted('remove-point')?.[0]).toEqual([0])
    expect(wrapper.emitted('open-path')?.[0]).toEqual(['/cases?module_id=10'])
    expect(wrapper.emitted('open-source')?.[0]).toEqual([{ label: '运行报告', path: '/reports' }])
  })
})
