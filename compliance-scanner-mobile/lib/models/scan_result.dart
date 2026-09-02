class Violation {
  final String fieldName;
  final String violationType;
  final String severity;
  final String details;
  final String? ruleReference;

  Violation({
    required this.fieldName,
    required this.violationType,
    required this.severity,
    required this.details,
    this.ruleReference,
  });

  factory Violation.fromJson(Map<String, dynamic> json) {
    return Violation(
      fieldName: json['field_name'] ?? json['field'] ?? 'unknown',
      violationType: json['violation_type'] ?? 'missing',
      severity: json['severity'] ?? 'medium',
      details: json['details'] ?? '',
      ruleReference: json['rule_reference'],
    );
  }
}

class ScanResult {
  final int scanId;
  final String productName;
  final String productCategory;
  final String complianceStatus;
  final int violationsCount;
  final List<Violation> violations;
  final String? sourceUrl;

  ScanResult({
    required this.scanId,
    required this.productName,
    required this.productCategory,
    required this.complianceStatus,
    required this.violationsCount,
    required this.violations,
    this.sourceUrl,
  });

  factory ScanResult.fromJson(Map<String, dynamic> json) {
    final vList = (json['violations'] as List<dynamic>?)
            ?.map((v) => Violation.fromJson(v as Map<String, dynamic>))
            .toList() ??
        [];

    return ScanResult(
      scanId: json['scan_id'] ?? 0,
      productName: json['product_name'] ?? 'Product Scan',
      productCategory: json['category'] ?? 'General',
      complianceStatus: json['compliance_status'] ?? 'compliant',
      violationsCount: json['violations_count'] ?? vList.length,
      violations: vList,
      sourceUrl: json['source_url'] ?? json['raw_image_url'],
    );
  }
}
