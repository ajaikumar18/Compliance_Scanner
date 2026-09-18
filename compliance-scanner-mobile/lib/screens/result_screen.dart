import 'package:flutter/material.dart';
import '../models/scan_result.dart';
import '../theme/app_colors.dart';

class ResultScreen extends StatelessWidget {
  final ScanResult scanResult;

  const ResultScreen({super.key, required this.scanResult});

  @override
  Widget build(BuildContext context) {
    final bool isCompliant = scanResult.complianceStatus == 'compliant';

    return Scaffold(
      backgroundColor: AppColors.slate900,
      appBar: AppBar(
        backgroundColor: AppColors.slate800,
        title: const Text('Compliance Scan Result', style: TextStyle(color: Colors.white, fontSize: 18)),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Citizen Evidence Confirmation & Gamification Banner
              if (scanResult.confirmationMessage != null) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: (scanResult.xpAwarded ?? 0) > 0
                        ? const Color(0xFF064E3B)
                        : const Color(0xFF451A03),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: (scanResult.xpAwarded ?? 0) > 0
                          ? const Color(0xFF10B981)
                          : const Color(0xFFF59E0B),
                      width: 1.5,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            (scanResult.xpAwarded ?? 0) > 0 ? Icons.verified : Icons.info_outline,
                            color: (scanResult.xpAwarded ?? 0) > 0 ? const Color(0xFF34D399) : const Color(0xFFFBBF24),
                            size: 22,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              (scanResult.xpAwarded ?? 0) > 0 ? 'VIOLATION CONFIRMED' : 'CITIZEN CLAIM PROCESSED',
                              style: TextStyle(
                                color: (scanResult.xpAwarded ?? 0) > 0 ? const Color(0xFF34D399) : const Color(0xFFFBBF24),
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ),
                          if (scanResult.xpAwarded != null && scanResult.xpAwarded! > 0)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: const Color(0xFF059669),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(Icons.star, color: Colors.amber, size: 14),
                                  const SizedBox(width: 4),
                                  Text(
                                    '+${scanResult.xpAwarded} XP',
                                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 11),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        scanResult.confirmationMessage!,
                        style: const TextStyle(color: Colors.white, fontSize: 13, height: 1.4),
                      ),
                      if (scanResult.currentXp != null) ...[
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Text(
                              'Citizen Trust: ${scanResult.currentXp} XP',
                              style: const TextStyle(color: Colors.white70, fontSize: 11, fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                              decoration: BoxDecoration(
                                color: Colors.white10,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                scanResult.reputationTier ?? 'Citizen Scout',
                                style: const TextStyle(color: AppColors.emeraldAccent, fontSize: 10),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
              ],
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: isCompliant ? const Color(0xFF064E3B) : const Color(0xFF7F1D1D),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: isCompliant ? AppColors.emeraldAccent.withOpacity(0.4) : AppColors.redAccent.withOpacity(0.4),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      isCompliant ? Icons.check_circle : Icons.warning_amber_rounded,
                      color: isCompliant ? AppColors.emeraldAccent : AppColors.redAccent,
                      size: 36,
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            isCompliant ? 'FULLY COMPLIANT LABEL' : 'NON-COMPLIANT (VIOLATIONS)',
                            style: TextStyle(
                              color: isCompliant ? AppColors.emeraldAccent : AppColors.redAccent,
                              fontWeight: FontWeight.bold,
                              fontSize: 15,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Legal Metrology Rules 2011 & FSSAI Guidelines',
                            style: TextStyle(
                              color: (isCompliant ? AppColors.emeraldAccent : AppColors.redAccent).withOpacity(0.8),
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                    )
                  ],
                ),
              ),
              const SizedBox(height: 24),

              Text(
                scanResult.productName,
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 18),
              ),
              const SizedBox(height: 4),
              Text(
                'Scan ID #${scanResult.scanId} • Category: ${scanResult.productCategory}',
                style: const TextStyle(color: AppColors.slate400, fontSize: 12),
              ),
              const SizedBox(height: 24),

              Row(
                children: [
                  const Text(
                    'Legal Violations Detected',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                  const Spacer(),
                  Chip(
                    label: Text(
                      '${scanResult.violationsCount} Issues',
                      style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                    backgroundColor: scanResult.violationsCount > 0 ? AppColors.redAccent : Colors.green,
                  )
                ],
              ),
              const SizedBox(height: 12),

              if (scanResult.violations.isEmpty)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppColors.slate800,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Center(
                    child: Text(
                      '🎉 No compliance violations detected on product label.',
                      style: TextStyle(color: AppColors.emeraldAccent, fontSize: 13),
                    ),
                  ),
                )
              else
                ListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: scanResult.violations.length,
                  itemBuilder: (ctx, idx) {
                    final v = scanResult.violations[idx];
                    Color sevColor = Colors.orangeAccent;
                    if (v.severity == 'high' || v.severity == 'critical') sevColor = AppColors.redAccent;
                    if (v.severity == 'low') sevColor = Colors.blueAccent;

                    return Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppColors.slate800,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: sevColor.withOpacity(0.3)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                v.fieldName.toUpperCase(),
                                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: sevColor.withOpacity(0.2),
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(color: sevColor),
                                ),
                                child: Text(
                                  '${v.severity.toUpperCase()} SEVERITY',
                                  style: TextStyle(color: sevColor, fontSize: 10, fontWeight: FontWeight.bold),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(v.details, style: const TextStyle(color: AppColors.slate300, fontSize: 12)),
                          if (v.ruleReference != null) ...[
                            const SizedBox(height: 6),
                            Text(
                              'Ref: ${v.ruleReference}',
                              style: const TextStyle(color: AppColors.slate500, fontSize: 11, fontStyle: FontStyle.italic),
                            )
                          ]
                        ],
                      ),
                    );
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }
}
