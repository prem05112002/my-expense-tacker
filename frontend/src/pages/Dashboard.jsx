import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import { Wallet, Receipt, ArrowUpRight, ArrowDownLeft } from 'lucide-react';
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

import { getAmountColor, formatCurrency } from '../utils/formatters';

const Dashboard = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await api.get('/dashboard');
                setStats(res.data);
            } catch (error) {
                console.error("Error fetching dashboard data", error);
            } finally {
                setLoading(false);
            }
        };
        fetchStats();
    }, []);

    if (loading) return <div className="text-white p-10 animate-pulse">Loading Dashboard...</div>;

    // Process Data for Charts
    const chartData = stats?.category_breakdown?.map((item) => ({
        name: item.name.substring(0, 3).toUpperCase(),
        amount: item.value,
        color: item.fill || '#4ade80' 
    })) || [];

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] gap-6 text-white font-sans overflow-hidden">
            
            {/* --- TOP ROW: KPI CARDS --- */}
            <div className="shrink-0 grid grid-cols-1 md:grid-cols-3 gap-6">
                <KPICard 
                    label="Total Spend" 
                    value={`₹${formatCurrency(stats?.total_spend)}`} 
                    icon={Wallet} 
                    iconColor="text-indigo-400" 
                    iconBg="bg-indigo-500/20" 
                />
                <KPICard 
                    label="Uncategorized" 
                    value={stats?.uncategorized_count || 0} 
                    icon={Receipt} 
                    iconColor="text-orange-400" 
                    iconBg="bg-orange-500/20" 
                />
                <KPICard 
                    label="Budget Status" 
                    value="Good" 
                    valueColor="text-emerald-400"
                    icon={ArrowUpRight} 
                    iconColor="text-emerald-400" 
                    iconBg="bg-emerald-500/20" 
                />
            </div>

            {/* --- BOTTOM ROW --- */}
            <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* 1. SPEND ANALYSIS */}
                <div className="lg:col-span-2 bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col">
                    <h3 className="text-lg font-bold text-white mb-6">Category Breakdown</h3>
                    <div className="flex-1 min-h-0 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartData} barSize={40}>
                                <XAxis dataKey="name" stroke="#525252" fontSize={11} tickLine={false} axisLine={false} dy={10} />
                                <Tooltip contentStyle={{ backgroundColor: '#000', borderColor: '#333', borderRadius: '8px', color: '#fff' }} itemStyle={{ color: '#fff' }} cursor={{fill: 'rgba(255,255,255,0.05)'}} />
                                <Bar dataKey="amount" radius={[6, 6, 0, 0]}>
                                    {chartData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* 2. RECENT TRANSACTIONS */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 flex flex-col min-h-0">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h3 className="text-lg font-bold text-white">Recent Activity</h3>
                        <Link to="/transactions" className="text-xs text-teal-400 hover:text-teal-300 font-bold uppercase tracking-wide">View All</Link>
                    </div>

                    <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-3">
                        {stats?.recent_transactions?.length === 0 ? (
                            <div className="text-slate-500 text-center py-10 text-sm">No recent transactions</div>
                        ) : (
                            stats?.recent_transactions?.map((txn) => (
                                <div key={txn.id} className="group flex items-center justify-between p-3 rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/5">
                                    <div className="flex items-center gap-3 overflow-hidden">
                                        <div className={`h-10 w-10 shrink-0 rounded-full flex items-center justify-center ${txn.payment_type === 'CREDIT' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                                            {txn.payment_type === 'CREDIT' ? <ArrowDownLeft size={18} /> : <ArrowUpRight size={18} />}
                                        </div>
                                        <div className="min-w-0">
                                            <p className="text-sm font-bold text-slate-200 truncate">{txn.merchant_name}</p>
                                            <p className="text-xs text-slate-500 truncate">{txn.category_name}</p>
                                        </div>
                                    </div>
                                    <div className="text-right shrink-0">
                                        {/* ✅ Use Helper */}
                                        <p className={`text-sm font-mono font-bold ${getAmountColor(txn.payment_type)}`}>
                                            ₹{formatCurrency(txn.amount)}
                                        </p>
                                        <p className="text-[10px] text-slate-600 font-bold uppercase tracking-wider">{txn.payment_mode}</p>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

// Internal Sub-component for Dashboard Cards (Optional extraction)
const KPICard = ({ label, value, icon: Icon, iconColor, iconBg, valueColor = "text-white" }) => (
    <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 flex items-center justify-between">
        <div>
            <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">{label}</p>
            <h2 className={`text-3xl font-bold ${valueColor}`}>{value}</h2>
        </div>
        <div className={`h-12 w-12 rounded-full flex items-center justify-center ${iconBg} ${iconColor}`}>
            <Icon size={24} />
        </div>
    </div>
);

export default Dashboard;