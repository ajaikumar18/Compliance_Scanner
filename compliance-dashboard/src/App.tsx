import { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import { Navbar } from './components/Navbar';
import { LoginPage } from './pages/LoginPage';
import { UploadPage } from './pages/UploadPage';
import { ScanResultPage } from './pages/ScanResultPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { TrustLookupPage } from './pages/TrustLookupPage';
import { PublicVerificationView } from './components/PublicVerificationView';
import { fetchScans, getBatchStatus, MOCK_SCANS } from './services/api';

import type { ScanResult, User } from './types';

export function App() {
  const [user, setUser] = useState<User | null>({
    id: 1,
    username: 'inspector',
    role: 'inspector',
  });
  const [token, setToken] = useState<string | null>('demo-token');
  const [activeTab, setActiveTab] = useState<'dashboard' | 'upload' | 'results' | 'analytics'>('dashboard');
  const [verifyId] = useState<string>(() => {
    if (typeof window === 'undefined') return '';
    const path = window.location.pathname;
    const search = window.location.search;
    if (path.includes('/verify/')) {
      return path.split('/verify/')[1]?.split('/')[0] || '';
    }
    if (search.includes('verify=')) {
      const match = search.match(/verify=([^&]+)/);
      return match ? decodeURIComponent(match[1]) : '';
    }
    return '';
  });
  const [viewMode, setViewMode] = useState<'app' | 'trust' | 'verify'>(() => {
    if (typeof window === 'undefined') return 'app';
    const path = window.location.pathname;
    const search = window.location.search;
    if (path.includes('/verify/') || search.includes('verify=')) return 'verify';
    if (
      path.includes('trust') ||
      window.location.hash.includes('trust') ||
      path.includes('lookup') ||
      search.includes('trust')
    ) {
      return 'trust';
    }
    return 'app';
  });

  const [scans, setScans] = useState<ScanResult[]>(MOCK_SCANS);
  const [activeScan, setActiveScan] = useState<ScanResult | null>(MOCK_SCANS[0]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Active background batch tracking
  const [activeBatch, setActiveBatch] = useState<{
    batchId: string;
    status: 'queued' | 'processing' | 'completed' | 'failed';
    processed: number;
    total: number;
    progressPercent: number;
    message: string;
  } | null>(null);

  // Initial load: Fetch real scans from backend database
  const refreshScansFromBackend = async () => {
    setIsRefreshing(true);
    try {
      const backendScans = await fetchScans();
      if (backendScans && backendScans.length > 0) {
        setScans(backendScans);
        setActiveScan(backendScans[0]);
      }
    } catch (err) {
      console.warn('Could not fetch backend scans:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    refreshScansFromBackend();
  }, []);

  // Poll active batch progress every 1.5s
  useEffect(() => {
    if (!activeBatch || activeBatch.status === 'completed' || activeBatch.status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const data = await getBatchStatus(activeBatch.batchId);
        setActiveBatch(prev => prev ? {
          ...prev,
          status: data.status,
          processed: data.processed,
          total: data.total,
          progressPercent: data.progress_percent,
          message: data.message || prev.message,
        } : null);

        if (data.status === 'completed') {
          const newScans = data.results || data.result?.results || [];
          if (newScans.length > 0) {
            setScans(prev => {
              const existingIds = new Set(prev.map(s => s.scan_id));
              const filtered = newScans.filter((s: ScanResult) => !existingIds.has(s.scan_id));
              return [...filtered, ...prev];
            });
            setActiveScan(newScans[0]);
          }
          // Refresh full dataset from backend database
          refreshScansFromBackend();

          // Clear banner after 5 seconds
          setTimeout(() => {
            setActiveBatch(null);
          }, 5000);
        } else if (data.status === 'failed') {
          setTimeout(() => {
            setActiveBatch(null);
          }, 6000);
        }
      } catch (err) {
        console.error('Failed to poll batch status:', err);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [activeBatch?.batchId, activeBatch?.status]);

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

  const handleBatchQueued = (batchId: string) => {
    setActiveBatch({
      batchId,
      status: 'queued',
      processed: 0,
      total: 0,
      progressPercent: 0,
      message: 'Scraping and analyzing e-commerce listings in background...',
    });
    setActiveTab('dashboard');
  };

  const handleBatchCompleted = (newScans: ScanResult[]) => {
    setScans(prev => {
      const existingIds = new Set(prev.map(s => s.scan_id));
      const filtered = newScans.filter(s => !existingIds.has(s.scan_id));
      return [...filtered, ...prev];
    });
    if (newScans.length > 0) {
      setActiveScan(newScans[0]);
    }
    setActiveTab('dashboard');
  };

  const handleSelectScan = (scan: ScanResult) => {
    setActiveScan(scan);
    setActiveTab('results');
  };

  if (viewMode === 'verify') {
    return (
      <PublicVerificationView
        verificationId={verifyId}
        onBack={() => {
          setViewMode('app');
          window.history.pushState({}, '', '/');
        }}
      />
    );
  }

  if (viewMode === 'trust') {
    return <TrustLookupPage onBackToLogin={() => setViewMode('app')} />;
  }

  if (!user || !token) {
    return (
      <LoginPage
        onLoginSuccess={handleLoginSuccess}
        onOpenPublicTrust={() => setViewMode('trust')}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#1C2B3A] flex flex-col font-sans">
      <Navbar
        user={user}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onLogout={handleLogout}
        onOpenPublicTrust={() => setViewMode('trust')}
      />

      {/* Active Batch Docket Progress Banner */}
      {activeBatch && (
        <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 pt-4">
          <div className={`p-4 bg-white border border-[#D8D2C6] flex flex-col md:flex-row items-center justify-between gap-4 ${
            activeBatch.status === 'completed'
              ? 'border-l-4 border-l-[#2F6F4E]'
              : activeBatch.status === 'failed'
              ? 'border-l-4 border-l-[#A8342A]'
              : 'border-l-4 border-l-[#1C2B3A]'
          }`}>
            <div className="flex items-center gap-3.5">
              {activeBatch.status === 'completed' ? (
                <div className="w-9 h-9 bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE] flex items-center justify-center shrink-0">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
              ) : activeBatch.status === 'failed' ? (
                <div className="w-9 h-9 bg-[#F9EBE9] text-[#A8342A] border border-[#E09891] flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-5 h-5" />
                </div>
              ) : (
                <div className="w-9 h-9 bg-[#FAF8F5] text-[#1C2B3A] border border-[#D8D2C6] flex items-center justify-center shrink-0">
                  <Loader2 className="w-5 h-5 animate-spin" />
                </div>
              )}
              <div>
                <div className="text-sm font-bold text-[#1C2B3A] font-serif flex items-center gap-2">
                  {activeBatch.status === 'completed' ? (
                    <span className="text-[#2F6F4E]">Batch Audit Complete</span>
                  ) : activeBatch.status === 'failed' ? (
                    <span className="text-[#A8342A]">Batch Ingestion Aborted</span>
                  ) : (
                    <span>Active E-Commerce Dossier Crawl ({activeBatch.processed}/{activeBatch.total || '...'})</span>
                  )}
                  <span className="text-[11px] px-2 py-0.5 bg-[#F7F5F0] text-[#1C2B3A] font-mono border border-[#D8D2C6]">
                    ID: {activeBatch.batchId}
                  </span>
                </div>
                <p className="text-xs text-[#5E6E80] mt-0.5">{activeBatch.message}</p>
              </div>
            </div>

            <div className="w-full md:w-64 flex flex-col gap-1 shrink-0">
              <div className="flex justify-between text-xs font-mono text-[#5E6E80]">
                <span>Ingestion Progress</span>
                <span className="font-semibold text-[#1C2B3A]">{Math.round(activeBatch.progressPercent)}%</span>
              </div>
              <div className="w-full bg-[#EAE6DE] h-2 rounded-none overflow-hidden border border-[#D8D2C6]">
                <div
                  className={`h-full transition-all duration-300 ${
                    activeBatch.status === 'completed' ? 'bg-[#2F6F4E]' : 'bg-[#1C2B3A]'
                  }`}
                  style={{ width: `${Math.max(activeBatch.progressPercent, 4)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Database Sync Bar */}
      <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 pt-3 flex justify-end">
        <button
          onClick={refreshScansFromBackend}
          disabled={isRefreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#1C2B3A] hover:bg-[#EFECE6] bg-white border border-[#D8D2C6] transition-all disabled:opacity-50"
          title="Synchronize repository with PostgreSQL ledger"
        >
          <RefreshCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin text-[#1C2B3A]' : ''}`} />
          {isRefreshing ? 'Syncing Ledger...' : 'Sync Database'}
        </button>
      </div>

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
            onBatchCompleted={handleBatchCompleted}
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

      <footer className="border-t border-[#D8D2C6] bg-white py-4 px-6 text-center text-xs text-[#5E6E80] font-mono">
        labelGuard AI • Official Legal Metrology (Packaged Commodities) Compliance Platform • Rule 6, 7 & 8 Evidence Analyzer
      </footer>
    </div>
  );

}

export default App;
