import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  BookOpenCheck,
  FileCheck,
  CheckCircle2,
  AlertCircle,
  UploadCloud,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  FileText,
  Clock,
  Layers,
  CreditCard,
  Plus
} from 'lucide-react';
import { api } from '../services/api';
import { useStudioStore } from '../store/useStudioStore';

type WizardStep = 'mode' | 'plan' | 'payment' | 'upload' | 'processing';

interface HelpMode {
  id: string;
  backendMode: string;
  title: string;
  description: string;
  icon: React.FC<{ className?: string }>;
  features: string[];
}

const HELP_MODES: HelpMode[] = [
  {
    id: 'proofread',
    backendMode: 'light_copyediting',
    title: 'Proofread my document',
    description: 'Correct grammar, typos, punctuation, spelling, and improve clarity while strictly preserving your words.',
    icon: FileCheck,
    features: ['Typo and spelling checks', 'Sentence readability', 'Protected numeric and unit facts'],
  },
  {
    id: 'academic',
    backendMode: 'academic_revision',
    title: 'Improve academic writing',
    description: 'Refine sentence flow, improve phrasing, elevate academic vocabulary, and remove colloquialisms.',
    icon: Sparkles,
    features: ['Academic tone and voice', 'Clear transitions', 'Passive/active voice refinement'],
  },
  {
    id: 'research',
    backendMode: 'research_grounded',
    title: 'Review research and citations',
    description: 'Verify supporting evidence, bibliographic citations, reference attribution, and claim consistency.',
    icon: BookOpenCheck,
    features: ['IEEE & APA citation alignment', 'Evidence verification', 'Attribution auditing'],
  },
];

interface PlanTier {
  id: string;
  name: string;
  priceRupees: number;
  pages: number;
  maxChars: number;
  maxMB: number;
  description: string;
  isPopular?: boolean;
}

const PLAN_TIERS: PlanTier[] = [
  {
    id: 'basic',
    name: 'Basic',
    priceRupees: 20,
    pages: 4,
    maxChars: 15000,
    maxMB: 10,
    description: 'Short lab reports, seminar summaries, and short assignments.',
  },
  {
    id: 'standard',
    name: 'Standard',
    priceRupees: 50,
    pages: 20,
    maxChars: 65000,
    maxMB: 20,
    description: 'Semester project reports, literature surveys, and capstones.',
    isPopular: true,
  },
  {
    id: 'extended',
    name: 'Extended',
    priceRupees: 100,
    pages: 50,
    maxChars: 160000,
    maxMB: 30,
    description: 'Comprehensive research manuscripts, final thesis, and dissertations.',
  },
];

export const NewDocumentWizard: React.FC = () => {
  const navigate = useNavigate();
  const { setActiveDocument, triggerRefresh } = useStudioStore();

  const [step, setStep] = useState<WizardStep>('mode');
  const [selectedMode, setSelectedMode] = useState<string>('academic_revision');
  const [selectedPlan, setSelectedPlan] = useState<string>('standard');
  const [entitlements, setEntitlements] = useState<any[]>([]);
  const [activeEntitlementId, setActiveEntitlementId] = useState<string | null>(null);

  // Upload & File State
  const [docFile, setDocFile] = useState<File | null>(null);
  const [sourceFiles, setSourceFiles] = useState<File[]>([]);
  const [detectorFile, setDetectorFile] = useState<File | null>(null);
  const [showOptionalFiles, setShowOptionalFiles] = useState(false);
  const [clientEstimate, setClientEstimate] = useState<any | null>(null);
  const [overageInfo, setOverageInfo] = useState<any | null>(null);

  // Async & Progress State
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [createdDocId, setCreatedDocId] = useState<string | null>(null);

  useEffect(() => {
    api.getMyEntitlements()
      .then((items) => {
        setEntitlements(items);
        const available = items.find((e) => e.status === 'AVAILABLE');
        if (available) {
          setActiveEntitlementId(available.id);
          setSelectedPlan(available.plan_tier);
          setSelectedMode(available.operating_mode || 'academic_revision');
        }
      })
      .catch(() => {});
  }, []);

  const availableEntitlements = entitlements.filter((e) => e.status === 'AVAILABLE');

  const runClientEstimate = (file: File) => {
    try {
      const sizeMB = file.size / (1024 * 1024);
      const approxWords = Math.round(file.size / 220);
      const approxChars = approxWords * 6;
      const estPages = Math.max(1, Math.ceil(approxWords / 350));
      const recTier =
        approxChars > 65000 || estPages > 20 || sizeMB > 20
          ? 'extended'
          : approxChars > 15000 || estPages > 4 || sizeMB > 10
          ? 'standard'
          : 'basic';

      setClientEstimate({
        sizeMB: sizeMB.toFixed(2),
        estimatedChars: approxChars,
        estimatedWords: approxWords,
        estimatedPages: estPages,
        recommendedTier: recTier,
      });
    } catch {
      setClientEstimate(null);
    }
  };

  const handleDocFileSelect = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setErrorMessage('The primary manuscript must be a Microsoft Word (.docx) document.');
      return;
    }
    setDocFile(file);
    setErrorMessage('');
    setOverageInfo(null);
    runClientEstimate(file);
  };

  // Payment checkout
  const handleProceedToPayment = async () => {
    setIsProcessing(true);
    setErrorMessage('');
    setProcessingStatus('Creating secure payment order...');

    try {
      const order = await api.createPaymentOrder(selectedPlan, selectedMode);

      const win = window as any;
      const isPlaceholderKey =
        !order.key_id ||
        order.key_id === 'rzp_test_writelynx' ||
        order.key_id.startsWith('mock_');
      const isDevMockAllowed =
        import.meta.env.DEV || import.meta.env.VITE_ENABLE_MOCK_PAYMENTS === 'true' || isPlaceholderKey;

      if (win.Razorpay && !isPlaceholderKey) {
        const rzp = new win.Razorpay({
          key: order.key_id,
          amount: order.amount_paise,
          currency: order.currency || 'INR',
          name: 'Writelynx Academic Studio',
          description: `${selectedPlan.toUpperCase()} Plan - Single-Use Manuscript Slot`,
          order_id: order.order_id,
          config: {
            display: {
              blocks: {
                upi: {
                  name: 'Pay via UPI',
                  instruments: [{ method: 'upi' }],
                },
              },
              sequence: ['block.upi'],
              preferences: {
                show_default_blocks: true,
              },
            },
          },
          handler: async (response: any) => {
            try {
              setProcessingStatus('Verifying payment on server...');
              const verified = await api.verifyPayment(
                order.order_id,
                response.razorpay_payment_id,
                response.razorpay_signature
              );
              const updated = await api.getMyEntitlements();
              setEntitlements(updated);
              setActiveEntitlementId(verified.id || updated.find((e: any) => e.status === 'AVAILABLE')?.id);
              setIsProcessing(false);
              setStep('upload');
            } catch (err: any) {
              setIsProcessing(false);
              setErrorMessage(err.message || 'Payment verification failed on server.');
            }
          },
          theme: { color: '#4f46e5' },
        });
        rzp.open();
        setIsProcessing(false);
      } else {
        const isDevMockAllowed =
          import.meta.env.DEV || import.meta.env.VITE_ENABLE_MOCK_PAYMENTS === 'true';

        if (!isDevMockAllowed) {
          setIsProcessing(false);
          setErrorMessage(
            'Payment gateway (Razorpay) failed to load. Please ensure your ad-blocker allows checkout.razorpay.com and refresh.'
          );
          return;
        }

        // Test sandbox fallback
        setProcessingStatus('Fulfilling transaction in sandbox mode...');
        const testPayId = `pay_test_${Date.now()}`;
        const verified = await api.verifyPayment(
          order.order_id,
          testPayId,
          `mock_sig_${order.order_id}_${testPayId}`
        );
        const updated = await api.getMyEntitlements();
        setEntitlements(updated);
        setActiveEntitlementId(verified.id || updated.find((e: any) => e.status === 'AVAILABLE')?.id);
        setIsProcessing(false);
        setStep('upload');
      }
    } catch (err: any) {
      setIsProcessing(false);
      setErrorMessage(err.message || 'Payment order creation failed.');
    }
  };

  // Upgrade handler if file is over limit
  const handleUpgradeOverage = async () => {
    if (!overageInfo || !overageInfo.recommended_tier) return;
    try {
      setIsProcessing(true);
      setErrorMessage('');
      setProcessingStatus(`Initiating upgrade to ${overageInfo.recommended_tier.toUpperCase()}...`);
      const upgOrder = await api.createUpgradeOrder(overageInfo.entitlement_id, overageInfo.recommended_tier);

      const win = window as any;
      const isPlaceholderUpgKey =
        !upgOrder.key_id ||
        upgOrder.key_id === 'rzp_test_writelynx' ||
        upgOrder.key_id.startsWith('mock_');

      if (win.Razorpay && !isPlaceholderUpgKey) {
        const rzp = new win.Razorpay({
          key: upgOrder.key_id,
          amount: upgOrder.upgrade_amount_paise,
          currency: upgOrder.currency || 'INR',
          name: 'Writelynx Plan Upgrade',
          description: `Upgrade to ${overageInfo.recommended_tier.toUpperCase()}`,
          order_id: upgOrder.order_id,
          config: {
            display: {
              blocks: {
                upi: {
                  name: 'Pay via UPI',
                  instruments: [{ method: 'upi' }],
                },
              },
              sequence: ['block.upi'],
            },
          },
          handler: async (response: any) => {
            try {
              setProcessingStatus('Verifying upgrade on server...');
              await api.verifyUpgrade(
                overageInfo.entitlement_id,
                overageInfo.recommended_tier,
                upgOrder.order_id,
                response.razorpay_payment_id,
                response.razorpay_signature
              );
              setOverageInfo(null);
              setIsProcessing(false);
              handleUploadAndStart();
            } catch (err: any) {
              setIsProcessing(false);
              setErrorMessage(err.message || 'Upgrade verification failed.');
            }
          },
          theme: { color: '#4f46e5' },
        });
        rzp.open();
        setIsProcessing(false);
      } else {
        // Sandbox upgrade
        setProcessingStatus(`Fulfilling upgrade for ₹${upgOrder.upgrade_amount_rupees} in test mode...`);
        const testUpgPayId = `pay_upg_${Date.now()}`;
        await api.verifyUpgrade(
          overageInfo.entitlement_id,
          overageInfo.recommended_tier,
          upgOrder.order_id,
          testUpgPayId,
          `mock_sig_${upgOrder.order_id}_${testUpgPayId}`
        );
        setOverageInfo(null);
        setIsProcessing(false);
        handleUploadAndStart();
      }
    } catch (err: any) {
      setIsProcessing(false);
      setErrorMessage(err.message || 'Upgrade failed.');
    }
  };

  // Upload and start analysis
  const handleUploadAndStart = async () => {
    if (!docFile) {
      setErrorMessage('Please select a Microsoft Word (.docx) document.');
      return;
    }

    const entitlementToUse = activeEntitlementId
      ? entitlements.find((e) => e.id === activeEntitlementId)
      : entitlements.find((e) => e.status === 'AVAILABLE');

    if (!entitlementToUse) {
      setErrorMessage('No available paid plan slot found. Please select a plan to proceed.');
      setStep('plan');
      return;
    }

    setIsProcessing(true);
    setStep('processing');
    setErrorMessage('');
    setProcessingStatus('Requesting quarantine upload token...');

    try {
      const slot = await api.requestUploadToken(entitlementToUse.id);
      setProcessingStatus('Verifying document safety in quarantine...');
      const uploadRes = await api.uploadAuthorizedDocument(slot.upload_token, docFile);

      if (uploadRes.status === 'UNSUPPORTED_OVER_LIMIT' || uploadRes.overLimit) {
        setIsProcessing(false);
        setStep('upload');
        setOverageInfo(uploadRes);
        setErrorMessage(
          `Document exceeds ${uploadRes.current_tier} limit: ${uploadRes.actual_characters.toLocaleString()} characters (max ${uploadRes.allowed_characters.toLocaleString()}).`
        );
        return;
      }

      const docId = uploadRes.document_id;
      setCreatedDocId(docId);

      // Upload optional detector PDF if provided
      if (detectorFile) {
        setProcessingStatus('Aligning external detector PDF highlights...');
        try {
          await api.uploadDetectorPdf(docId, detectorFile);
        } catch (e) {
          console.warn('Detector PDF upload notice:', e);
        }
      }

      // Upload optional reference sources if provided
      for (const source of sourceFiles) {
        setProcessingStatus(`Importing reference source: ${source.name}...`);
        try {
          await api.uploadSource(docId, source, false);
        } catch (e) {
          console.warn('Source upload notice:', e);
        }
      }

      // Start background analysis
      setProcessingStatus('Reviewing content and preparing suggestions...');
      await api.startAnalysis(docId, selectedMode, 'general');

      // Poll until analysis reaches completed
      let polls = 0;
      const pollInterval = setInterval(async () => {
        polls += 1;
        try {
          const doc = await api.getDocument(docId);
          if (doc.processing_status === 'completed') {
            clearInterval(pollInterval);
            setActiveDocument(doc);
            triggerRefresh();
            setProcessingStatus('Ready! Opening Document Review...');
            setTimeout(() => {
              navigate(`/documents/${docId}`);
            }, 600);
          } else if (doc.processing_status === 'failed') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            setErrorMessage('Document analysis paused. You can still inspect the document in the workspace.');
            setTimeout(() => {
              navigate(`/documents/${docId}`);
            }, 1200);
          } else {
            if (polls % 3 === 0) {
              setProcessingStatus('Checking writing structure and citations...');
            } else if (polls % 3 === 1) {
              setProcessingStatus('Validating facts and technical invariants...');
            } else {
              setProcessingStatus('Generating natural academic suggestions...');
            }
          }
        } catch {
          // Keep polling
        }
      }, 1500);

    } catch (err: any) {
      setIsProcessing(false);
      setStep('upload');
      setErrorMessage(err.message || 'An error occurred during upload or analysis.');
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-8">
      {/* Step Progress Tracker */}
      <div className="border-b border-slate-200 pb-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">New Manuscript Review</h1>
            <p className="text-xs text-slate-500 mt-1">Guided 4-step preparation, payment, and analysis</p>
          </div>
          <button
            onClick={() => navigate('/documents')}
            className="text-xs text-slate-500 hover:text-slate-800 transition"
          >
            Cancel and exit
          </button>
        </div>

        {/* Wizard Steps Pills */}
        <div className="flex items-center gap-2 mt-6 overflow-x-auto">
          {[
            { id: 'mode', label: '1. Help Mode' },
            { id: 'plan', label: '2. Choose Plan' },
            { id: 'payment', label: '3. Payment' },
            { id: 'upload', label: '4. Upload DOCX' },
            { id: 'processing', label: '5. Analysis' },
          ].map((s, idx) => {
            const isCurrent = step === s.id;
            const isDone =
              (s.id === 'mode' && step !== 'mode') ||
              (s.id === 'plan' && !['mode', 'plan'].includes(step)) ||
              (s.id === 'payment' && ['upload', 'processing'].includes(step)) ||
              (s.id === 'upload' && step === 'processing');

            return (
              <div
                key={s.id}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 transition ${
                  isCurrent
                    ? 'bg-indigo-600 text-white font-semibold'
                    : isDone
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'bg-slate-100 text-slate-500'
                }`}
              >
                {isDone ? <CheckCircle2 className="w-3.5 h-3.5 text-indigo-600" /> : null}
                <span>{s.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {errorMessage && (
        <div role="alert" className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage('')} className="underline shrink-0">
            Dismiss
          </button>
        </div>
      )}

      {/* STEP 1: SELECT HELP MODE */}
      {step === 'mode' && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">What would you like help with?</h2>
            <p className="text-xs text-slate-500 mt-1">
              Select the primary review goal for this manuscript. Your choice determines the editorial depth and focus.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {HELP_MODES.map((mode) => {
              const Icon = mode.icon;
              const isSelected = selectedMode === mode.backendMode;
              return (
                <div
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.backendMode)}
                  className={`p-6 rounded-xl border cursor-pointer transition flex flex-col justify-between space-y-4 ${
                    isSelected
                      ? 'border-indigo-600 bg-indigo-50/30 ring-2 ring-indigo-500/20'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="space-y-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isSelected ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <h3 className="font-semibold text-slate-900 text-sm">{mode.title}</h3>
                    <p className="text-xs text-slate-500 leading-relaxed">{mode.description}</p>
                  </div>

                  <ul className="space-y-1.5 pt-2 border-t border-slate-100 text-[11px] text-slate-600">
                    {mode.features.map((feat, i) => (
                      <li key={i} className="flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>

          <div className="flex justify-end pt-4">
            <button
              onClick={() => {
                if (availableEntitlements.length > 0) {
                  setStep('plan');
                } else {
                  setStep('plan');
                }
              }}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
            >
              <span>Continue to Plan Selection</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: CHOOSE PLAN TIER */}
      {step === 'plan' && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Choose a Plan for this Manuscript</h2>
            <p className="text-xs text-slate-500 mt-1">
              Select the tier that fits your document size. Each plan grants single-use analysis for one manuscript.
            </p>
          </div>

          {/* Existing Unused Plan Slot Offer */}
          {availableEntitlements.length > 0 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                <div>
                  <div className="text-xs font-bold text-emerald-900">
                    You have {availableEntitlements.length} unused plan slot(s) available!
                  </div>
                  <p className="text-xs text-emerald-700 mt-0.5">
                    Use your previously purchased slot instead of paying again.
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  const ent = availableEntitlements[0];
                  setActiveEntitlementId(ent.id);
                  setSelectedPlan(ent.plan_tier);
                  setStep('upload');
                }}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs transition shrink-0"
              >
                Use Existing Slot ({availableEntitlements[0].plan_tier.toUpperCase()})
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {PLAN_TIERS.map((tier) => {
              const isSelected = selectedPlan === tier.id;
              return (
                <div
                  key={tier.id}
                  onClick={() => setSelectedPlan(tier.id)}
                  className={`p-6 rounded-xl border cursor-pointer transition flex flex-col justify-between space-y-4 relative ${
                    isSelected
                      ? 'border-indigo-600 bg-indigo-50/30 ring-2 ring-indigo-500/20'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  {tier.isPopular && (
                    <span className="absolute -top-2.5 right-4 bg-indigo-600 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded shadow-xs">
                      Popular
                    </span>
                  )}
                  <div className="space-y-3">
                    <div className="flex justify-between items-baseline">
                      <h3 className="font-bold text-slate-900 text-base">{tier.name}</h3>
                      <div className="text-xl font-extrabold text-indigo-950">₹{tier.priceRupees}</div>
                    </div>
                    <p className="text-xs text-slate-500">{tier.description}</p>
                    <div className="space-y-1 pt-2 border-t border-slate-100 text-xs text-slate-600">
                      <div>Up to <strong>{tier.pages} pages</strong></div>
                      <div>Max <strong>{tier.maxChars.toLocaleString()}</strong> characters</div>
                      <div>Max <strong>{tier.maxMB} MB</strong> file size</div>
                    </div>
                  </div>

                  <div className="pt-2">
                    <div className={`w-full py-2 rounded-lg text-xs font-semibold text-center ${isSelected ? 'bg-indigo-600 text-white' : 'border border-slate-200 text-slate-700'}`}>
                      {isSelected ? 'Selected' : 'Select Plan'}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between pt-4">
            <button
              onClick={() => setStep('mode')}
              className="flex items-center gap-1.5 px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs hover:bg-slate-50 transition"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
            <button
              onClick={() => setStep('payment')}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
            >
              <span>Continue to Payment (₹{PLAN_TIERS.find((p) => p.id === selectedPlan)?.priceRupees})</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: PAYMENT CHECKOUT */}
      {step === 'payment' && (
        <div className="max-w-xl mx-auto space-y-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Order Confirmation & Payment</h2>
            <p className="text-xs text-slate-500 mt-1">
              Payment unlocks one document upload and its included review allowance.
            </p>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5 shadow-xs">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <div className="font-semibold text-slate-900 text-sm">
                  {selectedPlan.toUpperCase()} Plan Slot
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Help Mode: {HELP_MODES.find((m) => m.backendMode === selectedMode)?.title}
                </div>
              </div>
              <div className="text-2xl font-extrabold text-slate-900">
                ₹{PLAN_TIERS.find((p) => p.id === selectedPlan)?.priceRupees}
              </div>
            </div>

            <div className="space-y-2 text-xs text-slate-600">
              <div className="flex justify-between">
                <span>Included Allowance:</span>
                <span className="font-medium text-slate-800">
                  {PLAN_TIERS.find((p) => p.id === selectedPlan)?.pages} pages (
                  {PLAN_TIERS.find((p) => p.id === selectedPlan)?.maxChars.toLocaleString()} characters)
                </span>
              </div>
              <div className="flex justify-between">
                <span>Payment Method:</span>
                <span className="font-medium text-slate-800">Instant UPI / NetBanking / Cards</span>
              </div>
              <div className="flex justify-between">
                <span>Validity:</span>
                <span className="font-medium text-slate-800">Single-use manuscript upload</span>
              </div>
            </div>

            <div className="p-3 bg-indigo-50 border border-indigo-100 rounded-lg text-xs text-indigo-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-600 shrink-0" />
              <span>Direct secure bank-grade UPI settlement via Razorpay.</span>
            </div>

            <div className="pt-2">
              <button
                disabled={isProcessing}
                onClick={handleProceedToPayment}
                className="w-full flex items-center justify-center gap-2 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold shadow-sm transition disabled:opacity-50"
              >
                {isProcessing ? (
                  <>
                    <Clock className="w-4 h-4 animate-spin" />
                    <span>Processing Payment...</span>
                  </>
                ) : (
                  <>
                    <CreditCard className="w-4 h-4" />
                    <span>Pay ₹{PLAN_TIERS.find((p) => p.id === selectedPlan)?.priceRupees} via UPI</span>
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="flex justify-start">
            <button
              disabled={isProcessing}
              onClick={() => setStep('plan')}
              className="flex items-center gap-1.5 px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs hover:bg-slate-50 transition"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Plans</span>
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: UPLOAD DOCX */}
      {step === 'upload' && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Upload Your Word Manuscript</h2>
            <p className="text-xs text-slate-500 mt-1">
              Active Plan: <strong>{selectedPlan.toUpperCase()}</strong> (up to{' '}
              {PLAN_TIERS.find((p) => p.id === selectedPlan)?.pages} pages,{' '}
              {PLAN_TIERS.find((p) => p.id === selectedPlan)?.maxChars.toLocaleString()} characters)
            </p>
          </div>

          {/* Overage Warning & Upgrade Option */}
          {overageInfo && (
            <div className="bg-amber-50 border border-amber-300 rounded-xl p-5 space-y-3">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-bold text-amber-900 text-sm">Document Exceeds Selected Plan</h3>
                  <p className="text-xs text-amber-800 mt-1">
                    Your manuscript contains <strong>{overageInfo.actual_characters?.toLocaleString()}</strong> characters, which exceeds the {overageInfo.current_tier} limit ({overageInfo.allowed_characters?.toLocaleString()}).
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <button
                  onClick={handleUpgradeOverage}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold transition"
                >
                  Upgrade to {overageInfo.recommended_tier?.toUpperCase()} (Pay Delta)
                </button>
                <button
                  onClick={() => {
                    setDocFile(null);
                    setOverageInfo(null);
                  }}
                  className="px-4 py-2 border border-amber-300 text-amber-900 hover:bg-amber-100 rounded-lg text-xs font-medium transition"
                >
                  Choose a Different File
                </button>
              </div>
            </div>
          )}

          {/* Primary Drag & Drop Zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleDocFileSelect(e.dataTransfer.files[0]);
              }
            }}
            className={`border-2 border-dashed rounded-2xl p-8 md:p-10 text-center transition ${
              docFile
                ? 'border-indigo-400 bg-indigo-50/20'
                : 'border-slate-300 bg-white hover:border-indigo-400 hover:bg-slate-50/50'
            }`}
          >
            <input
              type="file"
              id="doc-upload"
              accept=".docx"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleDocFileSelect(e.target.files[0]);
                }
              }}
              className="hidden"
            />
            <label htmlFor="doc-upload" className="cursor-pointer block space-y-3">
              <div className="w-12 h-12 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center mx-auto">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div>
                <span className="font-semibold text-sm text-indigo-600 hover:underline">
                  Choose your Word document (.docx)
                </span>
                <span className="text-slate-500 text-xs"> or drag and drop here</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Microsoft Word reports only. Formulas, images, and tables are preserved.
              </p>
            </label>
          </div>

          {/* Selected File Details */}
          {docFile && (
            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-semibold text-sm text-slate-900">{docFile.name}</div>
                    <div className="text-xs text-slate-500">{(docFile.size / 1024).toFixed(1)} KB</div>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setDocFile(null);
                    setClientEstimate(null);
                    setOverageInfo(null);
                  }}
                  className="text-xs text-rose-600 hover:underline"
                >
                  Remove
                </button>
              </div>

              {clientEstimate && (
                <div className="grid grid-cols-3 gap-3 pt-3 border-t border-slate-100 text-center text-xs">
                  <div className="bg-slate-50 p-2 rounded-lg">
                    <div className="text-slate-400 text-[10px]">Estimated Pages</div>
                    <div className="font-bold text-slate-800">{clientEstimate.estimatedPages} pages</div>
                  </div>
                  <div className="bg-slate-50 p-2 rounded-lg">
                    <div className="text-slate-400 text-[10px]">Estimated Words</div>
                    <div className="font-bold text-slate-800">{clientEstimate.estimatedWords.toLocaleString()}</div>
                  </div>
                  <div className="bg-slate-50 p-2 rounded-lg">
                    <div className="text-slate-400 text-[10px]">File Size</div>
                    <div className="font-bold text-slate-800">{clientEstimate.sizeMB} MB</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Optional Supporting Files Accordion */}
          <div className="border border-slate-200 rounded-xl bg-white overflow-hidden shadow-xs">
            <button
              onClick={() => setShowOptionalFiles(!showOptionalFiles)}
              className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-slate-50 transition"
            >
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-semibold text-slate-800">
                  Add supporting files (optional)
                </span>
                <span className="text-[11px] text-slate-400">— Reference PDFs or Turnitin reports</span>
              </div>
              {showOptionalFiles ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>

            {showOptionalFiles && (
              <div className="p-5 border-t border-slate-100 space-y-4 bg-slate-50/50">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Upload Detector PDF (Turnitin / ZeroGPT)
                  </label>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setDetectorFile(e.target.files[0]);
                      }
                    }}
                    className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                  />
                  {detectorFile && <p className="text-[11px] text-emerald-700 mt-1">Loaded: {detectorFile.name}</p>}
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Upload Reference Sources (Papers / Prior Reports)
                  </label>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.txt,.docx"
                    onChange={(e) => {
                      if (e.target.files) {
                        setSourceFiles(Array.from(e.target.files));
                      }
                    }}
                    className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                  />
                  {sourceFiles.length > 0 && (
                    <p className="text-[11px] text-emerald-700 mt-1">
                      {sourceFiles.length} reference file(s) attached
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Action Button */}
          <div className="flex items-center justify-between pt-4">
            <button
              onClick={() => setStep('plan')}
              className="flex items-center gap-1.5 px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs hover:bg-slate-50 transition"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
            <button
              disabled={!docFile || isProcessing}
              onClick={handleUploadAndStart}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition disabled:opacity-50"
            >
              <span>Upload and Begin Review</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 5: DURABLE BACKGROUND PROCESSING */}
      {step === 'processing' && (
        <div className="py-12 max-w-lg mx-auto text-center space-y-6">
          <div className="w-16 h-16 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto shadow-sm">
            <Clock className="w-8 h-8 animate-spin" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Analyzing Your Manuscript
            </h2>
            <p className="text-xs text-slate-500">
              {processingStatus || 'Checking document structure and preparing suggestions…'}
            </p>
          </div>

          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div className="bg-indigo-600 h-2 rounded-full animate-pulse w-3/4" />
          </div>

          <div className="text-[11px] text-slate-400 bg-slate-50 p-4 rounded-xl border border-slate-100 text-left space-y-1.5">
            <div className="font-semibold text-slate-700">Durable Processing Guarantee</div>
            <p>
              Your analysis is running securely on the backend. You can safely refresh or leave this page and return to My Documents at any time without losing your job.
            </p>
          </div>

          {createdDocId && (
            <div className="pt-2">
              <button
                onClick={() => navigate(`/documents/${createdDocId}`)}
                className="text-xs text-indigo-600 hover:underline font-semibold"
              >
                Go directly to Document Workspace →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
export default NewDocumentWizard;
