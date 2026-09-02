import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { LoginPage } from './pages/LoginPage';
import { UploadPage } from './pages/UploadPage';
import { ScanResultPage } from './pages/ScanResultPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { MOCK_SCANS } from './services/api';
import type { ScanResult, User } from './types';

export function App() {
  const [user, setUser] = useState<User | null>({
    id: 1,
    username: 'inspector',
    role: 'inspector',
  });
  const [token, setToken] = useState<string | null>('demo-token');
  const [activeTab, setActiveTab] = useState<'dashboard' | 'upload' | 'results' | 'analytics'>('dashboard');

  const [scans, setScans] = useState<ScanResult[]>(MOCK_SCANS);
  const [activeScan, setActiveScan] = useState<ScanResult | null>(MOCK_SCANS[0]);

  const handleLoginSuccess = (loggedInUser: User, jwtToken: string) => {
    setUser(loggedInUser);
    setToken(jwtToken);
    setActiveTab('dashboard');
  };

  const handleLogout = () => {
    setUser(null);
    setToken(null);
  };

  const handleScanCompleted = (newScan: ScanResult) => {
    setScans(prev => [newScan, ...prev]);
    setActiveScan(newScan);
    setActiveTab('results');
  };

  const handleBatchQueued = () => {
    setActiveTab('dashboard');
  };

  const handleSelectScan = (scan: ScanResult) => {
    setActiveScan(scan);
    setActiveTab('results');
  };

  if (!user || !token) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
      <Navbar
        user={user}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onLogout={handleLogout}
      />

      <main className="flex-1 pb-12">
        {activeTab === 'dashboard' && (
          <AnalyticsPage
            scans={scans}
            onSelectScan={handleSelectScan}
          />
        )}

        {activeTab === 'upload' && (
          <UploadPage
            onScanCompleted={handleScanCompleted}
            onBatchQueued={handleBatchQueued}
          />
        )}

        {activeTab === 'results' && activeScan && (
          <ScanResultPage
            scan={activeScan}
            onBackToHistory={() => setActiveTab('dashboard')}
          />
        )}

        {activeTab === 'analytics' && (
          <AnalyticsPage
            scans={scans}
            onSelectScan={handleSelectScan}
          />
        )}
      </main>

      <footer className="border-t border-slate-800/60 py-4 px-6 text-center text-xs text-slate-500 font-mono">
        Legal Metrology (Packaged Commodities) Compliance Platform • Powered by OpenCV, Tesseract, EasyOCR, Gemini Vision & FastAPI
      </footer>
    </div>
  );
}

export default App;
