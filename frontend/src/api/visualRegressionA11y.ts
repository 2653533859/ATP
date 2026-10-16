/**
 * 多模态视觉回归 Diff、VLM 智能断言、深度无障碍 a11y 与 Web Vitals API 客户端 (v4.4.0 / v4.5.0)
 */
import http from './http'

// --- Phase 1: 多模态视觉 Diff 与黄金基线 ---
export interface DiffBoundingBox {
  box_id: string
  x: number
  y: number
  width: number
  height: number
  diff_pixel_count: number
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
}

export interface ViewportComparisonResult {
  viewport_type: 'DESKTOP' | 'TABLET' | 'MOBILE'
  viewport_width: number
  viewport_height: number
  ssim_score: number
  mismatch_ratio_pct: number
  verdict: 'PERFECT_MATCH' | 'ACCEPTABLE_DRIFT' | 'REGRESSION_BLOCKED'
  diff_boxes_count: number
  diff_boxes: DiffBoundingBox[]
  baseline_hash?: string
  current_hash?: string
  diff_heatmap_base64?: string
}

export interface VisualDiffReport {
  report_id: string
  page_name: string
  overall_verdict: 'PERFECT_MATCH' | 'ACCEPTABLE_DRIFT' | 'REGRESSION_BLOCKED'
  average_ssim_score: number
  max_mismatch_ratio_pct: number
  total_diff_clusters_count: number
  viewports: ViewportComparisonResult[]
  created_at: string
}

export interface MaskRegion {
  mask_id: string
  name: string
  x: number
  y: number
  width: number
  height: number
  reason: string
  is_active: boolean
}

export interface BaselineSnapshot {
  baseline_id: string
  page_route: string
  branch_name: string
  version_tag: string
  viewport_snapshots: Record<string, string>
  approved_by: string
  is_active_golden: boolean
  changelog: string
  created_at: string
}

// API Methods
export async function compareVisualPixelDiff(payload: {
  page_name: string
  desktop_baseline_base64?: string
  desktop_current_base64?: string
  tablet_baseline_base64?: string
  tablet_current_base64?: string
  mobile_baseline_base64?: string
  mobile_current_base64?: string
  ssim_threshold?: number
}): Promise<{ message: string; report: VisualDiffReport }> {
  const resp = await http.post('/visual/pixel-diff/compare', payload)
  return resp.data
}

export async function listVisualDiffReports(limit = 50): Promise<{ total: number; reports: VisualDiffReport[] }> {
  const resp = await http.get('/visual/pixel-diff/reports', { params: { limit } })
  return resp.data
}

export async function registerMaskRegion(payload: {
  page_route: string
  name: string
  x: number
  y: number
  width: number
  height: number
  reason?: string
}): Promise<{ message: string; mask: MaskRegion }> {
  const resp = await http.post('/visual/noise-filter/masks', payload)
  return resp.data
}

export async function listMaskRegions(pageRoute?: string): Promise<{ total: number; masks: MaskRegion[] }> {
  const resp = await http.get('/visual/noise-filter/masks', { params: { page_route: pageRoute } })
  return resp.data
}

export async function registerBaselineSnapshot(payload: {
  page_route: string
  branch_name: string
  version_tag: string
  viewport_snapshots: Record<string, string>
  changelog?: string
  is_active_golden?: boolean
}): Promise<{ message: string; baseline_id: string }> {
  const resp = await http.post('/visual/baselines/register', payload)
  return resp.data
}

export async function listBaselineSnapshots(pageRoute?: string, branchName?: string): Promise<{ total: number; baselines: BaselineSnapshot[] }> {
  const resp = await http.get('/visual/baselines/list', { params: { page_route: pageRoute, branch_name: branchName } })
  return resp.data
}

export async function promoteGoldenBaseline(baselineId: string): Promise<{ message: string; baseline: BaselineSnapshot }> {
  const resp = await http.post(`/visual/baselines/promote/${baselineId}`)
  return resp.data
}

export async function compareBranchBaselines(payload: {
  page_route: string
  base_branch: string
  target_branch: string
}): Promise<{
  page_route: string
  base_branch: string
  target_branch: string
  evolution_type: string
  has_regression: boolean
  audit_summary: string
}> {
  const resp = await http.post('/visual/baselines/cross-branch-compare', payload)
  return resp.data
}

// --- Phase 2: VLM 智能断言、布局碰撞与设计系统 ---
export interface VlmRuleAssertion {
  rule_type: string
  description: string
  is_passed: boolean
  confidence_score: number
  failure_reason: string | null
}

export interface VlmAssertionReport {
  report_id: string
  page_route_or_name: string
  total_assertions_count: number
  passed_count: number
  failed_count: number
  semantic_score_pct: number
  is_page_integrity_pass: boolean
  assertions: VlmRuleAssertion[]
  created_at: string
}

export interface LayoutDefectItem {
  defect_id: string
  defect_type: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  element_id: string
  bounding_box: { x: number; y: number; width: number; height: number }
  description: string
  remediation_suggestion: string
}

export interface LayoutDefectReport {
  report_id: string
  target_name: string
  total_elements_checked: number
  collision_count: number
  horizontal_overflow_count: number
  truncation_count: number
  layout_integrity_score_pct: number
  has_blocking_defect: boolean
  defects: LayoutDefectItem[]
  created_at: string
}

export interface TokenViolationItem {
  violation_id: string
  element_id: string
  violation_type: string
  severity: string
  current_value: any
  recommended_token: any
  explanation: string
}

export interface DesignSystemAuditReport {
  report_id: string
  target_name: string
  total_elements_checked: number
  total_violations_count: number
  contrast_fails_count: number
  token_discrepancies_count: number
  compliance_score_pct: number
  is_wcag_aa_compliant: boolean
  violations: TokenViolationItem[]
  created_at: string
}

export async function evaluateVlmSemanticAssertions(payload: {
  page_route_or_name: string
  screenshot_base64?: string
  rules?: Array<{ rule_type: string; target_identifier?: string; custom_prompt?: string }>
}): Promise<{ message: string; report: VlmAssertionReport }> {
  const resp = await http.post('/visual-ai/semantic-assertion/evaluate', payload)
  return resp.data
}

export async function listVlmAssertionReports(limit = 50): Promise<{ total: number; reports: VlmAssertionReport[] }> {
  const resp = await http.get('/visual-ai/semantic-assertion/reports', { params: { limit } })
  return resp.data
}

export async function detectLayoutDefects(payload: {
  target_name: string
  elements: Array<{
    element_id: string
    tag_name?: string
    x?: number
    y?: number
    width?: number
    height?: number
    scroll_width?: number
    scroll_height?: number
    text_content?: string
    z_index?: number
    parent_id?: string
  }>
  viewport_width?: number
}): Promise<{ message: string; report: LayoutDefectReport }> {
  const resp = await http.post('/visual-ai/layout-collision/detect', payload)
  return resp.data
}

export async function listLayoutDefectReports(limit = 50): Promise<{ total: number; reports: LayoutDefectReport[] }> {
  const resp = await http.get('/visual-ai/layout-collision/reports', { params: { limit } })
  return resp.data
}

export async function auditDesignTokens(payload: {
  target_name: string
  elements: Array<{
    element_id: string
    color?: string
    background_color?: string
    font_size?: number
    is_bold?: boolean
    padding?: number
    border_radius?: number
  }>
}): Promise<{ message: string; report: DesignSystemAuditReport }> {
  const resp = await http.post('/visual-ai/design-tokens/audit', payload)
  return resp.data
}

export async function computeContrastRatio(payload: {
  foreground_hex: string
  background_hex: string
}): Promise<{
  foreground_hex: string
  background_hex: string
  contrast_ratio: number
  is_wcag_aa_pass: boolean
  is_wcag_aaa_pass: boolean
  rating: string
}> {
  const resp = await http.post('/visual-ai/design-tokens/compute-contrast', payload)
  return resp.data
}

export async function listDesignSystemReports(limit = 50): Promise<{ total: number; reports: DesignSystemAuditReport[] }> {
  const resp = await http.get('/visual-ai/design-tokens/reports', { params: { limit } })
  return resp.data
}

// --- Phase 3: 无障碍 WCAG 2.2 扫描、键盘导航与色盲仿真 ---
export interface A11yViolation {
  violation_id: string
  rule_id: string
  rule_name: string
  severity: string
  element_id: string
  tag_name: string
  selector: string
  issue_description: string
  remediation_suggestion: string
}

export interface WcagAccessibilityReport {
  report_id: string
  page_url_or_name: string
  total_elements_scanned: number
  total_violations_count: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  compliance_score_pct: number
  is_wcag_aa_compliant: boolean
  violations: A11yViolation[]
  created_at: string
}

export async function scanDomAccessibility(payload: {
  page_url_or_name: string
  elements: Array<{
    element_id?: string
    tag_name?: string
    attributes?: Record<string, any>
    text_content?: string
    width?: number
    height?: number
    selector?: string
  }>
}): Promise<{ message: string; report: WcagAccessibilityReport }> {
  const resp = await http.post('/a11y/wcag-scanner/scan', payload)
  return resp.data
}

export async function listWcagReports(limit = 50): Promise<{ total: number; reports: WcagAccessibilityReport[] }> {
  const resp = await http.get('/a11y/wcag-scanner/reports', { params: { limit } })
  return resp.data
}

export interface FocusTraversalStep {
  step_order: number
  element_id: string
  tag_name: string
  tabindex: number
  has_visible_focus: boolean
  container_id: string | null
}

export interface KeyboardDefectItem {
  defect_id: string
  defect_type: string
  severity: string
  element_id: string
  description: string
  remediation_suggestion: string
}

export interface KeyboardNavAuditReport {
  report_id: string
  page_name: string
  total_focusable_elements: number
  total_defects_count: number
  has_focus_trap: boolean
  keyboard_accessibility_score_pct: number
  is_fully_keyboard_accessible: boolean
  traversal_path: FocusTraversalStep[]
  defects: KeyboardDefectItem[]
  created_at: string
}

export async function simulateKeyboardNav(payload: {
  page_name: string
  elements: Array<{
    element_id?: string
    tag_name?: string
    tabindex?: number
    text_content?: string
    has_focus_ring?: boolean
    container_id?: string
    is_focus_trapped?: boolean
  }>
}): Promise<{ message: string; report: KeyboardNavAuditReport }> {
  const resp = await http.post('/a11y/keyboard-nav/simulate', payload)
  return resp.data
}

export async function listKeyboardNavReports(limit = 50): Promise<{ total: number; reports: KeyboardNavAuditReport[] }> {
  const resp = await http.get('/a11y/keyboard-nav/reports', { params: { limit } })
  return resp.data
}

export interface ColorSimulationResult {
  original_hex: string
  protanopia_hex: string
  deuteranopia_hex: string
  tritanopia_hex: string
  achromatopsia_hex: string
}

export interface ColorBlindnessAuditReport {
  report_id: string
  component_or_page: string
  total_indicators_checked: number
  total_violations_count: number
  critical_count: number
  is_wcag_1_4_1_compliant: boolean
  cvd_accessibility_score_pct: number
  violations: Array<{
    violation_id: string
    element_id: string
    violation_type: string
    severity: string
    blindness_type: string
    issue_description: string
    remediation_suggestion: string
  }>
  simulations: ColorSimulationResult[]
  created_at: string
}

export async function simulateColorVision(payload: { hex_color: string }): Promise<{ message: string; simulation: ColorSimulationResult }> {
  const resp = await http.post('/a11y/color-blindness/simulate-color', payload)
  return resp.data
}

export async function auditColorBlindness(payload: {
  component_or_page: string
  status_indicators: Array<{
    element_id: string
    color_hex: string
    has_text?: boolean
    has_icon?: boolean
    status_meaning?: string
  }>
}): Promise<{ message: string; report: ColorBlindnessAuditReport }> {
  const resp = await http.post('/a11y/color-blindness/audit', payload)
  return resp.data
}

export async function listColorBlindnessReports(limit = 50): Promise<{ total: number; reports: ColorBlindnessAuditReport[] }> {
  const resp = await http.get('/a11y/color-blindness/reports', { params: { limit } })
  return resp.data
}

// --- Phase 4: 运行时性能、内存泄漏与 Web Vitals ---
export interface LongTaskItem {
  task_id: string
  duration_ms: number
  blocking_duration_ms: number
  attribution_type: string
  culprit_symbol: string
  call_stack: string[]
  severity: string
}

export interface LongTaskJankProfileReport {
  report_id: string
  page_name: string
  total_tasks_count: number
  long_tasks_count: number
  total_duration_ms: number
  total_blocking_time_ms: number
  tbt_rating: 'GOOD' | 'NEEDS_IMPROVEMENT' | 'POOR'
  estimated_fps: number
  jank_rate_pct: number
  long_tasks: LongTaskItem[]
  jank_incidents: Array<{
    incident_id: string
    frame_duration_ms: number
    dropped_frames_count: number
    culprit_task_id: string
    impact_level: string
  }>
  remediation_recommendations: string[]
  created_at: string
}

export async function profileLongTasks(payload: {
  page_name: string
  task_events: Array<{ duration_ms: number; culprit_symbol?: string; call_stack?: string[] }>
  sampling_duration_ms?: number
}): Promise<{ message: string; report: LongTaskJankProfileReport }> {
  const resp = await http.post('/client-perf/long-tasks/profile', payload)
  return resp.data
}

export async function listLongTaskReports(limit = 50): Promise<{ total: number; reports: LongTaskJankProfileReport[] }> {
  const resp = await http.get('/client-perf/long-tasks/reports', { params: { limit } })
  return resp.data
}

export interface MemoryLeakFinding {
  finding_id: string
  leak_type: string
  severity: string
  title: string
  impact_description: string
  remediation_suggestion: string
}

export interface DetachedDomSample {
  node_id: string
  tag_name: string
  retained_size_bytes: number
  retaining_closure_or_symbol: string
  description: string
}

export interface MemoryLeakAuditReport {
  report_id: string
  page_or_scenario: string
  initial_heap_bytes: number
  final_heap_bytes: number
  heap_growth_percentage: number
  total_detached_dom_count: number
  total_unreleased_listeners_count: number
  has_critical_leak: boolean
  memory_health_score_pct: number
  findings: MemoryLeakFinding[]
  detached_nodes_sample: DetachedDomSample[]
  created_at: string
}

export async function analyzeMemoryLeak(payload: {
  page_or_scenario: string
  snapshots: Array<{
    timestamp_ms?: number
    js_heap_used_bytes: number
    js_heap_total_bytes?: number
    detached_dom_node_count?: number
    event_listener_count?: number
  }>
  detached_nodes?: Array<{
    node_id: string
    tag_name?: string
    retained_size_bytes?: number
    retaining_closure?: string
    description?: string
  }>
}): Promise<{ message: string; report: MemoryLeakAuditReport }> {
  const resp = await http.post('/client-perf/memory-leak/analyze', payload)
  return resp.data
}

export async function listMemoryLeakReports(limit = 50): Promise<{ total: number; reports: MemoryLeakAuditReport[] }> {
  const resp = await http.get('/client-perf/memory-leak/reports', { params: { limit } })
  return resp.data
}

export interface WebVitalsAuditReport {
  report_id: string
  target_url_or_page: string
  overall_cwv_passed: boolean
  performance_score_pct: number
  lcp: { name: string; value: number; unit: string; rating: string; good_threshold: number; poor_threshold: number }
  inp: { name: string; value: number; unit: string; rating: string; good_threshold: number; poor_threshold: number }
  cls: { name: string; value: number; unit: string; rating: string; good_threshold: number; poor_threshold: number }
  auxiliary_metrics: Array<{ name: string; value: number; unit: string; rating: string; description: string }>
  optimization_recommendations: string[]
  created_at: string
}

export async function generateWebVitalsReport(payload: {
  target_url_or_page: string
  lcp_ms: number
  inp_ms: number
  cls_score: number
  fcp_ms?: number
  ttfb_ms?: number
}): Promise<{ message: string; report: WebVitalsAuditReport }> {
  const resp = await http.post('/client-perf/web-vitals-report/generate', payload)
  return resp.data
}

export async function listWebVitalsReports(limit = 50): Promise<{ total: number; reports: WebVitalsAuditReport[] }> {
  const resp = await http.get('/client-perf/web-vitals-report/reports', { params: { limit } })
  return resp.data
}

export async function getWebVitalsMarkdown(reportId: string): Promise<{ report_id: string; markdown: string }> {
  const resp = await http.get(`/client-perf/web-vitals-report/reports/${reportId}/markdown`)
  return resp.data
}
