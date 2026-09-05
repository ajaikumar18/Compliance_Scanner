export type ViolationSeverity = 'low' | 'medium' | 'high' | 'critical';
export type ViolationType = 'missing' | 'incorrect_format' | 'undersized_font';
export type ComplianceStatus = 'compliant' | 'non_compliant' | 'partial_review_needed';

export interface User {
  id: number;
  username: string;
  role: 'inspector' | 'admin' | 'viewer';
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
  extraction_method: 'ocr_tesseract' | 'ocr_easyocr' | 'genai_fallback' | 'ecommerce_html_spec' | 'not_found' | string;
  confidence: number | string;
  bbox: [number, number, number, number] | null;
  format_valid?: boolean;
  measured_mm?: number;
  required_mm?: number;
  font_compliant?: boolean;
  tolerance_note?: string;
  calibration_tier?: 'ar_verified' | 'reference_object' | 'package_dimension' | 'dpi_estimated' | string;
  calibration_method?: string;
}

export interface ScanResult {
  scan_id: number;
  product_id?: number;
  product_name: string;
  product_category: string;
  source_url?: string;
  scanned_image_url?: string;
  scan_type: 'manual' | 'batch' | 'ecommerce' | string;
  gtin?: string | null;
  batch_code?: string | null;
  barcodes?: Array<{ text: string; format: string; gtin?: string | null; bbox?: [number, number, number, number] | null }>;
  compliance_status: ComplianceStatus;
  violations_count: number;
  violations: Violation[];
  fields: Record<string, FieldExtraction>;
  scale_calibration?: {
    pixels_per_mm: number;
    calibration_method: string;
    calibration_tier: string;
    tolerance_note: string;
  };
  created_at: string;
  summary?: {
    total_fields: number;
    fields_found: number;
    fields_missing: number;
    method_breakdown: Record<string, number>;
  };
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
  common_violations: { type: string; count: number }[];
  scans_over_time: { date: string; compliant: number; non_compliant: number }[];
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
}

export interface TicketSummaryStats {
  total_tickets: number;
  open_tickets: number;
  critical_tickets: number;
  high_tickets: number;
  investigating_tickets: number;
  resolved_tickets: number;
}

