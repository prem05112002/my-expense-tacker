import React from 'react';

// Base skeleton with shimmer animation
export const SkeletonBase = ({ className = '' }) => (
    <div
        className={`bg-slate-800 rounded animate-pulse ${className}`}
        style={{
            backgroundImage: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.5s infinite',
        }}
    />
);

// Single line of text
export const SkeletonLine = ({ width = 'w-full', height = 'h-4' }) => (
    <SkeletonBase className={`${width} ${height}`} />
);

// Rectangle (for cards, images, etc.)
export const SkeletonRect = ({ width = 'w-full', height = 'h-20', rounded = 'rounded-lg' }) => (
    <SkeletonBase className={`${width} ${height} ${rounded}`} />
);

// Circle (for avatars)
export const SkeletonCircle = ({ size = 'w-10 h-10' }) => (
    <SkeletonBase className={`${size} rounded-full`} />
);

// Add shimmer keyframes to document
if (typeof document !== 'undefined') {
    const styleId = 'skeleton-shimmer-styles';
    if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            @keyframes shimmer {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
        `;
        document.head.appendChild(style);
    }
}

export default {
    Base: SkeletonBase,
    Line: SkeletonLine,
    Rect: SkeletonRect,
    Circle: SkeletonCircle,
};
