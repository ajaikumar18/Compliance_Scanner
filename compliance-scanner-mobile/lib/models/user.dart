class User {
  final int id;
  final String username;
  final String role;
  final String token;

  User({
    required this.id,
    required this.username,
    required this.role,
    required this.token,
  });

  factory User.fromJson(Map<String, dynamic> json, String token) {
    return User(
      id: json['id'] ?? 1,
      username: json['username'] ?? 'inspector',
      role: json['role'] ?? 'inspector',
      token: token,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'role': role,
      'token': token,
    };
  }
}
