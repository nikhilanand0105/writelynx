import { create } from 'zustand';
import { DocumentItem } from '../types';

export type StudioTab =
  | 'dashboard'
  | 'new_analysis'
  | 'editor'
  | 'detector_highlights'
  | 'report_comparison'
  | 'flagged_comparison'
  | 'evidence'
  | 'overlap'
  | 'citation'
  | 'quality'
  | 'revisions'
  | 'export'
  | 'settings';

interface StudioState {
  activeTab: StudioTab;
  activeDocumentId: string | null;
  activeDocument: DocumentItem | null;
  activeBlockId: string | null;
  selectedSection: string | null;
  isAnalyzing: boolean;
  refreshTrigger: number;
  setActiveTab: (tab: StudioTab) => void;
  setActiveDocument: (doc: DocumentItem | null) => void;
  setActiveBlockId: (blockId: string | null) => void;
  setSelectedSection: (section: string | null) => void;
  setIsAnalyzing: (status: boolean) => void;
  triggerRefresh: () => void;
}

export const useStudioStore = create<StudioState>((set) => ({
  activeTab: 'dashboard',
  activeDocumentId: null,
  activeDocument: null,
  activeBlockId: null,
  selectedSection: null,
  isAnalyzing: false,
  refreshTrigger: 0,
  setActiveTab: (tab) => set({ activeTab: tab }),
  setActiveDocument: (doc) => set((state) => ({ activeDocument: doc, activeDocumentId: doc ? doc.id : null, ...(state.activeDocumentId !== doc?.id ? { activeBlockId: null, selectedSection: null } : {}) })),
  setActiveBlockId: (blockId) => set({ activeBlockId: blockId }),
  setSelectedSection: (section) => set({ selectedSection: section }),
  setIsAnalyzing: (status) => set({ isAnalyzing: status }),
  triggerRefresh: () => set((state) => ({ refreshTrigger: state.refreshTrigger + 1 })),
}));
