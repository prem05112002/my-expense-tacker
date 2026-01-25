import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const data = [
  { name: 'Mon', spend: 4000 },
  { name: 'Tue', spend: 3000 },
  { name: 'Wed', spend: 2000 },
  { name: 'Thu', spend: 2780 },
  { name: 'Fri', spend: 1890 },
  { name: 'Sat', spend: 2390 },
  { name: 'Sun', spend: 3490 },
];

const Dashboard = () => {
    return (
        <div className="space-y-6">
            <h2 className="text-3xl font-bold">Dashboard</h2>
            
            {/* Stats Row */}
            <div className="grid grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
                    <p className="text-sm text-slate-500">Total Spent (Month)</p>
                    <p className="text-3xl font-bold text-slate-800">₹45,230</p>
                </div>
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
                    <p className="text-sm text-slate-500">Uncategorized</p>
                    <p className="text-3xl font-bold text-red-500">12</p>
                </div>
            </div>

            {/* Chart */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-80">
                <h3 className="text-lg font-semibold mb-4">Weekly Spend Trend</h3>
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Area type="monotone" dataKey="spend" stroke="#2563eb" fill="#3b82f6" fillOpacity={0.1} />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default Dashboard;