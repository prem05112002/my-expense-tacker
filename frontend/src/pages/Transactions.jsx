import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import { Search, Filter, Edit2, Check, X, Loader } from 'lucide-react';

const Transactions = () => {
    const [transactions, setTransactions] = useState([]);
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);
    
    // Modal State
    const [editingTxn, setEditingTxn] = useState(null);
    const [selectedCat, setSelectedCat] = useState('');
    const [ruleKeyword, setRuleKeyword] = useState('');
    const [createRule, setCreateRule] = useState(false);
    const [applyRetro, setApplyRetro] = useState(false);

    // Initial Data Fetch
    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const [txnRes, catRes] = await Promise.all([
                api.get('/transactions?limit=100'),
                api.get('/categories')
            ]);
            setTransactions(txnRes.data);
            setCategories(catRes.data);
            setLoading(false);
        } catch (error) {
            console.error("Error fetching data", error);
            setLoading(false);
        }
    };

    // Open Modal
    const handleEditClick = (txn) => {
        setEditingTxn(txn);
        setSelectedCat(txn.category_id || '');
        // Default keyword: Clean up the merchant name slightly
        setRuleKeyword(txn.merchant_name || '');
        setCreateRule(false);
        setApplyRetro(false);
    };

    // Submit Logic (The Brains)
    const handleSave = async () => {
        if (!selectedCat) return;

        try {
            await api.post('/categorize', {
                transaction_ids: [editingTxn.id],
                category_id: selectedCat,
                create_rule: createRule,
                rule_keyword: ruleKeyword,
                apply_retroactive: applyRetro
            });
            
            // Refresh data to see changes
            fetchData();
            setEditingTxn(null); // Close modal
        } catch (error) {
            alert("Failed to update category");
            console.error(error);
        }
    };

    if (loading) return <div className="p-8 text-center">Loading transactions...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h2 className="text-3xl font-bold">Transactions</h2>
                <button onClick={fetchData} className="px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100">
                    Refresh
                </button>
            </div>

            {/* Transactions Table */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                            <th className="p-4 font-semibold text-slate-600">Date</th>
                            <th className="p-4 font-semibold text-slate-600">Merchant</th>
                            <th className="p-4 font-semibold text-slate-600">Amount</th>
                            <th className="p-4 font-semibold text-slate-600">Category</th>
                            <th className="p-4 font-semibold text-slate-600">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {transactions.map((txn) => (
                            <tr key={txn.id} className="hover:bg-slate-50 transition-colors">
                                <td className="p-4 text-slate-500">{txn.txn_date}</td>
                                <td className="p-4 font-medium text-slate-800">
                                    {txn.merchant_name || "Unknown Merchant"}
                                    <div className="text-xs text-slate-400">{txn.bank_name}</div>
                                </td>
                                <td className="p-4 font-bold text-slate-800">
                                    ₹{txn.amount.toLocaleString()}
                                </td>
                                <td className="p-4">
                                    <span 
                                        className="px-3 py-1 rounded-full text-sm font-medium"
                                        style={{ 
                                            backgroundColor: `${txn.category_color}20`, 
                                            color: txn.category_color 
                                        }}
                                    >
                                        {txn.category_name}
                                    </span>
                                </td>
                                <td className="p-4">
                                    <button 
                                        onClick={() => handleEditClick(txn)}
                                        className="p-2 hover:bg-slate-200 rounded-full text-slate-500"
                                    >
                                        <Edit2 size={16} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* EDIT MODAL */}
            {editingTxn && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
                        <div className="flex justify-between items-center">
                            <h3 className="text-xl font-bold">Categorize Transaction</h3>
                            <button onClick={() => setEditingTxn(null)} className="text-slate-400 hover:text-slate-600">
                                <X size={20} />
                            </button>
                        </div>
                        
                        <div className="bg-slate-50 p-4 rounded-lg">
                            <p className="text-sm text-slate-500">Merchant</p>
                            <p className="font-semibold">{editingTxn.merchant_name}</p>
                            <p className="text-lg font-bold text-blue-600 mt-1">₹{editingTxn.amount}</p>
                        </div>

                        {/* Category Select */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Select Category</label>
                            <select 
                                value={selectedCat} 
                                onChange={(e) => setSelectedCat(e.target.value)}
                                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                            >
                                <option value="">-- Choose Category --</option>
                                {categories.map(cat => (
                                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                                ))}
                            </select>
                        </div>

                        {/* THE SMART FEATURES */}
                        <div className="border-t border-slate-100 pt-4 space-y-3">
                            <label className="flex items-start gap-3 cursor-pointer">
                                <input 
                                    type="checkbox" 
                                    checked={createRule}
                                    onChange={(e) => setCreateRule(e.target.checked)}
                                    className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-blue-500" 
                                />
                                <div>
                                    <span className="font-medium text-slate-700">Create rule for future?</span>
                                    <p className="text-xs text-slate-500">Always assign this category to similar merchants.</p>
                                </div>
                            </label>

                            {createRule && (
                                <div className="ml-7">
                                    <label className="block text-xs font-medium text-slate-600 mb-1">Rule Keyword</label>
                                    <input 
                                        type="text" 
                                        value={ruleKeyword}
                                        onChange={(e) => setRuleKeyword(e.target.value)}
                                        className="w-full p-2 text-sm border border-slate-300 rounded focus:border-blue-500 outline-none"
                                        placeholder="e.g. Zomato"
                                    />
                                    <label className="flex items-center gap-2 mt-2 cursor-pointer">
                                        <input 
                                            type="checkbox" 
                                            checked={applyRetro}
                                            onChange={(e) => setApplyRetro(e.target.checked)}
                                            className="w-3 h-3 text-blue-600 rounded" 
                                        />
                                        <span className="text-xs text-slate-600">Apply to existing past transactions too?</span>
                                    </label>
                                </div>
                            )}
                        </div>

                        <button 
                            onClick={handleSave}
                            disabled={!selectedCat}
                            className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
                        >
                            Save Category
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Transactions;