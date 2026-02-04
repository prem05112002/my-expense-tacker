import React from 'react';
import { SkeletonLine, SkeletonRect, SkeletonCircle } from './Skeleton';

// Single stat card skeleton
export const StatCardSkeleton = () => (
    <div className="bg-[#161616] p-6 rounded-2xl border border-white/5">
        <SkeletonLine width="w-24" height="h-3" />
        <div className="mt-3">
            <SkeletonLine width="w-36" height="h-8" />
        </div>
        <div className="mt-3">
            <SkeletonLine width="w-28" height="h-5" />
        </div>
    </div>
);

// Wide card skeleton (for burn rate)
export const WideCardSkeleton = () => (
    <div className="md:col-span-2 bg-[#161616] p-6 rounded-2xl border border-white/5">
        <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
                <SkeletonLine width="w-20" height="h-3" />
                <SkeletonLine width="w-16" height="h-5" />
            </div>
            <SkeletonLine width="w-24" height="h-3" />
        </div>
        <SkeletonRect height="h-6" rounded="rounded-full" />
        <div className="flex justify-between mt-2">
            <SkeletonLine width="w-16" height="h-3" />
            <SkeletonLine width="w-16" height="h-3" />
        </div>
    </div>
);

// Chart card skeleton
export const ChartCardSkeleton = () => (
    <div className="lg:col-span-2 bg-[#161616] p-6 rounded-2xl border border-white/5">
        <div className="flex justify-between items-center mb-6">
            <SkeletonLine width="w-32" height="h-5" />
            <div className="flex gap-4">
                <SkeletonLine width="w-20" height="h-3" />
                <SkeletonLine width="w-20" height="h-3" />
            </div>
        </div>
        <SkeletonRect height="h-[300px]" />
    </div>
);

// Category list skeleton
export const CategoryListSkeleton = () => (
    <div className="bg-[#161616] p-6 rounded-2xl border border-white/5 h-[380px]">
        <SkeletonLine width="w-32" height="h-5" />
        <div className="space-y-4 mt-6">
            {Array.from({ length: 5 }).map((_, i) => (
                <div key={i}>
                    <div className="flex justify-between mb-1">
                        <SkeletonLine width="w-24" height="h-3" />
                        <SkeletonLine width="w-16" height="h-3" />
                    </div>
                    <SkeletonRect height="h-2" rounded="rounded-full" />
                </div>
            ))}
        </div>
    </div>
);

// Profile settings skeleton
export const ProfileSkeleton = () => (
    <div className="p-6 text-white h-[calc(100vh-4rem)] max-w-7xl mx-auto">
        <SkeletonLine width="w-48" height="h-8" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
            {/* Left column */}
            <div className="space-y-8">
                {/* Settings card */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5">
                    <SkeletonLine width="w-32" height="h-6" />
                    <div className="mt-4 space-y-4">
                        <div>
                            <SkeletonLine width="w-24" height="h-3" />
                            <SkeletonRect height="h-12" className="mt-1" />
                        </div>
                    </div>
                </div>
                {/* Budget card */}
                <div className="bg-[#161616] p-6 rounded-2xl border border-white/5">
                    <SkeletonLine width="w-28" height="h-6" />
                    <div className="mt-4 space-y-4">
                        <div className="grid grid-cols-2 gap-2">
                            <SkeletonRect height="h-12" />
                            <SkeletonRect height="h-12" />
                        </div>
                        <div>
                            <SkeletonLine width="w-32" height="h-3" />
                            <SkeletonRect height="h-12" className="mt-1" />
                        </div>
                    </div>
                </div>
            </div>
            {/* Right column - Rules table */}
            <div className="bg-[#161616] p-6 rounded-2xl border border-white/5">
                <SkeletonLine width="w-40" height="h-6" />
                <div className="mt-4 space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="flex gap-4 p-3 border-b border-white/5">
                            <SkeletonLine width="w-24" height="h-4" />
                            <SkeletonLine width="w-24" height="h-4" />
                            <SkeletonLine width="w-20" height="h-4" />
                            <SkeletonLine width="w-8" height="h-4" />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    </div>
);

// Inbox/NeedsReview skeleton
export const InboxSkeleton = () => (
    <div className="flex h-[calc(100vh-4rem)] bg-[#0b0b0b] rounded-2xl border border-white/5 overflow-hidden">
        {/* Left panel */}
        <div className="w-1/3 min-w-[300px] border-r border-white/5 flex flex-col">
            <div className="p-4 border-b border-white/5 bg-[#111]">
                <div className="flex items-center gap-2">
                    <SkeletonLine width="w-24" height="h-5" />
                    <SkeletonLine width="w-8" height="h-5" />
                </div>
            </div>
            <div className="flex-1 p-2">
                {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="p-4 border-b border-white/5">
                        <div className="flex justify-between mb-1">
                            <SkeletonLine width="w-24" height="h-4" />
                            <SkeletonLine width="w-16" height="h-3" />
                        </div>
                        <SkeletonLine width="w-full" height="h-3" />
                    </div>
                ))}
            </div>
        </div>
        {/* Right panel */}
        <div className="flex-1 flex flex-col items-center justify-center">
            <SkeletonRect width="w-16" height="h-16" rounded="rounded-lg" />
            <SkeletonLine width="w-40" height="h-4" className="mt-4" />
        </div>
    </div>
);

// Duplicates page skeleton
export const DuplicatesSkeleton = () => (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-[#0b0b0b] rounded-2xl border border-white/5 overflow-hidden">
        <div className="p-6 border-b border-white/5 shrink-0">
            <SkeletonLine width="w-48" height="h-7" />
            <SkeletonLine width="w-64" height="h-4" className="mt-2" />
        </div>
        <div className="flex-1 p-6">
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {Array.from({ length: 2 }).map((_, i) => (
                    <div key={i} className="bg-[#161616] border border-slate-800 rounded-xl p-5">
                        <div className="flex justify-between mb-6">
                            <SkeletonLine width="w-32" height="h-6" />
                            <SkeletonLine width="w-24" height="h-4" />
                        </div>
                        <div className="flex gap-4">
                            <SkeletonRect height="h-48" className="flex-1" />
                            <SkeletonRect height="h-48" className="flex-1" />
                        </div>
                        <div className="flex gap-3 mt-6 pt-6 border-t border-white/5">
                            <SkeletonRect height="h-10" className="flex-1" />
                            <SkeletonRect height="h-10" width="w-28" />
                            <SkeletonRect height="h-10" className="flex-1" />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    </div>
);

// Dashboard full skeleton
export const DashboardSkeleton = () => (
    <div className="flex flex-col h-[calc(100vh-4rem)] gap-6 p-1">
        {/* Header */}
        <div className="flex justify-between items-end">
            <div>
                <SkeletonLine width="w-32" height="h-7" />
                <SkeletonLine width="w-48" height="h-4" className="mt-1" />
            </div>
            <div className="flex gap-3">
                <SkeletonRect width="w-36" height="h-10" />
                <SkeletonRect width="w-10" height="h-10" />
                <SkeletonRect width="w-10" height="h-10" />
            </div>
        </div>

        {/* Hero cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCardSkeleton />
            <StatCardSkeleton />
            <WideCardSkeleton />
        </div>

        {/* Graph & Categories */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <ChartCardSkeleton />
            <CategoryListSkeleton />
        </div>

        {/* Recent transactions */}
        <div className="bg-[#161616] p-6 rounded-2xl border border-white/5">
            <SkeletonLine width="w-40" height="h-5" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                        <div className="flex items-center gap-3">
                            <SkeletonCircle size="w-10 h-10" />
                            <div>
                                <SkeletonLine width="w-24" height="h-4" />
                                <SkeletonLine width="w-16" height="h-3" className="mt-1" />
                            </div>
                        </div>
                        <SkeletonLine width="w-16" height="h-4" />
                    </div>
                ))}
            </div>
        </div>
    </div>
);

export default {
    StatCard: StatCardSkeleton,
    WideCard: WideCardSkeleton,
    ChartCard: ChartCardSkeleton,
    CategoryList: CategoryListSkeleton,
    Profile: ProfileSkeleton,
    Inbox: InboxSkeleton,
    Duplicates: DuplicatesSkeleton,
    Dashboard: DashboardSkeleton,
};
