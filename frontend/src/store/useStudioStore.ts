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

export type WorkspaceTab = 'review' | 'checks' | 'history';

interface StudioState {
  activeTab: StudioTab;
  workspaceTab: WorkspaceTab;
  activeChecksSubTab: string;
  activeDocumentId: string | null;
  activeDocument: DocumentItem | null;
  activeBlockId: string | null;
  selectedSection: string | null;
  isAnalyzing: boolean;
  refreshTrigger: number;
  setActiveTab: (tab: StudioTab) => void;
  setWorkspaceTab: (tab: WorkspaceTab) => void;
  setActiveChecksSubTab: (subTab: string) => void;
  setActiveDocument: (doc: DocumentItem | null) => void;
  setActiveBlockId: (blockId: string | null) => void;
  setSelectedSection: (section: string | null) => void;
  setIsAnalyzing: (status: boolean) => void;
  triggerRefresh: () => void;
}

export const useStudioStore = create<StudioState>((set) => ({
  activeTab: 'dashboard',
  workspaceTab: 'review',
  activeChecksSubTab: 'citations',
  activeDocumentId: null,
  activeDocument: null,
  activeBlockId: null,
  selectedSection: null,
  isAnalyzing: false,
  refreshTrigger: 0,
  setActiveTab: (tab) => set((state) => {
    // Map legacy tab requests to contextual workspace tabs
    let nextWorkspaceTab: WorkspaceTab = state.workspaceTab;
    let nextChecksSubTab: string = state.activeChecksSubTab;

    if (tab === 'editor' || tab === 'quality') {
      nextWorkspaceTab = 'review';
    } else if (tab === 'citation') {
      nextWorkspaceTab = 'checks';
      nextChecksSubTab = 'citations';
    } else if (tab === 'evidence') {
      nextWorkspaceTab = 'checks';
      nextChecksSubTab = 'sources';
    } else if (tab === 'overlap') {
      nextWorkspaceTab = 'checks';
      nextChecksSubTab = 'overlap';
    } else if (tab === 'detector_highlights') {
      nextWorkspaceTab = 'checks';
      nextChecksSubTab = 'highlights';
    } else if (tab === 'report_comparison' || tab === 'flagged_comparison') {
      nextWorkspaceTab = 'checks';
      nextChecksSubTab = 'comparison';
    } else if (tab === 'revisions') {
      nextWorkspaceTab = 'history';
    }

    return {
      activeTab: tab,
      workspaceTab: nextWorkspaceTab,
      activeChecksSubTab: nextChecksSubTab,
    };
  }),
  setWorkspaceTab: (tab) => set({ workspaceTab: tab }),
  setActiveChecksSubTab: (subTab) => set({ activeChecksSubTab: subTab }),
  setActiveDocument: (doc) =>
    set((state) => ({
      activeDocument: doc,
      activeDocumentId: doc ? doc.id : null,
      ...(state.activeDocumentId !== doc?.id ? { activeBlockId: null, selectedSection: null } : {}),
    })),
  setActiveBlockId: (blockId) => set({ activeBlockId: blockId }),
  setSelectedSection: (section) => set({ selectedSection: section }),
  setIsAnalyzing: (status) => set({ isAnalyzing: status }),
  triggerRefresh: () => set((state) => ({ refreshTrigger: state.refreshTrigger + 1 })),
}));
