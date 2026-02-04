import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/axios';
import {
    Edit2, TrendingUp, TrendingDown, RotateCcw,
    ChevronLeft, ChevronRight, X, Check, Save, Wand2, Plus
} from 'lucide-react';

// Utilities
import { getAmountColor, formatCurrency } from '../utils/formatters';
import SortableHeader from '../components/ui/SortableHeader';
import DateFilter from '../components/ui/DateFilter';
import FilterButton from '../components/ui/FilterButton';
import SmartSearchInput from '../components/ui/SmartSearchInput';
import SearchSummary from '../components/ui/SearchSummary';
import CategoryMultiselect from '../components/ui/CategoryMultiselect';
import useSmartSearch from '../hooks/useSmartSearch';

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
    const [debitSum, setDebitSum] = useState(0);
    const [creditSum, setCreditSum] = useState(0);
    const [filters, setFilters] = useState({ search: '', startDate: '', endDate: '', type: 'ALL' });
    const [sortConfig, setSortConfig] = useState({ key: 'txn_date', direction: 'desc' });

    // Category Filter
    const [selectedCategoryIds, setSelectedCategoryIds] = useState([]);

    // Smart Search
    const { executeSmartSearch, clearSearch, isLoading: smartSearchLoading, searchType, parsedFilters } = useSmartSearch();
    const [isSmartSearch, setIsSmartSearch] = useState(false);
    const [currentParsedFilters, setCurrentParsedFilters] = useState(null);

    // Edit Modal
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [editingTxn, setEditingTxn] = useState(null);
    const [applyMerchantToSimilar, setApplyMerchantToSimilar] = useState(false);
    const [applyCategoryToSimilar, setApplyCategoryToSimilar] = useState(false);

    // Category Modal
    const [isCatModalOpen, setIsCatModalOpen] = useState(false);
    const [newCatName, setNewCatName] = useState("");

    // Rule Engine
    const [showRuleModal, setShowRuleModal] = useState(false);
    const [ruleData, setRuleData] = useState({ pattern: '', new_name: '', category_id: '' });
    const [previewStep, setPreviewStep] = useState('INPUT');
    const [previewResults, setPreviewResults] = useState([]);
    const [excludedIds, setExcludedIds] = useState(new Set());

    // --- EFFECTS ---
    useEffect(() => {
        fetchCategories();
    }, []);

    useEffect(() => {
        // Don't fetch if we're in smart search mode
        if (!isSmartSearch) {
            fetchTransactions();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, filters, sortConfig, selectedCategoryIds, isSmartSearch]);

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
            if (selectedCategoryIds.length > 0) {
                params.append('category_ids', selectedCategoryIds.join(','));
            }

            const res = await api.get('/transactions', { params });
            if (res.data && Array.isArray(res.data.data)) {
                setTransactions(res.data.data);
                setTotalPages(res.data.total_pages);
                setTotalRecords(res.data.total);
                setDebitSum(res.data.debit_sum || 0);
                setCreditSum(res.data.credit_sum || 0);
            } else { setTransactions([]); }
        } catch (error) { setTransactions([]); } finally { setLoading(false); }
    };

    // --- HANDLERS ---

    // Handle fuzzy search (simple text search)
    const handleFuzzySearch = useCallback((val) => {
        setIsSmartSearch(false);
        setCurrentParsedFilters(null);
        clearSearch();
        setFilters(prev => ({ ...prev, search: val }));
        setPage(1);
    }, [clearSearch]);

    // Handle smart search (AI-powered)
    const handleSmartSearch = useCallback(async (query) => {
        if (!query || query.trim().length < 2) {
            handleFuzzySearch('');
            return;
        }

        setLoading(true);
        setIsSmartSearch(true);

        const result = await executeSmartSearch(query, {
            page: 1,
            limit,
            sort_by: sortConfig.key,
            sort_order: sortConfig.direction
        });

        if (result) {
            setTransactions(result.transactions);
            setTotalPages(result.totalPages);
            setTotalRecords(result.total);
            setDebitSum(result.debitSum);
            setCreditSum(result.creditSum);
            setPage(result.page);
            setCurrentParsedFilters(result.parsedFilters);

            // If it fell back to fuzzy, update the state
            if (result.searchType === 'fuzzy') {
                setIsSmartSearch(false);
            }
        }

        setLoading(false);
    }, [executeSmartSearch, limit, sortConfig, handleFuzzySearch]);

    const toggleSort = (key) => {
        setSortConfig(current => ({ key, direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc' }));
        setPage(1);
    };

    const clearAllFilters = () => {
        setFilters({ search: '', startDate: '', endDate: '', type: 'ALL' });
        setSortConfig({ key: 'txn_date', direction: 'desc' });
        setSelectedCategoryIds([]);
        setIsSmartSearch(false);
        setCurrentParsedFilters(null);
        clearSearch();
        setPage(1);
    };

    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPages) setPage(newPage);
    };

    const handleCategoryFilterChange = (newIds) => {
        setSelectedCategoryIds(newIds);
        setPage(1);
    };

    // Helper to create category (used by Modal)
    const ensureCategoryExists = async (categoryName) => {
        const existing = categories.find(c => c.name.toLowerCase() === categoryName.toLowerCase());
        if (existing) return existing.id;

        try {
            const res = await api.post('/categories/', { name: categoryName, is_income: false });
            const newCategory = res.data;
            setCategories(prev => [...prev, newCategory]);
            return newCategory.id;
        } catch (error) {
            console.error("Failed to create category:", error);
            alert("Failed to create new category.");
            return null;
        }
    };

    // Handle Saving New Category from Custom Modal
    const handleSaveNewCategory = async () => {
        if (!newCatName.trim()) return;
        const newId = await ensureCategoryExists(newCatName);
        if (newId) {
            setEditingTxn(prev => ({
                ...prev,
                category_id: newId,
                category_name: newCatName
            }));
            setIsCatModalOpen(false);
            setNewCatName("");
        }
    };

    const openEditModal = (txn) => {
        setEditingTxn({
            ...txn,
            merchant_name: txn.merchant_name || '',
            amount: txn.amount || 0,
            txn_date: txn.txn_date || '',
            payment_mode: txn.payment_mode || 'UPI',
            category_id: txn.category_id || '',
            category_name: txn.category_name || ''
        });
        setApplyMerchantToSimilar(false);
        setApplyCategoryToSimilar(false);
        setIsEditModalOpen(true);
    };

    const handleSaveTxn = async () => {
        if (!editingTxn) return;
        try {
            let finalCategoryId = editingTxn.category_id;
            if (editingTxn.category_name && !finalCategoryId) {
                finalCategoryId = await ensureCategoryExists(editingTxn.category_name);
            }
            if (!finalCategoryId) { alert("Please select a valid category."); return; }

            const payload = {
                merchant_name: editingTxn.merchant_name,
                amount: parseFloat(editingTxn.amount),
                txn_date: editingTxn.txn_date,
                category_id: finalCategoryId,
                payment_mode: editingTxn.payment_mode,
                payment_type: editingTxn.payment_type,
                apply_merchant_to_similar: applyMerchantToSimilar,
                apply_category_to_similar: applyCategoryToSimilar
            };

            await api.put(`/transactions/${editingTxn.id}`, payload);

            const selectedCategory = categories.find(c => c.id === payload.category_id);

            setTransactions(prev => prev.map(t => {
                if (t.id === editingTxn.id) {
                    return {
                        ...t,
                        ...payload,
                        category_name: selectedCategory ? selectedCategory.name : "Uncategorized",
                        category_color: selectedCategory ? selectedCategory.color : "#cbd5e1"
                    };
                }
                return t;
            }));

            setIsEditModalOpen(false);
            setEditingTxn(null);
        } catch (error) {
            console.error("Failed to update transaction", error);
            alert("Failed to save transaction.");
        }
    };

    // --- RULE ENGINE HANDLERS ---
    const handleOpenRule = (txn) => {
        setRuleData({ pattern: txn.merchant_name, new_name: '', category_id: '' });
        setShowRuleModal(true);
        setPreviewStep('INPUT');
    };

    const handlePreviewRule = async () => {
        try {
            setLoading(true);
            const res = await api.post('/rules/preview', {
                pattern: ruleData.pattern,
                new_merchant_name: ruleData.new_name,
                category_id: ruleData.category_id || 0,
                match_type: "CONTAINS"
            });
            setPreviewResults(res.data);
            setExcludedIds(new Set());
            setPreviewStep('PREVIEW');
        } catch (e) { alert("Failed to preview matches"); } finally { setLoading(false); }
    };

    const toggleExclusion = (id) => {
        const next = new Set(excludedIds);
        if (next.has(id)) next.delete(id); else next.add(id);
        setExcludedIds(next);
    };

    const handleConfirmRule = async () => {
        try {
            await api.post('/rules/', {
                pattern: ruleData.pattern,
                new_merchant_name: ruleData.new_name,
                category_id: ruleData.category_id,
                match_type: "CONTAINS",
                excluded_ids: Array.from(excludedIds)
            });
            setShowRuleModal(false);
            setPreviewStep('INPUT');
            fetchTransactions();
        } catch (e) { alert("Failed to save rule"); }
    };

    const isLoadingState = loading || smartSearchLoading;

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] bg-[#0b0b0b] rounded-2xl border border-white/5 text-white font-sans overflow-hidden relative">

            {/* --- TOP BAR --- */}
            <div className="p-6 border-b border-white/5 space-y-4 shrink-0 bg-[#0b0b0b]">
                <div className="flex flex-col md:flex-row justify-between items-end gap-4">
                    <div className="flex flex-wrap gap-4 items-end w-full md:w-auto">
                        <SmartSearchInput
                            categories={categories}
                            onSearch={handleFuzzySearch}
                            onSmartSearch={handleSmartSearch}
                            className="w-80"
                        />
                        <DateFilter label="From" value={filters.startDate} onChange={(val) => { setFilters(prev => ({...prev, startDate: val})); setIsSmartSearch(false); }} />
                        <DateFilter label="To" value={filters.endDate} onChange={(val) => { setFilters(prev => ({...prev, endDate: val})); setIsSmartSearch(false); }} />
                    </div>

                    <div className="flex items-center gap-3">
                        <div className="flex bg-[#1e1e1e] rounded-lg p-1 border border-white/10">
                            <FilterButton active={filters.type === 'ALL'} onClick={() => { setFilters({...filters, type: 'ALL'}); setPage(1); setIsSmartSearch(false); }} label="ALL" />
                            <FilterButton active={filters.type === 'DEBIT'} onClick={() => { setFilters({...filters, type: 'DEBIT'}); setPage(1); setIsSmartSearch(false); }} label="DEBIT" icon={TrendingDown} colorClass="text-red-400" bgClass="bg-red-500/20 border-red-500/30"/>
                            <FilterButton active={filters.type === 'CREDIT'} onClick={() => { setFilters({...filters, type: 'CREDIT'}); setPage(1); setIsSmartSearch(false); }} label="CREDIT" icon={TrendingUp} colorClass="text-emerald-400" bgClass="bg-emerald-500/20 border-emerald-500/30"/>
                        </div>
                        <button onClick={clearAllFilters} className="p-2 text-slate-500 hover:text-white hover:bg-white/10 rounded-lg transition-colors" title="Clear All Filters"><RotateCcw size={18} /></button>
                    </div>
                </div>
            </div>

            {/* --- SEARCH SUMMARY --- */}
            <SearchSummary
                totalRecords={totalRecords}
                debitSum={debitSum}
                creditSum={creditSum}
                isSmartSearch={isSmartSearch}
                parsedFilters={currentParsedFilters}
                onClearFilters={clearAllFilters}
            />

            {/* --- TABLE AREA --- */}
            <div className="flex-1 overflow-hidden relative">
                <div className="absolute inset-0 overflow-y-auto custom-scrollbar">
                    <table className="w-full text-left border-collapse">
                        <thead className="sticky top-0 z-10 bg-[#0b0b0b] shadow-[0_1px_0_rgba(255,255,255,0.1)]">
                            <tr>
                                <SortableHeader label="Date" active={sortConfig.key === 'txn_date'} direction={sortConfig.direction} onClick={() => toggleSort('txn_date')} />
                                <th className="p-4 text-xs font-bold uppercase tracking-widest text-slate-500">Merchant</th>
                                <th className="p-4 text-xs font-bold uppercase tracking-widest text-slate-500">Mode</th>
                                <th className="p-0">
                                    <CategoryMultiselect
                                        categories={categories}
                                        selectedIds={selectedCategoryIds}
                                        onChange={handleCategoryFilterChange}
                                    />
                                </th>
                                <SortableHeader label="Amount" align="right" active={sortConfig.key === 'amount'} direction={sortConfig.direction} onClick={() => toggleSort('amount')} />
                                <th className="p-4 w-20"></th>
                            </tr>
                        </thead>

                        <tbody className="divide-y divide-white/5">
                            {isLoadingState ? (
                                <tr><td colSpan="6" className="py-20 text-center text-slate-500 animate-pulse">Loading transactions...</td></tr>
                            ) : transactions.length === 0 ? (
                                <tr><td colSpan="6" className="py-20 text-center text-slate-500">No transactions found</td></tr>
                            ) : (
                                transactions.map((txn) => (
                                    <tr key={txn.id} className="group hover:bg-white/[0.02] transition-colors">
                                        <td className="p-4 text-sm text-slate-400 font-mono">{txn.txn_date}</td>
                                        <td className="p-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold" style={{ backgroundColor: `${txn.category_color}20`, color: txn.category_color }}>
                                                    {txn.merchant_name.charAt(0)}
                                                </div>
                                                <span className="text-sm font-medium text-slate-200 truncate max-w-[200px]" title={txn.merchant_name}>{txn.merchant_name}</span>
                                                <button onClick={(e) => { e.stopPropagation(); handleOpenRule(txn); }} className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-600 hover:text-teal-400 hover:bg-teal-500/10 rounded transition-all" title="Create Rule"><Wand2 size={14} /></button>
                                            </div>
                                        </td>
                                        <td className="p-4"><span className="text-xs font-bold text-slate-500 bg-white/5 px-2 py-1 rounded">{txn.payment_mode}</span></td>
                                        <td className="p-4">
                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border border-white/5" style={{ backgroundColor: `${txn.category_color}10`, color: txn.category_color, borderColor: `${txn.category_color}20` }}>{txn.category_name}</span>
                                        </td>
                                        <td className={`p-4 text-right text-sm font-bold font-mono ${getAmountColor(txn.payment_type)}`}>{formatCurrency(txn.amount)}</td>
                                        <td className="p-4 text-right">
                                            <button onClick={() => openEditModal(txn)} className="p-2 text-slate-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors"><Edit2 size={14} /></button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* --- PAGINATION --- */}
            <div className="p-4 border-t border-white/5 flex items-center justify-between bg-[#0b0b0b] text-xs text-slate-500">
                <span>Showing {totalRecords > 0 ? (page - 1) * limit + 1 : 0} to {Math.min(page * limit, totalRecords)} of {totalRecords} results</span>
                <div className="flex items-center gap-2">
                    <button onClick={() => handlePageChange(page - 1)} disabled={page === 1} className="p-2 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"><ChevronLeft size={16} /></button>
                    <span className="font-mono text-white px-2">Page {page} of {totalPages || 1}</span>
                    <button onClick={() => handlePageChange(page + 1)} disabled={page === totalPages || totalPages === 0} className="p-2 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"><ChevronRight size={16} /></button>
                </div>
            </div>

            {/* --- EDIT MODAL --- */}
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
                                <div className="space-y-1.5"><label className="text-xs font-bold text-slate-500 uppercase">Amount ({'\u20B9'})</label><input type="number" value={editingTxn.amount} onChange={(e) => setEditingTxn({...editingTxn, amount: e.target.value})} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white font-mono focus:border-teal-500/50 outline-none"/></div>
                                <div className="space-y-1.5"><label className="text-xs font-bold text-slate-500 uppercase">Date</label><input type="date" value={editingTxn.txn_date} onChange={(e) => setEditingTxn({...editingTxn, txn_date: e.target.value})} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white focus:border-teal-500/50 outline-none"/></div>
                            </div>

                            {/* CATEGORY SELECT + BUTTON */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-500 uppercase">Category</label>
                                <div className="flex gap-2">
                                    <select
                                        value={editingTxn.category_id || ""}
                                        onChange={(e) => {
                                            const catId = parseInt(e.target.value);
                                            const cat = categories.find(c => c.id === catId);
                                            setEditingTxn({ ...editingTxn, category_id: catId, category_name: cat ? cat.name : "" });
                                        }}
                                        className="flex-1 bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white focus:border-teal-500/50 outline-none appearance-none"
                                    >
                                        <option value="">Select Category...</option>
                                        {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                    </select>
                                    <button
                                        onClick={() => setIsCatModalOpen(true)}
                                        className="bg-teal-600 hover:bg-teal-500 text-white p-3 rounded-lg transition-colors flex items-center justify-center border border-teal-500/20"
                                        title="Create New Category"
                                    >
                                        <Plus size={20} />
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-500 uppercase">Mode</label>
                                <select value={editingTxn.payment_mode} onChange={(e) => setEditingTxn({...editingTxn, payment_mode: e.target.value})} className="w-full bg-[#1e1e1e] border border-white/10 rounded-lg p-3 text-sm text-white focus:border-teal-500/50 outline-none">
                                    <option value="UPI">UPI</option><option value="CARD">CARD</option><option value="CASH">CASH</option><option value="NETBANKING">NETBANKING</option>
                                </select>
                            </div>
                            <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-3">
                                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Bulk Actions</p>
                                <div className="flex items-center gap-3"><input type="checkbox" id="applyMerchant" checked={applyMerchantToSimilar} onChange={(e) => setApplyMerchantToSimilar(e.target.checked)} className="w-4 h-4 rounded bg-slate-800 border-slate-600 text-teal-500"/><label htmlFor="applyMerchant" className="text-sm text-slate-300">Update <b>Merchant Name</b> for all similar</label></div>
                                <div className="flex items-center gap-3"><input type="checkbox" id="applyCategory" checked={applyCategoryToSimilar} onChange={(e) => setApplyCategoryToSimilar(e.target.checked)} className="w-4 h-4 rounded bg-slate-800 border-slate-600 text-teal-500"/><label htmlFor="applyCategory" className="text-sm text-slate-300">Update <b>Category</b> for all similar</label></div>
                            </div>
                        </div>
                        <div className="p-6 border-t border-white/10 bg-[#161616] flex justify-end gap-3">
                            <button onClick={() => setIsEditModalOpen(false)} className="px-5 py-2.5 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 transition-all text-sm font-bold">Cancel</button>
                            <button onClick={handleSaveTxn} className="px-5 py-2.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white shadow-lg shadow-teal-500/20 transition-all text-sm font-bold flex items-center gap-2"><Save size={16} /> Save Changes</button>
                        </div>
                    </div>
                </div>
            )}

            {/* ADD CATEGORY MODAL (Z-Index 60 to overlap Edit Modal) */}
            {isCatModalOpen && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4">
                    <div className="bg-[#111] rounded-2xl border border-white/10 w-full max-w-sm shadow-2xl overflow-hidden">
                        <div className="p-5 border-b border-white/10 bg-[#161616] flex justify-between items-center">
                            <h3 className="text-md font-bold text-white">New Category</h3>
                            <button onClick={() => setIsCatModalOpen(false)} className="text-slate-500 hover:text-white"><X size={18} /></button>
                        </div>
                        <div className="p-6">
                            <label className="text-xs font-bold text-slate-500 uppercase">Category Name</label>
                            <input autoFocus type="text" placeholder="e.g., Gym, Subscription..." value={newCatName} onChange={(e) => setNewCatName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSaveNewCategory()} className="w-full mt-2 bg-[#1e1e1e] border border-white/10 text-white p-3 rounded-lg outline-none focus:border-teal-500 transition-all placeholder:text-slate-700"/>
                        </div>
                        <div className="p-4 bg-[#161616] flex justify-end gap-3">
                            <button onClick={() => setIsCatModalOpen(false)} className="px-4 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 text-sm font-medium transition-colors">Cancel</button>
                            <button onClick={handleSaveNewCategory} className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-bold shadow-lg shadow-teal-500/20 transition-all">Create</button>
                        </div>
                    </div>
                </div>
            )}

            {/* --- RULE MODAL --- */}
            {showRuleModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div
                        className="bg-[#111] border border-white/10 p-6 rounded-xl w-full max-w-lg max-h-[80vh] flex flex-col box-shadow-xl"
                        style={{ boxShadow: '0 4px 60px -15px rgba(45, 212, 191, 0.2)' }}
                    >
                        <h3 className="text-xl text-white font-bold mb-6 flex items-center gap-3 border-b border-white/5 pb-4">
                            <Wand2 style={{ color: 'rgb(45, 212, 191)' }} size={24} />
                            {previewStep === 'INPUT' ? "Create Automation Rule" : "Verify Matches"}
                        </h3>

                        {previewStep === 'INPUT' ? (
                            <div className="space-y-5">
                                <div>
                                    <label className="text-xs font-semibold uppercase tracking-wider mb-1 block" style={{ color: 'rgb(45, 212, 191)' }}>If Merchant Name Contains</label>
                                    <input className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:outline-none transition-colors" style={{ borderColor: 'rgba(255,255,255,0.1)' }} onFocus={(e) => e.target.style.borderColor = 'rgb(45, 212, 191)'} onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'} value={ruleData.pattern} placeholder="e.g. Swiggy" autoFocus onChange={e => setRuleData({...ruleData, pattern: e.target.value})} />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold uppercase tracking-wider mb-1 block" style={{ color: 'rgb(45, 212, 191)' }}>Rename Merchant To</label>
                                    <input className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:outline-none transition-colors" style={{ borderColor: 'rgba(255,255,255,0.1)' }} onFocus={(e) => e.target.style.borderColor = 'rgb(45, 212, 191)'} onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'} placeholder="e.g. Swiggy" value={ruleData.new_name} onChange={e => setRuleData({...ruleData, new_name: e.target.value})} />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold uppercase tracking-wider mb-1 block" style={{ color: 'rgb(45, 212, 191)' }}>Auto-Categorize As</label>
                                    <select className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:outline-none" style={{ borderColor: 'rgba(255,255,255,0.1)' }} onFocus={(e) => e.target.style.borderColor = 'rgb(45, 212, 191)'} onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'} value={ruleData.category_id} onChange={e => setRuleData({...ruleData, category_id: e.target.value})}>
                                        <option value="">Select Category...</option>
                                        {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                    </select>
                                </div>
                                <div className="flex gap-3 mt-6">
                                    <button onClick={() => { setShowRuleModal(false); setPreviewStep('INPUT'); }} className="flex-1 px-4 py-3 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 transition-all font-medium">Cancel</button>
                                    <button onClick={handlePreviewRule} className="flex-1 text-[#111] font-bold py-3 rounded-lg transition-all shadow-lg" style={{ backgroundColor: 'rgb(45, 212, 191)', boxShadow: '0 4px 20px -5px rgba(45, 212, 191, 0.5)' }}>Preview Matches</button>
                                </div>
                            </div>
                        ) : (
                            <div>
                                <div className="flex justify-between items-center mb-4"><h4 className="font-bold text-white">Found {previewResults.length} Matches</h4><span className="text-xs text-slate-500">Uncheck to exclude</span></div>
                                <div className="bg-[#1a1a1a] rounded-xl border border-white/10 overflow-hidden max-h-[300px] overflow-y-auto custom-scrollbar">
                                    {previewResults.map(m => (
                                        <div key={m.transaction_id} className={`flex items-center gap-3 p-3 border-b border-white/5 cursor-pointer hover:bg-white/5 transition-colors ${excludedIds.has(m.transaction_id) ? 'opacity-50' : ''}`} onClick={() => toggleExclusion(m.transaction_id)}>
                                            <div className={`w-5 h-5 rounded flex items-center justify-center border`} style={{ borderColor: excludedIds.has(m.transaction_id) ? 'rgba(255,255,255,0.2)' : 'rgb(45, 212, 191)', backgroundColor: excludedIds.has(m.transaction_id) ? 'transparent' : 'rgb(45, 212, 191)' }}>
                                                {!excludedIds.has(m.transaction_id) && <Check size={12} className="text-[#111]" />}
                                            </div>
                                            <div className="flex-1 text-sm"><div className="flex justify-between"><span className="text-white font-medium">{m.current_name}</span><span className="text-slate-400 font-mono">{m.date}</span></div><div className="text-xs text-slate-500 mt-0.5">Will become: <span style={{ color: 'rgb(45, 212, 191)' }}>{ruleData.new_name || m.current_name}</span></div></div>
                                        </div>
                                    ))}
                                </div>
                                <div className="mt-6 flex gap-3">
                                    <button onClick={() => setPreviewStep('INPUT')} className="flex-1 px-4 py-3 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 transition-all font-medium">Back</button>
                                    <button onClick={handleConfirmRule} className="flex-1 text-[#111] font-bold py-3 rounded-lg transition-all shadow-lg" style={{ backgroundColor: 'rgb(45, 212, 191)', boxShadow: '0 4px 20px -5px rgba(45, 212, 191, 0.5)' }}>Confirm & Apply</button>
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
