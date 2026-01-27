export const getAmountColor = (type) => {
    const normalizedType = (type || "DEBIT").toUpperCase();
    return normalizedType === 'CREDIT' ? 'text-emerald-400' : 'text-red-400';
};

export const formatCurrency = (amount) => {
    return Number(amount || 0).toLocaleString('en-IN'); // Added 'en-IN' for Indian formatting if preferred
};