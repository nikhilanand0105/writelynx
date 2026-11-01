import React, { useState } from 'react';
import {
  UploadCloud,
  FileCheck,
  ShieldAlert,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  FileUp,
  X
} from 'lucide-react';
import { api } from '../services/api';
import { useStudioStore } from '../store/useStudioStore';

export const NewAnalysisPage: React.FC = () => {
  const { setActiveDocument, setActiveTab, triggerRefresh } = useStudioStore();
  
  const [docFile, setDocFile] = useState<File | null>(null);
  const [sourceFiles, setSourceFiles] = useState<File[]>([]);
  const [detectorFile, setDetectorFile] = useState<File | null>(null);
  const [isExternalReport, setIsExternalReport] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string>('standard');
  const [editingMode, setEditingMode] = useState<string>('academic_revision');
  const [entitlements, setEntitlements] = useState<any[]>([]);
  const [overageInfo, setOverageInfo] = useState<any | null>(null);
  const [clientEstimate, setClientEstimate] = useState<any | null>(null);
  const [paymentSuccessMsg, setPaymentSuccessMsg] = useState<string>('');

  React.useEffect(() => {
    api.getMyEntitlements()
      .then((items) => setEntitlements(items))
      .catch(() => {});
  }, []);

  const runClientEstimate = (file: File) => {
    try {
      // Safe client-side file-size metric (0 bytes uploaded to server)
      const sizeMB = file.size / (1024 * 1024);
      const approxWords = Math.round(file.size / 220);
      const approxChars = approxWords * 6;
      const estPages = Math.max(1, Math.ceil(approxWords / 350));
      const recTier = approxChars > 65000 || estPages > 20 || sizeMB > 20
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
      setSelectedPlan(recTier);
    } catch {
      setClientEstimate(null);
    }
  };

  const handlePurchaseSlot = async (tier: string) => {
    try {
      setIsUploading(true);
      setErrorMsg('');
      setUploadProgress(`Creating payment order for ${tier.toUpperCase()} plan...`);
      const order = await api.createPaymentOrder(tier, editingMode);

      const win = window as any;
      if (win.Razorpay && order.key_id && !order.key_id.startsWith('mock_')) {
        const rzp = new win.Razorpay({
          key: order.key_id,
          amount: order.amount_paise,
          currency: order.currency || 'INR',
          name: 'Writelynx Academic Studio',
          description: `${tier.toUpperCase()} Plan - Single-Use Manuscript Slot`,
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
              setUploadProgress('Verifying payment on server...');
              await api.verifyPayment(order.order_id, response.razorpay_payment_id, response.razorpay_signature);
              const updated = await api.getMyEntitlements();
              setEntitlements(updated);
              setIsUploading(false);
              setPaymentSuccessMsg('Payment verified. You can now upload your document.');
            } catch (err: any) {
              setIsUploading(false);
              setErrorMsg(err.message || 'Payment verification failed on server.');
            }
          },
          theme: { color: '#4f46e5' },
        });
        rzp.open();
        setIsUploading(false);
      } else {
        const isDevMockAllowed =
          import.meta.env.DEV || import.meta.env.VITE_ENABLE_MOCK_PAYMENTS === 'true';

        if (!isDevMockAllowed) {
          setIsUploading(false);
          setErrorMsg(
            'Payment gateway (Razorpay) failed to load. Please ensure your ad-blocker allows checkout.razorpay.com and refresh the page.'
          );
          return;
        }

        // Test sandbox mode fallback
        setUploadProgress('Fulfilling transaction in sandbox test mode...');
        await api.verifyPayment(
          order.order_id,
          `pay_test_${Date.now()}`,
          `mock_sig_${order.order_id}_pay_test_${Date.now()}`
        );
        const updated = await api.getMyEntitlements();
        setEntitlements(updated);
        setIsUploading(false);
        setUploadProgress('');
        setPaymentSuccessMsg('Payment verified. You can now upload your document.');
      }
    } catch (err: any) {
      setIsUploading(false);
      setErrorMsg(err.message || 'Payment initiation failed.');
    }
  };

  const handleUpgradeOverage = async () => {
    if (!overageInfo || !overageInfo.recommended_tier) return;
    try {
      setIsUploading(true);
      setUploadProgress(`Initiating upgrade to ${overageInfo.recommended_tier}...`);
      const upgOrder = await api.createUpgradeOrder(overageInfo.entitlement_id, overageInfo.recommended_tier);

      const win = window as any;
      if (win.Razorpay && upgOrder.key_id && !upgOrder.key_id.startsWith('mock_')) {
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
              preferences: {
                show_default_blocks: true,
              },
            },
          },
          handler: async (response: any) => {
            try {
              setUploadProgress('Verifying upgrade on server...');
              await api.verifyUpgrade(
                overageInfo.entitlement_id,
                overageInfo.recommended_tier,
                upgOrder.order_id,
                response.razorpay_payment_id,
                response.razorpay_signature
              );
              setOverageInfo(null);
              setIsUploading(false);
              handleStartAnalysis();
            } catch (err: any) {
              setIsUploading(false);
              setErrorMsg(err.message || 'Upgrade verification failed.');
            }
          },
          theme: { color: '#4f46e5' },
        });
        rzp.open();
        setIsUploading(false);
      } else {
        const isDevMockAllowed =
          import.meta.env.DEV || import.meta.env.VITE_ENABLE_MOCK_PAYMENTS === 'true';

        if (!isDevMockAllowed) {
          setIsUploading(false);
          setErrorMsg(
            'Payment gateway (Razorpay) failed to load for upgrade. Please check your connection and refresh.'
          );
          return;
        }

        setUploadProgress(`Fulfilling upgrade for ₹${upgOrder.upgrade_amount_rupees} in test mode...`);
        await api.verifyUpgrade(
          overageInfo.entitlement_id,
          overageInfo.recommended_tier,
          upgOrder.order_id,
          `pay_upg_${Date.now()}`,
          `mock_sig_${upgOrder.order_id}_pay_upg_${Date.now()}`
        );
        setOverageInfo(null);
        setUploadProgress('Upgraded! Re-submitting document...');
        setIsUploading(false);
        handleStartAnalysis();
      }
    } catch (err: any) {
      setIsUploading(false);
      setErrorMsg(err.message || 'Upgrade failed.');
    }
  };
  const [profile, setProfile] = useState('general');
  const [uploadedId, setUploadedId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');

  const handleDocDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith('.docx')) {
        setDocFile(file);
        setErrorMsg('');
        runClientEstimate(file);
      } else {
        setErrorMsg('Primary manuscript must be a Microsoft Word (.docx) document.');
      }
    }
  };

  const handleSourceDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      const files = Array.from(e.dataTransfer.files);
      setSourceFiles((prev) => [...prev, ...files]);
    }
  };

  const handleRemoveSource = (index: number) => {
    setSourceFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleStartAnalysis = async () => {
    if (!docFile) {
      setErrorMsg('Please upload a Microsoft Word (.docx) manuscript to analyze.');
      return;
    }

    setIsUploading(true);
    setErrorMsg('');

    try {
      let docId = uploadedId;
      if (!docId) {
        const availEnt = entitlements.find((e) => e.status === 'AVAILABLE' && e.plan_tier === selectedPlan) || entitlements.find((e) => e.status === 'AVAILABLE');
        if (availEnt) {
          setUploadProgress('Requesting quarantine upload token...');
          const slot = await api.requestUploadToken(availEnt.id);
          setUploadProgress('Verifying document safety in quarantine...');
          const uploadRes = await api.uploadAuthorizedDocument(slot.upload_token, docFile);
          if (uploadRes.status === 'UNSUPPORTED_OVER_LIMIT' || uploadRes.overLimit) {
            setIsUploading(false);
            setOverageInfo(uploadRes);
            setUploadProgress('');
            return;
          }
          docId = uploadRes.document_id;
          setUploadedId(docId);
          const uploadedDoc = await api.getDocument(docId);
          setActiveDocument(uploadedDoc);
        } else {
          // Priority 0.1: Unpaid bypass fallback removed! Require purchasing an entitlement slot.
          setIsUploading(false);
          setErrorMsg('No available paid analysis slot. Please purchase a plan tier below before uploading.');
          return;
        }
      }

      if (detectorFile && docId) {
        setUploadProgress('Extracting detector highlights and matching passages…');
        await api.uploadDetectorPdf(docId, detectorFile);
        setDetectorFile(null);
      }
      for (const sourceFile of sourceFiles) {
        if (!docId) break;
        setUploadProgress(`Importing reference: ${sourceFile.name}`);
        await api.uploadSource(docId, sourceFile, isExternalReport);
        setSourceFiles((files) => files.filter((file) => file !== sourceFile));
      }
      if (docId) {
        setUploadProgress('Starting background analysis…');
        await api.startAnalysis(docId, editingMode, profile);
        const refreshed = await api.getDocument(docId);
        setActiveDocument(refreshed);
        triggerRefresh();
        setIsUploading(false);
        setActiveTab('editor');
      }

    } catch (err: any) {
      setIsUploading(false);
      setErrorMsg(err.message || 'An error occurred during upload or analysis.');
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">New Manuscript Analysis</h2>
        <p className="text-sm text-slate-500 mt-1">
          Upload an academic report, attach optional benchmark sources, configure editing mode, and run genuine diagnostic tests.
        </p>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {paymentSuccessMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-600" />
            <span className="font-medium">{paymentSuccessMsg}</span>
          </div>
          <button onClick={() => setPaymentSuccessMsg('')} className="text-emerald-600 hover:text-emerald-800 text-xs font-semibold">
            Dismiss
          </button>
        </div>
      )}

      {clientEstimate && (
        <div className="p-4 rounded-xl bg-slate-50 border border-indigo-200 text-slate-800 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-bold text-indigo-900 flex items-center gap-1.5">
              <FileCheck className="w-4 h-4 text-indigo-600" />
              Client Pre-Upload Inspection (Non-Authoritative Estimate)
            </span>
            <span className="text-[11px] font-semibold text-indigo-700 bg-indigo-100 px-2 py-0.5 rounded">
              Recommended Plan: {clientEstimate.recommendedTier.toUpperCase()}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-slate-600 pt-1">
            <div>• File Size: <strong>{clientEstimate.sizeMB} MB</strong></div>
            <div>• Approx. Words: <strong>{clientEstimate.estimatedWords.toLocaleString()}</strong></div>
            <div>• Approx. Chars: <strong>{clientEstimate.estimatedChars.toLocaleString()}</strong></div>
            <div>• Approx. Pages: <strong>~{clientEstimate.estimatedPages}</strong></div>
          </div>
          <p className="text-[11px] text-slate-600 italic">
            *Client estimation runs locally in your browser with 0 bytes uploaded. Server-side validation upon upload remains authoritative.
          </p>
        </div>
      )}

      {overageInfo && (
        <div className="p-5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 space-y-3 shadow-xs">
          <div className="flex items-center gap-2 font-semibold text-sm text-amber-950">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
            <span>
              {overageInfo.status === 'UNSUPPORTED_OVER_LIMIT' || !overageInfo.recommended_tier
                ? 'Maximum System Capacity Exceeded'
                : 'Manuscript Capacity Overage Detected'}
            </span>
          </div>
          {overageInfo.status === 'UNSUPPORTED_OVER_LIMIT' || !overageInfo.recommended_tier ? (
            <div className="space-y-3">
              <p className="text-xs text-amber-800 leading-relaxed">
                Your document contains <strong>{overageInfo.actual_pages} pages</strong> ({overageInfo.actual_characters.toLocaleString()} characters),
                which exceeds the maximum 50-page / 160,000-character ceiling of all Writelynx plans.
                Your paid entitlement has <strong>not</strong> been consumed. Please split your document into smaller chapters before analyzing.
              </p>
              <button
                onClick={() => { setOverageInfo(null); setDocFile(null); }}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold shadow-xs transition"
              >
                Select a Different Manuscript
              </button>
            </div>
          ) : (
            <>
              <p className="text-xs text-amber-800 leading-relaxed">
                Your document contains <strong>{overageInfo.actual_pages} pages</strong> ({overageInfo.actual_characters.toLocaleString()} characters),
                which exceeds the capacity of your <strong>{overageInfo.current_tier.toUpperCase()}</strong> plan (max {overageInfo.max_pages} pages).
                Your payment is preserved. Upgrade to <strong>{overageInfo.recommended_tier.toUpperCase()}</strong> for the exact price difference:
              </p>
              <div className="flex items-center gap-4 pt-1">
                <button
                  onClick={handleUpgradeOverage}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
                >
                  Pay ₹{overageInfo.upgrade_difference_rupees} Upgrade Difference
                </button>
                <button
                  onClick={() => { setOverageInfo(null); setDocFile(null); }}
                  className="text-xs text-amber-700 hover:underline"
                >
                  Cancel and select another document
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Pricing Tier Selector */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4 shadow-xs">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Select Analysis Plan Tier (Pay-Per-Document)
          </span>
          <span className="text-xs text-indigo-600 font-medium">Single-Use Paid Entitlement</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { id: 'basic', name: 'Basic', price: '₹20', paise: 2000, pages: 'Max 4 Pages', chars: '15,000 Chars', limit: '10 MB DOCX' },
            { id: 'standard', name: 'Standard', price: '₹50', paise: 5000, pages: 'Max 20 Pages', chars: '65,000 Chars', limit: '20 MB DOCX', badge: 'Most Popular' },
            { id: 'extended', name: 'Extended', price: '₹100', paise: 10000, pages: 'Max 50 Pages', chars: '160,000 Chars', limit: '30 MB DOCX' },
          ].map((plan) => {
            const hasSlot = entitlements.some((e) => e.status === 'AVAILABLE' && e.plan_tier === plan.id);
            return (
              <div
                key={plan.id}
                onClick={() => setSelectedPlan(plan.id)}
                className={`p-4 rounded-xl border cursor-pointer transition flex flex-col justify-between ${
                  selectedPlan === plan.id
                    ? 'border-indigo-600 bg-indigo-50/40 ring-2 ring-indigo-500/20'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-900">{plan.name}</span>
                    <span className="text-base font-extrabold text-indigo-600">{plan.price}</span>
                  </div>
                  {plan.badge && (
                    <span className="inline-block mt-1 text-[10px] font-semibold bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded">
                      {plan.badge}
                    </span>
                  )}
                  <ul className="text-xs text-slate-500 mt-3 space-y-1">
                    <li>• {plan.pages}</li>
                    <li>• {plan.chars}</li>
                    <li>• {plan.limit}</li>
                  </ul>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  {hasSlot ? (
                    <span className="text-xs text-emerald-600 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> 1 Slot Ready
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); handlePurchaseSlot(plan.id); }}
                      className="w-full text-center py-1.5 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition"
                    >
                      Buy {plan.name} ({plan.price})
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Step 1: Upload Primary Manuscript */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Step 1: Primary Manuscript</span>
            <span className="text-[11px] font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">Required (.docx)</span>
          </div>

          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDocDrop}
            className={`border-2 border-dashed rounded-xl p-8 text-center transition ${
              docFile ? 'border-emerald-400 bg-emerald-50/20' : 'border-slate-300 hover:border-indigo-400 bg-slate-50/50'
            }`}
          >
            {docFile ? (
              <div className="space-y-2">
                <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                  <FileCheck className="w-6 h-6" />
                </div>
                <div className="text-sm font-semibold text-slate-900">{docFile.name}</div>
                <div className="text-xs text-slate-500">{(docFile.size / 1024).toFixed(1)} KB</div>
                <button
                  type="button"
                  onClick={() => { setDocFile(null); setUploadedId(null); }}
                  className="text-xs text-rose-600 font-medium hover:underline mt-2"
                >
                  Change File
                </button>
              </div>
            ) : (
              <label className="cursor-pointer space-y-3 block">
                <div className="w-12 h-12 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <div>
                  <span className="text-sm font-semibold text-indigo-600 hover:text-indigo-700">Click to browse</span>
                  <span className="text-sm text-slate-600"> or drag DOCX here</span>
                </div>
                <p className="text-xs text-slate-600">
                  Preserves tables, figures, footnotes, font styles, and run metadata
                </p>
                <input
                  type="file"
                  accept=".docx"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      const f = e.target.files[0];
                      setDocFile(f);
                      runClientEstimate(f);
                    }
                  }}
                />
              </label>
            )}
          </div>
        </div>

        {/* Step 2: Upload Reference Sources */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Step 2: Reference Sources</span>
            <span className="text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">Optional</span>
          </div>

          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleSourceDrop}
            className="border-2 border-dashed border-slate-300 hover:border-indigo-400 bg-slate-50/50 rounded-xl p-6 text-center transition"
          >
            <label className="cursor-pointer space-y-2 block">
              <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center mx-auto">
                <FileUp className="w-5 h-5" />
              </div>
              <div className="text-xs text-slate-600">
                <span className="font-semibold text-indigo-600">Upload references</span> (PDF, DOCX, TXT)
              </div>
              <p className="text-[11px] text-slate-600">
                Sources to test for exact and fuzzy textual overlap
              </p>
              <input
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    setSourceFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
                  }
                }}
              />
            </label>
          </div>

          {/* External Report Checkbox */}
          <div className="pt-2 flex items-center gap-2">
            <input
              type="checkbox"
              id="extReport"
              checked={isExternalReport}
              onChange={(e) => setIsExternalReport(e.target.checked)}
              className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
            />
            <label htmlFor="extReport" className="text-xs text-slate-600 select-none cursor-pointer">
              Uploaded source includes an authorized historical similarity report (PDF)
            </label>
          </div>

          {/* Selected sources list */}
          {sourceFiles.length > 0 && (
            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {sourceFiles.map((f, idx) => (
                <div key={idx} className="flex items-center justify-between px-3 py-1.5 bg-slate-100/80 rounded text-xs text-slate-800">
                  <span className="truncate max-w-[240px]">{f.name}</span>
                  <button
                    onClick={() => handleRemoveSource(idx)}
                    className="text-slate-400 hover:text-rose-600 p-0.5"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Optional Step 2.5: Third-party Detector PDF */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4 shadow-xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-500" />
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Optional: Third-Party Detector PDF Export (ZeroGPT / Turnitin)
            </span>
          </div>
          <span className="text-[11px] font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
            Diagnostic Only
          </span>
        </div>

        <div className="border-2 border-dashed border-slate-300 hover:border-amber-400 bg-slate-50/50 rounded-xl p-6 text-center transition">
          {detectorFile ? (
            <div className="flex items-center justify-between bg-amber-50/60 border border-amber-200 p-3 rounded-lg text-xs">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-600" />
                <span className="font-semibold text-slate-800">{detectorFile.name}</span>
                <span className="text-slate-500">({(detectorFile.size / 1024).toFixed(1)} KB)</span>
              </div>
              <button
                type="button"
                onClick={() => setDetectorFile(null)}
                className="text-xs text-rose-600 font-medium hover:underline"
              >
                Remove
              </button>
            </div>
          ) : (
            <label className="cursor-pointer space-y-2 block">
              <div className="w-10 h-10 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div className="text-xs text-slate-600">
                <span className="font-semibold text-amber-600">Import detector PDF</span> (e.g. ZeroGPT export)
              </div>
              <p className="text-[11px] text-slate-500 max-w-lg mx-auto">
                Extracts yellow highlight regions, matches them against manuscript paragraphs, and displays comparative statistics without claiming detector replication.
              </p>
              <input
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => e.target.files && setDetectorFile(e.target.files[0])}
              />
            </label>
          )}
        </div>
      </div>

      {/* Step 3: Analysis & Writing Assistant Mode Selection */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4 shadow-xs">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Step 3: Natural Academic Voice</span>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            { id: 'proofreading', title: 'Proofreading and clarity', desc: 'Targeted clarity and proofreading suggestions. Preserve clear prose and technical content.' },
            { id: 'academic_revision', title: 'Natural academic revision', desc: 'Direct academic language with proportionate claims and natural academic voice.' },
            { id: 'evidence_review', title: 'Research and evidence-grounded review', desc: 'Use supplied research evidence; identify missing support before proposing revisions.' },
          ].map((mode) => (
            <div
              key={mode.id}
              onClick={() => setEditingMode(mode.id)}
              className={`p-3.5 rounded-xl border cursor-pointer transition flex flex-col justify-between ${
                editingMode === mode.id
                  ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div>
                <div className="text-xs font-bold text-slate-900">{mode.title}</div>
                <p className="text-[11px] text-slate-500 mt-1.5 leading-relaxed">{mode.desc}</p>
              </div>
              {editingMode === mode.id && (
                <div className="mt-2 text-[10px] font-semibold text-indigo-700 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-indigo-600" />
                  <span>Selected</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <label className="block text-sm font-medium">Scientific review profile
        <select aria-label="Scientific review profile" value={profile} onChange={event => setProfile(event.target.value)} className="block mt-2 border rounded-lg p-2 bg-white">
          <option value="general">General academic review</option><option value="quantlens_xai">QuantLens-XAI scientific review</option>
        </select>
      </label>
      {uploadedId && errorMsg && <p className="text-sm text-slate-600">Your manuscript was saved. Retry continues with that document, or open it from the dashboard.</p>}
      {/* Action Button & Progress */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-200">
        <div className="text-xs text-slate-500">
          Strict fact validation enabled: measurements, metrics, and citations will be protected.
        </div>

        <button
          onClick={handleStartAnalysis}
          disabled={!docFile || isUploading}
          className={`flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white shadow-sm transition ${
            !docFile || isUploading
              ? 'bg-slate-300 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-700'
          }`}
        >
          {isUploading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>{uploadProgress || 'Processing...'}</span>
            </>
          ) : (
            <>
              <span>Run Diagnostic Analysis</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
};
