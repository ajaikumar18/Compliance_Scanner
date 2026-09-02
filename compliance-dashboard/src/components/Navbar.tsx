import { ShieldCheck, LayoutDashboard, UploadCloud, BarChart3, LogOut, User as UserIcon } from 'lucide-react';
import type { User } from '../types';

interface NavbarProps {
  user: User | null;
  activeTab: 'dashboard' | 'upload' | 'results' | 'analytics';
  setActiveTab: (tab: 'dashboard' | 'upload' | 'results' | 'analytics') => void;
  onLogout: () => void;
}

export const Navbar = ({
  user,
  activeTab,
  setActiveTab,
  onLogout,
}: NavbarProps) => {
  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800/80 px-4 lg:px-8 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
          <div className="p-2 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-lg shadow-indigo-500/30">
            <ShieldCheck className="w-6 h-6 text-white" />
          </div>
          <div>
            <span className="text-lg font-bold bg-gradient-to-r from-white via-slate-100 to-indigo-200 bg-clip-text text-transparent tracking-tight">
              ComplianceScanner
            </span>
            <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              AI v0.1
            </span>
          </div>
        </div>

        {/* Navigation Tabs */}
        {user && (
          <nav className="hidden md:flex items-center gap-1 bg-slate-950/60 p-1.5 rounded-xl border border-slate-800/80">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'dashboard'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              Scan History
            </button>

            <button
              onClick={() => setActiveTab('upload')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'upload'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <UploadCloud className="w-4 h-4" />
              New Scan
            </button>

            <button
              onClick={() => setActiveTab('analytics')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'analytics'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              Analytics
            </button>
          </nav>
        )}

        {/* User Account Controls */}
        {user ? (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-slate-300 bg-slate-800/50 px-3 py-1.5 rounded-lg border border-slate-700/50">
              <UserIcon className="w-4 h-4 text-indigo-400" />
              <span className="font-semibold">{user.username}</span>
              <span className="text-xs uppercase bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded font-mono">
                {user.role}
              </span>
            </div>
            <button
              onClick={onLogout}
              title="Logout"
              className="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        ) : (
          <div className="text-xs text-slate-400 font-mono">Legal Metrology AI Engine</div>
        )}
      </div>
    </header>
  );
};
