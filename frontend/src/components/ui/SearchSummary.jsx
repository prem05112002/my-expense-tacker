import React from 'react';
import { Sparkles, X, TrendingDown, TrendingUp } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';

const SearchSummary = ({
    totalRecords,
    debitSum = 0,
    creditSum = 0,
    isSmartSearch = false,
    parsedFilters = null,
    onClearFilters = null
}) => {
    // Calculate net amount
    const netAmount = creditSum - debitSum;
    const isNetPositive = netAmount >= 0;

    // Don't show if no filters are active
    const hasActiveFilters = isSmartSearch ||
        (parsedFilters && (
            parsedFilters.categories?.length > 0 ||
            parsedFilters.amount_min != null ||
            parsedFilters.amount_max != null ||
            parsedFilters.date_from ||
            parsedFilters.date_to ||
            parsedFilters.payment_type ||
            parsedFilters.merchant_pattern
        ));

    if (!hasActiveFilters && totalRecords === 0) {
        return null;
    }

    const renderFilterTags = () => {
        if (!parsedFilters || !isSmartSearch) return null;

        const tags = [];

        if (parsedFilters.categories?.length > 0) {
            tags.push(
                <span key="categories" className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">
                    {parsedFilters.categories.join(', ')}
                </span>
            );
        }

        if (parsedFilters.amount_min != null || parsedFilters.amount_max != null) {
            let amountText = '';
            if (parsedFilters.amount_min != null && parsedFilters.amount_max != null) {
                amountText = `₹${parsedFilters.amount_min} - ₹${parsedFilters.amount_max}`;
            } else if (parsedFilters.amount_min != null) {
                amountText = `> ₹${parsedFilters.amount_min}`;
            } else {
                amountText = `< ₹${parsedFilters.amount_max}`;
            }
            tags.push(
                <span key="amount" className="px-2 py-1 bg-amber-500/20 text-amber-400 rounded text-xs">
                    {amountText}
                </span>
            );
        }

        if (parsedFilters.date_from || parsedFilters.date_to) {
            let dateText = '';
            if (parsedFilters.date_from && parsedFilters.date_to) {
                dateText = `${parsedFilters.date_from} to ${parsedFilters.date_to}`;
            } else if (parsedFilters.date_from) {
                dateText = `From ${parsedFilters.date_from}`;
            } else {
                dateText = `Until ${parsedFilters.date_to}`;
            }
            tags.push(
                <span key="date" className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">
                    {dateText}
                </span>
            );
        }

        if (parsedFilters.payment_type) {
            tags.push(
                <span key="type" className={`px-2 py-1 rounded text-xs ${
                    parsedFilters.payment_type === 'DEBIT'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-emerald-500/20 text-emerald-400'
                }`}>
                    {parsedFilters.payment_type}
                </span>
            );
        }

        if (parsedFilters.merchant_pattern) {
            tags.push(
                <span key="merchant" className="px-2 py-1 bg-slate-500/20 text-slate-400 rounded text-xs">
                    "{parsedFilters.merchant_pattern}"
                </span>
            );
        }

        return tags.length > 0 ? (
            <div className="flex flex-wrap gap-2 mt-2">
                {tags}
            </div>
        ) : null;
    };

    return (
        <div className="px-6 py-3 bg-[#0f0f0f] border-b border-white/5">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    {isSmartSearch && (
                        <div className="flex items-center gap-1.5 text-purple-400">
                            <Sparkles size={14} />
                            <span className="text-xs font-medium">AI Search</span>
                        </div>
                    )}
                    <div className="flex items-center gap-3 text-sm">
                        <span className="text-slate-400">
                            Found <span className="text-white font-semibold">{totalRecords}</span> transactions
                        </span>

                        <span className="text-slate-600">|</span>

                        {/* Debit Sum */}
                        <div className="flex items-center gap-1.5">
                            <TrendingDown size={14} className="text-red-400" />
                            <span className="text-slate-400">Spent:</span>
                            <span className="text-red-400 font-semibold font-mono">
                                {formatCurrency(debitSum)}
                            </span>
                        </div>

                        <span className="text-slate-600">|</span>

                        {/* Credit Sum */}
                        <div className="flex items-center gap-1.5">
                            <TrendingUp size={14} className="text-emerald-400" />
                            <span className="text-slate-400">Received:</span>
                            <span className="text-emerald-400 font-semibold font-mono">
                                {formatCurrency(creditSum)}
                            </span>
                        </div>

                        <span className="text-slate-600">|</span>

                        {/* Net Amount */}
                        <div className="flex items-center gap-1.5">
                            <span className="text-slate-400">
                                {isNetPositive ? 'Net Gain:' : 'Net Spend:'}
                            </span>
                            <span className={`font-bold font-mono ${
                                isNetPositive ? 'text-emerald-400' : 'text-red-400'
                            }`}>
                                {isNetPositive ? '+' : '-'}{formatCurrency(Math.abs(netAmount))}
                            </span>
                        </div>
                    </div>
                </div>

                {onClearFilters && hasActiveFilters && (
                    <button
                        onClick={onClearFilters}
                        className="flex items-center gap-1.5 px-2 py-1 text-xs text-slate-500 hover:text-white hover:bg-white/5 rounded transition-colors"
                    >
                        <X size={12} />
                        Clear
                    </button>
                )}
            </div>
            {renderFilterTags()}
        </div>
    );
};

export default SearchSummary;
