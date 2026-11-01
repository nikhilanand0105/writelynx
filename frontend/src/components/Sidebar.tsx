import React from 'react';
import {
  LayoutDashboard,
  UploadCloud,
  FileEdit,
  ShieldAlert,
  GitCompare,
  Scale,
  Database,
  Layers,
  BookOpenCheck,
  Sparkles,
  History,
  Download,
  Settings,
  Lock
} from 'lucide-react';
import { useStudioStore, StudioTab } from '../store/useStudioStore';

interface NavItem {
  id: StudioTab;
  label: string;
  icon: React.FC<{ className?: string }>;
  description: string;
  badge?: string;
}

export const Sidebar: React.FC = () => {
  const { activeTab, setActiveTab } = useStudioStore();

  const navItems: NavItem[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      description: 'System metrics & documents',
    },
    {
      id: 'new_analysis',
      label: 'New Analysis',
      icon: UploadCloud,
      description: 'Upload report & sources',
    },
    {
      id: 'editor',
      label: 'Document Editor',
      icon: FileEdit,
      description: '3-panel document review',
    },
    {
      id: 'detector_highlights',
      label: 'Detector Highlights',
      icon: ShieldAlert,
      description: 'ZeroGPT & Turnitin alignment',
    },
    {
      id: 'report_comparison',
      label: 'Report Comparison',
      icon: GitCompare,
      description: 'Compare multiple detector PDFs',
    },
    {
      id: 'flagged_comparison',
      label: 'Flagged Comparison',
      icon: Scale,
      description: 'Observable style statistics',
    },
    {
      id: 'evidence',
      label: 'Research Evidence',
      icon: Database,
      description: 'Author logs & verification',
    },
    {
      id: 'overlap',
      label: 'Overlap Review',
      icon: Layers,
      description: 'Local text overlap evidence',
    },
    {
      id: 'citation',
      label: 'Citation Review',
      icon: BookOpenCheck,
      description: 'IEEE/APA attribution audit',
    },
    {
      id: 'quality',
      label: 'Writing Quality',
      icon: Sparkles,
      description: 'Academic clarity & flow',
    },
    {
      id: 'revisions',
      label: 'Revision History',
      icon: History,
      description: 'Authorship audit trail',
    },
    {
      id: 'export',
      label: 'Export Center',
      icon: Download,
      description: 'DOCX, PDF & validation',
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
      description: 'LLM & offline preferences',
    },
  ];

  return (
    <aside className="w-64 border-r border-slate-200 bg-white flex flex-col justify-between h-[calc(100vh-4rem)] sticky top-16 select-none shrink-0">
      <div className="p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-[11px] font-semibold tracking-wider text-slate-600 uppercase">
          Studio Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${
                isActive
                  ? 'bg-slate-900 text-white font-medium shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
              }`}
            >
              <Icon
                className={`w-5 h-5 shrink-0 mt-0.5 ${
                  isActive ? 'text-indigo-400' : 'text-slate-600'
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium leading-none">{item.label}</span>
                </div>
                <p
                  className={`text-[11px] mt-1 truncate ${
                    isActive ? 'text-slate-300' : 'text-slate-600'
                  }`}
                >
                  {item.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Footer Info Box */}
      <div className="p-4 border-t border-slate-200 bg-slate-50/70">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-700 mb-1">
          <Lock className="w-3.5 h-3.5 text-slate-500" />
          <span>Local Trust Boundary</span>
        </div>
        <p className="text-[11px] text-slate-500 leading-normal">
          Documents are stored locally. Remote model processing requires authorization in Settings. Local diagnostics are distinct from external detector judgments.
        </p>
      </div>
    </aside>
  );
};
