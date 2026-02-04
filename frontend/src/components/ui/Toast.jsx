import React, { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const variantStyles = {
    success: {
        bg: 'bg-emerald-500/10 border-emerald-500/30',
        icon: CheckCircle,
        iconColor: 'text-emerald-400',
        text: 'text-emerald-200',
    },
    error: {
        bg: 'bg-red-500/10 border-red-500/30',
        icon: XCircle,
        iconColor: 'text-red-400',
        text: 'text-red-200',
    },
    warning: {
        bg: 'bg-amber-500/10 border-amber-500/30',
        icon: AlertTriangle,
        iconColor: 'text-amber-400',
        text: 'text-amber-200',
    },
    info: {
        bg: 'bg-blue-500/10 border-blue-500/30',
        icon: Info,
        iconColor: 'text-blue-400',
        text: 'text-blue-200',
    },
};

const Toast = ({ message, variant = 'info', duration = 4000, onClose }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [isLeaving, setIsLeaving] = useState(false);

    const styles = variantStyles[variant] || variantStyles.info;
    const Icon = styles.icon;

    useEffect(() => {
        // Trigger enter animation
        requestAnimationFrame(() => setIsVisible(true));

        // Auto dismiss
        const dismissTimer = setTimeout(() => {
            setIsLeaving(true);
        }, duration);

        return () => clearTimeout(dismissTimer);
    }, [duration]);

    useEffect(() => {
        if (isLeaving) {
            const removeTimer = setTimeout(() => {
                onClose();
            }, 300); // Match animation duration
            return () => clearTimeout(removeTimer);
        }
    }, [isLeaving, onClose]);

    const handleClose = () => {
        setIsLeaving(true);
    };

    return (
        <div
            className={`
                pointer-events-auto
                flex items-center gap-3 px-4 py-3 rounded-lg border backdrop-blur-sm
                shadow-lg shadow-black/20 min-w-[280px] max-w-[400px]
                transition-all duration-300 ease-out
                ${styles.bg}
                ${isVisible && !isLeaving ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'}
            `}
            role="alert"
            aria-live="polite"
        >
            <Icon size={18} className={styles.iconColor} />
            <p className={`flex-1 text-sm font-medium ${styles.text}`}>{message}</p>
            <button
                onClick={handleClose}
                className="text-slate-400 hover:text-white transition-colors p-1 rounded hover:bg-white/10"
                aria-label="Dismiss notification"
            >
                <X size={14} />
            </button>
        </div>
    );
};

export default Toast;
