import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import {
    Wallet, TrendingUp, TrendingDown, Settings, Calendar, PiggyBank, ArrowRight, AlertTriangle, RefreshCw
} from 'lucide-react';
import { 
    LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { getAmountColor, formatCurrency } from '../utils/formatters';
import { DashboardSkeleton } from '../components/ui/CardSkeleton';

const Dashboard = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [cycleOffset, setCycleOffset] = useState(0);
    const [syncing, setSyncing] = useState(false);
    const [syncResult, setSyncResult] = useState(null);

    const handleSync = async () => {
        if (syncing) return;

        setSyncing(true);
        setSyncResult(null);

        try {
            const res = await api.post('/sync/trigger');
            setSyncResult(res.data);

            // Refresh dashboard data after sync completes
            if (res.data.status === 'completed' && res.data.transactions_saved > 0) {
                await fetchStats();
            }
        } catch (error) {
            console.error("Sync failed:", error);
            setSyncResult({ status: 'failed', error: error.message || 'Sync failed' });
        } finally {
            setSyncing(false);
        }
    };

    const fetchStats = async () => {
        try {
            setLoading(true);
            const res = await api.get(`/dashboard/?offset=${cycleOffset}`);
            setStats(res.data);
        } catch (error) {
            console.error("Error fetching dashboard data", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStats();
    }, [cycleOffset]);

    if (loading) return <DashboardSkeleton />;
    if (!stats) return <div className="p-10 text-white">Failed to load data.</div>;

    const trendData = stats.spending_trend || [];
    const breakdownData = stats.category_breakdown || [];
    const recentTxns = stats.recent_transactions || [];
    
    // Calculations
    let budgetUsedPercent = 0;
    if (stats.total_budget > 0) {
        budgetUsedPercent = Math.min((stats.total_spend / stats.total_budget) * 100, 100);
    } else if (stats.total_spend > 0) {
        // Budget is 0 but we spent money -> 100% used (Critical)
        budgetUsedPercent = 100;
    }

    const timePassedPercent = Math.min((stats.days_passed / stats.days_in_cycle) * 100, 100);
    
    const isSpendingMore = stats.spend_diff_percent > 0;
    const spendDiffAbs = Math.abs(stats.spend_diff_percent).toFixed(1);
    
    const isPastCycle = stats.days_left === 0 || cycleOffset > 0;
    
    // Determine Status Text
    let burnStatusText = "On Track";
    let burnStatusColor = "bg-emerald-500/20 text-emerald-400";
    
    if (stats.total_budget === 0 && stats.total_spend > 0) {
        burnStatusText = "Unbudgeted";
        burnStatusColor = "bg-red-500/20 text-red-400";
    } else if (budgetUsedPercent > 100) {
         burnStatusText = "Over Budget";
         burnStatusColor = "bg-red-500/20 text-red-400";
    } else if (budgetUsedPercent > timePassedPercent + 15) { // 15% buffer
         burnStatusText = "High Burn";
         burnStatusColor = "bg-yellow-500/20 text-yellow-400";
    }

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] gap-6 text-white font-sans overflow-y-auto custom-scrollbar p-1">
            
            {/* --- HEADER --- */}
            <div className="flex flex-col md:flex-row justify-between md:items-end gap-4 shrink-0">
                <div>
                    <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                    <div className="flex items-center gap-2 text-sm text-slate-500 mt-1">
                        <Calendar size={14} />
                        <span>Cycle: <span className="text-white font-mono">{stats.cycle_start}</span> to <span className="text-white font-mono">{stats.cycle_end}</span></span>
                    </div>
                </div>
                
                <div className="flex items-center gap-3">
                    <div className="relative">
                        <select 
                            className="bg-[#1a1a1a] text-white border border-white/10 rounded-lg px-4 py-2 text-sm font-bold appearance-none cursor-pointer hover:border-blue-500/50 outline-none pr-8"
                            value={cycleOffset}
                            onChange={(e) => setCycleOffset(parseInt(e.target.value))}
                        >
                            <option value={0}>Current Cycle</option>
                            <option value={1}>Last Month</option>
                            <option value={2}>2 Months Ago</option>
                            <option value={3}>3 Months Ago</option>
                        </select>
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                            <ChevronDown size={14} className="text-slate-400" />
                        </div>
                    </div>

                    <button
                        onClick={handleSync}
                        disabled={syncing}
                        className="bg-[#1a1a1a] hover:bg-[#252525] text-white p-2 rounded-lg border border-white/10 transition-all hover:border-teal-500/50 disabled:opacity-50 disabled:cursor-not-allowed relative group"
                        title="Sync emails"
                    >
                        <RefreshCw size={20} className={`text-teal-400 ${syncing ? 'animate-spin' : ''}`} />
                        {syncResult && syncResult.status === 'completed' && syncResult.transactions_saved > 0 && (
                            <span className="absolute -top-1 -right-1 bg-teal-500 text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                                {syncResult.transactions_saved}
                            </span>
                        )}
                    </button>

                    <Link to="/profile" className="bg-[#1a1a1a] hover:bg-[#252525] text-white p-2 rounded-lg border border-white/10 transition-all hover:border-blue-500/50">
                        <Settings size={20} className="text-blue-400" />
                    </Link>
                </div>
            </div>

            {/* --- HERO CARDS --- */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 shrink-0">
                
                {/* 1. Total Spend */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 relative overflow-hidden group">
                    <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">Total Spend</p>
                    <h2 className="text-3xl font-bold text-white">₹{formatCurrency(stats.total_spend)}</h2>
                    <div className={`mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${isSpendingMore ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                        {isSpendingMore ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                        {spendDiffAbs}% vs last cycle
                    </div>
                </div>

                {/* 2. Remaining Budget / Savings (Dynamic Label) */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 relative overflow-hidden">
                    <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                        {isPastCycle ? (stats.budget_remaining >= 0 ? "Net Savings" : "Deficit") : "Remaining Budget"}
                    </p>
                    
                    <h2 className={`text-3xl font-bold ${stats.budget_remaining < 0 ? 'text-red-500' : 'text-emerald-400'}`}>
                        {stats.budget_remaining < 0 ? '-' : ''}₹{formatCurrency(Math.abs(stats.budget_remaining))}
                    </h2>
                    
                    <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
                        {isPastCycle ? (
                            <span className="text-slate-400 italic">Cycle Completed</span>
                        ) : (
                            <>
                                <span className="text-emerald-400 font-bold">₹{formatCurrency(stats.safe_to_spend_daily)}</span> safe / day
                            </>
                        )}
                    </p>
                </div>

                {/* 3. Burn Rate / Cycle Status */}
                <div className="md:col-span-2 bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col justify-center">
                    <div className="flex justify-between items-center mb-4">
                        <div className="flex items-center gap-2">
                            <p className="text-slate-400 text-xs font-bold uppercase tracking-wider">
                                {isPastCycle ? "Final Cycle Status" : "Burn Rate"}
                            </p>
                            {/* ✅ Updated Status Pill */}
                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${burnStatusColor}`}>
                                {burnStatusText}
                            </span>
                        </div>
                        <div className="text-xs text-slate-500">Day {stats.days_passed} of {stats.days_in_cycle}</div>
                    </div>

                    <div className="relative h-6 bg-slate-800 rounded-full overflow-hidden mb-2">
                         <div 
                            className="absolute top-0 left-0 h-full bg-slate-600/30 border-r-2 border-slate-500/50"
                            style={{ width: `${timePassedPercent}%` }}
                        />
                        <div 
                            className={`absolute top-0 left-0 h-full transition-all duration-1000 ${budgetUsedPercent >= 100 || (stats.total_budget === 0 && stats.total_spend > 0) ? 'bg-red-500' : 'bg-emerald-500'}`}
                            style={{ width: `${budgetUsedPercent}%` }}
                        />
                    </div>
                    
                    <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        <span>Used: {budgetUsedPercent.toFixed(0)}%</span>
                        <span>Time: {timePassedPercent.toFixed(0)}%</span>
                    </div>
                </div>
            </div>
            
            {/* ... Rest of the component (Graph, Categories, etc.) remains same ... */}
            
            {/* --- GRAPH & CATEGORIES --- */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 shrink-0">
                <div className="lg:col-span-2 bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="text-lg font-bold text-white flex items-center gap-2">
                            <TrendingUp size={18} className="text-blue-400" /> Spending Trend
                        </h3>
                        <div className="flex items-center gap-4 text-xs font-bold">
                            <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-blue-500"></div>This Cycle</div>
                            <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-slate-500"></div>Last Cycle</div>
                        </div>
                    </div>
                    
                    <div className="h-[300px] w-full relative">
                        <div className="absolute inset-0 min-w-0"> 
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={trendData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                                    <XAxis dataKey="day" stroke="#525252" fontSize={11} tickLine={false} axisLine={false} />
                                    <YAxis stroke="#525252" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(val) => `₹${val/1000}k`} />
                                    <Tooltip 
                                        contentStyle={{ backgroundColor: '#111', border: '1px solid #333' }} 
                                        labelFormatter={(label, payload) => payload?.[0]?.payload?.date || `Day ${label}`}
                                        formatter={(val, name) => [
                                            `₹${formatCurrency(val)}`, 
                                            name === 'actual' ? 'This Cycle' : name === 'previous' ? 'Last Cycle' : 'Ideal'
                                        ]}
                                    />
                                    <Line type="monotone" dataKey="ideal" stroke="#334155" strokeDasharray="5 5" dot={false} strokeWidth={2} activeDot={false} />
                                    <Line type="monotone" dataKey="previous" stroke="#64748b" strokeWidth={2} dot={false} strokeOpacity={0.6} activeDot={{ r: 4 }} />
                                    <Line type="monotone" dataKey="actual" stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 6, strokeWidth: 0 }} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col h-[380px]">
                    <h3 className="text-lg font-bold text-white mb-6">Top Categories</h3>
                    <div className="space-y-4 overflow-y-auto custom-scrollbar pr-2 flex-1">
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
                        )) : <div className="text-slate-600 text-sm text-center mt-10">No categories yet</div>}
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
        </div>
    );
};

// Simple Icon component helper if ChevronDown wasn't imported
const ChevronDown = ({ size, className }) => (
    <svg 
        xmlns="http://www.w3.org/2000/svg" 
        width={size} 
        height={size} 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
        className={className}
    >
        <path d="m6 9 6 6 6-6"/>
    </svg>
);

export default Dashboard;