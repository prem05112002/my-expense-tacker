import React, { useState, useRef, useEffect, useCallback } from 'react';
import api from '../api/axios';

const STORAGE_KEY = 'chatbot-position';
const SESSION_KEY = 'chatbot-session-id';
const DEFAULT_POSITION = { bottom: 24, right: 24 };

// Chat window dimensions for viewport boundary calculations
const CHAT_WIDTH = 384;   // w-96 = 24rem = 384px
const CHAT_HEIGHT = 500;
const BUTTON_SIZE = 56;   // w-14 h-14 = 56px
const GAP = 8;            // Gap between button and chat window
const EDGE_PADDING = 16;  // Minimum padding from viewport edges

const ChatBot = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([
        {
            id: crypto.randomUUID(),
            type: 'bot',
            text: "Hi! I'm your financial assistant. Ask me about your budget, spending trends, savings goals, or affordability of purchases. I can remember our conversation for follow-up questions!",
        },
    ]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [rateLimit, setRateLimit] = useState(null);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    // Session management for multi-turn conversations
    const [sessionId, setSessionId] = useState(() => {
        try {
            return sessionStorage.getItem(SESSION_KEY) || null;
        } catch {
            return null;
        }
    });

    // Draggable state
    const [position, setPosition] = useState(() => {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            return saved ? JSON.parse(saved) : DEFAULT_POSITION;
        } catch {
            return DEFAULT_POSITION;
        }
    });
    const [isDragging, setIsDragging] = useState(false);
    const dragRef = useRef(null);
    const dragStartPos = useRef({ x: 0, y: 0, bottom: 0, right: 0 });
    const hasDragged = useRef(false); // Track if actual dragging occurred to prevent click after drag

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    useEffect(() => {
        if (isOpen && !rateLimit) {
            fetchRateLimit();
        }
        // Focus input when chat opens
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen, rateLimit]);

    // Save position to localStorage when it changes
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(position));
    }, [position]);

    // Escape key handler
    useEffect(() => {
        const handleEscape = (e) => {
            if (e.key === 'Escape' && isOpen) {
                setIsOpen(false);
            }
        };
        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [isOpen]);

    // Mouse drag handlers
    const handleDragStart = useCallback((e) => {
        if (isOpen) return; // Don't allow dragging when chat is open
        e.preventDefault();
        setIsDragging(true);
        hasDragged.current = false; // Reset at start of potential drag
        dragStartPos.current = {
            x: e.clientX,
            y: e.clientY,
            bottom: position.bottom,
            right: position.right,
        };
    }, [isOpen, position]);

    const handleDragMove = useCallback((e) => {
        if (!isDragging) return;

        const clientX = e.clientX || (e.touches && e.touches[0]?.clientX);
        const clientY = e.clientY || (e.touches && e.touches[0]?.clientY);

        if (clientX === undefined || clientY === undefined) return;

        const deltaX = dragStartPos.current.x - clientX;
        const deltaY = dragStartPos.current.y - clientY;

        // Mark as dragged if there's any movement
        if (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2) {
            hasDragged.current = true;
        }

        const newRight = Math.max(24, Math.min(window.innerWidth - 80, dragStartPos.current.right + deltaX));
        const newBottom = Math.max(24, Math.min(window.innerHeight - 80, dragStartPos.current.bottom + deltaY));

        setPosition({ right: newRight, bottom: newBottom });
    }, [isDragging]);

    const handleDragEnd = useCallback(() => {
        setIsDragging(false);
    }, []);

    // Touch drag handlers
    const handleTouchStart = useCallback((e) => {
        if (isOpen) return;
        const touch = e.touches[0];
        setIsDragging(true);
        hasDragged.current = false;
        dragStartPos.current = {
            x: touch.clientX,
            y: touch.clientY,
            bottom: position.bottom,
            right: position.right,
        };
    }, [isOpen, position]);

    const handleTouchMove = useCallback((e) => {
        if (!isDragging) return;
        const touch = e.touches[0];

        const deltaX = dragStartPos.current.x - touch.clientX;
        const deltaY = dragStartPos.current.y - touch.clientY;

        if (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2) {
            hasDragged.current = true;
        }

        const newRight = Math.max(24, Math.min(window.innerWidth - 80, dragStartPos.current.right + deltaX));
        const newBottom = Math.max(24, Math.min(window.innerHeight - 80, dragStartPos.current.bottom + deltaY));

        setPosition({ right: newRight, bottom: newBottom });
    }, [isDragging]);

    const handleTouchEnd = useCallback(() => {
        setIsDragging(false);
    }, []);

    // Attach global mouse/touch listeners for dragging
    useEffect(() => {
        if (isDragging) {
            window.addEventListener('mousemove', handleDragMove);
            window.addEventListener('mouseup', handleDragEnd);
            window.addEventListener('touchmove', handleTouchMove, { passive: false });
            window.addEventListener('touchend', handleTouchEnd);
            return () => {
                window.removeEventListener('mousemove', handleDragMove);
                window.removeEventListener('mouseup', handleDragEnd);
                window.removeEventListener('touchmove', handleTouchMove);
                window.removeEventListener('touchend', handleTouchEnd);
            };
        }
    }, [isDragging, handleDragMove, handleDragEnd, handleTouchMove, handleTouchEnd]);

    // Calculate chat window position to keep it within viewport bounds
    const getChatWindowPosition = useCallback(() => {
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;

        // Default: chat window above and aligned right edge with button
        let chatRight = position.right;
        let chatBottom = position.bottom + BUTTON_SIZE + GAP;

        // If chat would overflow right edge, shift left
        if (chatRight + CHAT_WIDTH > windowWidth - EDGE_PADDING) {
            chatRight = Math.max(EDGE_PADDING, windowWidth - CHAT_WIDTH - EDGE_PADDING);
        }

        // If chat would overflow left edge (button near right side of screen)
        if (chatRight < EDGE_PADDING) {
            chatRight = EDGE_PADDING;
        }

        // If chat would overflow top (button too high), position it lower
        if (chatBottom + CHAT_HEIGHT > windowHeight - EDGE_PADDING) {
            chatBottom = Math.max(EDGE_PADDING, windowHeight - CHAT_HEIGHT - EDGE_PADDING);
        }

        return { bottom: chatBottom, right: chatRight };
    }, [position]);

    // Handle button click - only toggle if no drag occurred
    const handleButtonClick = useCallback(() => {
        if (hasDragged.current) {
            hasDragged.current = false;
            return;
        }
        setIsOpen(!isOpen);
    }, [isOpen]);

    const fetchRateLimit = async () => {
        try {
            const response = await api.get('/chatbot/rate-limit');
            setRateLimit(response.data);
        } catch (error) {
            console.error('Failed to fetch rate limit:', error);
        }
    };

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput('');
        setMessages((prev) => [...prev, { id: crypto.randomUUID(), type: 'user', text: userMessage }]);
        setIsLoading(true);

        try {
            // Include session_id for multi-turn conversation support
            const payload = { message: userMessage };
            if (sessionId) {
                payload.session_id = sessionId;
            }

            const response = await api.post('/chatbot/ask', payload);
            const { response: botResponse, intent, rate_limit, session_id: returnedSessionId } = response.data;

            // Store session ID for future requests
            if (returnedSessionId) {
                setSessionId(returnedSessionId);
                try {
                    sessionStorage.setItem(SESSION_KEY, returnedSessionId);
                } catch {
                    // sessionStorage might not be available
                }
            }

            setMessages((prev) => [
                ...prev,
                {
                    id: crypto.randomUUID(),
                    type: 'bot',
                    text: botResponse,
                    intent,
                },
            ]);

            if (rate_limit) {
                setRateLimit(rate_limit);
            }
        } catch {
            setMessages((prev) => [
                ...prev,
                {
                    id: crypto.randomUUID(),
                    type: 'bot',
                    text: 'Sorry, something went wrong. Please try again.',
                    isError: true,
                },
            ]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const suggestedQueries = [
        "What's my budget status?",
        "Will I stay under budget?",
        "Can I save ₹50k in 6 months?",
    ];

    const handleSuggestion = (query) => {
        setInput(query);
    };

    return (
        <>
            {/* Floating Button (Draggable) */}
            <button
                ref={dragRef}
                onClick={handleButtonClick}
                onMouseDown={handleDragStart}
                onTouchStart={handleTouchStart}
                style={{
                    bottom: `${position.bottom}px`,
                    right: `${position.right}px`,
                    cursor: isDragging ? 'grabbing' : isOpen ? 'pointer' : 'grab',
                }}
                className={`fixed w-14 h-14 bg-teal-600 hover:bg-teal-700
                           rounded-full shadow-lg flex items-center justify-center
                           transition-colors duration-300 z-50 select-none
                           ${isDragging ? 'scale-110' : ''}`}
                aria-label={isOpen ? 'Close chat' : 'Open chat'}
                aria-expanded={isOpen}
                title={isOpen ? 'Close chat' : 'Drag to move, click to open'}
            >
                {isOpen ? (
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                ) : (
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                )}
            </button>

            {/* Chat Window */}
            {isOpen && (
                <div
                    style={{
                        bottom: `${getChatWindowPosition().bottom}px`,
                        right: `${getChatWindowPosition().right}px`,
                    }}
                    className="fixed w-[calc(100vw-2rem)] max-w-96 sm:w-96 h-[500px] bg-[#121212] border border-slate-700
                               rounded-xl shadow-2xl flex flex-col z-50 overflow-hidden"
                    role="dialog"
                    aria-modal="true"
                    aria-label="Financial Assistant Chat"
                >
                    {/* Header */}
                    <div className="bg-teal-600 px-4 py-3 flex items-center justify-between">
                        <div>
                            <h3 className="font-semibold text-white" id="chatbot-title">Financial Assistant</h3>
                            {rateLimit && (
                                <p className="text-xs text-teal-200">
                                    {rateLimit.daily_remaining} queries remaining today
                                </p>
                            )}
                        </div>
                        <button
                            onClick={() => setIsOpen(false)}
                            className="text-white/70 hover:text-white p-1 rounded hover:bg-white/10 transition-colors"
                            aria-label="Close chat"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    {/* Messages */}
                    <div
                        className="flex-1 overflow-y-auto p-4 space-y-4"
                        role="log"
                        aria-live="polite"
                        aria-label="Chat messages"
                    >
                        {messages.map((msg) => (
                            <div
                                key={msg.id}
                                className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div
                                    className={`max-w-[80%] px-4 py-2 rounded-xl text-sm whitespace-pre-wrap
                                        ${msg.type === 'user'
                                            ? 'bg-teal-600 text-white'
                                            : msg.isError
                                                ? 'bg-red-900/50 text-red-200 border border-red-700'
                                                : 'bg-slate-800 text-slate-200'
                                        }`}
                                >
                                    {msg.text}
                                </div>
                            </div>
                        ))}

                        {isLoading && (
                            <div className="flex justify-start">
                                <div className="bg-slate-800 px-4 py-2 rounded-xl">
                                    <div className="flex space-x-1">
                                        <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                        <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                        <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Suggestions */}
                    {messages.length <= 2 && (
                        <div className="px-4 pb-2 flex flex-wrap gap-2">
                            {suggestedQueries.map((query) => (
                                <button
                                    key={query}
                                    onClick={() => handleSuggestion(query)}
                                    className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300
                                             px-3 py-1.5 rounded-full transition-colors"
                                >
                                    {query}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Input */}
                    <div className="border-t border-slate-700 p-3">
                        <div className="flex items-center gap-2">
                            <input
                                ref={inputRef}
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask about your finances..."
                                className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2
                                         text-sm text-slate-200 placeholder-slate-500
                                         focus:outline-none focus:border-teal-500"
                                disabled={isLoading}
                                aria-label="Type your message"
                            />
                            <button
                                onClick={handleSend}
                                disabled={isLoading || !input.trim()}
                                className="bg-teal-600 hover:bg-teal-700 disabled:bg-slate-700
                                         disabled:cursor-not-allowed px-4 py-2 rounded-lg
                                         transition-colors flex items-center justify-center min-w-[52px]"
                                aria-label={isLoading ? 'Sending message' : 'Send message'}
                            >
                                {isLoading ? (
                                    <svg className="w-5 h-5 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                ) : (
                                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default ChatBot;
