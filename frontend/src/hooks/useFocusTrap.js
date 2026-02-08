import { useEffect, useRef, useCallback } from 'react';

const FOCUSABLE_SELECTORS = [
    'a[href]',
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Hook to trap focus within a container when active.
 * Also handles Escape key to close the modal.
 *
 * @param {boolean} isActive - Whether the focus trap is active
 * @param {Function} onEscape - Callback when Escape is pressed
 * @returns {Object} ref - Ref to attach to the container element
 */
const useFocusTrap = (isActive, onEscape) => {
    const containerRef = useRef(null);
    const previousActiveElement = useRef(null);
    const hasInitialFocus = useRef(false);

    // Get all focusable elements within the container
    const getFocusableElements = useCallback(() => {
        if (!containerRef.current) return [];
        return Array.from(containerRef.current.querySelectorAll(FOCUSABLE_SELECTORS));
    }, []);

    // Handle Escape key - attached to document for reliable closing
    useEffect(() => {
        if (!isActive || !onEscape) return;

        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                onEscape();
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [isActive, onEscape]);

    // Handle Tab key navigation - attached to container to avoid interfering with inputs
    useEffect(() => {
        if (!isActive) return;

        const container = containerRef.current;
        if (!container) return;

        const handleTabKey = (e) => {
            if (e.key !== 'Tab') return;

            const focusableElements = getFocusableElements();
            if (focusableElements.length === 0) return;

            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            // Shift+Tab from first element -> focus last element
            if (e.shiftKey && document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
                return;
            }

            // Tab from last element -> focus first element
            if (!e.shiftKey && document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
                return;
            }
        };

        container.addEventListener('keydown', handleTabKey);
        return () => container.removeEventListener('keydown', handleTabKey);
    }, [isActive, getFocusableElements]);

    // Handle initial focus and restore focus on close
    useEffect(() => {
        if (!isActive) {
            // Reset initial focus flag when modal closes
            hasInitialFocus.current = false;
            return;
        }

        // Store currently focused element to restore later
        previousActiveElement.current = document.activeElement;

        // Focus first focusable element only once when modal opens
        if (!hasInitialFocus.current) {
            const focusableElements = getFocusableElements();
            if (focusableElements.length > 0) {
                requestAnimationFrame(() => {
                    focusableElements[0].focus();
                    hasInitialFocus.current = true;
                });
            }
        }

        return () => {
            // Restore focus to previous element when trap is deactivated
            if (previousActiveElement.current && previousActiveElement.current.focus) {
                previousActiveElement.current.focus();
            }
        };
    }, [isActive, getFocusableElements]);

    return containerRef;
};

export default useFocusTrap;
