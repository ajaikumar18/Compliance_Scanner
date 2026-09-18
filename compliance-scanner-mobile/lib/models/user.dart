class User {
  final int id;
  final String username;
  final String role;
  final String token;
  final int xp;

  User({
    required this.id,
    required this.username,
    required this.role,
    required this.token,
    this.xp = 100,
  });

  String get reputationTier {
    if (xp >= 500) return "Master Metrologist";
    if (xp >= 200) return "Vigilant Citizen";
    if (xp >= 50) return "Citizen Scout";
    if (xp >= 0) return "Probationary";
    return "Restricted (-XP)";
  }

  bool get isRestricted => xp < 0;

  factory User.fromJson(Map<String, dynamic> json, String token) {
    return User(
      id: json['id'] ?? 1,
      username: json['username'] ?? 'inspector',
      role: json['role'] ?? 'inspector',
      token: token,
      xp: json['xp'] ?? 100,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'role': role,
      'token': token,
      'xp': xp,
    };
  }
}

