class QueuedImage {
  final String id;
  final String localPath;
  final DateTime capturedAt;
  final String category;
  final String? storeAisle;
  bool isUploaded;
  String? error;

  QueuedImage({
    required this.id,
    required this.localPath,
    required this.capturedAt,
    this.category = 'Store Inspection',
    this.storeAisle,
    this.isUploaded = false,
    this.error,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'localPath': localPath,
      'capturedAt': capturedAt.toIso8601String(),
      'category': category,
      'storeAisle': storeAisle,
      'isUploaded': isUploaded ? 1 : 0,
      'error': error,
    };
  }

  factory QueuedImage.fromMap(Map<String, dynamic> map) {
    return QueuedImage(
      id: map['id'],
      localPath: map['localPath'],
      capturedAt: DateTime.parse(map['capturedAt']),
      category: map['category'] ?? 'Store Inspection',
      storeAisle: map['storeAisle'],
      isUploaded: (map['isUploaded'] ?? 0) == 1,
      error: map['error'],
    );
  }
}
