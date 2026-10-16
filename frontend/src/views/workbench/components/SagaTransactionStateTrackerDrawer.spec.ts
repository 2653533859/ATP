import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SagaTransactionStateTrackerDrawer from './SagaTransactionStateTrackerDrawer.vue'
import { sagaTransactionApi } from '@/api/distributedConsistency'

const mockHangingReport = {
  global_tx_id: 'gtx_sim_hanging_101',
  business_key: 'order_88291',
  pattern: 'TCC',
  status: 'HANGING',
  is_consistent: false,
  detected_anomaly: 'HANGING_TRANSACTION',
  anomaly_description: '微服务 [pay-service] 遭遇严重悬挂事务：Cancel 优先到达执行，晚到的 Try 产生永久资源冻结。',
  branches_count: 3,
  branches: [
    {
      branch_id: 'br_order_1',
      global_tx_id: 'gtx_sim_hanging_101',
      service_name: 'order-service',
      action_name: 'create_order',
      stage: 'TRY',
      status: 'SUCCESS',
      duration_ms: 45.0,
      error_message: '',
      retry_count: 0,
      payload: {},
      recorded_at: '2026-10-16T12:00:00Z',
    },
    {
      branch_id: 'br_pay_cancel',
      global_tx_id: 'gtx_sim_hanging_101',
      service_name: 'pay-service',
      action_name: 'deduct_balance',
      stage: 'CANCEL',
      status: 'SUCCESS',
      duration_ms: 20.0,
      error_message: '',
      retry_count: 0,
      payload: {},
      recorded_at: '2026-10-16T12:00:01Z',
    },
    {
      branch_id: 'br_pay_try',
      global_tx_id: 'gtx_sim_hanging_101',
      service_name: 'pay-service',
      action_name: 'deduct_balance',
      stage: 'TRY',
      status: 'SUCCESS',
      duration_ms: 60.0,
      error_message: '',
      retry_count: 0,
      payload: {},
      recorded_at: '2026-10-16T12:00:02Z',
    },
  ],
  remediation_advice: [
    '在 Try 接口执行前先检查是否已存在当前全局事务的 Cancel 记录，若已 Cancel 则拒绝 Try 执行并回滚',
    '通过唯一事务凭据表保证 Try 与 Cancel 的严格防悬挂状态机校验',
  ],
  audited_at: '2026-10-16T12:00:05Z',
}

const mockNormalReport = {
  global_tx_id: 'gtx_sim_normal_202',
  business_key: 'order_99012',
  pattern: 'TCC',
  status: 'COMMITTED',
  is_consistent: true,
  detected_anomaly: 'NONE',
  anomaly_description: '所有微服务分支事务均成功执行并确认，全局数据最终一致性达标。',
  branches_count: 2,
  branches: [
    {
      branch_id: 'br_normal_1',
      global_tx_id: 'gtx_sim_normal_202',
      service_name: 'order-service',
      action_name: 'create_order',
      stage: 'CONFIRM',
      status: 'SUCCESS',
      duration_ms: 15.0,
      error_message: '',
      retry_count: 0,
      payload: {},
      recorded_at: '2026-10-16T12:05:00Z',
    },
  ],
  remediation_advice: [],
  audited_at: '2026-10-16T12:05:02Z',
}

vi.mock('@/api/distributedConsistency', () => ({
  sagaTransactionApi: {
    createGlobalTx: vi.fn(),
    recordBranch: vi.fn(),
    auditGlobalTx: vi.fn(),
    listHangingTransactions: vi.fn(),
    simulateScenario: vi.fn(),
    clearTransactions: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  ApartmentOutlined: { template: '<span>Apartment</span>' },
  AlertOutlined: { template: '<span>Alert</span>' },
}))

describe('SagaTransactionStateTrackerDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(sagaTransactionApi.simulateScenario).mockResolvedValue({
      message: '分布式事务场景仿真完成',
      report: mockHangingReport as any,
    })
    vi.mocked(sagaTransactionApi.listHangingTransactions).mockResolvedValue({
      total: 3,
      transactions: [],
    })
  })

  it('renders drawer header, anomaly cards, verdict banner, and branches table', async () => {
    const wrapper = mount(SagaTransactionStateTrackerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.branch_id" class="row">
                  <span class="svc">{{ item.service_name }}</span>
                  <span class="stage">{{ item.stage }}</span>
                  <span class="status">{{ item.status }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(sagaTransactionApi.simulateScenario).toHaveBeenCalledWith('hanging')
    expect(wrapper.text()).toContain('多微服务 Sagas/TCC 分布式长事务一致性与悬挂防线')

    // 检查异常模式卡片
    expect(wrapper.text()).toContain('悬挂事务 (Hanging)')
    expect(wrapper.text()).toContain('空补偿 (Empty Compensation)')
    expect(wrapper.text()).toContain('超时未决 (Timeout Pending)')

    // 检查裁决横幅
    expect(wrapper.text()).toContain('HANGING')
    expect(wrapper.text()).toContain('一致性受损')
    expect(wrapper.text()).toContain('遭遇严重悬挂事务')

    // 检查分支表格
    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('pay-service')

    // 检查加固指引
    expect(wrapper.text()).toContain('分布式事务防悬挂加固指引')
  })

  it('switches preset to normal and checks committed status', async () => {
    vi.mocked(sagaTransactionApi.simulateScenario).mockResolvedValueOnce({
      message: '分布式事务场景仿真完成',
      report: mockHangingReport as any,
    }).mockResolvedValueOnce({
      message: '分布式事务场景仿真完成',
      report: mockNormalReport as any,
    })

    const wrapper = mount(SagaTransactionStateTrackerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('normal')
    await flushPromises()

    expect(sagaTransactionApi.simulateScenario).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('COMMITTED')
    expect(wrapper.text()).toContain('最终一致性达标')

    // 触发全网探测
    await vm.fetchHangingList()
    expect(sagaTransactionApi.listHangingTransactions).toHaveBeenCalled()
    expect(wrapper.text()).toContain('3')
  })
})
