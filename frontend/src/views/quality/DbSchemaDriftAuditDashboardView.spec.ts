import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DbSchemaDriftAuditDashboardView from './DbSchemaDriftAuditDashboardView.vue'
import { dbSchemaDriftApi } from '@/api/cloudNativeCluster'

const mockReport = {
  report_id: 'schema_drift_commerce_db_1001',
  database_name: 'commerce_db',
  base_env: 'production',
  target_env: 'testing',
  total_tables_checked: 2,
  identical_tables_count: 0,
  drift_items_count: 3,
  highest_severity: 'CRITICAL',
  compatibility_rate_pct: 0.0,
  remediation_ddl_script: 'CREATE TABLE orders (\n  order_id VARCHAR(64) PRIMARY KEY NOT NULL,\n  total_amount DECIMAL NOT NULL\n);',
  drifts: [
    {
      table_name: 'orders',
      object_name: 'orders',
      drift_type: 'TABLE_MISSING',
      severity: 'CRITICAL',
      base_detail: '包含 2 列',
      target_detail: null,
      risk_explanation: '目标环境缺少整张业务表 [orders]',
      remediation_ddl: 'CREATE TABLE orders (...)',
    },
    {
      table_name: 'users',
      object_name: 'phone',
      drift_type: 'COLUMN_MISSING',
      severity: 'HIGH',
      base_detail: 'VARCHAR(32)',
      target_detail: null,
      risk_explanation: '表 [users] 在目标环境中缺少必要列 [phone]',
      remediation_ddl: 'ALTER TABLE users ADD COLUMN phone VARCHAR(32);',
    },
  ],
  created_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  dbSchemaDriftApi: {
    compare: vi.fn(),
    registerSnapshot: vi.fn(),
    listReports: vi.fn(),
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
  DatabaseOutlined: { template: '<span>Database</span>' },
  AuditOutlined: { template: '<span>Audit</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  TableOutlined: { template: '<span>Table</span>' },
  CodeOutlined: { template: '<span>Code</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))

describe('DbSchemaDriftAuditDashboardView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(dbSchemaDriftApi.compare).mockResolvedValue({
      message: '数据库表结构比对完成',
      report: mockReport as any,
    })
  })

  it('renders header, KPI cards, table drift items, and DDL script', async () => {
    const wrapper = mount(DbSchemaDriftAuditDashboardView, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-empty': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(dbSchemaDriftApi.compare).toHaveBeenCalled()
    expect(wrapper.text()).toContain('数据库 Schema 结构与索引变更漂移双向比对大盘')
    expect(wrapper.text()).toContain('2 张')
    expect(wrapper.text()).toContain('3 项')
    expect(wrapper.text()).toContain('CRITICAL')
    expect(wrapper.text()).toContain('CREATE TABLE orders')
  })
})
