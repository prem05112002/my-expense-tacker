import React, { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import {
    TrendingUp, TrendingDown, Settings, Calendar, RefreshCw
} from 'lucide-react';
import { getAmountColor, formatCurrency } from '../utils/formatters';
import { DashboardSkeleton } from '../components/ui/CardSkeleton';
import EmbeddedChat from '../components/EmbeddedChat';
import CategoryPieChart from '../components/ui/CategoryPieChart';
import GoalsCard from '../components/ui/GoalsCard';
import { useToast } from '../contexts/ToastContext';

const Dashboard = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [cycleOffset, setCycleOffset] = useState(0);
    const [syncing, setSyncing] = useState(false);
    const [syncResult, setSyncResult] = useState(null);
    const budgetAlertShown = useRef(false);
    const toast = useToast();

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

    // Refresh stats without showing loading skeleton (preserves chat state)
    const refreshStats = async () => {
        try {
            const res = await api.get(`/dashboard/?offset=${cycleOffset}`);
            setStats(res.data);
        } catch (error) {
            console.error("Error refreshing dashboard data", error);
        }
    };

    useEffect(() => {
        fetchStats();
    }, [cycleOffset]);

    // Budget alert toast (show once per session when >= 80%)
    useEffect(() => {
        if (stats && stats.show_budget_alert && !budgetAlertShown.current && cycleOffset === 0) {
            toast.warning(`Budget alert: You've used ${stats.budget_used_percent}% of your budget!`);
            budgetAlertShown.current = true;
        }
    }, [stats, cycleOffset, toast]);

    if (loading) return <DashboardSkeleton />;
    if (!stats) return <div className="p-10 text-white">Failed to load data.</div>;

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
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col justify-center">
                    <div className="flex justify-between items-center mb-3">
                        <div className="flex items-center gap-2">
                            <p className="text-slate-400 text-xs font-bold uppercase tracking-wider">
                                {isPastCycle ? "Status" : "Burn Rate"}
                            </p>
                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${burnStatusColor}`}>
                                {burnStatusText}
                            </span>
                        </div>
                    </div>

                    <div className="relative h-4 bg-slate-800 rounded-full overflow-hidden mb-2">
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
                        <span>Day {stats.days_passed}/{stats.days_in_cycle}</span>
                    </div>
                </div>

                {/* 4. Little Goals */}
                <GoalsCard goals={stats.goals || []} />
            </div>
            
            {/* --- EMBEDDED CHAT (Financial Assistant) --- */}
            <EmbeddedChat />

            {/* --- CATEGORIES & RECENT TRANSACTIONS --- */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 shrink-0">
                {/* Category Breakdown Pie Chart */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col">
                    <h3 className="text-lg font-bold text-white mb-4">Spending by Category</h3>
                    <div className="flex-1 min-h-[280px]">
                        <CategoryPieChart data={breakdownData} totalSpend={stats.total_spend} />
                    </div>
                </div>

                {/* Recent Transactions */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col">
                    <h3 className="text-lg font-bold text-white mb-4">Recent Transactions</h3>
                    <div className="space-y-3 overflow-y-auto custom-scrollbar pr-2 flex-1 max-h-[300px]">
                        {recentTxns.map((txn) => (
                            <div key={txn.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5 hover:border-white/10 transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className="h-10 w-10 rounded-full flex items-center justify-center font-bold text-xs" style={{ backgroundColor: `${txn.category_color}20`, color: txn.category_color }}>
                                        {txn.merchant_name.charAt(0)}
                                    </div>
                                    <div>
                                        <p className="text-sm font-bold text-white truncate max-w-[150px]">{txn.merchant_name}</p>
                                        <p className="text-[10px] text-slate-500">{txn.txn_date}</p>
                                    </div>
                                </div>
                                <span className={`text-sm font-bold ${getAmountColor(txn.payment_type)}`}>₹{formatCurrency(txn.amount)}</span>
                            </div>
                        ))}
                    </div>
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