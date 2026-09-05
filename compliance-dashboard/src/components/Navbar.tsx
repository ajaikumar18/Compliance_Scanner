import { ShieldCheck, LayoutDashboard, UploadCloud, BarChart3, LogOut, User as UserIcon } from 'lucide-react';
import type { User } from '../types';

interface NavbarProps {
  user: User | null;
  activeTab: 'dashboard' | 'upload' | 'results' | 'analytics';
  setActiveTab: (tab: 'dashboard' | 'upload' | 'results' | 'analytics') => void;
  onLogout: () => void;
  onOpenPublicTrust?: () => void;
}

export const Navbar = ({
  user,
  activeTab,
  setActiveTab,
  onLogout,
  onOpenPublicTrust,
}: NavbarProps) => {
  return (
    <header className="sticky top-0 z-50 bg-[#1C2B3A] border-b border-[#2E3F50] px-4 lg:px-8 py-3 text-[#F7F5F0]">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
          <div className="p-2 rounded-sm bg-[#24374A] border border-[#3A5066] text-[#F7F5F0]">
            <ShieldCheck className="w-5 h-5 text-[#9BC6AE]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold font-serif tracking-tight text-[#F7F5F0]">
                labelGuard AI
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-none bg-[#24374A] text-[#DFBF82] border border-[#3A5066]">
                Audit v1.0
              </span>
            </div>
            <p className="text-[10px] text-[#A6B5C5] font-sans tracking-wide">
              Legal Metrology (Packaged Commodities) Bureau
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        {user && (
          <nav className="hidden md:flex items-center gap-1 bg-[#121D28] p-1 rounded-sm border border-[#2E3F50]">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-none text-xs font-medium transition-all ${
                activeTab === 'dashboard'
                  ? 'bg-[#24374A] text-white border border-[#445B73]'
                  : 'text-[#A6B5C5] hover:text-white hover:bg-[#1C2B3A]'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              Inspection Log
            </button>

            <button
              onClick={() => setActiveTab('upload')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-none text-xs font-medium transition-all ${
                activeTab === 'upload'
                  ? 'bg-[#24374A] text-white border border-[#445B73]'
                  : 'text-[#A6B5C5] hover:text-white hover:bg-[#1C2B3A]'
              }`}
            >
              <UploadCloud className="w-3.5 h-3.5" />
              New Ingestion
            </button>

            <button
              onClick={() => setActiveTab('analytics')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-none text-xs font-medium transition-all ${
                activeTab === 'analytics'
                  ? 'bg-[#24374A] text-white border border-[#445B73]'
                  : 'text-[#A6B5C5] hover:text-white hover:bg-[#1C2B3A]'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              Ledger Metrics
            </button>

            {onOpenPublicTrust && (
              <button
                onClick={onOpenPublicTrust}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-none text-xs font-semibold text-[#9BC6AE] hover:text-white hover:bg-[#2F6F4E]/30 border border-[#2F6F4E]/60 transition-all ml-1"
                title="Open Public Trust Score Portal"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-[#9BC6AE]" />
                <span>Public Portal</span>
              </button>
            )}
          </nav>
        )}

        {/* User Account Controls */}
        {user ? (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-[#EAE6DE] bg-[#24374A] px-3 py-1.5 rounded-none border border-[#3A5066]">
              <UserIcon className="w-3.5 h-3.5 text-[#DFBF82]" />
              <span className="font-medium">{user.username}</span>
              <span className="text-[10px] uppercase bg-[#1C2B3A] text-[#DFBF82] px-1.5 py-0.2 border border-[#B8862B]/50 font-mono">
                {user.role}
              </span>
            </div>
            <button
              onClick={onLogout}
              title="Sign Out"
              className="p-1.5 text-[#A6B5C5] hover:text-[#E09891] hover:bg-[#A8342A]/20 rounded-none border border-transparent hover:border-[#A8342A]/40 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="text-xs text-[#A6B5C5] font-mono">Bureau Authority Portal</div>
        )}
      </div>
    </header>
  );
};
