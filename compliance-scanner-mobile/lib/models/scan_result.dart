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
  final String scanId;
  final String productName;
  final String productCategory;
  final String complianceStatus;
  final int violationsCount;
  final List<Violation> violations;
  final String? sourceUrl;
  final int? xpAwarded;
  final int? currentXp;
  final String? confirmationMessage;
  final String? reputationTier;

  ScanResult({
    required this.scanId,
    required this.productName,
    required this.productCategory,
    required this.complianceStatus,
    required this.violationsCount,
    required this.violations,
    this.sourceUrl,
    this.xpAwarded,
    this.currentXp,
    this.confirmationMessage,
    this.reputationTier,
  });

  factory ScanResult.fromJson(Map<String, dynamic> json) {
    final vList = (json['violations'] as List<dynamic>?)
            ?.map((v) => Violation.fromJson(v as Map<String, dynamic>))
            .toList() ??
        [];

    return ScanResult(
      scanId: json['scan_id']?.toString() ?? json['scan_uid']?.toString() ?? '0',
      productName: json['product_name'] ?? 'Product Scan',
      productCategory: json['product_category'] ?? json['category'] ?? 'General',
      complianceStatus: json['compliance_status'] ?? 'compliant',
      violationsCount: json['violations_count'] is int
          ? json['violations_count']
          : (int.tryParse(json['violations_count']?.toString() ?? '') ?? vList.length),
      violations: vList,
      sourceUrl: json['source_url'] ?? json['raw_image_url'] ?? json['scanned_image_url'],
      xpAwarded: json['xp_awarded'] is int
          ? json['xp_awarded']
          : int.tryParse(json['xp_awarded']?.toString() ?? ''),
      currentXp: json['current_xp'] is int
          ? json['current_xp']
          : int.tryParse(json['current_xp']?.toString() ?? ''),
      confirmationMessage: json['confirmation_message']?.toString(),
      reputationTier: json['reputation_tier']?.toString(),
    );
  }
}

