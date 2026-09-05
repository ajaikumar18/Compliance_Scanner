import React from 'react';

export interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color?: 'indigo' | 'emerald' | 'amber' | 'rose' | 'cyan' | 'purple' | 'blue';
  subtitle?: string;
  badge?: string;
  className?: string;
}

const COLOR_MAP = {
  indigo: {
    accentBar: 'border-l-[#1C2B3A]',
    iconBox: 'bg-[#F7F5F0] text-[#1C2B3A] border border-[#D8D2C6]',
    badge: 'bg-[#F7F5F0] text-[#1C2B3A] border border-[#D8D2C6]',
  },
  emerald: {
    accentBar: 'border-l-[#2F6F4E]',
    iconBox: 'bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]',
    badge: 'bg-[#EAF4EE] text-[#2F6F4E] border border-[#9BC6AE]',
  },
  amber: {
    accentBar: 'border-l-[#B8862B]',
    iconBox: 'bg-[#FAF3E6] text-[#B8862B] border border-[#DFBF82]',
    badge: 'bg-[#FAF3E6] text-[#B8862B] border border-[#DFBF82]',
  },
  rose: {
    accentBar: 'border-l-[#A8342A]',
    iconBox: 'bg-[#F9EBE9] text-[#A8342A] border border-[#E09891]',
    badge: 'bg-[#F9EBE9] text-[#A8342A] border border-[#E09891]',
  },
  cyan: {
    accentBar: 'border-l-[#244F64]',
    iconBox: 'bg-[#EDF4F7] text-[#244F64] border border-[#9BBBC9]',
    badge: 'bg-[#EDF4F7] text-[#244F64] border border-[#9BBBC9]',
  },
  purple: {
    accentBar: 'border-l-[#543864]',
    iconBox: 'bg-[#F4EEF7] text-[#543864] border border-[#C5A8D4]',
    badge: 'bg-[#F4EEF7] text-[#543864] border border-[#C5A8D4]',
  },
  blue: {
    accentBar: 'border-l-[#1C2B3A]',
    iconBox: 'bg-[#F7F5F0] text-[#1C2B3A] border border-[#D8D2C6]',
    badge: 'bg-[#F7F5F0] text-[#1C2B3A] border border-[#D8D2C6]',
  },
};

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  color = 'indigo',
  subtitle,
  badge,
  className = '',
}) => {
  const styles = COLOR_MAP[color] || COLOR_MAP.indigo;

  return (
    <div
      className={`bg-white p-4 rounded-none border border-[#D8D2C6] border-l-4 ${styles.accentBar} flex items-center justify-between transition-colors ${className}`}
    >
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <p className="text-[11px] font-semibold text-[#5E6E80] uppercase tracking-wider font-sans">
            {title}
          </p>
          {badge && (
            <span className={`text-[10px] px-1.5 py-0.2 rounded-none font-mono font-medium ${styles.badge}`}>
              {badge}
            </span>
          )}
        </div>
        <h3 className="text-2xl font-bold font-serif text-[#1C2B3A] tracking-tight">{value}</h3>
        {subtitle && <p className="text-xs text-[#5E6E80] font-sans">{subtitle}</p>}
      </div>

      <div className={`p-2.5 rounded-none shrink-0 ${styles.iconBox}`}>
        {icon}
      </div>
    </div>
  );
};
