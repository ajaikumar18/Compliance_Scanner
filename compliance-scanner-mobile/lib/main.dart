import 'package:flutter/material.dart';
import 'models/user.dart';
import 'screens/login_screen.dart';
import 'screens/capture_screen.dart';

/// Global navigator key — allows navigation from outside of widget trees
/// (e.g. from API service error handlers) without needing a BuildContext.
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ComplianceScannerApp());
}

class ComplianceScannerApp extends StatefulWidget {
  const ComplianceScannerApp({super.key});

  @override
  State<ComplianceScannerApp> createState() => _ComplianceScannerAppState();
}

class _ComplianceScannerAppState extends State<ComplianceScannerApp> {
  User? _currentUser;

  void _handleLoginSuccess(User user) {
    setState(() {
      _currentUser = user;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'InnoveXguard AI Mobile',
      debugShowCheckedModeBanner: false,
      navigatorKey: navigatorKey,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        primaryColor: const Color(0xFF4F46E5),
        useMaterial3: true,
      ),
      home: _currentUser == null
          ? LoginScreen(onLoginSuccess: _handleLoginSuccess)
          : CaptureScreen(
              currentUser: _currentUser,
              onLogout: () => setState(() => _currentUser = null),
            ),
    );
  }
}
