import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  AlertOctagon,
  FileText,
  Download,
  Eye,
  Search,
  RefreshCw,
  Users,
  Award,
} from 'lucide-react';
import { ReInspectionQueue } from '../components/ReInspectionQueue';
import { fetchScans } from '../services/api';
import type { ScanResult } from '../types';

interface CitizenQueuePageProps {
  scans?: ScanResult[];
  onSelectScan?: (scan: ScanResult) => void;
}

export const CitizenQueuePage: React.FC<CitizenQueuePageProps> = ({
  scans: initialScans,
  onSelectScan,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'auto_approved' | 'pending_review'>('auto_approved');
  const [allScans, setAllScans] = useState<ScanResult[]>(initialScans || []);
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [reputationFilter, setReputationFilter] = useState<'all' | 'trusted' | 'flagged'>('all');

  const loadScans = async () => {
    setIsLoading(true);
    try {
      const data = await fetchScans();
      if (data && data.length > 0) {
        setAllScans(data);
      }
    } catch (err) {
      console.warn('Failed to load scans:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!initialScans || initialScans.length === 0) {
      loadScans();
    } else {
      setAllScans(initialScans);
    }
  }, [initialScans]);

  // Filter for citizen-submitted scans
  const citizenAutoApproved = allScans.filter(s => {
    const isCitizen = (s.source || '').toLowerCase() === 'citizen' || (s as any).submitter_role === 'citizen';
    if (!isCitizen) return false;

    // Reputation Filter
    const userXp = s.submitter_xp ?? (s as any).current_xp ?? 100;
    if (reputationFilter === 'trusted' && userXp < 100) return false;
    if (reputationFilter === 'flagged' && userXp >= 0) return false;

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const matchName = (s.product_name || '').toLowerCase().includes(q);
      const matchCat = (s.product_category || '').toLowerCase().includes(q);
      const matchGtin = (s.gtin || '').toLowerCase().includes(q);
      if (!matchName && !matchCat && !matchGtin) return false;
    }
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">
      {/* Header Banner */}
      <div className="bg-white border border-[#D8D2C6] p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE] flex items-center justify-center shrink-0">
              <Users className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold font-serif text-[#1C2B3A] tracking-tight">
                  Citizen Evidence Queue
                </h1>
                <span className="px-2 py-0.5 bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE] font-mono text-[10px] uppercase font-bold">
                  Rule 6 & 10 Enforcement
                </span>
              </div>
              <p className="text-xs text-[#5E6E80] mt-1">
                Public submissions ingested with client-side SHA-256 tamper verification and priority violation triage.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadScans}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#1C2B3A] bg-white border border-[#D8D2C6] hover:bg-[#EFECE6] transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Refresh Ingestion</span>
            </button>
          </div>
        </div>

        {/* Tab Navigation: Auto-Approved vs Pending Review */}
        <div className="mt-6 flex border-b border-[#D8D2C6] gap-2">
          <button
            onClick={() => setActiveSubTab('auto_approved')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold font-mono uppercase tracking-wider transition-all border-b-2 ${
              activeSubTab === 'auto_approved'
                ? 'border-[#2F6F4E] text-[#2F6F4E] bg-[#EAF4EE]/40'
                : 'border-transparent text-[#5E6E80] hover:text-[#1C2B3A]'
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Auto-Approved ({citizenAutoApproved.length})</span>
          </button>

          <button
            onClick={() => setActiveSubTab('pending_review')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold font-mono uppercase tracking-wider transition-all border-b-2 ${
              activeSubTab === 'pending_review'
                ? 'border-[#B8862B] text-[#B8862B] bg-[#FAF3E6]/40'
                : 'border-transparent text-[#5E6E80] hover:text-[#1C2B3A]'
            }`}
          >
            <AlertOctagon className="w-4 h-4" />
            <span>Pending Review (Re-Inspection Tickets)</span>
          </button>
        </div>
      </div>

      {/* Subtab 1: Auto-Approved Scans */}
      {activeSubTab === 'auto_approved' && (
        <div className="space-y-4">
          {/* Search & Reputation Toolbar */}
          <div className="bg-white border border-[#D8D2C6] p-3 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative flex-1 w-full max-w-md">
              <Search className="w-3.5 h-3.5 text-[#5E6E80] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search citizen specimen, brand, or GTIN..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs border border-[#C4BCAC] bg-[#FAF8F5] text-[#1C2B3A] rounded-none focus:outline-none focus:border-[#1C2B3A]"
              />
            </div>
            <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
              <div className="flex items-center gap-2">
                <span className="text-xs text-[#5E6E80] whitespace-nowrap">Filter:</span>
                <select
                  value={reputationFilter}
                  onChange={e => setReputationFilter(e.target.value as any)}
                  className="text-xs px-2.5 py-1.5 border border-[#C4BCAC] bg-[#FAF8F5] text-[#1C2B3A] rounded-none focus:outline-none"
                >
                  <option value="all">All Submissions</option>
                  <option value="trusted">Trusted (XP &ge; 100)</option>
                  <option value="flagged">Flagged / Restricted (XP &lt; 0)</option>
                </select>
              </div>
              <span className="text-xs text-[#5E6E80] font-mono whitespace-nowrap">
                {citizenAutoApproved.length} verified
              </span>
            </div>
          </div>

          {citizenAutoApproved.length === 0 ? (
            <div className="bg-white border border-[#D8D2C6] p-12 text-center space-y-3">
              <div className="w-12 h-12 bg-[#FAF8F5] text-[#5E6E80] border border-[#D8D2C6] flex items-center justify-center mx-auto">
                <FileText className="w-6 h-6" />
              </div>
              <h3 className="text-base font-serif font-bold text-[#1C2B3A]">No Auto-Approved Citizen Scans Found</h3>
              <p className="text-xs text-[#5E6E80] max-w-md mx-auto">
                When citizens capture product labels via the Mobile App in Citizen Mode with high confidence and no ledger conflicts, certified reports are compiled automatically here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {citizenAutoApproved.map(scan => (
                <div
                  key={scan.scan_id || scan.id}
                  className="bg-white border border-[#D8D2C6] p-4 space-y-3 border-l-4 border-l-[#2F6F4E] shadow-sm hover:shadow transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="px-2 py-0.5 text-[10px] font-mono uppercase font-bold bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]">
                        Citizen Evidence • Docket #{scan.scan_id || scan.id}
                      </span>
                      <h3 className="text-sm font-bold font-serif text-[#1C2B3A] mt-1.5">
                        {scan.product_name}
                      </h3>
                      <p className="text-xs text-[#5E6E80]">Category: {scan.product_category}</p>
                    </div>

                    <span className="px-2 py-0.5 text-[10px] font-mono uppercase font-semibold bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]">
                      Auto-Approved
                    </span>
                  </div>

                  {/* Citizen Submitter Trust XP & Reputation Chip */}
                  <div className="flex items-center justify-between text-xs bg-[#FAF8F5] p-2 border border-[#EAE6DE]">
                    <div className="flex items-center gap-1.5 font-mono text-[11px]">
                      <span className="text-[#5E6E80]">Submitter Trust:</span>
                      <span className={`font-bold ${(scan.submitter_xp ?? 100) < 0 ? 'text-[#A8342A]' : 'text-[#2F6F4E]'}`}>
                        {scan.submitter_xp ?? 100} XP
                      </span>
                      <span className="text-[10px] px-1.5 py-0.2 bg-white border border-[#D8D2C6]">
                        {scan.reputation_tier || ((scan.submitter_xp ?? 100) >= 100 ? 'Citizen Scout' : 'Restricted')}
                      </span>
                    </div>

                    {scan.confirmation_message && (
                      <span className="text-[10px] text-[#2F6F4E] font-medium truncate max-w-[160px]" title={scan.confirmation_message}>
                        ✓ Confirmed
                      </span>
                    )}
                  </div>

                  {/* Claimed Violation & Priority Check Details */}
                  {scan.claimed_violation_type && (
                    <div className="bg-[#FAF8F5] border border-[#D8D2C6] p-2.5 text-xs space-y-1 font-mono">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-[#5E6E80]">Citizen Claimed:</span>
                        <span className="font-bold text-[#1C2B3A] uppercase">{scan.claimed_violation_type}</span>
                      </div>
                      {scan.priority_check_result && (
                        <div className="text-[11px] text-[#2F6F4E] font-medium pt-1 border-t border-[#EAE6DE]">
                          ✓ {scan.priority_check_result.details || 'Priority statutory check verified.'}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Metadata Row */}
                  <div className="flex items-center justify-between text-[11px] font-mono text-[#5E6E80] pt-1">
                    <span>GTIN: {scan.gtin || 'Not Decoded'}</span>
                    <span>{scan.violations_count} statutory violation(s)</span>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-2 border-t border-[#EAE6DE]">
                    <a
                      href={
                        (scan.pdf_report_url && scan.pdf_report_url.startsWith('http'))
                          ? scan.pdf_report_url
                          : `http://localhost:8000${scan.pdf_report_url || `/reports/${scan.scan_id || scan.id}/pdf`}`
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#1C2B3A] text-white text-xs font-medium hover:bg-[#2E3F50] transition-all"
                    >
                      <Download className="w-3.5 h-3.5 text-[#DFBF82]" />
                      <span>Certified Report</span>
                    </a>

                    {onSelectScan && (
                      <button
                        onClick={() => onSelectScan(scan)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#D8D2C6] text-[#1C2B3A] text-xs font-medium hover:bg-[#EFECE6] transition-all"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect Specimen</span>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Subtab 2: Pending Review (Reusing existing ReInspectionQueue with citizen filter) */}
      {activeSubTab === 'pending_review' && (
        <div className="space-y-4">
          <div className="bg-[#FAF3E6] border border-[#DFBF82] p-4 text-xs text-[#8C6B1C] flex items-center gap-3">
            <Award className="w-5 h-5 shrink-0 text-[#B8862B]" />
            <div>
              <span className="font-bold">Inspector Discrepancy & Manual Review Queue:</span> Citizen submissions that triggered consensus disputes, sensor escalations, or confidence drops are held here for certified inspector override and penalty confirmation.
            </div>
          </div>

          <ReInspectionQueue
            sourceFilter="citizen"
            onSelectScan={(scanId: number) => {
              const matched = allScans.find(s => s.id === scanId || s.scan_id === scanId);
              if (matched && onSelectScan) {
                onSelectScan(matched);
              }
            }}
          />
        </div>
      )}
    </div>
  );
};
