import React, { useState, useRef, useEffect } from 'react';
import api from '../api/axios';

const SESSION_KEY = 'chatbot-session-id';

// Parse simple markdown (bold **text**) and return React elements
const parseMarkdown = (text) => {
    if (!text) return text;

    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={index} className="font-semibold">{part.slice(2, -2)}</strong>;
        }
        return part;
    });
};

const EmbeddedChat = ({ className = '' }) => {
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
    const messagesContainerRef = useRef(null);
    const inputRef = useRef(null);

    // Session management for multi-turn conversations
    const [sessionId, setSessionId] = useState(() => {
        try {
            return sessionStorage.getItem(SESSION_KEY) || null;
        } catch {
            return null;
        }
    });

    const scrollToBottom = () => {
        // Use container scrollTop instead of scrollIntoView to avoid scrolling the entire page
        const container = messagesContainerRef.current;
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    useEffect(() => {
        if (!rateLimit) {
            fetchRateLimit();
        }
    }, [rateLimit]);

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
        "How much do I spend on food?",
    ];

    const handleSuggestion = (query) => {
        setInput(query);
        // Use preventScroll to avoid scrolling the page when focusing
        inputRef.current?.focus({ preventScroll: true });
    };

    return (
        <div className={`bg-[#161616] rounded-2xl border border-white/5 flex flex-col overflow-hidden shrink-0 ${className}`}>
            {/* Header */}
            <div className="bg-purple-600 px-4 py-3 flex items-center justify-between shrink-0">
                <div>
                    <h3 className="font-semibold text-white">Financial Assistant</h3>
                    {rateLimit && (
                        <p className="text-xs text-purple-200">
                            {rateLimit.daily_remaining} queries remaining today
                        </p>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <svg className="w-6 h-6 text-white/80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                </div>
            </div>

            {/* Messages */}
            <div
                ref={messagesContainerRef}
                className="overflow-y-auto p-4 space-y-4 bg-[#161616]"
                style={{ minHeight: '300px', maxHeight: '50vh' }}
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
                                    ? 'bg-purple-600 text-white'
                                    : msg.isError
                                        ? 'bg-red-900/50 text-red-200 border border-red-700'
                                        : 'bg-slate-800 text-slate-200'
                                }`}
                        >
                            {msg.type === 'bot' ? parseMarkdown(msg.text) : msg.text}
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
                <div className="px-4 pb-2 flex flex-wrap gap-2 shrink-0">
                    {suggestedQueries.map((query) => (
                        <button
                            key={query}
                            onClick={() => handleSuggestion(query)}
                            className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300
                                     px-3 py-1.5 rounded-full transition-colors border border-slate-700"
                        >
                            {query}
                        </button>
                    ))}
                </div>
            )}

            {/* Input */}
            <div className="border-t border-slate-700 p-3 shrink-0">
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
                                 focus:outline-none focus:border-purple-500"
                        disabled={isLoading}
                        aria-label="Type your message"
                    />
                    <button
                        onClick={handleSend}
                        disabled={isLoading || !input.trim()}
                        className="bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700
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
    );
};

export default EmbeddedChat;
