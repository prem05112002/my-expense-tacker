import React, { useEffect, useState } from 'react';
import api from '../api/axios';
import { 
    AlertTriangle, Check, Calendar, CreditCard, 
    ArrowUpRight, ArrowDownLeft, Split // ✅ Added Split icon for "Keep Both"
} from 'lucide-react';

const Duplicates = () => {
    const [groups, setGroups] = useState([]);
    const [loading, setLoading] = useState(true);

    // 1. Fetch Duplicates
    useEffect(() => {
        fetchDuplicates();
    }, []);

    const fetchDuplicates = async () => {
        try {
            const res = await api.get('/transactions/duplicates');
            setGroups(res.data);
        } catch (error) {
            console.error("Failed to fetch duplicates", error);
        } finally {
            setLoading(false);
        }
    };

    // 2. Handle Resolution
    const handleResolve = async (groupId, keepId, deleteId) => {
        const group = groups.find(g => g.group_id === groupId);
        if (!group) return;

        const [t1, t2] = group.transactions;

        try {
            // Optimistic UI: Remove immediately
            setGroups(current => current.filter(g => g.group_id !== groupId));

            await api.post('/transactions/duplicates/resolve', {
                keep_id: keepId,
                delete_id: deleteId,
                txn1_id: t1.id, 
                txn2_id: t2.id
            });
        } catch (error) {
            console.error("Error resolving duplicate", error);
            fetchDuplicates(); 
        }
    };

    if (loading) return <div className="text-white p-10 animate-pulse">Scanning for duplicates...</div>;

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] bg-[#0b0b0b] rounded-2xl border border-white/5 text-white font-sans overflow-hidden">
            
            {/* Header */}
            <div className="p-6 border-b border-white/5 bg-[#0b0b0b] shrink-0">
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    <AlertTriangle className="text-amber-400" />
                    Potential Duplicates
                </h1>
                <p className="text-slate-400 text-sm mt-1">
                    Found {groups.length} pairs of transactions that look identical. Select which one to keep.
                </p>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
                {groups.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center opacity-50">
                        <Check size={64} className="text-emerald-500 mb-4" />
                        <h3 className="text-2xl font-bold text-white">All Clean!</h3>
                        <p className="text-slate-400 mt-2">No potential duplicates found.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                        {groups.map(group => (
                            <DuplicateCard 
                                key={group.group_id} 
                                group={group} 
                                onResolve={handleResolve} 
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

const DuplicateCard = ({ group, onResolve }) => {
    const [t1, t2] = group.transactions;

    return (
        <div className="bg-[#161616] border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col">
            
            {/* Warning & Score */}
            <div className="flex justify-between items-start mb-6 shrink-0">
                <div className="bg-amber-500/10 text-amber-400 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border border-amber-500/20">
                    {group.warning_message}
                </div>
                <div className="text-right">
                     <span className="text-xs text-slate-500 font-mono">Similarity: </span>
                     <span className="text-emerald-400 font-bold">{group.confidence_score}%</span>
                </div>
            </div>

            {/* Comparison */}
            <div className="flex gap-4 items-stretch relative flex-1 min-h-0">
                <TransactionSide txn={t1} />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                    <div className="bg-[#0a0a0a] border border-slate-700 text-slate-500 text-[10px] font-black p-2 rounded-full shadow-xl">
                        VS
                    </div>
                </div>
                <TransactionSide txn={t2} />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 mt-6 pt-6 border-t border-white/5 shrink-0">
                {/* KEEP LEFT */}
                <button 
                    onClick={() => onResolve(group.group_id, t1.id, t2.id)}
                    className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 py-2.5 rounded-lg text-sm font-bold transition-all"
                >
                    Keep Left
                </button>
                
                {/* KEEP BOTH (Formerly Ignore) */}
                <button 
                    onClick={() => onResolve(group.group_id, null, null)}
                    className="px-6 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-sm font-bold transition-colors flex items-center gap-2"
                >
                    <Split size={14} />
                    Keep Both
                </button>

                {/* KEEP RIGHT */}
                <button 
                    onClick={() => onResolve(group.group_id, t2.id, t1.id)}
                    className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 py-2.5 rounded-lg text-sm font-bold transition-all"
                >
                    Keep Right
                </button>
            </div>
        </div>
    );
};

const TransactionSide = ({ txn }) => (
    <div className="flex-1 bg-[#1e1e1e] rounded-lg p-4 space-y-3 min-w-0 border border-white/5">
        
        {/* Merchant */}
        <div>
            <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider mb-1">Merchant</div>
            <div className="text-white font-semibold text-sm leading-tight truncate" title={txn.merchant_name}>
                {txn.merchant_name}
            </div>
            {txn.upi_transaction_id && (
                <div className="text-[10px] text-teal-500 font-mono mt-1 bg-teal-500/10 inline-block px-1.5 py-0.5 rounded border border-teal-500/20">
                    UPI: {txn.upi_transaction_id}
                </div>
            )}
        </div>

        {/* Amount */}
        <div className="flex justify-between items-center border-t border-white/5 pt-2">
            <span className="text-slate-500 text-xs">Amount</span>
            <span className="text-slate-200 font-mono font-bold">₹{Number(txn.amount).toLocaleString()}</span>
        </div>

        {/* Date */}
        <div className="flex justify-between items-center border-t border-white/5 pt-2">
            <span className="text-slate-500 text-xs flex items-center gap-1"><Calendar size={10} /> Date</span>
            <span className="text-slate-300 text-xs font-mono">{txn.txn_date}</span>
        </div>

        {/* Mode */}
        <div className="flex justify-between items-center border-t border-white/5 pt-2">
            <span className="text-slate-500 text-xs flex items-center gap-1"><CreditCard size={10} /> Mode</span>
            <span className="text-slate-300 text-[10px] bg-slate-800 px-2 py-0.5 rounded border border-white/10">{txn.payment_mode || 'UNK'}</span>
        </div>

        {/* Payment Type */}
        <div className="flex justify-between items-center border-t border-white/5 pt-2">
            <span className="text-slate-500 text-xs flex items-center gap-1">
                {txn.payment_type === 'CREDIT' ? <ArrowDownLeft size={10} /> : <ArrowUpRight size={10} />} Type
            </span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${txn.payment_type === 'CREDIT' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>
                {txn.payment_type}
            </span>
        </div>
    </div>
);

export default Duplicates;