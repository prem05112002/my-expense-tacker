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

    // Get all focusable elements within the container
    const getFocusableElements = useCallback(() => {
        if (!containerRef.current) return [];
        return Array.from(containerRef.current.querySelectorAll(FOCUSABLE_SELECTORS));
    }, []);

    // Handle Tab key navigation
    const handleKeyDown = useCallback((e) => {
        if (e.key === 'Escape' && onEscape) {
            e.preventDefault();
            onEscape();
            return;
        }

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
    }, [getFocusableElements, onEscape]);

    useEffect(() => {
        if (!isActive) return;

        // Store currently focused element to restore later
        previousActiveElement.current = document.activeElement;

        // Focus first focusable element in container
        const focusableElements = getFocusableElements();
        if (focusableElements.length > 0) {
            // Small delay to ensure DOM is ready
            requestAnimationFrame(() => {
                focusableElements[0].focus();
            });
        }

        // Add keydown listener
        document.addEventListener('keydown', handleKeyDown);

        return () => {
            document.removeEventListener('keydown', handleKeyDown);

            // Restore focus to previous element when trap is deactivated
            if (previousActiveElement.current && previousActiveElement.current.focus) {
                previousActiveElement.current.focus();
            }
        };
    }, [isActive, getFocusableElements, handleKeyDown]);

    return containerRef;
};

export default useFocusTrap;
