import 'dart:convert';
import 'dart:io';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/queued_image.dart';
import '../models/scan_result.dart';
import 'api_service.dart';

class OfflineQueueService {
  static const String _storageKey = 'offline_scan_queue_v1';

  // ── Load Cached Queue Items ────────────────────────────────────────────────
  static Future<List<QueuedImage>> getQueuedImages() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr = prefs.getString(_storageKey);
    if (jsonStr == null || jsonStr.isEmpty) return [];

    try {
      final List<dynamic> decoded = jsonDecode(jsonStr);
      return decoded.map((item) => QueuedImage.fromMap(item as Map<String, dynamic>)).toList();
    } catch (_) {
      return [];
    }
  }

  // ── Save Queue Items ──────────────────────────────────────────────────────
  static Future<void> _saveQueue(List<QueuedImage> queue) async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = jsonEncode(queue.map((q) => q.toMap()).toList());
    await prefs.setString(_storageKey, encoded);
  }

  // ── Add Item to Queue ──────────────────────────────────────────────────────
  static Future<QueuedImage> addToQueue(String localPath, {String category = 'Store Aisle', String? aisle}) async {
    final queue = await getQueuedImages();
    final newItem = QueuedImage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      localPath: localPath,
      capturedAt: DateTime.now(),
      category: category,
      storeAisle: aisle,
    );
    queue.add(newItem);
    await _saveQueue(queue);
    return newItem;
  }

  // ── Auto-Sync / Upload Queued Items ─────────────────────────────────────────
  static Future<List<ScanResult>> syncQueue() async {
    final queue = await getQueuedImages();
    final pending = queue.where((q) => !q.isUploaded).toList();
    if (pending.isEmpty) return [];

    final List<File> filesToUpload = [];
    for (final item in pending) {
      final file = File(item.localPath);
      if (await file.exists()) {
        filesToUpload.add(file);
      }
    }

    if (filesToUpload.isEmpty) return [];

    try {
      final results = await ApiService.uploadBatchImages(filesToUpload);

      // Mark uploaded in queue
      for (final item in pending) {
        item.isUploaded = true;
      }
      await _saveQueue(queue);
      return results;
    } catch (e) {
      // Retain items for future auto-sync
      rethrow;
    }
  }

  // ── Clear Uploaded Items ───────────────────────────────────────────────────
  static Future<void> clearCompleted() async {
    final queue = await getQueuedImages();
    final remaining = queue.where((q) => !q.isUploaded).toList();
    await _saveQueue(remaining);
  }
}
