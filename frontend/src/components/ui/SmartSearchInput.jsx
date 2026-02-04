import React, { useState, useEffect, useCallback } from 'react';
import { Search, Sparkles, Zap } from 'lucide-react';
import debounce from 'lodash.debounce';

// Keywords that trigger smart search detection
const DATE_KEYWORDS = [
    'today', 'yesterday', 'week', 'month', 'year', 'last', 'this', 'past',
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december'
];

const AMOUNT_PATTERNS = [
    /over\s*₹?\s*\d+/i,
    /under\s*₹?\s*\d+/i,
    /above\s*₹?\s*\d+/i,
    /below\s*₹?\s*\d+/i,
    /more\s+than\s*₹?\s*\d+/i,
    /less\s+than\s*₹?\s*\d+/i,
    /₹\s*\d+/,
    /\d+\s*rupees?/i
];

const FILTER_PHRASES = [
    'expenses', 'spending', 'transactions', 'payments',
    'show me', 'find', 'search for', 'list',
    'debit', 'credit', 'income'
];

const SmartSearchInput = ({
    categories = [],
    onSearch,
    onSmartSearch,
    placeholder = "Search transactions or try 'food expenses over 500 last week'",
    className = ''
}) => {
    const [inputValue, setInputValue] = useState('');
    const [searchType, setSearchType] = useState('fuzzy'); // 'smart' or 'fuzzy'
    const [isFocused, setIsFocused] = useState(false);

    // Detect search type based on query content
    const detectSearchType = useCallback((query) => {
        if (!query || query.trim().length < 3) return 'fuzzy';

        const queryLower = query.toLowerCase();

        // Check for date keywords
        for (const keyword of DATE_KEYWORDS) {
            if (queryLower.includes(keyword)) return 'smart';
        }

        // Check for amount patterns
        for (const pattern of AMOUNT_PATTERNS) {
            if (pattern.test(queryLower)) return 'smart';
        }

        // Check for category names
        for (const cat of categories) {
            if (queryLower.includes(cat.name.toLowerCase())) return 'smart';
        }

        // Check for filter phrases
        for (const phrase of FILTER_PHRASES) {
            if (queryLower.includes(phrase)) return 'smart';
        }

        return 'fuzzy';
    }, [categories]);

    // Debounced search handler
    const debouncedSearch = useCallback(
        debounce((value, type) => {
            if (type === 'smart' && onSmartSearch) {
                onSmartSearch(value);
            } else if (onSearch) {
                onSearch(value);
            }
        }, 600),
        [onSearch, onSmartSearch]
    );

    // Handle input change
    const handleChange = (e) => {
        const value = e.target.value;
        setInputValue(value);

        const detectedType = detectSearchType(value);
        setSearchType(detectedType);

        debouncedSearch(value, detectedType);
    };

    // Handle Enter key for immediate search
    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            debouncedSearch.cancel();
            if (searchType === 'smart' && onSmartSearch) {
                onSmartSearch(inputValue);
            } else if (onSearch) {
                onSearch(inputValue);
            }
        }
    };

    const isSmartMode = searchType === 'smart' && inputValue.trim().length >= 3;

    return (
        <div className={`relative group ${className}`}>
            {/* Search Icon or Mode Indicator */}
            <div className="absolute left-3 top-1/2 -translate-y-1/2 transition-colors">
                {isSmartMode ? (
                    <Sparkles
                        size={16}
                        className="text-purple-400"
                    />
                ) : (
                    <Search
                        size={16}
                        className={`${isFocused ? 'text-teal-400' : 'text-slate-500'} transition-colors`}
                    />
                )}
            </div>

            {/* Input Field */}
            <input
                type="text"
                value={inputValue}
                onChange={handleChange}
                onKeyDown={handleKeyDown}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setIsFocused(false)}
                placeholder={placeholder}
                className={`w-full bg-[#1e1e1e] rounded-lg py-2 pl-10 pr-20 text-sm text-white placeholder:text-slate-600 focus:outline-none transition-all ${
                    isSmartMode
                        ? 'border border-purple-500/50 focus:border-purple-500'
                        : 'border border-white/10 focus:border-teal-500/50'
                }`}
            />

            {/* Mode Badge */}
            {inputValue.trim().length >= 3 && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {isSmartMode ? (
                        <span className="flex items-center gap-1 px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-[10px] font-bold uppercase">
                            <Sparkles size={10} />
                            AI
                        </span>
                    ) : (
                        <span className="flex items-center gap-1 px-2 py-0.5 bg-teal-500/20 text-teal-400 rounded text-[10px] font-bold uppercase">
                            <Zap size={10} />
                            Fuzzy
                        </span>
                    )}
                </div>
            )}

            {/* Smart Search Hint */}
            {isFocused && inputValue.length === 0 && (
                <div className="absolute top-full left-0 mt-2 p-3 bg-[#1a1a1a] border border-white/10 rounded-lg shadow-xl z-50 w-80">
                    <p className="text-xs text-slate-400 mb-2">Try natural language search:</p>
                    <div className="space-y-1.5">
                        <p className="text-xs text-slate-500">
                            <span className="text-purple-400">"food expenses over 500"</span>
                        </p>
                        <p className="text-xs text-slate-500">
                            <span className="text-purple-400">"last week shopping"</span>
                        </p>
                        <p className="text-xs text-slate-500">
                            <span className="text-purple-400">"swiggy transactions this month"</span>
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
};

export default SmartSearchInput;
