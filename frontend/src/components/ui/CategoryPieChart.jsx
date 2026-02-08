import React from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { formatCurrency } from '../../utils/formatters';

const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
        const item = payload[0].payload;
        return (
            <div className="bg-[#1a1a1a] border border-white/10 rounded-lg p-3 shadow-xl">
                <p className="text-white font-bold text-sm">{item.name}</p>
                <p className="text-slate-300 text-xs mt-1">
                    Amount: <span className="text-white font-mono">₹{formatCurrency(item.value)}</span>
                </p>
                <p className="text-slate-300 text-xs">
                    Share: <span className="text-white font-mono">{item.percent}%</span>
                </p>
            </div>
        );
    }
    return null;
};

const renderLegend = (props) => {
    const { payload } = props;
    return (
        <div className="flex flex-col gap-2 text-xs max-h-[200px] overflow-y-auto custom-scrollbar pr-2">
            {payload.map((entry, index) => (
                <div key={`legend-${index}`} className="flex items-center gap-2">
                    <div
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: entry.color }}
                    />
                    <span className="text-slate-300 truncate max-w-[100px]" title={entry.value}>
                        {entry.value}
                    </span>
                </div>
            ))}
        </div>
    );
};

const CategoryPieChart = ({ data, totalSpend }) => {
    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                No spending data yet
            </div>
        );
    }

    // Calculate percentage for each category
    const chartData = data.map(cat => ({
        ...cat,
        percent: totalSpend > 0 ? ((cat.value / totalSpend) * 100).toFixed(1) : 0
    }));

    return (
        <ResponsiveContainer width="100%" height="100%">
            <PieChart>
                <Pie
                    data={chartData}
                    cx="40%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                    nameKey="name"
                    stroke="none"
                >
                    {chartData.map((entry, index) => (
                        <Cell
                            key={`cell-${index}`}
                            fill={entry.color || '#94a3b8'}
                            className="hover:opacity-80 transition-opacity cursor-pointer"
                        />
                    ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend
                    layout="vertical"
                    align="right"
                    verticalAlign="middle"
                    content={renderLegend}
                    wrapperStyle={{ paddingLeft: '20px' }}
                />
            </PieChart>
        </ResponsiveContainer>
    );
};

export default CategoryPieChart;
