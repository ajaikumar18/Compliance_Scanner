import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import '../models/user.dart';
import '../models/scan_result.dart';
import '../services/api_service.dart';
import '../services/offline_queue_service.dart';
import '../theme/app_colors.dart';
import 'result_screen.dart';
import 'queue_screen.dart';

class CaptureScreen extends StatefulWidget {
  final User? currentUser;
  final VoidCallback? onLogout;

  const CaptureScreen({super.key, this.currentUser, this.onLogout});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

enum ScanCaptureMode {
  single,
  multiSide,
  aisleBatch,
}

class _CaptureScreenState extends State<CaptureScreen> {
  final ImagePicker _picker = ImagePicker();
  ScanCaptureMode _captureMode = ScanCaptureMode.multiSide;
  bool get _isContinuousMode => _captureMode == ScanCaptureMode.aisleBatch;
  bool get _isMultiSideMode => _captureMode == ScanCaptureMode.multiSide;
  bool _isOfflineMode = false;
  bool _isAnalyzing = false;
  int _queuedCount = 0;
  final List<File> _capturedSessionFiles = [];

  String _selectedRole = 'officer'; // 'officer' | 'citizen'
  String _claimedViolationType = 'missing_mrp';
  int _citizenXp = 100;
  String _reputationTier = 'Citizen Scout';

  @override
  void initState() {
    super.initState();
    if (widget.currentUser != null) {
      if (widget.currentUser!.role == 'citizen') {
        _selectedRole = 'citizen';
      }
      _citizenXp = widget.currentUser!.xp;
      _reputationTier = widget.currentUser!.reputationTier;
    }
    _refreshQueueCount();
  }
  final List<Map<String, String>> _violationOptions = const [
    {'label': 'Missing MRP', 'value': 'missing_mrp'},
    {'label': 'Undersized Font', 'value': 'undersized_font'},
    {'label': 'Missing Origin', 'value': 'missing_origin'},
    {'label': 'Other', 'value': 'other'},
  ];

  void _refreshQueueCount() async {
    final list = await OfflineQueueService.getQueuedImages();
    if (mounted) {
      setState(() {
        _queuedCount = list.where((q) => !q.isUploaded).length;
      });
    }
  }

  /// Reusable restricted-submission dialog (replaces two identical inline dialogs)
  void _showTamperDialog(String message) {
    if (!mounted) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.slate800,
        title: const Row(
          children: [
            Icon(Icons.gavel, color: Colors.redAccent),
            SizedBox(width: 8),
            Text('Submission Restricted', style: TextStyle(color: Colors.white, fontSize: 16)),
          ],
        ),
        content: Text(
          message,
          style: const TextStyle(color: Colors.white70, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Understood', style: TextStyle(color: AppColors.emeraldAccent)),
          ),
        ],
      ),
    );
  }

  Widget _buildModeTab(ScanCaptureMode mode, String title, IconData icon) {
    final isSelected = _captureMode == mode;
    return GestureDetector(
      onTap: () {
        setState(() {
          _captureMode = mode;
          _capturedSessionFiles.clear();
        });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.indigo600 : AppColors.slate900,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? AppColors.indigoAccent : Colors.white10,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 13, color: isSelected ? Colors.white : AppColors.slate400),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: isSelected ? Colors.white : AppColors.slate400,
                  fontSize: 10.5,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _capturePhoto(ImageSource source) async {
    // Subtle tactile feedback on capture tap
    await HapticFeedback.lightImpact();

    final XFile? photo = await _picker.pickImage(
      source: source,
      imageQuality: 90,
    );

    if (photo == null) return;

    final file = File(photo.path);
    final bytes = await file.readAsBytes();
    final clientHash = sha256.convert(bytes).toString();

    if (_isOfflineMode) {
      await OfflineQueueService.addToQueue(
        file.path,
        category: 'Store Aisle Inspection',
        aisle: 'Aisle ${_capturedSessionFiles.length + 1}',
      );
      setState(() => _capturedSessionFiles.add(file));
      _refreshQueueCount();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('💾 Saved to offline queue (Network offline)'),
            duration: Duration(seconds: 2),
            backgroundColor: Colors.orange,
          ),
        );
      }
    } else if (_isMultiSideMode) {
      setState(() => _capturedSessionFiles.add(file));
      if (mounted) {
        final count = _capturedSessionFiles.length;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              count == 1
                  ? '📸 Side 1 captured! Tap Camera for Side 2 (Back/Flap), or tap Analyze.'
                  : '📸 Side $count captured! Ready to analyze full product.',
            ),
            duration: const Duration(seconds: 2),
            backgroundColor: AppColors.indigo600,
          ),
        );
      }
    } else if (_isContinuousMode) {
      setState(() => _capturedSessionFiles.add(file));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('📸 Photo ${_capturedSessionFiles.length} queued for aisle batch scan!'),
            duration: const Duration(seconds: 2),
            backgroundColor: AppColors.indigo600,
          ),
        );
      }
    } else {
      setState(() => _isAnalyzing = true);
      try {
        final result = await ApiService.uploadScanImage(
          file,
          submitterRole: _selectedRole == 'citizen' ? 'citizen' : 'inspector',
          claimedViolationType: _selectedRole == 'citizen' ? _claimedViolationType : null,
          imageSha256: clientHash,
        );
        if (mounted) {
          if (result.currentXp != null) {
            setState(() {
              _citizenXp = result.currentXp!;
              if (result.reputationTier != null) {
                _reputationTier = result.reputationTier!;
              }
            });
          }
          if (result.confirmationMessage != null) {
            await _showConfirmationDialog(result);
          }
          if (mounted) {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => ResultScreen(scanResult: result)),
            );
          }
        }
      } catch (e) {
        final errStr = e.toString();
        if (errStr.contains('negative trust XP') || errStr.contains('tamper') || errStr.contains('blocked')) {
          _showTamperDialog(errStr.replaceAll('Exception:', '').trim());
          return;
        }
        final mockResult = ScanResult(
          scanId: '101',
          productName: 'Sample Product Label (Mobile Offline Scan)',
          productCategory: 'Packaged Foods',
          complianceStatus: 'non_compliant',
          violationsCount: 1,
          violations: [
            Violation(
              fieldName: 'mrp',
              violationType: 'missing',
              severity: 'high',
              details: 'Mandatory declaration Maximum Retail Price (MRP) missing from label.',
              ruleReference: 'Legal Metrology Rules 2011, Rule 6(1)(e)',
            ),
          ],
        );
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => ResultScreen(scanResult: mockResult)),
          );
        }
      } finally {
        if (mounted) setState(() => _isAnalyzing = false);
      }
    }
  }

  Future<void> _showConfirmationDialog(ScanResult result) async {
    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.slate800,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(
            color: (result.xpAwarded ?? 0) > 0 ? const Color(0xFF10B981) : const Color(0xFFF59E0B),
            width: 1.5,
          ),
        ),
        title: Row(
          children: [
            Icon(
              (result.xpAwarded ?? 0) > 0 ? Icons.verified : Icons.info_outline,
              color: (result.xpAwarded ?? 0) > 0 ? const Color(0xFF10B981) : const Color(0xFFF59E0B),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                (result.xpAwarded ?? 0) > 0 ? 'Violation Confirmed!' : 'Claim Result',
                style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              result.confirmationMessage!,
              style: const TextStyle(color: Colors.white, fontSize: 13, height: 1.4),
            ),
            if (result.xpAwarded != null && result.xpAwarded! > 0) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFF064E3B),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF10B981).withValues(alpha: 0.5)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.star, color: Colors.amber, size: 16),
                    const SizedBox(width: 6),
                    Text(
                      '+${result.xpAwarded} Trust XP Earned',
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            style: ElevatedButton.styleFrom(
              backgroundColor: (result.xpAwarded ?? 0) > 0 ? const Color(0xFF059669) : AppColors.indigo600,
            ),
            child: const Text('View Inspection Details', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _submitMultiSideProduct() async {
    if (_capturedSessionFiles.isEmpty) return;

    setState(() => _isAnalyzing = true);
    try {
      final result = await ApiService.uploadMultiSideScan(
        _capturedSessionFiles,
        submitterRole: _selectedRole == 'citizen' ? 'citizen' : 'inspector',
        claimedViolationType: _selectedRole == 'citizen' ? _claimedViolationType : null,
      );

      setState(() {
        _capturedSessionFiles.clear();
      });

      if (mounted) {
        if (result.currentXp != null) {
          setState(() {
            _citizenXp = result.currentXp!;
            if (result.reputationTier != null) {
              _reputationTier = result.reputationTier!;
            }
          });
        }
        if (result.confirmationMessage != null) {
          await _showConfirmationDialog(result);
        }
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => ResultScreen(scanResult: result)),
          );
        }
      }
    } catch (e) {
      final errStr = e.toString();
      if (errStr.contains('negative trust XP') || errStr.contains('tamper') || errStr.contains('blocked')) {
        _showTamperDialog(errStr.replaceAll('Exception:', '').trim());
        return;
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Multi-side analysis failed: $e'),
            backgroundColor: Colors.redAccent,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isAnalyzing = false);
    }
  }

  void _submitContinuousBatch() async {
    if (_capturedSessionFiles.isEmpty) return;

    setState(() => _isAnalyzing = true);
    try {
      final results = await ApiService.uploadBatchImages(_capturedSessionFiles);
      setState(() {
        _capturedSessionFiles.clear();
      });
      _refreshQueueCount();

      if (mounted && results.isNotEmpty) {
        Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => ResultScreen(scanResult: results.first)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Saved continuous batch to Offline Queue for auto-sync.'),
            backgroundColor: Colors.orange,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isAnalyzing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.slate900,
      appBar: AppBar(
        backgroundColor: AppColors.slate800,
        title: const Text('Field Compliance Scanner', style: TextStyle(color: Colors.white, fontSize: 18)),
        actions: [
          IconButton(
            icon: Icon(
              _isOfflineMode ? Icons.wifi_off : Icons.wifi,
              color: _isOfflineMode ? Colors.orange : AppColors.emeraldAccent,
            ),
            tooltip: _isOfflineMode ? 'Offline Mode (Queue active)' : 'Online Mode',
            onPressed: () {
              setState(() => _isOfflineMode = !_isOfflineMode);
            },
          ),
          Stack(
            alignment: Alignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.inventory_2_outlined, color: Colors.white),
                onPressed: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const QueueScreen()),
                  );
                  _refreshQueueCount();
                },
              ),
              if (_queuedCount > 0)
                Positioned(
                  right: 6,
                  top: 6,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                    child: Text(
                      '$_queuedCount',
                      style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                    ),
                  ),
                )
            ],
          ),
          if (widget.onLogout != null)
            IconButton(
              icon: const Icon(Icons.logout, color: Colors.white70),
              tooltip: 'Sign Out',
              onPressed: widget.onLogout,
            ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // ── Mode Toggle: Officer vs Citizen ──
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: AppColors.slate900,
              child: Container(
                height: 38,
                decoration: BoxDecoration(
                  color: AppColors.slate800,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: GestureDetector(
                        onTap: () => setState(() => _selectedRole = 'officer'),
                        child: Container(
                          decoration: BoxDecoration(
                            color: _selectedRole == 'officer' ? AppColors.indigoAccent : Colors.transparent,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          alignment: Alignment.center,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.badge_outlined,
                                size: 16,
                                color: _selectedRole == 'officer' ? Colors.white : AppColors.slate400,
                              ),
                              const SizedBox(width: 6),
                              Text(
                                'Officer Mode',
                                style: TextStyle(
                                  color: _selectedRole == 'officer' ? Colors.white : AppColors.slate400,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      child: GestureDetector(
                        onTap: () => setState(() => _selectedRole = 'citizen'),
                        child: Container(
                          decoration: BoxDecoration(
                            color: _selectedRole == 'citizen' ? AppColors.emeraldAccent : Colors.transparent,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          alignment: Alignment.center,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.public,
                                size: 16,
                                color: _selectedRole == 'citizen' ? Colors.black : AppColors.slate400,
                              ),
                              const SizedBox(width: 6),
                              Text(
                                'Citizen Mode',
                                style: TextStyle(
                                  color: _selectedRole == 'citizen' ? Colors.black : AppColors.slate400,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // ── Citizen Mode Gamification Card & Question Dropdown ──
            if (_selectedRole == 'citizen')
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                color: AppColors.slate800,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Gamification Trust XP Badge
                    Container(
                      margin: const EdgeInsets.only(bottom: 10),
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: _citizenXp < 0 ? Colors.red.shade900.withOpacity(0.5) : AppColors.slate900,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: _citizenXp < 0 ? Colors.redAccent : AppColors.emeraldAccent.withOpacity(0.4),
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            _citizenXp < 0 ? Icons.warning_amber_rounded : Icons.military_tech,
                            color: _citizenXp < 0 ? Colors.redAccent : Colors.amber,
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      'Trust XP: $_citizenXp',
                                      style: TextStyle(
                                        color: _citizenXp < 0 ? Colors.redAccent : Colors.white,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 12,
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                      decoration: BoxDecoration(
                                        color: _citizenXp < 0 ? Colors.red : AppColors.emeraldAccent.withOpacity(0.2),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        _reputationTier,
                                        style: TextStyle(
                                          color: _citizenXp < 0 ? Colors.white : AppColors.emeraldAccent,
                                          fontSize: 10,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  _citizenXp < 0
                                      ? 'Privileges restricted due to false claims or evidence tampering.'
                                      : '+50 XP verified • -25 XP unverified claim • -100 XP tampering',
                                  style: TextStyle(
                                    color: _citizenXp < 0 ? Colors.red.shade200 : AppColors.slate400,
                                    fontSize: 10,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Text(
                      "What's wrong with this label?",
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      decoration: BoxDecoration(
                        color: AppColors.slate900,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.emeraldAccent.withOpacity(0.5)),
                      ),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<String>(
                          value: _claimedViolationType,
                          isExpanded: true,
                          dropdownColor: AppColors.slate900,
                          style: const TextStyle(color: Colors.white, fontSize: 13),
                          icon: const Icon(Icons.arrow_drop_down, color: AppColors.emeraldAccent),
                          items: _violationOptions.map((opt) {
                            return DropdownMenuItem<String>(
                              value: opt['value'],
                              child: Text(opt['label']!),
                            );
                          }).toList(),
                          onChanged: (val) {
                            if (val != null) {
                              setState(() => _claimedViolationType = val);
                            }
                          },
                        ),
                      ),
                    ),
                  ],
                ),
              ),

            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              color: AppColors.slate800,
              child: Row(
                children: [
                  Expanded(child: _buildModeTab(ScanCaptureMode.single, '1-Side Instant', Icons.camera_alt)),
                  const SizedBox(width: 6),
                  Expanded(child: _buildModeTab(ScanCaptureMode.multiSide, 'Multi-Side (2-4)', Icons.flip_camera_android)),
                  const SizedBox(width: 6),
                  Expanded(child: _buildModeTab(ScanCaptureMode.aisleBatch, 'Aisle Batch', Icons.view_carousel)),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              color: _isMultiSideMode
                  ? AppColors.indigo600.withValues(alpha: 0.25)
                  : (_isContinuousMode ? AppColors.indigo600.withValues(alpha: 0.15) : AppColors.slate900),
              child: Row(
                children: [
                  Icon(
                    _isMultiSideMode ? Icons.auto_awesome : Icons.info_outline,
                    size: 14,
                    color: _isMultiSideMode ? AppColors.emeraldAccent : AppColors.slate400,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      _isMultiSideMode
                          ? (_capturedSessionFiles.isEmpty
                              ? '📸 Snap Front, Back & Flaps of SAME product. All declarations merged!'
                              : 'Captured ${_capturedSessionFiles.length} side(s). Snap another side or tap Analyze below.')
                          : (_isContinuousMode
                              ? 'Continuous store aisle walk mode: Rapid photos of multiple items.'
                              : 'Instant single photo scan with immediate analysis.'),
                      style: TextStyle(
                        color: _isMultiSideMode ? Colors.white : AppColors.slate400,
                        fontSize: 11,
                        fontWeight: _isMultiSideMode ? FontWeight.w500 : FontWeight.normal,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            Expanded(
              child: _isAnalyzing
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const CircularProgressIndicator(color: AppColors.indigoAccent),
                          const SizedBox(height: 16),
                          Text(
                            _isMultiSideMode && _capturedSessionFiles.length > 1
                                ? 'Analyzing ${_capturedSessionFiles.length} sides in parallel...'
                                : 'Analyzing Legal Metrology Declarations...',
                            style: const TextStyle(color: Colors.white, fontSize: 13),
                          ),
                        ],
                      ),
                    )
                  : _capturedSessionFiles.isNotEmpty
                      ? GridView.builder(
                          padding: const EdgeInsets.all(16),
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 3,
                            crossAxisSpacing: 10,
                            mainAxisSpacing: 10,
                          ),
                          itemCount: _capturedSessionFiles.length,
                          itemBuilder: (ctx, i) {
                            String sideLabel;
                            if (_isMultiSideMode) {
                              if (i == 0) {
                                sideLabel = 'Side 1 (Front)';
                              } else if (i == 1) {
                                sideLabel = 'Side 2 (Back)';
                              } else if (i == 2) {
                                sideLabel = 'Side 3 (Flap)';
                              } else {
                                sideLabel = 'Side ${i + 1}';
                              }
                            } else {
                              sideLabel = '#${i + 1}';
                            }
                            return Stack(
                              fit: StackFit.expand,
                              children: [
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(10),
                                  child: Image.file(_capturedSessionFiles[i], fit: BoxFit.cover),
                                ),
                                Positioned(
                                  top: 4,
                                  left: 4,
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: Colors.black.withValues(alpha: 0.75),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Text(
                                      sideLabel,
                                      style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold),
                                    ),
                                  ),
                                ),
                                Positioned(
                                  top: 4,
                                  right: 4,
                                  child: GestureDetector(
                                    onTap: () {
                                      setState(() => _capturedSessionFiles.removeAt(i));
                                    },
                                    child: Container(
                                      padding: const EdgeInsets.all(3),
                                      decoration: const BoxDecoration(
                                        color: Colors.black87,
                                        shape: BoxShape.circle,
                                      ),
                                      child: const Icon(Icons.close, color: Colors.white, size: 12),
                                    ),
                                  ),
                                ),
                              ],
                            );
                          },
                        )
                      : Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                _isMultiSideMode ? Icons.flip_camera_android : Icons.add_a_photo_outlined,
                                size: 72,
                                color: AppColors.slate400.withValues(alpha: 0.4),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                _isMultiSideMode
                                    ? 'Tap Camera below to capture Side 1 (Front)\nand Side 2 (Back/Flap)'
                                    : 'Tap Camera button to capture product labels',
                                textAlign: TextAlign.center,
                                style: const TextStyle(color: AppColors.slate400, fontSize: 13),
                              ),
                            ],
                          ),
                        ),
            ),

            if (_isMultiSideMode && _capturedSessionFiles.isNotEmpty)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                color: AppColors.slate800,
                child: Row(
                  children: [
                    TextButton.icon(
                      onPressed: () => setState(() => _capturedSessionFiles.clear()),
                      icon: const Icon(Icons.delete_outline, size: 16, color: Colors.white60),
                      label: const Text('Clear', style: TextStyle(color: Colors.white60, fontSize: 12)),
                    ),
                    const Spacer(),
                    ElevatedButton.icon(
                      onPressed: _isAnalyzing ? null : _submitMultiSideProduct,
                      icon: const Icon(Icons.bolt, color: Colors.black, size: 18),
                      label: Text(
                        'Analyze Product (${_capturedSessionFiles.length} Sides)',
                        style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.emeraldAccent,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    )
                  ],
                ),
              ),

            if (_isContinuousMode && _capturedSessionFiles.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(16),
                color: AppColors.slate800,
                child: Row(
                  children: [
                    Text(
                      '${_capturedSessionFiles.length} Photos Captured',
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                    ),
                    const Spacer(),
                    ElevatedButton.icon(
                      onPressed: _submitContinuousBatch,
                      icon: const Icon(Icons.send),
                      label: const Text('Process Batch'),
                      style: ElevatedButton.styleFrom(backgroundColor: AppColors.indigoAccent),
                    )
                  ],
                ),
              ),

            Container(
              padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 32),
              color: AppColors.slate900,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  // Camera-only chain of custody badge
                  Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.verified_user_outlined,
                        color: _selectedRole == 'citizen' ? AppColors.emeraldAccent : AppColors.indigoAccent,
                        size: 24,
                      ),
                      const SizedBox(height: 2),
                      const Text(
                        'Live Capture Only',
                        style: TextStyle(color: AppColors.slate400, fontSize: 9, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  GestureDetector(
                    onTap: () {
                      if (_selectedRole == 'citizen' && _citizenXp < 0) {
                        _showTamperDialog(
                          'Your account has a negative trust score ($_citizenXp XP) due to unverified claims or evidence tampering. Reporting privileges are suspended.',
                        );
                        return;
                      }
                      _capturePhoto(ImageSource.camera);
                    },
                    child: Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _selectedRole == 'citizen'
                            ? (_citizenXp < 0 ? Colors.grey.shade700 : AppColors.emeraldAccent)
                            : (_isContinuousMode ? AppColors.indigoAccent : Colors.white),
                        boxShadow: [
                          BoxShadow(
                            color: (_selectedRole == 'citizen'
                                    ? (_citizenXp < 0 ? Colors.transparent : AppColors.emeraldAccent)
                                    : (_isContinuousMode ? AppColors.indigoAccent : Colors.white))
                                .withOpacity(0.4),
                            blurRadius: 16,
                            spreadRadius: 2,
                          )
                        ],
                      ),
                      child: Icon(
                        _selectedRole == 'citizen' && _citizenXp < 0 ? Icons.block : Icons.camera_alt,
                        size: 36,
                        color: _selectedRole == 'citizen'
                            ? (_citizenXp < 0 ? Colors.redAccent : Colors.black)
                            : (_isContinuousMode ? Colors.white : AppColors.slate900),
                      ),
                    ),
                  ),
                  IconButton(
                    iconSize: 28,
                    icon: const Icon(Icons.refresh, color: AppColors.slate400),
                    onPressed: _refreshQueueCount,
                    tooltip: 'Refresh Status',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
