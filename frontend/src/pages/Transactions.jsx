import React, { useState, useEffect, useMemo } from 'react';
import api from '../api/axios';
import { 
    Search, Edit2, TrendingUp, TrendingDown, RotateCcw, 
    ChevronLeft, ChevronRight, X, Check, Save, Wand2 
} from 'lucide-react';
import debounce from 'lodash.debounce';

// ✅ Imports
import { getAmountColor, formatCurrency } from '../utils/formatters';
import SortableHeader from '../components/ui/SortableHeader';
import DateFilter from '../components/ui/DateFilter';
import FilterButton from '../components/ui/FilterButton';

const Transactions = () => {
    // --- STATE ---
    const [transactions, setTransactions] = useState([]);
    const [categories, setCategories] = useState([]); 
    const [loading, setLoading] = useState(true);
    
    // Pagination & Filters
    const [page, setPage] = useState(1);
    const [limit] = useState(15);
    const [totalPages, setTotalPages] = useState(0);
    const [totalRecords, setTotalRecords] = useState(0);
    const [filters, setFilters] = useState({ search: '', startDate: '', endDate: '', type: 'ALL' });
    const [sortConfig, setSortConfig] = useState({ key: 'txn_date', direction: 'desc' });

    // Edit Modal
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [editingTxn, setEditingTxn] = useState(null);
    const [applyMerchantToSimilar, setApplyMerchantToSimilar] = useState(false);
    const [applyCategoryToSimilar, setApplyCategoryToSimilar] = useState(false);
    const [isCreatingCategory, setIsCreatingCategory] = useState(false);
    const [newCategoryName, setNewCategoryName] = useState("");

    const [showRuleModal, setShowRuleModal] = useState(false);
    const [ruleData, setRuleData] = useState({ pattern: '', new_name: '', category_id: '' });

    const [previewStep, setPreviewStep] = useState('INPUT'); // 'INPUT' or 'PREVIEW'
    const [previewResults, setPreviewResults] = useState([]);
    const [excludedIds, setExcludedIds] = useState(new Set());

    // --- EFFECTS ---
    useEffect(() => {
        fetchTransactions();
        fetchCategories();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, filters, sortConfig]);

    // --- API CALLS ---
    const fetchCategories = async () => {
        try {
            const res = await api.get('/categories');
            setCategories(res.data || []);
        } catch (error) { console.error("Failed to fetch categories"); }
    };

    const fetchTransactions = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            params.append('page', page);
            params.append('limit', limit);
            params.append('sort_by', sortConfig.key);
            params.append('sort_order', sortConfig.direction);
            if (filters.search) params.append('search', filters.search);
            if (filters.startDate) params.append('start_date', filters.startDate);
            if (filters.endDate) params.append('end_date', filters.endDate);
            if (filters.type !== 'ALL') params.append('payment_type', filters.type);
            
            const res = await api.get('/transactions', { params });
            if (res.data && Array.isArray(res.data.data)) {
                setTransactions(res.data.data);
                setTotalPages(res.data.total_pages);
                setTotalRecords(res.data.total);
            } else { setTransactions([]); }
        } catch (error) { setTransactions([]); } finally { setLoading(false); }
    };

    // --- HANDLERS (Create & Edit) ---
    const handleCreateCategory = async () => {
        if (!newCategoryName.trim()) return;
        try {
            const res = await api.post('/categories', { name: newCategoryName });
            setCategories(prev => [...prev, res.data]);
            setEditingTxn({ ...editingTxn, category_id: res.data.id });
            setIsCreatingCategory(false);
            setNewCategoryName("");
        } catch (error) { alert("Failed to create category."); }
    };

    const openEditModal = (txn) => {
        setEditingTxn({
            ...txn,
            merchant_name: txn.merchant_name || '',
            amount: txn.amount || 0,
            txn_date: txn.txn_date || '',
            payment_mode: txn.payment_mode || 'UPI',
            category_id: txn.category_id || ''
        });
        setApplyMerchantToSimilar(false);
        setApplyCategoryToSimilar(false);
        setIsCreatingCategory(false);
        setIsEditModalOpen(true);
    };

    const saveEdit = async () => {
        if (!editingTxn) return;
        try {
            const payload = {
                ...editingTxn,
                amount: parseFloat(editingTxn.amount),
                category_id: editingTxn.category_id ? parseInt(editingTxn.category_id) : null,
                apply_merchant_to_similar: applyMerchantToSimilar,
                apply_category_to_similar: applyCategoryToSimilar
            };
            await api.put(`/transactions/${editingTxn.id}`, payload);
            fetchTransactions();
            setIsEditModalOpen(false);
        } catch (error) { alert("Failed to save changes."); }
    };

    const handleOpenRule = (txn) => {
        setRuleData({
            pattern: txn.merchant_name, // Default pattern is current name
            new_name: '',
            category_id: ''
        });
        setShowRuleModal(true);
    };
    
    const handleCreateRule = async () => {
        try {
            await api.post('/rules/', {
                pattern: ruleData.pattern,
                new_merchant_name: ruleData.new_name,
                category_id: ruleData.category_id,
                match_type: "CONTAINS"
            });
            setShowRuleModal(false);
            alert("Rule created & applied to history!");
            fetchTransactions(); // Refresh list to see cleaned names
        } catch (e) {
            alert("Failed to create rule");
        }
    };

    const handlePreviewRule = async () => {
        try {
            setLoading(true);
            const res = await api.post('/rules/preview', {
                pattern: ruleData.pattern,
                new_merchant_name: ruleData.new_name, // Not used for search, but required by schema
                category_id: ruleData.category_id || 0, // Dummy
                match_type: "CONTAINS"
            });
            setPreviewResults(res.data);
            setExcludedIds(new Set()); // Reset exclusions
            setPreviewStep('PREVIEW');
        } catch (e) {
            alert("Failed to preview matches");
        } finally {
            setLoading(false);
        }
    };
    
    // 2. Toggle Selection
    const toggleExclusion = (id) => {
        const next = new Set(excludedIds);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        setExcludedIds(next);
    };

    const handleConfirmRule = async () => {
        try {
            await api.post('/rules/', {
                pattern: ruleData.pattern,
                new_merchant_name: ruleData.new_name,
                category_id: ruleData.category_id,
                match_type: "CONTAINS",
                excluded_ids: Array.from(excludedIds) // ✅ Send unchecked IDs
            });
            setShowRuleModal(false);
            setPreviewStep('INPUT'); // Reset
            fetchTransactions(); // Refresh UI
        } catch (e) {
            alert("Failed to save rule");
        }
    };

    // --- FILTERS & UTILS ---
    const handleSearchChange = useMemo(() => debounce((val) => { setFilters(prev => ({ ...prev, search: val })); setPage(1); }, 500), []);
    const toggleSort = (key) => { setSortConfig(current => ({ key, direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc' })); setPage(1); };
    const clearAllFilters = () => { setFilters({ search: '', startDate: '', endDate: '', type: 'ALL' }); setSortConfig({ key: 'txn_date', direction: 'desc' }); setPage(1); document.getElementById('search-input').value = ""; };
    const handlePageChange = (newPage) => { if (newPage >= 1 && newPage <= totalPages) setPage(newPage); };

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] bg-[#0b0b0b] rounded-2xl border border-white/5 text-white font-sans overflow-hidden relative">
            
            {/* --- TOP BAR --- */}
            <div className="p-6 border-b border-white/5 space-y-4 shrink-0 bg-[#0b0b0b]">
                <div className="flex flex-col md:flex-row justify-between items-end gap-4">
                    <div className="flex flex-wrap gap-4 items-end w-full md:w-auto">
                        {/* Search Input */}
                        <div className="relative w-64 group">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-teal-400 transition-colors" size={16} />
                            <input id="search-input" type="text" placeholder="Search merchant..." onChange={(e) => handleSearchChange(e.target.value)} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg py-2 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-teal-500/50 transition-all" />
                        </div>
                        {/* Date Filters (Reusable Component) */}
                        <DateFilter label="From" value={filters.startDate} onChange={(val) => setFilters(prev => ({...prev, startDate: val}))} />
                        <DateFilter label="To" value={filters.endDate} onChange={(val) => setFilters(prev => ({...prev, endDate: val}))} />
                    </div>
                    
                    {/* Filter Buttons (Reusable Component) */}
                    <div className="flex items-center gap-3">
                        <div className="flex bg-[#1e1e1e] rounded-lg p-1 border border-white/10">
                            <FilterButton active={filters.type === 'ALL'} onClick={() => { setFilters({...filters, type: 'ALL'}); setPage(1); }} label="ALL" />
                            <FilterButton active={filters.type === 'DEBIT'} onClick={() => { setFilters({...filters, type: 'DEBIT'}); setPage(1); }} label="DEBIT" icon={TrendingDown} colorClass="text-red-400" bgClass="bg-red-500/20 border-red-500/30"/>
                            <FilterButton active={filters.type === 'CREDIT'} onClick={() => { setFilters({...filters, type: 'CREDIT'}); setPage(1); }} label="CREDIT" icon={TrendingUp} colorClass="text-emerald-400" bgClass="bg-emerald-500/20 border-emerald-500/30"/>
                        </div>
                        <button onClick={clearAllFilters} className="p-2 text-slate-500 hover:text-white hover:bg-white/10 rounded-lg transition-colors" title="Clear All Filters"><RotateCcw size={18} /></button>
                    </div>
                </div>
            </div>

            {/* --- TABLE AREA --- */}
            <div className="flex-1 overflow-hidden relative">
                <div className="absolute inset-0 overflow-y-auto custom-scrollbar">
                    <table className="w-full text-left border-collapse">
                        <thead className="sticky top-0 z-10 bg-[#0b0b0b] shadow-[0_1px_0_rgba(255,255,255,0.1)]">
                            <tr>
                                {/* Sortable Headers (Reusable Component) */}
                                <SortableHeader label="Date" active={sortConfig.key === 'txn_date'} direction={sortConfig.direction} onClick={() => toggleSort('txn_date')} />
                                <th className="p-4 text-xs font-bold uppercase tracking-widest text-slate-500">Merchant</th>
                                <th className="p-4 text-xs font-bold uppercase tracking-widest text-slate-500">Mode</th>
                                <th className="p-4 text-xs font-bold uppercase tracking-widest text-slate-500">Category</th>
                                <SortableHeader label="Amount" align="right" active={sortConfig.key === 'amount'} direction={sortConfig.direction} onClick={() => toggleSort('amount')} />
                                <th className="p-4 w-20"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {loading ? ( <tr><td colSpan="6" className="p-20 text-center text-slate-500 animate-pulse">Loading...</td></tr> ) : transactions.length === 0 ? ( <tr><td colSpan="6" className="p-20 text-center text-slate-500">No transactions found</td></tr> ) : (
                                transactions.map((txn) => (
                                    <tr key={txn.id} className="group hover:bg-white/[0.02] transition-colors border-b border-white/5 last:border-0">
                                        <td className="p-4 text-slate-400 font-mono text-xs">{txn.txn_date}</td>
                                        <td className="p-4 flex items-center gap-2">
                                            <span>{txn.merchant_name}</span>
                                            <button 
                                                onClick={(e) => { e.stopPropagation(); handleOpenRule(txn); }}
                                                className="text-slate-600 hover:text-blue-400 transition-colors"
                                                title="Create cleanup rule"
                                            >
                                                <Wand2 size={14} />
                                            </button>
                                        </td>
                                        <td className="p-4"><span className="text-[10px] font-bold bg-[#1e1e1e] border border-white/10 px-2 py-1 rounded text-slate-400 uppercase">{txn.payment_mode || 'CASH'}</span></td>
                                        <td className="p-4"><span className="px-2.5 py-1 rounded-full text-[10px] font-bold border tracking-wide" style={{ borderColor: `${txn.category_color}30`, backgroundColor: `${txn.category_color}10`, color: txn.category_color }}>{txn.category_name}</span></td>
                                        <td className={`p-4 text-right font-mono text-sm font-bold ${getAmountColor(txn.payment_type)}`}>₹{formatCurrency(txn.amount)}</td>
                                        <td className="p-4 text-right"><button onClick={() => openEditModal(txn)} className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-all"><Edit2 size={14} /></button></td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
            
            {/* --- FOOTER --- */}
            <div className="p-4 border-t border-white/5 bg-[#0b0b0b] flex justify-between items-center shrink-0 z-20">
                <span className="text-xs text-slate-500">Total: <span className="text-white font-bold">{totalRecords}</span></span>
                <div className="flex items-center gap-2">
                    <button onClick={() => handlePageChange(page - 1)} disabled={page === 1} className="p-2 rounded bg-[#1e1e1e] border border-white/10 text-slate-400 hover:text-white disabled:opacity-50 transition-all"><ChevronLeft size={16} /></button>
                    <span className="text-xs font-mono text-slate-400 bg-[#1e1e1e] px-3 py-2 rounded border border-white/10">Page {page} of {totalPages || 1}</span>
                    <button onClick={() => handlePageChange(page + 1)} disabled={page >= totalPages} className="p-2 rounded bg-[#1e1e1e] border border-white/10 text-slate-400 hover:text-white disabled:opacity-50 transition-all"><ChevronRight size={16} /></button>
                </div>
            </div>

            {/* --- EDIT MODAL (Content condensed for brevity, logic remains same) --- */}
            {isEditModalOpen && editingTxn && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div className="bg-[#111] w-full max-w-lg rounded-2xl border border-white/10 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
                        <div className="p-5 border-b border-white/10 flex justify-between items-center bg-[#161616]">
                            <h3 className="text-lg font-bold text-white flex items-center gap-2"><Edit2 size={18} className="text-teal-400"/> Edit Transaction</h3>
                            <button onClick={() => setIsEditModalOpen(false)} className="text-slate-400 hover:text-white"><X size={20}/></button>
                        </div>
                        <div className="p-6 space-y-5 overflow-y-auto">
                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-500 uppercase">Merchant</label>
                                <input type="text" value={editingTxn.merchant_name} onChange={(e) => setEditingTxn({...editingTxn, merchant_name: e.target.value})} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white focus:border-teal-500/50 outline-none"/>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5"><label className="text-xs font-bold text-slate-500 uppercase">Amount (₹)</label><input type="number" value={editingTxn.amount} onChange={(e) => setEditingTxn({...editingTxn, amount: e.target.value})} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white font-mono focus:border-teal-500/50 outline-none"/></div>
                                <div className="space-y-1.5"><label className="text-xs font-bold text-slate-500 uppercase">Date</label><input type="date" value={editingTxn.txn_date} onChange={(e) => setEditingTxn({...editingTxn, txn_date: e.target.value})} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white focus:border-teal-500/50 outline-none"/></div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-bold text-slate-500 uppercase flex justify-between">
                                        Category <button onClick={() => setIsCreatingCategory(!isCreatingCategory)} className="text-[10px] text-teal-400 hover:underline">{isCreatingCategory ? 'Select Existing' : '+ Create New'}</button>
                                    </label>
                                    {isCreatingCategory ? (
                                        <div className="flex gap-2">
                                            <input type="text" placeholder="New Category Name" value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} className="w-full bg-[#1e1e1e] border border-teal-500/50 rounded-lg p-3 text-sm text-white focus:outline-none"/>
                                            <button onClick={handleCreateCategory} className="bg-teal-500 hover:bg-teal-400 text-black p-3 rounded-lg"><Check size={16} /></button>
                                        </div>
                                    ) : (
                                        <select value={editingTxn.category_id || ""} onChange={(e) => setEditingTxn({...editingTxn, category_id: e.target.value})} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white focus:border-teal-500/50 outline-none">
                                            <option value="">Uncategorized</option>
                                            {categories.map(cat => <option key={cat.id} value={cat.id}>{cat.name}</option>)}
                                        </select>
                                    )}
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-bold text-slate-500 uppercase">Mode</label>
                                    <select value={editingTxn.payment_mode} onChange={(e) => setEditingTxn({...editingTxn, payment_mode: e.target.value})} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white focus:border-teal-500/50 outline-none">
                                        <option value="UPI">UPI</option><option value="CARD">CARD</option><option value="CASH">CASH</option><option value="NETBANKING">NETBANKING</option>
                                    </select>
                                </div>
                            </div>
                            <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-3">
                                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Bulk Actions</p>
                                <div className="flex items-center gap-3"><input type="checkbox" id="applyMerchant" checked={applyMerchantToSimilar} onChange={(e) => setApplyMerchantToSimilar(e.target.checked)} className="w-4 h-4 rounded bg-slate-800 border-slate-600 text-teal-500"/><label htmlFor="applyMerchant" className="text-sm text-slate-300">Update <b>Merchant Name</b> for all similar</label></div>
                                <div className="flex items-center gap-3"><input type="checkbox" id="applyCategory" checked={applyCategoryToSimilar} onChange={(e) => setApplyCategoryToSimilar(e.target.checked)} className="w-4 h-4 rounded bg-slate-800 border-slate-600 text-teal-500"/><label htmlFor="applyCategory" className="text-sm text-slate-300">Update <b>Category</b> for all similar</label></div>
                            </div>
                        </div>
                        <div className="p-5 border-t border-white/10 flex justify-end gap-3 bg-[#161616]">
                            <button onClick={() => setIsEditModalOpen(false)} className="px-5 py-2 rounded-lg text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5">Cancel</button>
                            <button onClick={saveEdit} className="px-6 py-2 rounded-lg text-sm font-bold bg-teal-500 text-black hover:bg-teal-400 flex items-center gap-2"><Save size={16} /> Save Changes</button>
                        </div>
                    </div>
                </div>
            )}
            {showRuleModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div 
                        className="bg-[#111] border border-white/10 p-6 rounded-xl w-full max-w-lg max-h-[80vh] flex flex-col box-shadow-xl"
                        style={{ boxShadow: '0 4px 60px -15px rgba(45, 212, 191, 0.2)' }}
                    >
                        <h3 className="text-xl text-white font-bold mb-6 flex items-center gap-3 border-b border-white/5 pb-4">
                            {/* 🎨 THEME UPDATE: Exact RGB Color */}
                            <Wand2 style={{ color: 'rgb(45, 212, 191)' }} size={24} /> 
                            {previewStep === 'INPUT' ? "Create Automation Rule" : "Verify Matches"}
                        </h3>
                        
                        {previewStep === 'INPUT' ? (
                            // --- STEP 1: INPUT FORM ---
                            <div className="space-y-5">
                                <div>
                                    <label 
                                        className="text-xs font-semibold uppercase tracking-wider mb-1 block"
                                        style={{ color: 'rgb(45, 212, 191)' }}
                                    >
                                        If Merchant Name Contains
                                    </label>
                                    <input 
                                        className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:outline-none transition-colors"
                                        style={{ borderColor: 'rgba(255,255,255,0.1)' }}
                                        onFocus={(e) => e.target.style.borderColor = 'rgb(45, 212, 191)'}
                                        onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
                                        value={ruleData.pattern}
                                        placeholder="e.g. Swiggy"
                                        autoFocus
                                        onChange={e => setRuleData({...ruleData, pattern: e.target.value})}
                                    />
                                </div>
                                <div>
                                    <label 
                                        className="text-xs font-semibold uppercase tracking-wider mb-1 block"
                                        style={{ color: 'rgb(45, 212, 191)' }}
                                    >
                                        Rename Merchant To
                                    </label>
                                    <input 
                                        className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:outline-none transition-colors"
                                        style={{ borderColor: 'rgba(255,255,255,0.1)' }}
                                        onFocus={(e) => e.target.style.borderColor = 'rgb(45, 212, 191)'}
                                        onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
                                        placeholder="e.g. Swiggy"
                                        value={ruleData.new_name}
                                        onChange={e => setRuleData({...ruleData, new_name: e.target.value})}
                                    />
                                </div>
                                <div>
                                    <label 
                                        className="text-xs font-semibold uppercase tracking-wider mb-1 block"
                                        style={{ color: 'rgb(45, 212, 191)' }}
                                    >
                                        Auto-Categorize As
                                    </label>
                                    <select 
                                        className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:outline-none"
                                        style={{ borderColor: 'rgba(255,255,255,0.1)' }}
                                        onFocus={(e) => e.target.style.borderColor = 'rgb(45, 212, 191)'}
                                        onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
                                        value={ruleData.category_id}
                                        onChange={e => setRuleData({...ruleData, category_id: e.target.value})}
                                    >
                                        <option value="">Select Category...</option>
                                        {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                    </select>
                                </div>

                                <div className="flex gap-3 mt-6">
                                    <button 
                                        onClick={() => { setShowRuleModal(false); setPreviewStep('INPUT'); }}
                                        className="flex-1 px-4 py-3 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 transition-all font-medium"
                                    >
                                        Cancel
                                    </button>
                                    <button 
                                        onClick={handlePreviewRule}
                                        className="flex-1 text-[#111] font-bold py-3 rounded-lg transition-all shadow-lg"
                                        style={{ 
                                            backgroundColor: 'rgb(45, 212, 191)',
                                            boxShadow: '0 4px 20px -5px rgba(45, 212, 191, 0.5)'
                                        }}
                                    >
                                        Preview Matches
                                    </button>
                                </div>
                            </div>
                        ) : (
                            // --- STEP 2: VERIFICATION LIST ---
                            <div className="flex flex-col h-full overflow-hidden">
                                <div 
                                    className="rounded-lg p-3 mb-4 text-sm"
                                    style={{ 
                                        backgroundColor: 'rgba(45, 212, 191, 0.1)', 
                                        color: 'rgb(45, 212, 191)',
                                        border: '1px solid rgba(45, 212, 191, 0.2)'
                                    }}
                                >
                                    Found <strong>{previewResults.length}</strong> historical matches. 
                                    Uncheck any you want to ignore.
                                </div>
                                
                                <div className="flex-1 overflow-y-auto border border-white/10 rounded-lg bg-[#1a1a1a] p-2 space-y-2 custom-scrollbar">
                                    {previewResults.map(txn => (
                                        <div key={txn.transaction_id} className="flex items-center gap-3 p-3 hover:bg-white/5 rounded-lg transition-colors border border-transparent hover:border-white/5">
                                            <input 
                                                type="checkbox"
                                                checked={!excludedIds.has(txn.transaction_id)}
                                                onChange={() => toggleExclusion(txn.transaction_id)}
                                                className="w-5 h-5 rounded cursor-pointer accent-[rgb(45,212,191)]"
                                                style={{ accentColor: 'rgb(45, 212, 191)' }}
                                            />
                                            <div className="flex-1">
                                                <div className="text-white font-medium">{txn.current_name}</div>
                                                <div className="text-xs text-slate-500 mt-0.5">
                                                    {txn.date} • {formatCurrency(txn.amount)}
                                                </div>
                                            </div>
                                            <div 
                                                className="text-sm font-bold flex items-center gap-1"
                                                style={{ color: 'rgb(45, 212, 191)' }}
                                            >
                                                <Check size={14} />
                                                {ruleData.new_name}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="mt-6 flex gap-3">
                                    <button 
                                        onClick={() => setPreviewStep('INPUT')}
                                        className="flex-1 px-4 py-3 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 transition-all font-medium"
                                    >
                                        Back
                                    </button>
                                    <button 
                                        onClick={handleConfirmRule}
                                        className="flex-1 text-[#111] font-bold py-3 rounded-lg transition-all shadow-lg"
                                        style={{ 
                                            backgroundColor: 'rgb(45, 212, 191)',
                                            boxShadow: '0 4px 20px -5px rgba(45, 212, 191, 0.5)'
                                        }}
                                    >
                                        Confirm & Apply
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default Transactions;