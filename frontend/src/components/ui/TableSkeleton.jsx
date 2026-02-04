import React from 'react';
import { SkeletonLine, SkeletonCircle } from './Skeleton';

const TableSkeleton = ({ rows = 8, columns = 6 }) => {
    return (
        <div className="w-full">
            {/* Header skeleton */}
            <div className="flex items-center gap-4 p-4 border-b border-white/5">
                {Array.from({ length: columns }).map((_, i) => (
                    <SkeletonLine key={`header-${i}`} width={i === 0 ? 'w-24' : i === columns - 1 ? 'w-16' : 'w-32'} height="h-3" />
                ))}
            </div>

            {/* Row skeletons */}
            {Array.from({ length: rows }).map((_, rowIndex) => (
                <div key={`row-${rowIndex}`} className="flex items-center gap-4 p-4 border-b border-white/5">
                    {/* Date column */}
                    <SkeletonLine width="w-24" height="h-4" />

                    {/* Merchant column with avatar */}
                    <div className="flex items-center gap-3 flex-1">
                        <SkeletonCircle size="w-8 h-8" />
                        <SkeletonLine width="w-32" height="h-4" />
                    </div>

                    {/* Mode column */}
                    <SkeletonLine width="w-16" height="h-6" />

                    {/* Category column */}
                    <SkeletonLine width="w-24" height="h-5" />

                    {/* Amount column */}
                    <SkeletonLine width="w-20" height="h-4" />

                    {/* Actions column */}
                    <SkeletonLine width="w-8" height="h-8" />
                </div>
            ))}
        </div>
    );
};

export default TableSkeleton;
