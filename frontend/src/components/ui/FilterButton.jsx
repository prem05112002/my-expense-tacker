import React from 'react';

const FilterButton = ({ active, onClick, label, icon: Icon, colorClass, bgClass }) => (
    <button 
        onClick={onClick} 
        className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-[11px] font-bold transition-all border ${
            active 
                ? `${bgClass || 'bg-slate-700 border-slate-600'} ${colorClass || 'text-white'} shadow-sm` 
                : 'bg-transparent border-transparent text-slate-500 hover:text-slate-300 hover:bg-white/5'
        }`}
    >
        {Icon && <Icon size={12} />}
        {label}
    </button>
);

export default FilterButton;