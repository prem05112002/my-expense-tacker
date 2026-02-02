import React, { useState, useRef, useEffect } from 'react';
import api from '../api/axios';

const ChatBot = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([
        {
            type: 'bot',
            text: "Hi! I'm your financial assistant. Ask me about your budget, spending trends, or affordability of purchases.",
        },
    ]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [rateLimit, setRateLimit] = useState(null);
    const messagesEndRef = useRef(null);

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
    }, [isOpen, rateLimit]);

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
        setMessages((prev) => [...prev, { type: 'user', text: userMessage }]);
        setIsLoading(true);

        try {
            const response = await api.post('/chatbot/ask', { message: userMessage });
            const { response: botResponse, intent, rate_limit } = response.data;

            setMessages((prev) => [
                ...prev,
                {
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
        "How much do I spend on food?",
        "Where can I save money?",
    ];

    const handleSuggestion = (query) => {
        setInput(query);
    };

    return (
        <>
            {/* Floating Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="fixed bottom-6 right-6 w-14 h-14 bg-indigo-600 hover:bg-indigo-700
                           rounded-full shadow-lg flex items-center justify-center
                           transition-all duration-300 z-50"
                aria-label="Toggle chat"
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
                <div className="fixed bottom-24 right-6 w-96 h-[500px] bg-[#121212] border border-slate-700
                               rounded-xl shadow-2xl flex flex-col z-50 overflow-hidden">
                    {/* Header */}
                    <div className="bg-indigo-600 px-4 py-3 flex items-center justify-between">
                        <div>
                            <h3 className="font-semibold text-white">Financial Assistant</h3>
                            {rateLimit && (
                                <p className="text-xs text-indigo-200">
                                    {rateLimit.daily_remaining} queries remaining today
                                </p>
                            )}
                        </div>
                        <button
                            onClick={() => setIsOpen(false)}
                            className="text-white/70 hover:text-white"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {messages.map((msg, idx) => (
                            <div
                                key={idx}
                                className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div
                                    className={`max-w-[80%] px-4 py-2 rounded-xl text-sm whitespace-pre-wrap
                                        ${msg.type === 'user'
                                            ? 'bg-indigo-600 text-white'
                                            : msg.isError
                                                ? 'bg-red-900/50 text-red-200 border border-red-700'
                                                : 'bg-slate-800 text-slate-200'
                                        }`}
                                >
                                    {msg.text}
                                    {msg.intent && (
                                        <span className="block mt-1 text-xs opacity-60">
                                            [{msg.intent}]
                                        </span>
                                    )}
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
                            {suggestedQueries.map((query, idx) => (
                                <button
                                    key={idx}
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
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask about your finances..."
                                className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2
                                         text-sm text-slate-200 placeholder-slate-500
                                         focus:outline-none focus:border-indigo-500"
                                disabled={isLoading}
                            />
                            <button
                                onClick={handleSend}
                                disabled={isLoading || !input.trim()}
                                className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-700
                                         disabled:cursor-not-allowed px-4 py-2 rounded-lg
                                         transition-colors"
                            >
                                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                          d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default ChatBot;
