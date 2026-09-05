import 'package:flutter_test/flutter_test.dart';
import 'package:compliance_scanner_mobile/main.dart';

void main() {
  testWidgets('ComplianceScannerApp loads login screen initially', (WidgetTester tester) async {
    await tester.pumpWidget(const ComplianceScannerApp());
    expect(find.text('labelGuard AI Mobile'), findsOneWidget);
    expect(find.text('Sign In to Mobile Portal'), findsOneWidget);
  });
}
