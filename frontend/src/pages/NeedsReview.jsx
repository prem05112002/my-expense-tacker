import React, { useEffect, useState } from 'react';
import api from '../api/axios';
import { useToast } from '../contexts/ToastContext';
import {
    Mail, Trash2, CheckCircle, Calendar,
    CreditCard, ArrowRight, AlertCircle, FileText, X
} from 'lucide-react';
import { InboxSkeleton } from '../components/ui/CardSkeleton';
import useFocusTrap from '../hooks/useFocusTrap';

const NeedsReview = () => {
    const toast = useToast();
    const [items, setItems] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState(false);

    // Modal State
    const [showDismissModal, setShowDismissModal] = useState(false);

    const dismissModalRef = useFocusTrap(showDismissModal, () => setShowDismissModal(false));

    // Form State
    const [formData, setFormData] = useState({
        merchant_name: '',
        amount: '',
        txn_date: '',
        payment_mode: 'UPI',
        payment_type: 'DEBIT',
        category_id: ''
    });

    const [categories, setCategories] = useState([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [stagingRes, catRes] = await Promise.all([
                    api.get('/staging'),
                    api.get('/categories')
                ]);
                setItems(stagingRes.data);
                setCategories(catRes.data);
            } catch (error) {
                console.error("Failed to fetch staging items", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const handleSelect = (item) => {
        setSelectedId(item.id);
        const simpleDate = item.received_at ? item.received_at.split('T')[0] : new Date().toISOString().split('T')[0];
        setFormData({
            merchant_name: '', 
            amount: '',
            txn_date: simpleDate,
            payment_mode: 'UPI',
            payment_type: 'DEBIT',
            category_id: ''
        });
    };

    // 1. Open Modal instead of window.confirm
    const requestDismiss = () => {
        if (!selectedId) return;
        setShowDismissModal(true);
    };

    // 2. Actual API Call (Triggered by Modal)
    const confirmDismiss = async () => {
        setProcessing(true);
        try {
            await api.delete(`/staging/${selectedId}`);
            setItems(prev => prev.filter(i => i.id !== selectedId));
            setSelectedId(null);
            setShowDismissModal(false);
            toast.success("Email dismissed successfully");
        } catch (error) {
            console.error("Failed to dismiss item", error);
            toast.error("Error dismissing item");
        } finally {
            setProcessing(false);
        }
    };

    const handleSave = async (e) => {
        e.preventDefault();
        if (!formData.amount || !formData.merchant_name) {
            toast.warning("Please fill in Amount and Merchant Name");
            return;
        }

        setProcessing(true);
        try {
            await api.post('/staging/convert', {
                staging_id: selectedId,
                ...formData,
                amount: parseFloat(formData.amount)
            });
            setItems(prev => prev.filter(i => i.id !== selectedId));
            setSelectedId(null);
            toast.success("Transaction created successfully");
        } catch (error) {
            console.error("Failed to convert item", error);
            toast.error("Error creating transaction");
        } finally {
            setProcessing(false);
        }
    };

    const selectedItem = items.find(i => i.id === selectedId);

    if (loading) return <InboxSkeleton />;

    return (
        <div className="flex h-[calc(100vh-4rem)] bg-[#0b0b0b] rounded-2xl border border-white/5 overflow-hidden relative">
            
            {/* --- CUSTOM CONFIRMATION MODAL --- */}
            {showDismissModal && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                    <div
                        ref={dismissModalRef}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="dismiss-modal-title"
                        className="bg-[#111] border border-white/10 rounded-2xl p-6 max-w-sm w-full shadow-2xl shadow-black"
                    >
                        <div className="flex justify-between items-start mb-4">
                            <div className="p-3 bg-red-500/10 rounded-full">
                                <Trash2 className="text-red-500" size={24} />
                            </div>
                            <button
                                onClick={() => setShowDismissModal(false)}
                                className="text-slate-500 hover:text-white transition-colors"
                                aria-label="Close modal"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        <h3 id="dismiss-modal-title" className="text-white text-lg font-bold mb-2">Delete Email?</h3>
                        <p className="text-slate-400 text-sm mb-6 leading-relaxed">
                            Are you sure you want to dismiss this email? It will be permanently removed from your review list.
                        </p>

                        <div className="flex gap-3">
                            <button 
                                onClick={() => setShowDismissModal(false)}
                                className="flex-1 py-2.5 rounded-lg border border-white/10 text-slate-300 text-sm font-medium hover:bg-white/5 transition-colors"
                            >
                                Cancel
                            </button>
                            <button 
                                onClick={confirmDismiss}
                                disabled={processing}
                                className="flex-1 py-2.5 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-bold transition-colors shadow-lg shadow-red-500/20"
                            >
                                {processing ? "Deleting..." : "Delete Email"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* LEFT PANEL: LIST */}
            <div className="w-1/3 min-w-[300px] border-r border-white/5 flex flex-col bg-[#0b0b0b]">
                <div className="p-4 border-b border-white/5 bg-[#111]">
                    <h2 className="text-white font-bold flex items-center gap-2">
                        <Mail className="text-blue-400" size={18} />
                        Needs Review
                        <span className="bg-blue-500/10 text-blue-400 text-xs px-2 py-0.5 rounded-full border border-blue-500/20">
                            {items.length}
                        </span>
                    </h2>
                </div>
                
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                    {items.length === 0 ? (
                        <div className="text-center p-10 opacity-50">
                            <CheckCircle size={40} className="text-emerald-500 mx-auto mb-3" />
                            <p className="text-slate-400 text-sm">All caught up!</p>
                        </div>
                    ) : (
                        items.map(item => (
                            <div 
                                key={item.id}
                                onClick={() => handleSelect(item)}
                                className={`p-4 border-b border-white/5 cursor-pointer transition-colors hover:bg-white/5 ${selectedId === item.id ? 'bg-blue-500/10 border-l-2 border-l-blue-500' : ''}`}
                            >
                                <div className="flex justify-between mb-1">
                                    <span className="font-semibold text-slate-200 text-sm truncate pr-2">HDFC Bank</span>
                                    <span className="text-[10px] text-slate-500 whitespace-nowrap">
                                        {item.received_at ? new Date(item.received_at).toLocaleDateString() : 'Unknown'}
                                    </span>
                                </div>
                                <div className="text-xs text-slate-400 truncate">{item.email_subject}</div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* RIGHT PANEL: DETAIL VIEW */}
            <div className="flex-1 flex flex-col bg-[#0e0e0e] relative">
                {!selectedItem ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-500 opacity-50">
                        <FileText size={64} className="mb-4 text-slate-700" />
                        <p>Select an email to review</p>
                    </div>
                ) : (
                    <>
                        <div className="p-6 border-b border-white/5 bg-[#111]">
                            <h3 className="text-lg font-bold text-white mb-2">{selectedItem.email_subject}</h3>
                            <div className="flex gap-4 text-xs text-slate-500 font-mono mb-4">
                                <span>FROM: HDFC Bank</span>
                                <span>ID: {selectedItem.email_uid}</span>
                            </div>
                            
                            <div className="bg-[#050505] p-4 rounded border border-white/10 max-h-60 overflow-y-auto">
                                <span className="text-xs text-slate-500 block mb-2 uppercase tracking-wider font-bold">Email Content</span>
                                <div className="text-slate-300 text-sm font-mono whitespace-pre-wrap">
                                    {selectedItem.email_body ? selectedItem.email_body : (
                                        <span className="text-slate-600 italic">[Content not available]</span>
                                    )}
                                </div>
                            </div>
                        </div>

                        <form onSubmit={handleSave} className="flex-1 p-6 overflow-y-auto">
                            <h4 className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-4 flex items-center gap-2">
                                <AlertCircle size={14} className="text-amber-500" />
                                Extract Transaction Details
                            </h4>

                            <div className="grid grid-cols-2 gap-6">
                                <div className="col-span-2">
                                    <label className="block text-slate-500 text-xs mb-1">Merchant Name</label>
                                    <input 
                                        type="text" 
                                        className="w-full bg-[#1e1e1e] border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-teal-500 transition-colors"
                                        value={formData.merchant_name}
                                        onChange={e => setFormData({...formData, merchant_name: e.target.value})}
                                        placeholder="e.g. Swiggy, Uber"
                                    />
                                </div>
                                
                                <div>
                                    <label className="block text-slate-500 text-xs mb-1">Amount (₹)</label>
                                    <input 
                                        type="number" 
                                        className="w-full bg-[#1e1e1e] border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-teal-500 transition-colors font-mono"
                                        value={formData.amount}
                                        onChange={e => setFormData({...formData, amount: e.target.value})}
                                        placeholder="0.00"
                                    />
                                </div>

                                <div>
                                    <label className="block text-slate-500 text-xs mb-1">Date</label>
                                    <div className="relative">
                                        <Calendar size={14} className="absolute left-3 top-3 text-slate-500" />
                                        <input 
                                            type="date" 
                                            className="w-full bg-[#1e1e1e] border border-white/10 rounded pl-9 pr-3 py-2 text-white focus:outline-none focus:border-teal-500 transition-colors"
                                            value={formData.txn_date}
                                            onChange={e => setFormData({...formData, txn_date: e.target.value})}
                                        />
                                    </div>
                                </div>
                                
                                <div>
                                    <label className="block text-slate-500 text-xs mb-1">Category</label>
                                    <select 
                                        className="w-full bg-[#1e1e1e] border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-teal-500 transition-colors"
                                        value={formData.category_id}
                                        onChange={e => setFormData({...formData, category_id: e.target.value})}
                                    >
                                        <option value="">Select Category...</option>
                                        {categories.map(c => (
                                            <option key={c.id} value={c.id}>{c.name}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="flex gap-3 mt-8 pt-6 border-t border-white/5">
                                <button 
                                    type="button" 
                                    onClick={requestDismiss} // Changed to open modal
                                    disabled={processing}
                                    className="px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors flex items-center gap-2 text-sm font-semibold"
                                >
                                    <Trash2 size={16} />
                                    Dismiss
                                </button>
                                <button 
                                    type="submit"
                                    disabled={processing}
                                    className="flex-1 bg-emerald-500 text-black font-bold py-2 rounded-lg hover:bg-emerald-400 transition-colors flex items-center justify-center gap-2 text-sm"
                                >
                                    {processing ? 'Saving...' : 'Create Transaction'}
                                    <ArrowRight size={16} />
                                </button>
                            </div>
                        </form>
                    </>
                )}
            </div>
        </div>
    );
};

export default NeedsReview;