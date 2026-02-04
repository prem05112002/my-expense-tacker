import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, X } from 'lucide-react';

const CategoryMultiselect = ({
    categories = [],
    selectedIds = [],
    onChange,
    className = ''
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleToggle = (categoryId) => {
        const newSelection = selectedIds.includes(categoryId)
            ? selectedIds.filter(id => id !== categoryId)
            : [...selectedIds, categoryId];
        onChange(newSelection);
    };

    const handleClear = (e) => {
        e.stopPropagation();
        onChange([]);
    };

    const selectedCount = selectedIds.length;

    return (
        <div className={`relative ${className}`} ref={dropdownRef}>
            {/* Header Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`flex items-center gap-2 p-4 text-xs font-bold uppercase tracking-widest transition-colors ${
                    selectedCount > 0
                        ? 'text-purple-400'
                        : 'text-slate-500 hover:text-slate-300'
                }`}
            >
                <span>Category</span>
                {selectedCount > 0 && (
                    <span className="flex items-center gap-1">
                        <span className="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded text-[10px] font-bold">
                            {selectedCount}
                        </span>
                        <button
                            onClick={handleClear}
                            className="p-0.5 hover:bg-white/10 rounded"
                            title="Clear selection"
                        >
                            <X size={12} />
                        </button>
                    </span>
                )}
                <ChevronDown
                    size={14}
                    className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
            </button>

            {/* Dropdown */}
            {isOpen && (
                <div className="absolute top-full left-0 mt-1 w-64 bg-[#1a1a1a] border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
                    <div className="p-2 border-b border-white/5 flex justify-between items-center">
                        <span className="text-xs text-slate-500 px-2">
                            {selectedCount > 0 ? `${selectedCount} selected` : 'Select categories'}
                        </span>
                        {selectedCount > 0 && (
                            <button
                                onClick={handleClear}
                                className="text-xs text-slate-500 hover:text-white px-2 py-1 hover:bg-white/5 rounded transition-colors"
                            >
                                Clear all
                            </button>
                        )}
                    </div>
                    <div className="max-h-64 overflow-y-auto custom-scrollbar">
                        {categories.map((category) => {
                            const isSelected = selectedIds.includes(category.id);
                            return (
                                <button
                                    key={category.id}
                                    onClick={() => handleToggle(category.id)}
                                    className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors ${
                                        isSelected
                                            ? 'bg-purple-500/10'
                                            : 'hover:bg-white/5'
                                    }`}
                                >
                                    <div
                                        className={`w-5 h-5 rounded flex items-center justify-center border transition-colors ${
                                            isSelected
                                                ? 'border-purple-500 bg-purple-500'
                                                : 'border-white/20 bg-transparent'
                                        }`}
                                    >
                                        {isSelected && <Check size={12} className="text-white" />}
                                    </div>
                                    <div className="flex items-center gap-2 flex-1">
                                        <div
                                            className="w-3 h-3 rounded-full"
                                            style={{ backgroundColor: category.color }}
                                        />
                                        <span className={`text-sm ${
                                            isSelected ? 'text-white font-medium' : 'text-slate-300'
                                        }`}>
                                            {category.name}
                                        </span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default CategoryMultiselect;
