import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User,
  ShieldCheck,
  CreditCard,
  Trash2,
  HelpCircle,
  LogOut,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Mail,
  FileText,
  Lock
} from 'lucide-react';
import { api } from '../services/api';

export const AccountPage: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<any>(null);
  const [entitlements, setEntitlements] = useState<any[]>([]);
  const [purchases, setPurchases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [erasing, setErasing] = useState(false);
  const [erasureMessage, setErasureMessage] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.all([
      api.getMe().catch(() => null),
      api.getMyEntitlements().catch(() => []),
      api.getMyPurchases().catch(() => []),
    ])
      .then(([userData, entData, purchData]) => {
        if (cancelled) return;
        setUser(userData);
        setEntitlements(entData || []);
        setPurchases(purchData || []);
      })
      .catch((err) => {
        console.error('Account load error:', err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleSignOut = async () => {
    try {
      await api.logout();
      window.location.href = '/';
    } catch {
      window.location.href = '/';
    }
  };

  const handleEraseAllData = async () => {
    const confirmation = window.prompt(
      'DPDP Act 2023 - Right to Erasure:\nThis will permanently delete all your uploaded manuscripts, revision history, detector reports, and active sessions.\nType "ERASE" to confirm:'
    );
    if (confirmation !== 'ERASE') return;

    try {
      setErasing(true);
      const res = await api.eraseMyData();
      setErasureMessage(res.message || 'All personal manuscripts and sessions successfully erased.');
      setTimeout(() => {
        window.location.href = '/';
      }, 2000);
    } catch (err: any) {
      alert(err.message || 'Failed to execute data erasure.');
    } finally {
      setErasing(false);
    }
  };

  const unusedEntitlements = entitlements.filter((e) => e.status === 'AVAILABLE');

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="pb-6 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Student Account</h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage your verified institutional identity, unused plan slots, and transaction receipts.
          </p>
        </div>
        <button
          onClick={handleSignOut}
          className="flex items-center gap-1.5 px-4 py-2 border border-slate-200 hover:bg-rose-50 hover:border-rose-200 hover:text-rose-600 rounded-lg text-xs font-semibold text-slate-700 transition self-start sm:self-auto"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>

      {loading ? (
        <div className="py-16 text-center text-sm text-slate-500">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          Loading student profile…
        </div>
      ) : (
        <div className="space-y-8">
          {/* Student Profile Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 md:p-8 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-indigo-900 text-white flex items-center justify-center font-bold text-xl shadow-xs">
                {user?.registration_number?.slice(0, 2) || 'VIT'}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-slate-900">
                    {user?.full_name || 'VIT Student'}
                  </h2>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <ShieldCheck className="w-3 h-3 text-emerald-600" />
                    Verified VIT Identity
                  </span>
                </div>
                <div className="text-xs text-slate-500 flex items-center gap-3">
                  <span className="font-mono text-slate-700 font-medium">
                    {user?.registration_number || 'REG: N/A'}
                  </span>
                  <span>•</span>
                  <span>{user?.email}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3 w-full md:w-auto">
              <div className="px-4 py-3 bg-indigo-50 border border-indigo-100 rounded-xl text-center flex-1 md:flex-initial">
                <div className="text-xl font-bold text-indigo-950">
                  {unusedEntitlements.length}
                </div>
                <div className="text-[10px] uppercase font-semibold text-indigo-700 tracking-wider">
                  Unused Plan Slots
                </div>
              </div>
            </div>
          </div>

          {/* Unused Paid Entitlements */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-slate-900">Active Unused Entitlements</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Pre-paid document review allowances ready to use.
                </p>
              </div>
              <button
                onClick={() => navigate('/documents/new')}
                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
              >
                Use Slot Now
              </button>
            </div>

            {unusedEntitlements.length === 0 ? (
              <p className="text-xs text-slate-400 italic py-2">
                No unused plan slots. Each new document purchase generates an active single-use slot.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                {unusedEntitlements.map((ent) => (
                  <div
                    key={ent.id}
                    className="p-4 rounded-xl border border-indigo-200 bg-indigo-50/20 space-y-2 text-xs"
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-slate-900 uppercase">{ent.plan_tier} Plan</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                        Available
                      </span>
                    </div>
                    <div className="text-slate-600 text-[11px] space-y-0.5">
                      <div>Up to {ent.max_pages} pages ({ent.max_characters?.toLocaleString()} chars)</div>
                      <div>Max {ent.max_file_size_mb} MB</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Payment History & Receipts */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200">
              <h3 className="font-bold text-sm text-slate-900">Payment & Transaction History</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Receipt records for past manuscript purchases via Razorpay UPI.
              </p>
            </div>

            {purchases.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No past transactions found.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-400 uppercase font-semibold text-[10px]">
                    <tr>
                      <th className="px-6 py-3">Order ID</th>
                      <th className="px-6 py-3">Plan Tier</th>
                      <th className="px-6 py-3">Amount</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {purchases.map((p) => (
                      <tr key={p.id} className="hover:bg-slate-50/60">
                        <td className="px-6 py-3.5 font-mono text-[11px]">{p.razorpay_order_id || p.id}</td>
                        <td className="px-6 py-3.5 capitalize font-medium">{p.plan_tier}</td>
                        <td className="px-6 py-3.5 font-bold text-slate-900">₹{p.amount_rupees}</td>
                        <td className="px-6 py-3.5">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                              p.status === 'captured' || p.status === 'verified'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : 'bg-amber-50 text-amber-700'
                            }`}
                          >
                            {p.status}
                          </span>
                        </td>
                        <td className="px-6 py-3.5 text-slate-500">
                          {p.created_at ? new Date(p.created_at).toLocaleDateString() : 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Privacy & DPDP Act 2023 Data Erasure */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div>
              <h3 className="font-bold text-sm text-slate-900">Student Privacy & Data Sovereignty</h3>
              <p className="text-xs text-slate-500 mt-1">
                Under India's Digital Personal Data Protection (DPDP) Act 2023, you have the right to permanent erasure of all your uploaded documents, detector files, and revision records at any time.
              </p>
            </div>

            {erasureMessage && (
              <div role="status" className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800">
                {erasureMessage}
              </div>
            )}

            <div className="pt-2">
              <button
                disabled={erasing}
                onClick={handleEraseAllData}
                className="flex items-center gap-2 px-4 py-2.5 border border-rose-200 hover:bg-rose-50 text-rose-700 rounded-lg text-xs font-semibold transition"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{erasing ? 'Erasing data…' : 'Permanently Erase All My Manuscripts & Data'}</span>
              </button>
            </div>
          </div>

          {/* Support Information */}
          <div className="bg-slate-50 rounded-xl border border-slate-200 p-6 flex items-start gap-3 text-xs text-slate-600">
            <HelpCircle className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-slate-800">Need Assistance with a Manuscript or Payment?</div>
              <p className="mt-1">
                For questions regarding report formats, billing inquiries, or technical support, contact the Writelynx campus desk at{' '}
                <a href="mailto:support@writelynx.in" className="text-indigo-600 underline font-medium">
                  support@writelynx.in
                </a>.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default AccountPage;
