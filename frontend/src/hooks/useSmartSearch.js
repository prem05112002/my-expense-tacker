import { useState, useCallback } from 'react';
import api from '../api/axios';

/**
 * Custom hook for smart search functionality.
 * Handles both fuzzy (simple) and smart (AI-powered) search modes.
 */
const useSmartSearch = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [searchType, setSearchType] = useState('fuzzy');
    const [parsedFilters, setParsedFilters] = useState(null);

    /**
     * Execute a smart search query.
     * @param {string} query - Natural language search query
     * @param {object} options - Search options (page, limit, sort)
     * @returns {Promise<object>} Search results with parsed filters
     */
    const executeSmartSearch = useCallback(async (query, options = {}) => {
        if (!query || query.trim().length < 2) {
            return null;
        }

        setIsLoading(true);
        setError(null);

        try {
            const response = await api.post('/transactions/smart-search', {
                query: query.trim(),
                page: options.page || 1,
                limit: options.limit || 15,
                sort_by: options.sort_by || 'txn_date',
                sort_order: options.sort_order || 'desc'
            });

            const data = response.data;
            setSearchType(data.search_type || 'fuzzy');
            setParsedFilters(data.parsed_filters || null);

            return {
                transactions: data.data || [],
                total: data.total || 0,
                totalPages: data.total_pages || 0,
                debitSum: data.debit_sum || 0,
                creditSum: data.credit_sum || 0,
                page: data.page || 1,
                searchType: data.search_type || 'fuzzy',
                parsedFilters: data.parsed_filters || null
            };
        } catch (err) {
            console.error('Smart search error:', err);
            setError(err.message || 'Search failed');
            return null;
        } finally {
            setIsLoading(false);
        }
    }, []);

    /**
     * Clear search state.
     */
    const clearSearch = useCallback(() => {
        setSearchType('fuzzy');
        setParsedFilters(null);
        setError(null);
    }, []);

    return {
        executeSmartSearch,
        clearSearch,
        isLoading,
        error,
        searchType,
        parsedFilters
    };
};

export default useSmartSearch;
