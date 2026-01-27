import React from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

const SortableHeader = ({ label, active, direction, onClick, align = "left" }) => (
    <th 
        className={`p-4 cursor-pointer hover:bg-white/5 transition-colors select-none bg-[#0b0b0b] ${align === "right" ? "text-right" : "text-left"}`} 
        onClick={onClick}
    >
        <div className={`flex items-center gap-2 ${align === "right" ? "justify-end" : "justify-start"}`}>
            <span className={`text-xs font-bold uppercase tracking-widest ${active ? "text-teal-400" : "text-slate-500"}`}>
                {label}
            </span>
            <div className="flex flex-col">
                {!active && <ArrowUpDown size={12} className="text-slate-700" />}
                {active && direction === 'asc' && <ArrowUp size={12} className="text-teal-400" />}
                {active && direction === 'desc' && <ArrowDown size={12} className="text-teal-400" />}
            </div>
        </div>
    </th>
);

export default SortableHeader;