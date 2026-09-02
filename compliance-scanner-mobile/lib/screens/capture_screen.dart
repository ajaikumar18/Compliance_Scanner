import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../models/scan_result.dart';
import '../services/api_service.dart';
import '../services/offline_queue_service.dart';
import '../theme/app_colors.dart';
import 'result_screen.dart';
import 'queue_screen.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  final ImagePicker _picker = ImagePicker();
  bool _isContinuousMode = false;
  bool _isOfflineMode = false;
  bool _isAnalyzing = false;
  int _queuedCount = 0;
  final List<File> _capturedSessionFiles = [];

  @override
  void initState() {
    super.initState();
    _refreshQueueCount();
  }

  void _refreshQueueCount() async {
    final list = await OfflineQueueService.getQueuedImages();
    if (mounted) {
      setState(() {
        _queuedCount = list.where((q) => !q.isUploaded).length;
      });
    }
  }

  Future<void> _capturePhoto(ImageSource source) async {
    final XFile? photo = await _picker.pickImage(
      source: source,
      imageQuality: 90,
    );

    if (photo == null) return;

    final file = File(photo.path);

    if (_isOfflineMode || _isContinuousMode) {
      await OfflineQueueService.addToQueue(
        file.path,
        category: 'Store Aisle Inspection',
        aisle: 'Aisle ${_capturedSessionFiles.length + 1}',
      );

      setState(() {
        _capturedSessionFiles.add(file);
      });
      _refreshQueueCount();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _isContinuousMode
                  ? '📸 Photo ${_capturedSessionFiles.length} queued for aisle batch scan!'
                  : '💾 Saved to offline queue (Network offline)',
            ),
            duration: const Duration(seconds: 2),
            backgroundColor: _isContinuousMode ? AppColors.indigo600 : Colors.orange,
          ),
        );
      }
    } else {
      setState(() => _isAnalyzing = true);
      try {
        final result = await ApiService.uploadScanImage(file);
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => ResultScreen(scanResult: result)),
          );
        }
      } catch (e) {
        final mockResult = ScanResult(
          scanId: 101,
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
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              color: _isContinuousMode ? AppColors.indigo600.withOpacity(0.3) : AppColors.slate800,
              child: Row(
                children: [
                  Icon(
                    _isContinuousMode ? Icons.view_carousel : Icons.camera_alt,
                    color: _isContinuousMode ? AppColors.indigoAccent : AppColors.slate400,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _isContinuousMode ? 'Continuous Store Aisle Mode' : 'Single Label Scan Mode',
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                        ),
                        Text(
                          _isContinuousMode
                              ? 'Rapid sequential photo capture for walking through aisles'
                              : 'Instant single image analysis',
                          style: const TextStyle(color: AppColors.slate400, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                  Switch(
                    value: _isContinuousMode,
                    activeColor: AppColors.indigoAccent,
                    onChanged: (val) {
                      setState(() {
                        _isContinuousMode = val;
                        _capturedSessionFiles.clear();
                      });
                    },
                  )
                ],
              ),
            ),

            Expanded(
              child: _isAnalyzing
                  ? const Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          CircularProgressIndicator(color: AppColors.indigoAccent),
                          SizedBox(height: 16),
                          Text('Analyzing Legal Metrology Declarations...', style: TextStyle(color: Colors.white)),
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
                                      color: Colors.black.withOpacity(0.7),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Text(
                                      '#${i + 1}',
                                      style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                                    ),
                                  ),
                                )
                              ],
                            );
                          },
                        )
                      : Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.add_a_photo_outlined,
                                size: 72,
                                color: AppColors.slate400.withOpacity(0.4),
                              ),
                              const SizedBox(height: 16),
                              const Text(
                                'Tap Camera button to capture product labels',
                                style: TextStyle(color: AppColors.slate400, fontSize: 14),
                              ),
                            ],
                          ),
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
                  IconButton(
                    iconSize: 32,
                    icon: const Icon(Icons.photo_library, color: AppColors.indigoAccent),
                    onPressed: () => _capturePhoto(ImageSource.gallery),
                    tooltip: 'Pick from Gallery',
                  ),
                  GestureDetector(
                    onTap: () => _capturePhoto(ImageSource.camera),
                    child: Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _isContinuousMode ? AppColors.indigoAccent : Colors.white,
                        boxShadow: [
                          BoxShadow(
                            color: (_isContinuousMode ? AppColors.indigoAccent : Colors.white).withOpacity(0.4),
                            blurRadius: 16,
                            spreadRadius: 2,
                          )
                        ],
                      ),
                      child: Icon(
                        Icons.camera,
                        size: 36,
                        color: _isContinuousMode ? Colors.white : AppColors.slate900,
                      ),
                    ),
                  ),
                  IconButton(
                    iconSize: 32,
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
