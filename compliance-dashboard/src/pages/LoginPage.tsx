import React, { useState } from 'react';
import { ShieldCheck, Lock, User as UserIcon, AlertCircle, ArrowRight, Award } from 'lucide-react';
import { loginUser } from '../services/api';
import type { User } from '../types';

interface LoginPageProps {
  onLoginSuccess: (user: User, token: string) => void;
  onOpenPublicTrust?: () => void;
}

export const LoginPage = ({ onLoginSuccess, onOpenPublicTrust }: LoginPageProps) => {
  const [username, setUsername] = useState('inspector');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await loginUser(username, password);
      onLoginSuccess(res.user, res.token);
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = (role: 'inspector' | 'admin') => {
    const demoUser: User = {
      id: role === 'admin' ? 99 : 1,
      username: `${role}_demo`,
      role,
    };
    onLoginSuccess(demoUser, 'demo-jwt-token-xyz');
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md bg-white border-2 border-[#1C2B3A] p-8 shadow-none relative">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 bg-[#1C2B3A] text-white mb-3">
            <Award className="w-8 h-8 text-[#DFBF82]" />
          </div>
          <span className="block text-[10px] font-mono uppercase tracking-widest text-[#5A6E82] font-bold">
            LEGAL METROLOGY DIVISION • INNOVEXGUARD AI
          </span>
          <h2 className="text-2xl font-serif font-bold text-[#1C2B3A] tracking-tight mt-1">
            Inspector Portal Login
          </h2>
          <p className="text-xs text-[#5A6E82] mt-1">
            InnoveXguard AI – Statutory Packaging Compliance & Laboratory Calibration
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-[#F9EBE9] border border-[#E09891] flex items-start gap-3 text-[#A8342A] text-xs font-mono">
            <AlertCircle className="w-4 h-4 text-[#A8342A] shrink-0 mt-0.5" />
            <div>{error}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] tracking-wider mb-1.5">
              Inspector ID / Username
            </label>
            <div className="relative">
              <UserIcon className="w-4 h-4 text-[#5A6E82] absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                required
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="Enter username"
                className="w-full pl-10 pr-4 py-2.5 bg-white border border-[#D8D2C6] text-sm text-[#1C2B3A] font-mono focus:outline-none focus:border-[#1C2B3A]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono uppercase font-semibold text-[#1C2B3A] tracking-wider mb-1.5">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-[#5A6E82] absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full pl-10 pr-4 py-2.5 bg-white border border-[#D8D2C6] text-sm text-[#1C2B3A] font-mono focus:outline-none focus:border-[#1C2B3A]"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-6 bg-[#1C2B3A] hover:bg-[#2A3F55] text-white font-semibold text-xs border border-[#1C2B3A] transition-all flex items-center justify-center gap-2 disabled:opacity-50 tracking-wider uppercase"
          >
            {loading ? 'Authenticating Credentials...' : 'Sign In as Officer'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-[#E2DDD5] text-center">
          <p className="text-[11px] text-[#5A6E82] font-mono uppercase tracking-wider mb-3 font-semibold">
            Authorized Quick Access:
          </p>
          <div className="flex justify-center gap-2 font-mono text-xs">
            <button
              onClick={() => handleDemoLogin('inspector')}
              className="px-3 py-1.5 bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] border border-[#D8D2C6] transition-colors"
            >
              Inspector Demo
            </button>
            <button
              onClick={() => handleDemoLogin('admin')}
              className="px-3 py-1.5 bg-[#F7F5F0] hover:bg-[#EBE7DF] text-[#1C2B3A] border border-[#D8D2C6] transition-colors"
            >
              Admin Demo
            </button>
          </div>

          {onOpenPublicTrust && (
            <div className="mt-5 pt-4 border-t border-[#E2DDD5]">
              <button
                type="button"
                onClick={onOpenPublicTrust}
                className="w-full py-2.5 px-4 bg-[#EAF4EE] hover:bg-[#D4E8DC] text-[#2F6F4E] text-xs font-semibold border border-[#9BC6AE] flex items-center justify-center gap-2 transition-all font-mono"
              >
                <ShieldCheck className="w-4 h-4 text-[#2F6F4E]" />
                <span>Public Product Trust Lookup (No Login Needed) →</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};


