import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/user.dart';
import '../theme/app_colors.dart';

class LoginScreen extends StatefulWidget {
  final Function(User) onLoginSuccess;

  const LoginScreen({super.key, required this.onLoginSuccess});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController(text: 'inspector');
  final _passwordController = TextEditingController(text: 'password123');
  bool _isLoading = false;
  String? _error;
  bool? _isServerReachable;

  void _handleLogin() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final user = await ApiService.login(
        _usernameController.text.trim(),
        _passwordController.text.trim(),
      );
      widget.onLoginSuccess(user);
    } catch (e) {
      setState(() {
        _error = 'Login failed. Please check backend connection.';
      });
      // Auto-dismiss error after 4 seconds
      Future.delayed(const Duration(seconds: 4), () {
        if (mounted) setState(() => _error = null);
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _checkServerConnectivity() {
    if (mounted) setState(() => _isServerReachable = null);
    ApiService.ping().then((reachable) {
      if (mounted) setState(() => _isServerReachable = reachable);
    });
  }

  @override
  void initState() {
    super.initState();
    _checkServerConnectivity();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _handleDemoLogin(String role) async {
    final user = User(
      id: 1,
      username: '${role}_demo',
      role: role,
      token: 'demo-jwt-token-xyz',
    );
    widget.onLoginSuccess(user);
  }

  void _showServerConfigDialog() {
    final controller = TextEditingController(text: ApiService.baseUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.slate800,
        title: const Row(
          children: [
            Icon(Icons.wifi, color: AppColors.emeraldAccent),
            SizedBox(width: 8),
            Text('Server Connection', style: TextStyle(color: Colors.white, fontSize: 16)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Enter backend URL (laptop Wi-Fi IP and port 8000):',
              style: TextStyle(color: Colors.white70, fontSize: 12),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              style: const TextStyle(color: Colors.white, fontSize: 14),
              decoration: InputDecoration(
                labelText: 'Backend URL',
                labelStyle: const TextStyle(color: AppColors.slate400),
                hintText: 'http://172.50.8.89:8000',
                hintStyle: const TextStyle(color: Colors.white30),
                filled: true,
                fillColor: AppColors.slate900,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () {
              final newUrl = controller.text.trim();
              if (newUrl.isNotEmpty) {
                ApiService.setBaseUrl(newUrl);
                Navigator.pop(ctx);
                _checkServerConnectivity();
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('Testing connection to: $newUrl...'),
                    backgroundColor: const Color(0xFF2F6F4E),
                    duration: const Duration(seconds: 2),
                  ),
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.indigo600),
            child: const Text('Save & Connect', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.slate900,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          // Connection status indicator (tap to recheck)
          GestureDetector(
            onTap: _checkServerConnectivity,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
              child: Center(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 400),
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _isServerReachable == null
                            ? Colors.grey
                            : _isServerReachable!
                                ? AppColors.emeraldAccent
                                : Colors.redAccent,
                      ),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      _isServerReachable == null
                          ? 'Checking...'
                          : _isServerReachable!
                              ? 'Online'
                              : 'Offline (tap)',
                      style: TextStyle(
                        color: _isServerReachable == null
                            ? Colors.grey
                            : _isServerReachable!
                                ? AppColors.emeraldAccent
                                : Colors.redAccent,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.settings_ethernet, color: AppColors.emeraldAccent),
            tooltip: 'Server Connection Config',
            onPressed: _showServerConfigDialog,
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Logo Icon
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppColors.indigo600.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppColors.indigoAccent.withOpacity(0.4)),
                  ),
                  child: const Icon(Icons.verified_user, size: 48, color: AppColors.indigoAccent),
                ),
                const SizedBox(height: 16),
                const Text(
                  'InnoveXguard AI Mobile',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Legal Metrology Field Inspector Portal',
                  style: TextStyle(fontSize: 13, color: AppColors.slate400),
                ),
                const SizedBox(height: 32),

                if (_error != null)
                  Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.red.withOpacity(0.3)),
                    ),
                    child: Text(_error!, style: const TextStyle(color: Colors.redAccent, fontSize: 13)),
                  ),

                // Username field
                TextField(
                  controller: _usernameController,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: 'Inspector Username',
                    labelStyle: const TextStyle(color: AppColors.slate400),
                    prefixIcon: const Icon(Icons.person, color: AppColors.indigoAccent),
                    filled: true,
                    fillColor: AppColors.slate800,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
                  ),
                ),
                const SizedBox(height: 16),

                // Password field
                TextField(
                  controller: _passwordController,
                  obscureText: true,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: 'Password',
                    labelStyle: const TextStyle(color: AppColors.slate400),
                    prefixIcon: const Icon(Icons.lock, color: AppColors.indigoAccent),
                    filled: true,
                    fillColor: AppColors.slate800,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
                  ),
                ),
                const SizedBox(height: 24),

                // Submit Button
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: _isLoading ? null : _handleLogin,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.indigo600,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      elevation: 4,
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator(color: Colors.white)
                        : const Text('Sign In to Mobile Portal', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white)),
                  ),
                ),
                const SizedBox(height: 24),

                // Demo Quick Sign-in
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    OutlinedButton(
                      onPressed: () => _handleDemoLogin('inspector'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.indigoAccent,
                        side: const BorderSide(color: AppColors.indigo600),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: const Text('Inspector Demo'),
                    ),
                    OutlinedButton(
                      onPressed: () => _handleDemoLogin('citizen'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.emeraldAccent,
                        side: const BorderSide(color: AppColors.emeraldAccent),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: const Text('Citizen Demo'),
                    ),
                    OutlinedButton(
                      onPressed: () => _handleDemoLogin('admin'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.purpleAccent,
                        side: const BorderSide(color: Colors.purpleAccent),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: const Text('Admin Demo'),
                    ),
                  ],
                )
              ],
            ),
          ),
        ),
      ),
    );
  }
}
