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
