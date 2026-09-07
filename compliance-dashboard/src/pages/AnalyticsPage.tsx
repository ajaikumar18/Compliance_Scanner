import { useState } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';
import { FileText, Search, Download, ExternalLink, Loader2 } from 'lucide-react';
import { downloadScanReport, downloadBatchReport } from '../services/api';
import { ReInspectionQueue } from '../components/ReInspectionQueue';
import type { ScanResult } from '../types';

interface AnalyticsPageProps {
  scans: ScanResult[];
  onSelectScan: (scan: ScanResult) => void;
}

export const AnalyticsPage = ({ scans, onSelectScan }: AnalyticsPageProps) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [isDownloadingBatch, setIsDownloadingBatch] = useState(false);
  const [downloadingScanId, setDownloadingScanId] = useState<string | number | null>(null);

  const handleDownloadBatchPdf = async () => {
    setIsDownloadingBatch(true);
    try {
      await downloadBatchReport({
        scans: filteredScans.length > 0 ? filteredScans : scans,
        batchTitle: 'Consolidated Compliance Audit Docket',
      });
    } catch (err: any) {
      alert('Could not download batch PDF docket: ' + (err.message || err));
    } finally {
      setIsDownloadingBatch(false);
    }
  };

  const handleDownloadSingleScan = async (scan: ScanResult) => {
    setDownloadingScanId(scan.scan_id);
    try {
      await downloadScanReport(scan.scan_id, 'pdf', scan);
    } catch (err: any) {
      alert('Could not download PDF report: ' + (err.message || err));
    } finally {
      setDownloadingScanId(null);
    }
  };

  const handleInspectTriggerScan = (scanId: number) => {
    const found = scans.find(s => s.scan_id === scanId);
    if (found) {
      onSelectScan(found);
    } else if (scans.length > 0) {
      onSelectScan(scans[0]);
    }
  };

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
    { name: 'Missing Field', count: violationCounts.missing || 1, color: '#A8342A' },
    { name: 'Incorrect Format', count: violationCounts.incorrect_format || 2, color: '#B8862B' },
    { name: 'Undersized Font', count: violationCounts.undersized_font || 3, color: '#1C2B3A' },
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
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 space-y-8">
      {/* Header */}
      <div className="border-b border-[#D8D2C6] pb-4">
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold font-serif text-[#1C2B3A] tracking-tight">
              Compliance Analytics & Audit Log
            </h1>
            <p className="text-xs text-[#5E6E80] mt-1 font-sans">
              Statutory verification under the Legal Metrology (Packaged Commodities) Rules 2011.
            </p>
          </div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              onClick={handleDownloadBatchPdf}
              disabled={isDownloadingBatch || filteredScans.length === 0}
              className="px-3 py-1.5 bg-[#1C2B3A] text-white hover:bg-[#2E3F50] transition-colors inline-flex items-center gap-1.5 text-xs font-serif font-semibold tracking-wide disabled:opacity-50 rounded-none shadow-sm"
              title="Download consolidated PDF docket for filtered scans"
            >
              {isDownloadingBatch ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              <span>Export Batch PDF Docket</span>
            </button>
            <div className="text-xs font-mono text-[#5E6E80] bg-[#FAF8F5] px-3 py-1.5 border border-[#D8D2C6]">
              OFFICIAL LEDGER • REGISTER NO. LM-2026-IN
            </div>
          </div>
        </div>
      </div>

      {/* ── Ruled Ledger-Row Summary Layout (Replaces Card Grid) ─────────────── */}
      <div className="bg-white border border-[#D8D2C6] rounded-none">
        <div className="px-5 py-3 border-b border-[#D8D2C6] bg-[#FAF8F5] flex items-center justify-between">
          <div className="flex items-center gap-2 text-[#1C2B3A]">
            <FileText className="w-4 h-4 text-[#1C2B3A]" />
            <span className="font-serif font-bold text-xs uppercase tracking-wider">
              Statutory Compliance Ledger • Summary Docket
            </span>
          </div>
          <span className="text-[11px] font-mono text-[#5E6E80]">
            Audit Period: 2026-Q3
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-[#D8D2C6]">
          {/* Column 1: Total Audited Commodities */}
          <div className="p-5 space-y-1.5 bg-white">
            <div className="flex items-center justify-between text-xs text-[#5E6E80] uppercase font-semibold font-sans">
              <span>Audited Commodities</span>
              <span className="font-mono text-[10px] bg-[#F7F5F0] px-1.5 py-0.5 border border-[#D8D2C6] text-[#1C2B3A]">REG-01</span>
            </div>
            <div className="text-3xl font-bold font-serif text-[#1C2B3A]">{totalScans}</div>
            <p className="text-xs text-[#5E6E80] font-sans">Retail packaging & e-commerce catalogs</p>
          </div>

          {/* Column 2: Compliance Rate */}
          <div className="p-5 space-y-1.5 bg-[#EAF4EE]/40">
            <div className="flex items-center justify-between text-xs text-[#2F6F4E] uppercase font-semibold font-sans">
              <span>Statutory Compliance</span>
              <span className="font-mono text-[10px] bg-[#EAF4EE] px-1.5 py-0.5 border border-[#9BC6AE] text-[#2F6F4E]">RATE</span>
            </div>
            <div className="text-3xl font-bold font-serif text-[#2F6F4E]">{complianceRate}%</div>
            <p className="text-xs text-[#5E6E80] font-sans">{compliantScans} fully verified commodities</p>
          </div>

          {/* Column 3: Flagged Non-Compliant */}
          <div className="p-5 space-y-1.5 bg-[#F9EBE9]/40">
            <div className="flex items-center justify-between text-xs text-[#A8342A] uppercase font-semibold font-sans">
              <span>Flagged Violations</span>
              <span className="font-mono text-[10px] bg-[#F9EBE9] px-1.5 py-0.5 border border-[#E09891] text-[#A8342A]">BREACH</span>
            </div>
            <div className="text-3xl font-bold font-serif text-[#A8342A]">{nonCompliantScans}</div>
            <p className="text-xs text-[#5E6E80] font-sans">Actionable Rule 6 & 7 violations</p>
          </div>

          {/* Column 4: Pending / Review */}
          <div className="p-5 space-y-1.5 bg-[#FAF3E6]/40">
            <div className="flex items-center justify-between text-xs text-[#B8862B] uppercase font-semibold font-sans">
              <span>Pending Investigation</span>
              <span className="font-mono text-[10px] bg-[#FAF3E6] px-1.5 py-0.5 border border-[#DFBF82] text-[#B8862B]">REVIEW</span>
            </div>
            <div className="text-3xl font-bold font-serif text-[#B8862B]">{partialScans}</div>
            <p className="text-xs text-[#5E6E80] font-sans">Disputed evidence or pending AR audit</p>
          </div>
        </div>
      </div>

      {/* Enforcement Discrepancy & Re-Inspection Queue */}
      <ReInspectionQueue onSelectScan={handleInspectTriggerScan} />

      {/* ── Analytics Charts Grid ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Violation Trends Area Chart */}
        <div className="lg:col-span-7 bg-white border border-[#D8D2C6] rounded-none p-5 space-y-4">
          <div className="border-b border-[#D8D2C6] pb-3 flex items-center justify-between">
            <h3 className="text-xs font-bold font-serif text-[#1C2B3A] uppercase tracking-wider">
              Scan Trends Over Time
            </h3>
            <span className="text-[11px] font-mono text-[#5E6E80]">7-Day Trend</span>
          </div>
          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={scansOverTimeData}>
                <defs>
                  <linearGradient id="colorCompliantAudit" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2F6F4E" stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="#2F6F4E" stopOpacity={0.02}/>
                  </linearGradient>
                  <linearGradient id="colorNonCompliantAudit" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#A8342A" stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="#A8342A" stopOpacity={0.02}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="2 2" stroke="#E2DDD5" />
                <XAxis dataKey="date" stroke="#5E6E80" fontSize={11} fontFamily="'IBM Plex Mono', monospace" />
                <YAxis stroke="#5E6E80" fontSize={11} fontFamily="'IBM Plex Mono', monospace" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderColor: '#D8D2C6',
                    borderRadius: '0px',
                    color: '#1C2B3A',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '11px',
                  }}
                />
                <Area type="monotone" dataKey="compliant" name="Compliant" stroke="#2F6F4E" strokeWidth={2} fillOpacity={1} fill="url(#colorCompliantAudit)" />
                <Area type="monotone" dataKey="non_compliant" name="Flagged" stroke="#A8342A" strokeWidth={2} fillOpacity={1} fill="url(#colorNonCompliantAudit)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Violation Types Bar Chart */}
        <div className="lg:col-span-5 bg-white border border-[#D8D2C6] rounded-none p-5 space-y-4">
          <div className="border-b border-[#D8D2C6] pb-3 flex items-center justify-between">
            <h3 className="text-xs font-bold font-serif text-[#1C2B3A] uppercase tracking-wider">
              Primary Statutory Infractions
            </h3>
            <span className="text-[11px] font-mono text-[#5E6E80]">Rule Breakdown</span>
          </div>
          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={violationTypeChartData} layout="vertical">
                <CartesianGrid strokeDasharray="2 2" stroke="#E2DDD5" />
                <XAxis type="number" stroke="#5E6E80" fontSize={11} fontFamily="'IBM Plex Mono', monospace" />
                <YAxis dataKey="name" type="category" stroke="#1C2B3A" fontSize={11} width={110} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderColor: '#D8D2C6',
                    borderRadius: '0px',
                    color: '#1C2B3A',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '11px',
                  }}
                />
                <Bar dataKey="count" radius={0}>
                  {violationTypeChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Official Legal Metrology Inspection Register ───────────────────── */}
      <div className="bg-white border border-[#D8D2C6] rounded-none p-5 space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#D8D2C6] pb-4">
          <div>
            <h3 className="text-base font-bold font-serif text-[#1C2B3A] tracking-tight">
              Inspection Register & Scan Repository
            </h3>
            <p className="text-xs text-[#5E6E80] mt-0.5">
              Certified logbook of physical packaging scans and e-commerce listings audited.
            </p>
          </div>

          {/* Search & Filter Bar */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[#5E6E80] absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search commodity or category..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="pl-8 pr-3 py-1.5 bg-white border border-[#C4BCAC] text-xs text-[#1C2B3A] placeholder-[#8C9BAA] rounded-none w-52 focus:outline-none focus:border-[#1C2B3A]"
              />
            </div>

            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-white border border-[#C4BCAC] text-xs text-[#1C2B3A] rounded-none focus:outline-none focus:border-[#1C2B3A]"
            >
              <option value="all">All Verdicts</option>
              <option value="compliant">Compliant</option>
              <option value="non_compliant">Non-Compliant</option>
              <option value="partial_review_needed">Needs Review</option>
            </select>

            <select
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-white border border-[#C4BCAC] text-xs text-[#1C2B3A] rounded-none focus:outline-none focus:border-[#1C2B3A]"
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
              <tr className="border-b-2 border-[#1C2B3A] text-[#1C2B3A] text-xs uppercase font-serif tracking-wider bg-[#FAF8F5]">
                <th className="py-2.5 px-3 font-bold">Docket ID</th>
                <th className="py-2.5 px-3 font-bold">Product Name</th>
                <th className="py-2.5 px-3 font-bold">Category</th>
                <th className="py-2.5 px-3 font-bold">Mode</th>
                <th className="py-2.5 px-3 font-bold">Verdict</th>
                <th className="py-2.5 px-3 font-bold">Violations</th>
                <th className="py-2.5 px-3 font-bold">Audit Date</th>
                <th className="py-2.5 px-3 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#D8D2C6] text-xs font-sans">
              {filteredScans.map(scan => {
                let statusBadge = 'bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]';
                if (scan.compliance_status === 'non_compliant') {
                  statusBadge = 'bg-[#F9EBE9] text-[#A8342A] border border-[#E09891]';
                } else if (scan.compliance_status === 'partial_review_needed') {
                  statusBadge = 'bg-[#FAF3E6] text-[#B8862B] border border-[#DFBF82]';
                }

                return (
                  <tr key={scan.scan_id} className="hover:bg-[#FAF8F5] transition-colors">
                    <td className="py-3 px-3 font-mono text-[#1C2B3A]">#{scan.scan_id}</td>
                    <td className="py-3 px-3 font-semibold text-[#1C2B3A]">{scan.product_name}</td>
                    <td className="py-3 px-3 text-[#5E6E80]">{scan.product_category}</td>
                    <td className="py-3 px-3 font-mono text-[#5E6E80] uppercase">{scan.scan_type}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded-none text-[10px] font-mono font-semibold uppercase ${statusBadge}`}>
                        {scan.compliance_status.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono">
                      {scan.violations_count > 0 ? (
                        <span className="text-[#A8342A] font-bold">{scan.violations_count} detected</span>
                      ) : (
                        <span className="text-[#2F6F4E]">0</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-[#5E6E80] font-mono text-[11px]">
                      {new Date(scan.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <button
                        onClick={() => onSelectScan(scan)}
                        className="px-2.5 py-1 bg-[#1C2B3A] text-white hover:bg-[#2E3F50] transition-colors inline-flex items-center gap-1 text-xs font-sans rounded-none"
                      >
                        <ExternalLink className="w-3 h-3" />
                        Inspect
                      </button>

                      <button
                        onClick={() => handleDownloadSingleScan(scan)}
                        disabled={downloadingScanId === scan.scan_id}
                        className="p-1.5 border border-[#D8D2C6] hover:bg-[#EFECE6] text-[#1C2B3A] inline-block rounded-none transition-colors disabled:opacity-50"
                        title="Download Certified PDF Report"
                      >
                        {downloadingScanId === scan.scan_id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-[#1C2B3A]" />
                        ) : (
                          <Download className="w-3.5 h-3.5" />
                        )}
                      </button>
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
