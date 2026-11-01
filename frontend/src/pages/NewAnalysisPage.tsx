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
  const [entitlements, setEntitlements] = useState<any[]>([]);
  const [overageInfo, setOverageInfo] = useState<any | null>(null);

  React.useEffect(() => {
    api.getMyEntitlements()
      .then((items) => setEntitlements(items))
      .catch(() => {});
  }, []);

  const handlePurchaseSlot = async (tier: string) => {
    try {
      setIsUploading(true);
      setUploadProgress(`Creating Razorpay order for ${tier.toUpperCase()} plan...`);
      const order = await api.createPaymentOrder(tier, editingMode);
      setUploadProgress('Fulfilling transaction in Razorpay test mode...');
      const verifyRes = await api.verifyPayment(
        order.order_id,
        `pay_mock_${Date.now()}`,
        `mock_sig_${order.order_id}_pay_mock_${Date.now()}`
      );
      setUploadProgress('Slot issued! Refreshing entitlements...');
      const updated = await api.getMyEntitlements();
      setEntitlements(updated);
      setIsUploading(false);
      setUploadProgress('');
      alert(`Success! Purchased 1 ${tier.toUpperCase()} analysis slot.`);
    } catch (err: any) {
      setIsUploading(false);
      setErrorMsg(err.message || 'Payment initiation failed.');
    }
  };

  const handleUpgradeOverage = async () => {
    if (!overageInfo) return;
    try {
      setIsUploading(true);
      setUploadProgress(`Initiating upgrade to ${overageInfo.recommended_tier}...`);
      const upgOrder = await api.createUpgradeOrder(overageInfo.entitlement_id, overageInfo.recommended_tier);
      setUploadProgress(`Fulfilling upgrade for ₹${upgOrder.upgrade_amount_rupees}...`);
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
          if (uploadRes.overLimit) {
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
          // Fallback to direct upload if test mode / no entitlement required
          setUploadProgress('Uploading and reading DOCX structure…');
          const uploadedDoc = await api.uploadDocument(docFile);
          docId = uploadedDoc.id;
          setUploadedId(docId);
          setActiveDocument(uploadedDoc);
        }
      }
      if (detectorFile) {
        setUploadProgress('Extracting detector highlights and matching passages…');
        await api.uploadDetectorPdf(uploadedDoc.id, detectorFile);
        setDetectorFile(null);
      }
      for (const sourceFile of sourceFiles) {
        setUploadProgress(`Importing reference: ${sourceFile.name}`);
        await api.uploadSource(uploadedDoc.id, sourceFile, isExternalReport);
        setSourceFiles(files => files.filter(file => file !== sourceFile));
      }
      setUploadProgress('Starting background analysis…');
      await api.startAnalysis(uploadedDoc.id, editingMode, profile);
      const refreshed = await api.getDocument(uploadedDoc.id);
      setActiveDocument(refreshed);
      triggerRefresh();
      setIsUploading(false);
      setActiveTab('editor');

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

      {overageInfo && (
        <div className="p-5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 space-y-3 shadow-xs">
          <div className="flex items-center gap-2 font-semibold text-sm text-amber-950">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
            <span>Manuscript Capacity Overage Detected</span>
          </div>
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
                  onChange={(e) => e.target.files && setDocFile(e.target.files[0])}
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
            { id: 'light_copyediting', title: 'Minimal proofreading', desc: 'Targeted clarity and proofreading suggestions. Preserve clear prose and technical content.' },
            { id: 'academic_revision', title: 'Natural academic editing', desc: 'Direct academic language with proportionate claims and your existing narrative voice.' },
            { id: 'research_grounded', title: 'Substantive research-grounded revision', desc: 'Use supplied research evidence; identify missing support before proposing new content.' },
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
