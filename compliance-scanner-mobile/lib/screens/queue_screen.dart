import 'dart:io';
import 'package:flutter/material.dart';
import '../models/queued_image.dart';
import '../services/offline_queue_service.dart';
import '../theme/app_colors.dart';
import 'result_screen.dart';

class QueueScreen extends StatefulWidget {
  const QueueScreen({super.key});

  @override
  State<QueueScreen> createState() => _QueueScreenState();
}

class _QueueScreenState extends State<QueueScreen> {
  List<QueuedImage> _queue = [];
  bool _isSyncing = false;
  String? _syncStatus;

  @override
  void initState() {
    super.initState();
    _loadQueue();
  }

  void _loadQueue() async {
    final list = await OfflineQueueService.getQueuedImages();
    if (mounted) {
      setState(() {
        _queue = list;
      });
    }
  }

  void _triggerAutoSync() async {
    setState(() {
      _isSyncing = true;
      _syncStatus = 'Auto-uploading cached aisle scans to server...';
    });

    try {
      final results = await OfflineQueueService.syncQueue();
      _loadQueue();

      if (mounted) {
        if (results.isNotEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('✅ Auto-synced ${results.length} scan results!'),
              backgroundColor: Colors.green,
            ),
          );
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => ResultScreen(scanResult: results.first)),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('No pending items to sync.')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Sync failed: $e. Check network connection.'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isSyncing = false;
          _syncStatus = null;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final pendingCount = _queue.where((q) => !q.isUploaded).length;

    return Scaffold(
      backgroundColor: AppColors.slate900,
      appBar: AppBar(
        backgroundColor: AppColors.slate800,
        title: const Text('Offline Scan Cache Queue', style: TextStyle(color: Colors.white, fontSize: 18)),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_sweep, color: AppColors.slate400),
            onPressed: () async {
              await OfflineQueueService.clearCompleted();
              _loadQueue();
            },
            tooltip: 'Clear Synced Items',
          )
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              color: AppColors.slate800,
              child: Row(
                children: [
                  const Icon(Icons.cloud_sync, color: AppColors.indigoAccent),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '$pendingCount Pending Auto-Sync Uploads',
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                        ),
                        const Text(
                          'Images captured offline or in continuous aisle mode',
                          style: TextStyle(color: AppColors.slate400, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                  ElevatedButton.icon(
                    onPressed: _isSyncing || pendingCount == 0 ? null : _triggerAutoSync,
                    icon: _isSyncing
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.sync, size: 18),
                    label: Text(_isSyncing ? 'Syncing...' : 'Sync Now'),
                    style: ElevatedButton.styleFrom(backgroundColor: AppColors.indigoAccent),
                  )
                ],
              ),
            ),

            if (_syncStatus != null)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                color: AppColors.indigo600.withOpacity(0.2),
                child: Text(_syncStatus!, style: const TextStyle(color: AppColors.indigoAccent, fontSize: 12)),
              ),

            Expanded(
              child: _queue.isEmpty
                  ? const Center(
                      child: Text(
                        'No cached offline images in queue',
                        style: TextStyle(color: AppColors.slate400),
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _queue.length,
                      itemBuilder: (ctx, idx) {
                        final item = _queue[idx];
                        final file = File(item.localPath);
                        final fileExists = file.existsSync();

                        return Card(
                          color: AppColors.slate800,
                          margin: const EdgeInsets.only(bottom: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          child: ListTile(
                            leading: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: fileExists
                                  ? Image.file(file, width: 48, height: 48, fit: BoxFit.cover)
                                  : Container(width: 48, height: 48, color: AppColors.slate500, child: const Icon(Icons.broken_image)),
                            ),
                            title: Text(
                              item.category,
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                            ),
                            subtitle: Text(
                              'Captured: ${item.capturedAt.toString().substring(11, 16)} • ${item.storeAisle ?? "Store Aisle"}',
                              style: const TextStyle(color: AppColors.slate400, fontSize: 11),
                            ),
                            trailing: item.isUploaded
                                ? const Chip(
                                    label: Text('Synced', style: TextStyle(fontSize: 10, color: AppColors.emeraldAccent)),
                                    backgroundColor: Color(0xFF064E3B),
                                  )
                                : const Chip(
                                    label: Text('Queued', style: TextStyle(fontSize: 10, color: Colors.orangeAccent)),
                                    backgroundColor: Color(0xFF7C2D12),
                                  ),
                          ),
                        );
                      },
                    ),
            )
          ],
        ),
      ),
    );
  }
}
