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
  extraction_method: 'ocr_tesseract' | 'ocr_easyocr' | 'genai_fallback' | 'not_found';
  confidence: number | string;
  bbox: [number, number, number, number] | null;
  format_valid?: boolean;
  measured_mm?: number;
  required_mm?: number;
  font_compliant?: boolean;
  tolerance_note?: string;
}

export interface ScanResult {
  scan_id: number;
  product_id?: number;
  product_name: string;
  product_category: string;
  source_url?: string;
  scanned_image_url?: string;
  scan_type: 'manual' | 'batch' | 'ecommerce';
  compliance_status: ComplianceStatus;
  violations_count: number;
  violations: Violation[];
  fields: Record<string, FieldExtraction>;
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
