import React from 'react';

const DateFilter = ({ label, value, onChange }) => (
    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg flex items-center px-3 py-2 gap-2 focus-within:border-teal-500/50 transition-colors h-10">
        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider whitespace-nowrap">
            {label}:
        </span>
        <input 
            type="date" 
            value={value} 
            onChange={(e) => onChange(e.target.value)} 
            className="bg-transparent border-none text-white text-xs focus:ring-0 p-0 w-28 font-mono [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50 hover:[&::-webkit-calendar-picker-indicator]:opacity-100"
        />
    </div>
);

export default DateFilter;