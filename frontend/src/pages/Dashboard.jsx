import React, { useEffect, useState } from 'react';
import api from '../api/axios';
import { 
    Wallet, TrendingUp, TrendingDown, Settings, 
    X, Save, AlertTriangle 
} from 'lucide-react';
import { 
    LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer 
} from 'recharts';

import { getAmountColor, formatCurrency } from '../utils/formatters';

const Dashboard = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    
    // Settings State
    const [showSettings, setShowSettings] = useState(false);
    const [settings, setSettings] = useState({
        salary_day: 1,
        budget_type: 'FIXED', 
        budget_value: 50000
    });

    const fetchStats = async () => {
        try {
            setLoading(true);
            const res = await api.get('/dashboard');
            setStats(res.data);
            
            try {
                const setRes = await api.get('/dashboard/settings');
                setSettings({
                    salary_day: setRes.data.salary_day,
                    budget_type: setRes.data.budget_type || 'FIXED',
                    budget_value: setRes.data.budget_value || setRes.data.monthly_budget
                });
            } catch (e) {
                console.warn("Could not fetch settings", e);
            }
        } catch (error) {
            console.error("Error fetching dashboard data", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStats();
    }, []);

    const handleSaveSettings = async () => {
        try {
            await api.put('/dashboard/settings', settings);
            setShowSettings(false);
            fetchStats(); 
        } catch (e) {
            alert("Failed to save settings");
        }
    };

    if (loading) return <div className="p-10 text-white animate-pulse">Loading Financial Health...</div>;
    if (!stats) return <div className="p-10 text-white">Failed to load data.</div>;

    // Safety Checks
    const trendData = stats.spending_trend || [];
    const breakdownData = stats.category_breakdown || [];
    const recentTxns = stats.recent_transactions || [];
    
    // Calculations
    const isSpendingMore = (stats.spend_diff_percent || 0) > 0;
    const spendDiffAbs = Math.abs(stats.spend_diff_percent || 0).toFixed(1);
    const budgetUsedPercent = Math.min((stats.total_spend / stats.total_budget) * 100, 100);
    const timePassedPercent = Math.min((stats.days_passed / stats.days_in_cycle) * 100, 100);

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] gap-6 text-white font-sans overflow-y-auto custom-scrollbar p-1">
            
            {/* ✅ FIXED: PROPER HEADER SECTION WITH BUTTON */}
            <div className="flex flex-col md:flex-row justify-between md:items-end gap-4 shrink-0">
                <div>
                    <h1 className="text-2xl font-bold text-white">Financial Health</h1>
                    <p className="text-slate-500 text-sm">
                        Cycle: <span className="text-white font-mono">{stats.cycle_start}</span> to <span className="text-white font-mono">{stats.cycle_end}</span>
                    </p>
                </div>
                <button 
                    onClick={() => setShowSettings(true)}
                    className="flex items-center gap-2 bg-[#1a1a1a] hover:bg-[#252525] text-white px-4 py-2 rounded-lg border border-white/10 transition-all text-sm font-bold hover:border-blue-500/50"
                >
                    <Settings size={16} className="text-blue-400" />
                    Configure Budget
                </button>
            </div>

            {/* --- HERO SECTION --- */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 shrink-0">
                
                {/* 1. Total Spend */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <Wallet size={48} className="text-white" />
                    </div>
                    <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">Total Spend</p>
                    <div className="flex items-end gap-3">
                        <h2 className="text-3xl font-bold text-white">₹{formatCurrency(stats.total_spend)}</h2>
                    </div>
                    <div className={`mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${isSpendingMore ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                        {isSpendingMore ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                        {spendDiffAbs}% vs last month
                    </div>
                </div>

                {/* 2. Safe to Spend */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 relative overflow-hidden">
                    <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">Safe to Spend</p>
                    <div className="flex items-end gap-2">
                        <h2 className="text-3xl font-bold text-emerald-400">₹{formatCurrency(stats.safe_to_spend_daily)}</h2>
                        <span className="text-sm text-slate-500 mb-1">/ day</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                        Based on ₹{formatCurrency(stats.budget_remaining)} left for {stats.days_left} days.
                    </p>
                </div>

                {/* 3. Survival Bar */}
                <div className="md:col-span-2 bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col justify-center">
                    <div className="flex justify-between items-center mb-4">
                        <div className="flex items-center gap-2">
                            <p className="text-slate-400 text-xs font-bold uppercase tracking-wider">Budget vs Time</p>
                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${stats.burn_rate_status === 'Green' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                                {stats.burn_rate_status === 'Green' ? 'On Track' : 'Slow Down!'}
                            </span>
                        </div>
                        <div className="text-xs text-slate-500">
                            Day {stats.days_passed} of {stats.days_in_cycle}
                        </div>
                    </div>

                    <div className="relative h-6 bg-slate-800 rounded-full overflow-hidden mb-2">
                        <div 
                            className="absolute top-0 left-0 h-full bg-slate-600/30 border-r-2 border-slate-500/50"
                            style={{ width: `${timePassedPercent}%` }}
                        />
                        <div 
                            className={`absolute top-0 left-0 h-full transition-all duration-1000 ${budgetUsedPercent > timePassedPercent ? 'bg-red-500' : 'bg-emerald-500'}`}
                            style={{ width: `${budgetUsedPercent}%` }}
                        />
                    </div>
                    <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        <span>Spent: {budgetUsedPercent.toFixed(0)}%</span>
                        <span>Time: {timePassedPercent.toFixed(0)}%</span>
                    </div>
                </div>
            </div>

            {/* --- MIDDLE SECTION --- */}
            <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* 1. Spend Trend */}
                <div className="lg:col-span-2 bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="text-lg font-bold text-white flex items-center gap-2">
                            <TrendingUp size={18} className="text-blue-400" /> Spending Trend
                        </h3>
                    </div>
                    <div className="flex-1 min-h-0 w-full">
                        {trendData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={trendData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                                    <XAxis dataKey="day" stroke="#525252" fontSize={11} tickLine={false} axisLine={false} />
                                    <YAxis stroke="#525252" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(val) => `₹${val/1000}k`} />
                                    <Tooltip contentStyle={{ backgroundColor: '#111', border: '1px solid #333' }} formatter={(val) => `₹${formatCurrency(val)}`} />
                                    <Line type="monotone" dataKey="ideal" stroke="#475569" strokeDasharray="5 5" dot={false} strokeWidth={2} />
                                    <Line type="monotone" dataKey="actual" stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 6, strokeWidth: 0 }} />
                                </LineChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full flex items-center justify-center text-slate-600">No Data Yet</div>
                        )}
                    </div>
                </div>

                {/* 2. Top Categories */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col">
                    <h3 className="text-lg font-bold text-white mb-6">Top Categories</h3>
                    <div className="space-y-4 overflow-y-auto custom-scrollbar pr-2">
                        {breakdownData.length > 0 ? breakdownData.map((cat, idx) => (
                            <div key={idx} className="group">
                                <div className="flex justify-between text-xs mb-1">
                                    <span className="text-slate-300 font-medium">{cat.name}</span>
                                    <span className="text-white font-bold">₹{formatCurrency(cat.value)}</span>
                                </div>
                                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                                    <div className="h-full rounded-full" style={{ width: `${(cat.value / stats.total_spend) * 100}%`, backgroundColor: cat.color || '#94a3b8' }} />
                                </div>
                            </div>
                        )) : <div className="text-slate-600 text-sm text-center">No categories yet</div>}
                    </div>
                </div>
            </div>

            {/* --- RECENT TRANSACTIONS --- */}
            <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 shrink-0">
                <h3 className="text-lg font-bold text-white mb-4">Recent Transactions</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {recentTxns.map((txn) => (
                        <div key={txn.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5 hover:border-white/10 transition-colors">
                            <div className="flex items-center gap-3">
                                <div className="h-10 w-10 rounded-full flex items-center justify-center font-bold text-xs" style={{ backgroundColor: `${txn.category_color}20`, color: txn.category_color }}>
                                    {txn.merchant_name.charAt(0)}
                                </div>
                                <div>
                                    <p className="text-sm font-bold text-white truncate max-w-[120px]">{txn.merchant_name}</p>
                                    <p className="text-[10px] text-slate-500">{txn.txn_date}</p>
                                </div>
                            </div>
                            <span className={`text-sm font-bold ${getAmountColor(txn.payment_type)}`}>₹{formatCurrency(txn.amount)}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* --- SETTINGS MODAL --- */}
            {showSettings && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div className="bg-[#111] border border-white/10 p-6 rounded-xl w-full max-w-md shadow-2xl">
                        <div className="flex justify-between items-center mb-6 border-b border-white/10 pb-4">
                            <h3 className="text-xl font-bold text-white flex items-center gap-2">
                                <Settings className="text-blue-500" /> Dashboard Settings
                            </h3>
                            <button onClick={() => setShowSettings(false)}><X className="text-slate-400 hover:text-white" /></button>
                        </div>
                        <div className="space-y-6">
                            <div>
                                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">Budget Mode</label>
                                <div className="grid grid-cols-2 gap-2 p-1 bg-[#222] rounded-lg">
                                    <button onClick={() => setSettings({...settings, budget_type: 'FIXED'})} className={`py-2 text-sm font-bold rounded-md transition-all ${settings.budget_type === 'FIXED' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-white'}`}>Fixed Amount</button>
                                    <button onClick={() => setSettings({...settings, budget_type: 'PERCENTAGE'})} className={`py-2 text-sm font-bold rounded-md transition-all ${settings.budget_type === 'PERCENTAGE' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-white'}`}>% of Salary</button>
                                </div>
                            </div>
                            {settings.budget_type === 'FIXED' ? (
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">Monthly Budget Amount (₹)</label>
                                    <input type="number" className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:border-blue-500 outline-none" value={settings.budget_value} onChange={(e) => setSettings({...settings, budget_value: parseFloat(e.target.value)})} />
                                </div>
                            ) : (
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">Spendable % of Salary</label>
                                    <input type="number" className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:border-blue-500 outline-none" value={settings.budget_value} onChange={(e) => setSettings({...settings, budget_value: parseFloat(e.target.value)})} />
                                </div>
                            )}
                            <div>
                                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">Expected Salary Day</label>
                                <input type="number" min="1" max="31" className="w-full bg-[#1a1a1a] text-white p-3 rounded-lg border border-white/10 focus:border-blue-500 outline-none" value={settings.salary_day} onChange={(e) => setSettings({...settings, salary_day: parseInt(e.target.value)})} />
                            </div>
                            <button onClick={handleSaveSettings} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg transition-all shadow-lg flex items-center justify-center gap-2"><Save size={18} /> Save Preferences</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;