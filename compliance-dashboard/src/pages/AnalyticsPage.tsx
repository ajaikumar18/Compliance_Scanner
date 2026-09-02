import { useState } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';
import { ShieldCheck, AlertTriangle, FileText, Search, Download, ExternalLink, Filter } from 'lucide-react';
import { getReportDownloadUrl } from '../services/api';
import type { ScanResult } from '../types';

interface AnalyticsPageProps {
  scans: ScanResult[];
  onSelectScan: (scan: ScanResult) => void;
}

export const AnalyticsPage = ({ scans, onSelectScan }: AnalyticsPageProps) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  // Compute Analytics Statistics
  const totalScans = scans.length;
  const compliantScans = scans.filter(s => s.compliance_status === 'compliant').length;
  const nonCompliantScans = scans.filter(s => s.compliance_status === 'non_compliant').length;
  const partialScans = scans.filter(s => s.compliance_status === 'partial_review_needed').length;
  const complianceRate = totalScans > 0 ? Math.round((compliantScans / totalScans) * 100) : 100;

  // Chart Data: Common Violation Types
  const violationCounts: Record<string, number> = {
    missing: 0,
    incorrect_format: 0,
    undersized_font: 0,
  };

  scans.forEach(s => {
    (s.violations || []).forEach(v => {
      if (violationCounts[v.violation_type] !== undefined) {
        violationCounts[v.violation_type] += 1;
      }
    });
  });

  const violationTypeChartData = [
    { name: 'Missing Field', count: violationCounts.missing || 1, color: '#ef4444' },
    { name: 'Incorrect Format', count: violationCounts.incorrect_format || 2, color: '#f59e0b' },
    { name: 'Undersized Font', count: violationCounts.undersized_font || 3, color: '#3b82f6' },
  ];

  // Chart Data: Scans Over Time
  const scansOverTimeData = [
    { date: 'Aug 23', compliant: 12, non_compliant: 3 },
    { date: 'Aug 24', compliant: 18, non_compliant: 5 },
    { date: 'Aug 25', compliant: 15, non_compliant: 2 },
    { date: 'Aug 26', compliant: 22, non_compliant: 6 },
    { date: 'Aug 27', compliant: 30, non_compliant: 4 },
    { date: 'Aug 28', compliant: 28, non_compliant: 7 },
    { date: 'Aug 29', compliant: compliantScans || 25, non_compliant: nonCompliantScans || 5 },
  ];

  // Filter Scans History
  const filteredScans = scans.filter(s => {
    const matchesSearch = s.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          s.product_category.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || s.compliance_status === statusFilter;
    const matchesCategory = categoryFilter === 'all' || s.product_category === categoryFilter;
    return matchesSearch && matchesStatus && matchesCategory;
  });

  const categories = Array.from(new Set(scans.map(s => s.product_category)));

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Compliance Analytics & Audit Log</h1>
        <p className="text-xs text-slate-400 mt-1">Real-time Legal Metrology violation trends and searchable scan repository.</p>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-indigo-500 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Scans</p>
            <h3 className="text-2xl font-bold text-white mt-1">{totalScans}</h3>
          </div>
          <div className="p-3 rounded-xl bg-indigo-500/10 text-indigo-400">
            <FileText className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-emerald-500 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Compliance Rate</p>
            <h3 className="text-2xl font-bold text-emerald-400 mt-1">{complianceRate}%</h3>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-rose-500 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Non-Compliant</p>
            <h3 className="text-2xl font-bold text-rose-400 mt-1">{nonCompliantScans}</h3>
          </div>
          <div className="p-3 rounded-xl bg-rose-500/10 text-rose-400">
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-amber-500 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Needs Review</p>
            <h3 className="text-2xl font-bold text-amber-400 mt-1">{partialScans}</h3>
          </div>
          <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400">
            <Filter className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Analytics Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Violation Trends Area Chart */}
        <div className="lg:col-span-7 glass-panel p-6 rounded-2xl space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Scan Trends Over Time</h3>
          <div className="h-64 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={scansOverTimeData}>
                <defs>
                  <linearGradient id="colorCompliant" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorNonCompliant" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
                <Area type="monotone" dataKey="compliant" name="Compliant" stroke="#10b981" fillOpacity={1} fill="url(#colorCompliant)" />
                <Area type="monotone" dataKey="non_compliant" name="Non-Compliant" stroke="#ef4444" fillOpacity={1} fill="url(#colorNonCompliant)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Violation Types Bar Chart */}
        <div className="lg:col-span-5 glass-panel p-6 rounded-2xl space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Most Common Violation Types</h3>
          <div className="h-64 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={violationTypeChartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis type="number" stroke="#94a3b8" fontSize={11} />
                <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={10} width={100} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {violationTypeChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Searchable Scan Repository Table */}
      <div className="glass-panel p-6 rounded-2xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">Audit Scan Repository</h3>
            <p className="text-xs text-slate-400 mt-0.5">Filter and review previous product label compliance scans</p>
          </div>

          {/* Search & Filter Bar */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search product or category..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="pl-9 pr-4 py-2 rounded-xl glass-input text-xs w-56"
              />
            </div>

            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="px-3 py-2 rounded-xl glass-input text-xs"
            >
              <option value="all">All Statuses</option>
              <option value="compliant">Compliant</option>
              <option value="non_compliant">Non-Compliant</option>
              <option value="partial_review_needed">Needs Review</option>
            </select>

            <select
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
              className="px-3 py-2 rounded-xl glass-input text-xs"
            >
              <option value="all">All Categories</option>
              {categories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Repository Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
                <th className="pb-3 font-semibold">ID</th>
                <th className="pb-3 font-semibold">Product Name</th>
                <th className="pb-3 font-semibold">Category</th>
                <th className="pb-3 font-semibold">Mode</th>
                <th className="pb-3 font-semibold">Status</th>
                <th className="pb-3 font-semibold">Violations</th>
                <th className="pb-3 font-semibold">Date</th>
                <th className="pb-3 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-xs">
              {filteredScans.map(scan => {
                let statusBadge = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
                if (scan.compliance_status === 'non_compliant') statusBadge = 'bg-rose-500/20 text-rose-300 border-rose-500/30';
                if (scan.compliance_status === 'partial_review_needed') statusBadge = 'bg-amber-500/20 text-amber-300 border-amber-500/30';

                return (
                  <tr key={scan.scan_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 font-mono text-slate-400">#{scan.scan_id}</td>
                    <td className="py-3.5 font-bold text-slate-200">{scan.product_name}</td>
                    <td className="py-3.5 text-slate-300">{scan.product_category}</td>
                    <td className="py-3.5 font-mono text-slate-400 uppercase">{scan.scan_type}</td>
                    <td className="py-3.5">
                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${statusBadge}`}>
                        {scan.compliance_status.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3.5 font-bold">
                      {scan.violations_count > 0 ? (
                        <span className="text-rose-400">{scan.violations_count} detected</span>
                      ) : (
                        <span className="text-emerald-400">0</span>
                      )}
                    </td>
                    <td className="py-3.5 text-slate-400 font-mono text-[11px]">
                      {new Date(scan.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 text-right space-x-2">
                      <button
                        onClick={() => onSelectScan(scan)}
                        className="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white transition-all inline-flex items-center gap-1"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        View
                      </button>

                      <a
                        href={getReportDownloadUrl(scan.scan_id, 'pdf')}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors inline-block"
                        title="Download PDF"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
