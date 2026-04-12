import { useState, useRef, useEffect } from 'react';
import { Send, Activity, ShieldAlert } from 'lucide-react';
import { MessageBubble } from './MessageBubble';
import { StatusIndicator } from './StatusIndicator';

import type { Message } from '../hooks/useChatAPI';

interface ChatPanelProps {
    messages: Message[];
    isLoading: boolean;
    sendMessage: (content: string) => void;
}

export function ChatPanel({ messages, isLoading, sendMessage }: ChatPanelProps) {

    const [inputValue, setInputValue] = useState('');
    const [isRateLimited, setIsRateLimited] = useState(false);
    const [queryCount, setQueryCount] = useState(0);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const RATE_LIMIT = 100;

    // Initial check for rate limiting mock
    useEffect(() => {
        const storedCount = localStorage.getItem('demo_query_count');
        const count = storedCount ? parseInt(storedCount) : 0;
        setQueryCount(count);
        if (count >= RATE_LIMIT) {
            setIsRateLimited(true);
        }
    }, [RATE_LIMIT]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isLoading]);

    const isAwaitingClarification = messages.length > 0 && messages[messages.length - 1].status === 'awaiting_clarification';

    const handleSend = (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputValue.trim() || isLoading || isRateLimited || isAwaitingClarification) return;

        // Check rate limit on submit
        const currentCount = parseInt(localStorage.getItem('demo_query_count') || '0');
        if (currentCount >= RATE_LIMIT) {
            setIsRateLimited(true);
            return;
        }

        // Increment query count
        const newCount = currentCount + 1;
        localStorage.setItem('demo_query_count', newCount.toString());
        setQueryCount(newCount);

        sendMessage(inputValue.trim());
        setInputValue('');

        // Only lock if we reached the limit
        if (newCount >= RATE_LIMIT) {
            setIsRateLimited(true);
        }
    };

    const renderInputForm = () => (
        <div className="w-full relative group">
            {isRateLimited && !isLoading && (
                <div className="absolute -top-10 left-0 right-0 flex justify-center fade-in">
                    <div className="bg-[#111] text-[#f4f4f2] text-[10px] font-bold uppercase tracking-widest px-3 py-1.5 rounded-md shadow-lg flex items-center gap-1.5">
                        <ShieldAlert size={12} />
                        <span>Demo limit reached ({queryCount}/{RATE_LIMIT})</span>
                    </div>
                </div>
            )}

            <form
                onSubmit={handleSend}
                className={`relative rounded-xl sm:rounded-2xl border-[1.5px] bg-white shadow-lg overflow-hidden transition-colors
                    ${isRateLimited && !isLoading ? 'border-red-300' : 'border-[#ddd] focus-within:border-[#111]'}`}
            >
                <textarea
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSend(e as any);
                        }
                    }}
                    disabled={isLoading || isRateLimited || isAwaitingClarification}
                    placeholder={
                        isLoading
                            ? 'Preparing your answer…'
                            : isRateLimited
                            ? 'Demo limit reached — contact us for full access.'
                            : isAwaitingClarification
                            ? 'Select an option above to continue.'
                            : 'Ask in plain language…'
                    }
                    className={`w-full bg-transparent text-[#111] placeholder:text-[#aaa] pl-4 sm:pl-5 pr-12 sm:pr-14 py-3.5 sm:py-4 focus:outline-none resize-none min-h-[48px] sm:min-h-[56px] max-h-[160px] text-[15px] font-medium leading-relaxed
                        ${(isRateLimited || isAwaitingClarification) ? 'opacity-50 cursor-not-allowed' : ''}`}
                    rows={1}
                />
                <button
                    type="submit"
                    disabled={!inputValue.trim() || isLoading || isRateLimited || isAwaitingClarification}
                    className="absolute right-2.5 sm:right-3 bottom-2.5 sm:bottom-3 p-2 bg-[#111] hover:bg-[#333] disabled:bg-[#e5e5e5] disabled:text-[#bbb] text-[#f4f4f2] rounded-lg sm:rounded-xl transition-all"
                >
                    <Send size={16} className={inputValue.trim() && !isLoading && !isRateLimited ? 'translate-x-0.5 -translate-y-0.5 transition-transform' : ''} />
                </button>
            </form>
            <div className={`text-center mt-2.5 text-[11px] text-[#aaa] font-medium tracking-tight ${messages.length === 0 ? 'block' : 'hidden sm:block'}`}>
                AI answers can be wrong. Confirm figures that drive decisions.
            </div>
        </div>
    );

    return (
        <div className="flex flex-col h-full bg-[#f4f4f2] overflow-hidden relative font-sans w-full max-w-full">

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-3 sm:px-6 md:px-8 custom-scrollbar">
                <div className="max-w-3xl mx-auto flex flex-col pt-4 sm:pt-8 pb-28 sm:pb-32">
                    {messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center mt-12 sm:mt-20 fade-in px-2">
                            <Activity size={40} className="text-[#111] mb-5 stroke-[1.5]" />
                            <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#111] text-center">
                                What would you like to know?
                            </h3>
                            <p className="text-[#777] mt-2.5 text-center max-w-sm text-[14px] sm:text-[15px] font-medium leading-relaxed">
                                Ask in everyday language. This sandbox uses a sales dataset — try counts, lists,
                                or filters.
                            </p>
                            <div className="mt-6 sm:mt-8 flex flex-col sm:flex-row flex-wrap justify-center gap-2 sm:gap-3 text-sm w-full max-w-lg">
                                <button
                                    type="button"
                                    className="bg-white text-[#333] px-4 py-2 rounded-full border border-[#ddd] hover:border-[#111] hover:bg-[#111] hover:text-white transition-all text-[13px] font-medium"
                                    onClick={() => setInputValue('What are my top 10 products according to sales?')}
                                >
                                    Top 10 products by sales?
                                </button>
                                <button
                                    type="button"
                                    className="bg-white text-[#333] px-4 py-2 rounded-full border border-[#ddd] hover:border-[#111] hover:bg-[#111] hover:text-white transition-all text-[13px] font-medium"
                                    onClick={() => setInputValue('Which region is performing the best?')}
                                >
                                    Which region performs best?
                                </button>
                            </div>

                            <div className="w-full max-w-2xl mt-6 sm:mt-8">
                                {renderInputForm()}
                            </div>
                        </div>
                    ) : (
                        messages.map((msg, idx) => (
                            <MessageBubble
                                key={msg.id}
                                message={msg}
                                isLast={idx === messages.length - 1}
                                onSend={sendMessage}
                            />
                        ))
                    )}

                    <StatusIndicator status={isLoading ? 'Working on your question…' : null} />
                    <div ref={messagesEndRef} className="h-4" />
                </div>
            </div>

            {/* Input Area (Bottom pinned when chat is active) */}
            {messages.length > 0 && (
                <div className="absolute bottom-0 left-0 right-0 bg-[#f4f4f2]/95 backdrop-blur-sm border-t border-[#e5e5e3] py-3 px-3 sm:px-4 md:px-0 z-10 w-full shrink-0">
                    <div className="max-w-3xl mx-auto">
                        {renderInputForm()}
                    </div>
                </div>
            )}
        </div>
    );
}
