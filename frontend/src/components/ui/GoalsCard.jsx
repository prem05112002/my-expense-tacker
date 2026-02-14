import React, { useState } from 'react';
import { Target, AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import api from '../../api/axios';

const GoalsCard = ({ goals = [], onGoalDeleted }) => {
    const [deletingId, setDeletingId] = useState(null);

    const handleDelete = async (goalId, e) => {
        e.stopPropagation();
        if (deletingId) return;

        setDeletingId(goalId);
        try {
            await api.delete(`/goals/${goalId}`);
            if (onGoalDeleted) {
                onGoalDeleted();
            }
        } catch (error) {
            console.error('Failed to delete goal:', error);
        } finally {
            setDeletingId(null);
        }
    };
    const activeGoals = goals.filter(g => g.is_active);
    const goalsOnTrack = activeGoals.filter(g => !g.is_over_budget).length;
    const goalsOverBudget = activeGoals.filter(g => g.is_over_budget).length;

    if (activeGoals.length === 0) {
        return (
            <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 relative overflow-hidden">
                <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">Category Goals</p>
                <div className="flex items-center gap-3 mt-2">
                    <Target size={24} className="text-slate-600" />
                    <p className="text-slate-500 text-sm">No goals set</p>
                </div>
                <p className="text-xs text-slate-600 mt-3">
                    Ask the chatbot to set spending caps!
                </p>
            </div>
        );
    }

    return (
        <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 relative overflow-hidden">
            <div className="flex justify-between items-start mb-4">
                <p className="text-slate-400 text-xs font-bold uppercase tracking-wider">Category Goals</p>
                <div className="flex items-center gap-2">
                    {goalsOnTrack > 0 && (
                        <span className="text-xs font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 flex items-center gap-1">
                            <CheckCircle2 size={10} />
                            {goalsOnTrack}
                        </span>
                    )}
                    {goalsOverBudget > 0 && (
                        <span className="text-xs font-bold px-2 py-0.5 rounded bg-red-500/20 text-red-400 flex items-center gap-1">
                            <AlertTriangle size={10} />
                            {goalsOverBudget}
                        </span>
                    )}
                </div>
            </div>

            <div className="space-y-3 max-h-[120px] overflow-y-auto custom-scrollbar pr-1">
                {activeGoals.slice(0, 3).map((goal) => (
                    <div key={goal.id} className="group relative">
                        <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-300 font-medium truncate max-w-[100px]" title={goal.category_name}>
                                {goal.category_name}
                            </span>
                            <div className="flex items-center gap-2">
                                <span className={`font-bold ${goal.is_over_budget ? 'text-red-400' : 'text-slate-400'}`}>
                                    ₹{formatCurrency(goal.current_spend)} / ₹{formatCurrency(goal.cap_amount)}
                                </span>
                                <button
                                    onClick={(e) => handleDelete(goal.id, e)}
                                    disabled={deletingId === goal.id}
                                    className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-red-500/20 text-slate-500 hover:text-red-400 disabled:opacity-50"
                                    aria-label={`Delete ${goal.category_name} goal`}
                                    title="Delete goal"
                                >
                                    <X size={12} className={deletingId === goal.id ? 'animate-spin' : ''} />
                                </button>
                            </div>
                        </div>
                        <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all duration-500 ${goal.is_over_budget ? 'bg-red-500' : 'bg-emerald-500'}`}
                                style={{
                                    width: `${Math.min(goal.progress_percent, 100)}%`,
                                    backgroundColor: goal.is_over_budget ? undefined : goal.category_color
                                }}
                            />
                        </div>
                    </div>
                ))}
            </div>

            {activeGoals.length > 3 && (
                <p className="text-xs text-slate-500 mt-2 text-center">
                    +{activeGoals.length - 3} more goals
                </p>
            )}
        </div>
    );
};

export default GoalsCard;
