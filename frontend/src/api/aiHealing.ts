import http from './http'

export type LocatorType = 'xpath' | 'css_selector' | 'accessibility_id' | 'id' | 'name' | 'test_id' | 'text'

export interface ElementFingerprintItem {
  tag_name: string
  text_content?: string | null
  element_id?: string | null
  class_names?: string[]
  attributes?: Record<string, string>
  parent_tag?: string | null
  xpath?: string | null
}

export interface HealedLocatorProposalItem {
  proposal_id: string
  healed_locator: string
  locator_type: LocatorType
  confidence_score: number
  match_strategy: string
  matched_element: ElementFingerprintItem
  reason: string
}

export interface LocatorHealingResultItem {
  audit_id: string
  success: boolean
  original_locator: string
  best_proposal: HealedLocatorProposalItem | null
  all_proposals: HealedLocatorProposalItem[]
  elements_scanned_count: number
  healed_at: string
}

export interface HealLocatorRequest {
  original_locator: string
  locator_type?: LocatorType
  last_known_fingerprint?: ElementFingerprintItem | null
  live_dom_elements: ElementFingerprintItem[]
  min_confidence?: number
  error_message?: string
}

export const aiHealingLocatorsApi = {
  healLocator(data: HealLocatorRequest): Promise<LocatorHealingResultItem> {
    return http.post('/ai-healing/locators/heal', data)
  },

  listHistory(): Promise<{ total: number; history: LocatorHealingResultItem[] }> {
    return http.get('/ai-healing/locators/history')
  },
}
