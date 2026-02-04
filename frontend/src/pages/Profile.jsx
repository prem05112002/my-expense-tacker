import React, { useEffect, useState, useRef } from 'react';
import api from '../api/axios';
import { useToast } from '../contexts/ToastContext';
import { Save, Trash2, Calendar, DollarSign, EyeOff, ChevronDown, Check, X, AlertTriangle } from 'lucide-react';
import { ProfileSkeleton } from '../components/ui/CardSkeleton';
import useFocusTrap from '../hooks/useFocusTrap';

// ... (MultiSelectDropdown Component remains the same) ...
const MultiSelectDropdown = ({ label, options, selected, onChange, placeholder = "Select..." }) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false);
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);
    const toggleOption = (value) => {
        if (selected.includes(value)) onChange(selected.filter(item => item !== value));
        else onChange([...selected, value]);
    };
    return (
        <div className="relative" ref={dropdownRef}>
            <label className="text-xs text-slate-400 font-bold uppercase mb-2 block">{label}</label>
            <button onClick={() => setIsOpen(!isOpen)} className="w-full bg-[#222] border border-white/10 rounded p-3 text-white text-sm flex justify-between items-center hover:border-white/30 transition-colors">
                <span className={selected.length ? "text-white" : "text-slate-500"}>{selected.length > 0 ? `${selected.length} Selected` : placeholder}</span>
                <ChevronDown size={16} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            {isOpen && (
                <div className="absolute z-20 w-full mt-2 bg-[#1a1a1a] border border-white/10 rounded-xl shadow-2xl max-h-60 overflow-y-auto custom-scrollbar">
                    {options.map(opt => (
                        <div key={opt.id} onClick={() => toggleOption(opt.name)} className={`flex items-center gap-3 p-3 cursor-pointer hover:bg-white/5 border-b border-white/5 last:border-0 transition-colors ${selected.includes(opt.name) ? 'bg-blue-900/20' : ''}`}>
                            <div className={`w-4 h-4 rounded border flex items-center justify-center ${selected.includes(opt.name) ? 'bg-blue-500 border-blue-500' : 'border-slate-600'}`}>
                                {selected.includes(opt.name) && <Check size={12} className="text-white" />}
                            </div>
                            <span className="text-sm text-slate-200">{opt.name}</span>
                        </div>
                    ))}
                </div>
            )}
            <div className="flex flex-wrap gap-2 mt-3">
                {selected.map(val => (
                    <div key={val} className="flex items-center gap-1 bg-white/5 text-slate-200 px-2 py-1 rounded-md text-xs border border-white/10">
                        <span>{val}</span>
                        <button onClick={() => toggleOption(val)} className="hover:text-red-400 transition-colors"><X size={12} /></button>
                    </div>
                ))}
            </div>
        </div>
    );
};

const Profile = () => {
    const toast = useToast();
    const [loading, setLoading] = useState(true);
    const [rules, setRules] = useState([]);
    const [allCategories, setAllCategories] = useState([]);
    const [deleteTarget, setDeleteTarget] = useState(null);

    const [settings, setSettings] = useState({
        salary_day: 1,
        budget_type: 'FIXED',
        budget_value: 0,
        view_cycle_offset: 0,
        ignored_categories: [],
        income_categories: []
    });

    const deleteModalRef = useFocusTrap(!!deleteTarget, () => setDeleteTarget(null));

    useEffect(() => {
        const loadData = async () => {
            try {
                const [setRes, ruleRes, catRes] = await Promise.all([
                    api.get('/dashboard/settings'),
                    api.get('/rules/'),
                    api.get('/categories/') 
                ]);
                const parseList = (val) => Array.isArray(val) ? val : [];
                setSettings({
                    ...setRes.data,
                    ignored_categories: parseList(setRes.data.ignored_categories),
                    income_categories: parseList(setRes.data.income_categories)
                });
                setRules(ruleRes.data);
                setAllCategories(catRes.data);
            } catch (e) { console.error("Failed to load profile", e); } finally { setLoading(false); }
        };
        loadData();
    }, []);

    const saveSettings = async () => {
        try { await api.put('/dashboard/settings', settings); toast.success("Settings saved successfully!"); } catch (e) { toast.error("Error saving settings"); }
    };

    const confirmDeleteRule = async () => {
        if (!deleteTarget) return;
        try {
            await api.delete(`/rules/${deleteTarget.id}`);
            setRules(rules.filter(r => r.id !== deleteTarget.id));
            setDeleteTarget(null); // Close modal
            toast.success("Rule deleted successfully");
        } catch (e) {
            toast.error("Failed to delete rule");
        }
    };

    if (loading) return <ProfileSkeleton />;

    return (
        <div className="p-6 text-white h-[calc(100vh-4rem)] overflow-y-auto custom-scrollbar max-w-7xl mx-auto">
            <h1 className="text-3xl font-bold mb-8">System Configuration</h1>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* --- SETTINGS --- */}
                <div className="space-y-8">
                    <section className="bg-[#161616] p-6 rounded-2xl border border-white/5">
                        <h2 className="text-xl font-bold mb-4 flex items-center gap-2"><Calendar className="text-blue-400"/> Cycle Settings</h2>
                        <div className="space-y-4">
                            <div>
                                <label className="text-xs text-slate-400 font-bold uppercase">Salary / Start Day</label>
                                <input type="number" min="1" max="31" className="w-full bg-[#222] border border-white/10 rounded p-3 text-white mt-1 outline-none focus:border-teal-500" value={settings.salary_day} onChange={e => setSettings({...settings, salary_day: parseInt(e.target.value)})} />
                            </div>
                        </div>
                    </section>
                    <section className="bg-[#161616] p-6 rounded-2xl border border-white/5">
                        <h2 className="text-xl font-bold mb-4 flex items-center gap-2"><DollarSign className="text-green-400"/> Budget Target</h2>
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-2">
                                <button onClick={() => setSettings({...settings, budget_type: 'FIXED'})} className={`p-3 rounded border text-sm font-bold transition-all ${settings.budget_type === 'FIXED' ? 'bg-blue-600 border-blue-500 text-white' : 'border-white/10 text-slate-400 hover:bg-[#222]'}`}>Fixed Amount</button>
                                <button onClick={() => setSettings({...settings, budget_type: 'PERCENTAGE'})} className={`p-3 rounded border text-sm font-bold transition-all ${settings.budget_type === 'PERCENTAGE' ? 'bg-blue-600 border-blue-500 text-white' : 'border-white/10 text-slate-400 hover:bg-[#222]'}`}>% of Salary</button>
                            </div>
                            <div>
                                <label className="text-xs text-slate-400 font-bold uppercase">{settings.budget_type === 'FIXED' ? 'Monthly Limit (₹)' : 'Percentage of Income (%)'}</label>
                                <input type="number" className="w-full bg-[#222] border border-white/10 rounded p-3 text-white mt-1 outline-none focus:border-teal-500" value={settings.budget_value} onChange={e => setSettings({...settings, budget_value: parseFloat(e.target.value)})} />
                            </div>
                        </div>
                    </section>
                    <section className="bg-[#161616] p-6 rounded-2xl border border-white/5">
                        <h2 className="text-xl font-bold mb-6 flex items-center gap-2"><EyeOff className="text-red-400"/> Computation Exclusions</h2>
                        <div className="space-y-6">
                            <MultiSelectDropdown label="Ignore from Spending" placeholder="Select categories..." options={allCategories} selected={settings.ignored_categories} onChange={(newList) => setSettings({...settings, ignored_categories: newList})} />
                            <MultiSelectDropdown label="Salary / Pure Income" placeholder="Select income tags..." options={allCategories} selected={settings.income_categories} onChange={(newList) => setSettings({...settings, income_categories: newList})} />
                        </div>
                    </section>
                    <button onClick={saveSettings} className="w-full py-4 bg-teal-600 text-white font-bold rounded-xl hover:bg-teal-500 transition-colors shadow-lg shadow-teal-500/20">Save System Configuration</button>
                </div>

                {/* --- RULES TABLE (New Table Layout) --- */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 h-fit sticky top-6">
                    <h2 className="text-xl font-bold mb-4 flex items-center gap-2"><Save className="text-yellow-400"/> Automation Rules ({rules.length})</h2>
                    <div className="overflow-x-auto overflow-hidden rounded-lg border border-white/10">
                        <table className="w-full text-left text-sm text-slate-400 min-w-[500px]">
                            <thead className="bg-white/5 text-xs uppercase font-bold text-white">
                                <tr>
                                    <th className="px-4 py-3">Pattern Match</th>
                                    <th className="px-4 py-3">Rename To</th>
                                    <th className="px-4 py-3">Category</th>
                                    <th className="px-4 py-3 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {rules.length > 0 ? (
                                    rules.map((rule) => (
                                        <tr key={rule.id} className="hover:bg-white/[0.02] transition-colors group">
                                            <td className="px-4 py-3 text-white font-medium">{rule.pattern}</td>
                                            
                                            {/* ✅ FIX: Use rule.newMerchantName instead of rule.new_merchant_name */}
                                            <td className="px-4 py-3 text-white font-medium">
                                                {rule.newMerchantName || rule.new_merchant_name}
                                            </td>

                                            <td className="px-4 py-3">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: rule.category_color || '#666' }}></div>
                                                    <span style={{ color: rule.category_color || '#999' }}>{rule.category_name}</span>
                                                </div>
                                            </td>
                                            <td className="px-4 py-3 text-right">
                                            <button 
                                                onClick={() => setDeleteTarget(rule)} 
                                                className="text-slate-500 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                                            >
                                                    <Trash2 size={16} />
                                                </button>
                                            </td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr>
                                        <td colSpan="4" className="text-center py-10 text-slate-500">No automation rules found.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            {deleteTarget && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div
                        ref={deleteModalRef}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="delete-modal-title"
                        className="bg-[#111] border border-white/10 p-6 rounded-2xl w-full max-w-sm shadow-2xl transform transition-all scale-100"
                    >
                        <div className="flex items-center gap-3 mb-4 text-red-400">
                            <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center border border-red-500/20">
                                <AlertTriangle size={20} />
                            </div>
                            <h3 id="delete-modal-title" className="text-lg font-bold text-white">Delete Rule?</h3>
                        </div>

                        <p className="text-slate-400 text-sm mb-6 leading-relaxed">
                            Are you sure you want to delete the automation rule for
                            <span className="text-white font-mono bg-white/10 px-1.5 py-0.5 rounded mx-1.5 border border-white/10">
                                {deleteTarget.pattern}
                            </span>?
                            This action cannot be undone.
                        </p>

                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setDeleteTarget(null)}
                                className="px-4 py-2 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 text-sm font-medium transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDeleteRule}
                                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-bold shadow-lg shadow-red-500/20 transition-all flex items-center gap-2"
                            >
                                <Trash2 size={14} />
                                Delete Rule
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Profile;