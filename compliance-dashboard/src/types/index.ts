export type ViolationSeverity = 'low' | 'medium' | 'high' | 'critical';
export type ViolationType = 'missing' | 'incorrect_format' | 'undersized_font';
export type ComplianceStatus = 'compliant' | 'non_compliant' | 'partial_review_needed' | 'undetermined';

export interface User {
  id: number;
  username: string;
  role: 'inspector' | 'admin' | 'viewer' | 'citizen';
  token?: string;
  xp?: number;
  reputation_tier?: string;
}

export interface Violation {
  id?: number;
  field_name: string;
  violation_type: ViolationType;
  severity: ViolationSeverity;
  details: string;
  rule_reference?: string;
}

export interface FieldExtraction {
  field_name: string;
  extracted_value: string | null;
  extraction_method: 'ocr_tesseract' | 'ocr_easyocr' | 'genai_fallback' | 'not_found' | 'webpage_extracted' | string;
  confidence: number | string;
  bbox: [number, number, number, number] | null;
  format_valid?: boolean;
  measured_mm?: number;
  required_mm?: number;
  font_compliant?: boolean;
  tolerance_note?: string;
  detected_on_image?: string | null;
  detected_on_index?: number | null;
  detected_on_label?: string | null;
  detected_on_side?: string | null;
  detected_scan_id?: number | null;
  packaging_ocr_value?: string | null;
}

export interface GalleryImage {
  index: number;
  scan_id?: number;
  url: string;
  label: string;
  fields_detected: string[];
  fields_count?: number;
  fields?: Record<string, FieldExtraction>;
}

export interface CrossValidationItem {
  field_name: string;
  display_name: string;
  ecommerce_value: string | null;
  packaging_value: string | null;
  status: 'MATCH' | 'MISMATCH' | 'WARNING' | 'ONLINE_ONLY' | 'PACKAGING_ONLY' | 'UNDETERMINED';
  details: string;
}

export interface ConfidenceMetrics {
  ocr_quality: number;
  extraction_confidence: number;
  compliance_confidence: number;
}

export interface GeoIntelligence {
  country: string;
  inferred_from: string | null;
  evidence_type: string;
  confidence: number;
  full_declaration: string | null;
}

export interface ProductDetails {
  product_name?: string | null;
  brand?: string | null;
  category?: string | null;
  net_quantity?: string | null;
  mrp?: string | null;
  selling_price?: string | null;
  manufacturer?: string | null;
  manufacturer_address?: string | null;
  packer?: string | null;
  packer_address?: string | null;
  importer?: string | null;
  importer_address?: string | null;
  country_of_origin?: string | null;
  manufacturing_date?: string | null;
  packing_date?: string | null;
  best_before?: string | null;
  expiry_date?: string | null;
  batch_number?: string | null;
  consumer_care?: string | null;
  ingredients?: string | null;
  seller?: string | null;
  specifications?: Record<string, string>;
}

export interface EcommerceData extends ProductDetails {
  description?: string | null;
}

export interface ComplianceRuleCheck {
  rule_id: string;
  rule_name: string;
  status: 'PASS' | 'FAIL' | 'WARNING' | 'NOT_APPLICABLE' | 'UNDETERMINED';
  details: string;
  field_name?: string;
  found_in_webpage?: boolean;
  found_in_packaging?: boolean;
}

export interface DataSources {
  webpage: boolean;
  structured_data: boolean;
  product_specifications: boolean;
  packaging_ocr: boolean;
  geo_intelligence: boolean;
}

export interface ScanResult {
  scan_id: number;
  id?: string | number;
  scan_uid?: string;
  product_id?: number;
  product_name: string;
  product_category: string;
  source_url?: string;
  scanned_image_url?: string;
  scan_type: 'manual' | 'batch' | 'ecommerce' | string;
  source?: 'inspector' | 'citizen' | string;
  claimed_violation_type?: string | null;
  priority_check_result?: any;
  report_generated?: boolean;
  pdf_report_url?: string;
  image_sha256?: string;
  submitter_xp?: number;
  xp_awarded?: number;
  confirmation_message?: string;
  reputation_tier?: string;
  gtin?: string | null;
  batch_code?: string | null;
  barcodes?: Array<{ text: string; format: string; gtin?: string | null; bbox?: [number, number, number, number] | null }>;
  scale_calibration?: {
    pixels_per_mm: number;
    calibration_method: string;
    calibration_tier: string;
    tolerance_note: string;
  };
  ledger_verdict?: string | null;
  ledger_confidence?: number | null;
  compliance_status: ComplianceStatus;
  compliant?: boolean;
  violations_count: number;
  violations: Violation[];
  fields: Record<string, FieldExtraction>;
  extracted_fields?: Record<string, any>;
  gallery_images?: GalleryImage[];
  image_scans?: ScanResult[];
  ecommerce_data?: EcommerceData;
  product_details?: ProductDetails;
  data_sources?: DataSources;
  compliance_analysis?: ComplianceRuleCheck[];
  packaging_images_available?: boolean;
  cross_validation?: CrossValidationItem[];
  confidence_metrics?: ConfidenceMetrics;
  geo_intelligence?: GeoIntelligence;
  action_recommendation?: string;
  processing_time_sec?: number;
  inspector_reviewed?: boolean;
  inspector_name?: string;
  inspector_verdict?: string;
  inspector_comments?: string;
  inspector_reviewed_at?: string;
  created_at: string;
  summary?: {
    total_fields: number;
    fields_found: number;
    fields_missing: number;
    method_breakdown?: Record<string, number>;
    total_panels_scanned?: number;
  };
  // Multi-Side Packaging Intelligence
  sides_analyzed?: number;
  multi_side_summary?: string;
  side_breakdown?: Array<{
    side_index: number;
    side_label: string;
    fields_detected: string[];
    fields_count: number;
  }>;
  all_image_urls?: string[];
  // AI Product Intelligence Layers
  qr_code?: QRCodeData;
  verification_id?: string;
  verification_url?: string;
  expiry_intelligence?: ExpiryIntelligence;
  damage_analysis?: PackageDamageAnalysis;
  nutrition_info?: NutritionInfo;
  consumption_prediction?: ConsumptionPrediction;
  audience_suitability?: AudienceSuitability;
}

export interface QRCodeData {
  verification_id: string;
  verification_url: string;
  qr_code_data_url: string;
}

export interface ExpiryIntelligence {
  manufacturing_date: string;
  expiry_date: string;
  raw_declaration?: string;
  days_remaining: number;
  is_expired: boolean;
  is_safe_to_consume: boolean;
  shelf_life_percent: number;
  status: 'SAFE' | 'EXPIRING SOON' | 'EXPIRING VERY SOON' | 'EXPIRED';
  badge_color: string;
  recommendation: string;
  food_waste_prevention_tip: string;
}

export interface PackageDamageIssue {
  type: string;
  severity: 'low' | 'medium' | 'high';
  confidence: number;
  description: string;
}

export interface PackageDamageAnalysis {
  condition: 'GOOD' | 'MINOR DAMAGE' | 'SIGNIFICANT DAMAGE' | 'SEVERE DAMAGE';
  condition_score: number;
  confidence: number;
  damage_detected: boolean;
  detected_issues: PackageDamageIssue[];
  regions?: number[][];
  recommendation: string;
  disclaimer: string;
}

export interface NutrientItem {
  name: string;
  per_100g: string;
  per_serving: string;
  dv_percent?: string;
}

export interface NutritionInfo {
  available: boolean;
  serving_size: string;
  nutrients: NutrientItem[];
  raw_values?: Record<string, any>;
  ingredients: string;
  status_message: string;
}

export interface ConsumptionPrediction {
  household_size: number;
  net_quantity_g: number;
  daily_consumption_rate_g: number;
  estimated_duration_days: number;
  expected_depletion_date: string;
  waste_risk_detected: boolean;
  warning_message?: string | null;
  summary: string;
  disclaimer: string;
}

export interface AudienceProfile {
  audience: string;
  suitability: string;
  badge_color: string;
  observation: string;
}

export interface AudienceSuitability {
  profiles: AudienceProfile[];
  allergen_notice?: string;
  disclaimer: string;
}

export interface BatchStatusResponse {
  batch_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  processed: number;
  total: number;
  progress_percent: number;
  message?: string;
  result?: {
    results: ScanResult[];
  };
  results?: ScanResult[];
}

export interface AnalyticsSummary {
  total_scans: number;
  compliant_scans: number;
  non_compliant_scans: number;
  partial_scans: number;
  compliance_rate: number;
  avg_processing_time_sec?: number;
  common_violations: { type: string; count: number }[];
  scans_over_time: { date: string; compliant: number; non_compliant: number }[];
  category_breakdown?: { category: string; count: number }[];
  status_breakdown?: Record<string, number>;
}

export interface ScanAuditLog {
  id?: number;
  scan_uid: string;
  username: string;
  action: string;
  old_value?: string | null;
  new_value?: string | null;
  reason?: string | null;
  timestamp: string;
}

export interface InspectorReviewPayload {
  inspector: string;
  verdict_override?: string;
  comments: string;
  field_overrides?: Record<string, any>;
}

export interface LegalMetrologyRuleItem {
  rule_id: string;
  name: string;
  sub_rule: string;
  description: string;
  mandatory: boolean;
  applies_to_categories?: string[];
  severity: 'critical' | 'high' | 'medium' | 'low';
  statutory_requirement: string;
  validation_type: string;
  legal_reference: string;
}

export interface RulesRegistryResponse {
  rules_version: string;
  title: string;
  governing_authority: string;
  rules: LegalMetrologyRuleItem[];
  total_rules: number;
  font_size_schedule?: Record<string, any>;
}

export interface CategoryScanResponse {
  status: string;
  category_url: string;
  total_found: number;
  total_scanned: number;
  total_failed: number;
  compliant_count: number;
  non_compliant_count: number;
  review_count: number;
  compliance_rate: number;
  results: ScanResult[];
  errors: Array<{ url: string; error: string }>;
}

export interface ComplianceLedgerData {
  gtin: string;
  product_name: string | null;
  category: string | null;
  total_scans: number;
  compliant_scans: number;
  non_compliant_scans: number;
  current_verdict: 'compliant' | 'non_compliant' | 'disputed';
  rolling_confidence: number;
  calibration_breakdown: {
    ar_verified: number;
    reference_object: number;
    package_dimension: number;
    dpi_estimated: number;
  };
  batch_breakdown: Record<string, {
    total_scans: number;
    compliant_scans: number;
    non_compliant_scans: number;
    ar_verified_count?: number;
    reference_object_count?: number;
    dpi_estimated_count?: number;
    current_verdict: string;
    last_scanned_at?: string;
  }>;
  last_scanned_at?: string;
  scan_history?: Array<{
    scan_id: number;
    scan_type: string;
    status: string;
    compliance_status: string;
    calibration_tier: string;
    batch_code?: string;
    violations_count: number;
    violations: Array<{
      field_name: string;
      violation_type: string;
      severity: string;
      details: string;
    }>;
    created_at: string;
  }>;
}

export interface ReInspectionTicket {
  id: number;
  ticket_number: string;
  gtin: string;
  product_name: string | null;
  batch_code: string | null;
  trigger_scan_id: number;
  prior_verdict: 'compliant' | 'non_compliant' | 'disputed' | string;
  prior_confidence: number;
  prior_calibration_tier?: string | null;
  new_verdict: 'compliant' | 'non_compliant' | 'disputed' | string;
  new_confidence: number;
  new_calibration_tier: string;
  conflict_type: 'sensor_tier_escalation' | 'verdict_inversion' | 'consensus_disputed' | 'confidence_drop' | string;
  discrepancy_reason: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  status: 'open' | 'investigating' | 'resolved' | 'dismissed';
  assigned_to?: string | null;
  resolution_notes?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
  trigger_scan_violations?: Array<{
    field_name: string;
    violation_type: string;
    severity: string;
    details: string;
  }>;
  source?: 'inspector' | 'citizen' | string;
  claimed_violation_type?: string | null;
}

export interface TicketSummaryStats {
  total_tickets: number;
  open_tickets: number;
  critical_tickets: number;
  high_tickets: number;
  investigating_tickets: number;
  resolved_tickets: number;
}
