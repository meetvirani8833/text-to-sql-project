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
                <div className="absolute -top-12 left-0 right-0 flex justify-center fade-in">
                    <div className="bg-[#111] text-[#f4f4f2] text-xs font-bold uppercase tracking-widest px-4 py-2 rounded-md shadow-lg flex items-center gap-2">
                        <ShieldAlert size={14} />
                        <span>Demo rate limit reached ({queryCount}/{RATE_LIMIT} IP Requests)</span>
                    </div>
                </div>
            )}

            <form
                onSubmit={handleSend}
                className={`relative rounded-2xl border-[1.5px] bg-[#fff] shadow-xl overflow-hidden transition-colors ${isRateLimited && !isLoading ? 'border-red-300' : 'border-[#111] focus-within:border-[#333]'}`}
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
                    placeholder={isLoading ? 'Preparing your answer…' : isRateLimited ? 'Demo limit reached-contact us for full access.' : isAwaitingClarification ? 'Please select an option above to continue.' : 'Ask Dfuse Data in plain language…'}
                    className={`w-full bg-transparent text-[#111] placeholder:text-[#888] pl-5 pr-14 py-5 focus:outline-none resize-none min-h-[60px] max-h-[200px] text-base font-medium ${(isRateLimited || isAwaitingClarification) ? 'opacity-50 cursor-not-allowed' : ''}`}
                    rows={1}
                />
                <button
                    type="submit"
                    disabled={!inputValue.trim() || isLoading || isRateLimited || isAwaitingClarification}
                    className="absolute right-3 bottom-3 p-2 bg-[#111] hover:bg-[#333] disabled:bg-[#ddd] disabled:text-[#999] text-[#f4f4f2] rounded-xl transition-all"
                >
                    <Send size={18} className={inputValue.trim() && !isLoading && !isRateLimited ? 'translate-x-0.5 -translate-y-0.5 transition-transform' : ''} />
                </button>
            </form>
            <div className={`text-center mt-3 text-xs text-[#666] font-medium tracking-tight ${messages.length === 0 ? 'block' : 'hidden md:block'}`}>
                AI-assisted answers can be wrong. Confirm figures that drive decisions with your data owners.
            </div>
        </div>
    );

    return (
        <div className="flex flex-col h-full bg-[#f4f4f2] overflow-hidden relative font-sans w-full max-w-full">

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 md:p-8 custom-scrollbar">
                <div className="max-w-3xl mx-auto flex flex-col pt-8 pb-32">
                    {messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center mt-20 fade-in">
                            <Activity size={48} className="text-[#111] mb-6 stroke-[1.5]" />
                            <h3 className="text-2xl font-bold tracking-tight text-[#111]">What would you like to know from your data?</h3>
                            <p className="text-[#666] mt-3 text-center max-w-md font-medium">
                                Ask in everyday language. This sandbox uses a sales dataset - try counts, lists,
                                or filters the way you would ask a colleague.
                            </p>
                            <div className="mt-8 flex flex-wrap justify-center gap-3 text-sm max-w-lg">
                                <button type="button" className="bg-[#e4e4e2] text-[#333] px-3 py-1.5 rounded-full border border-[#d4d4d2] hover:bg-[#d4d4d2] transition-colors" onClick={() => setInputValue('What are my top 10 products according to sales?')}>What are my top 10 products according to sales?</button>
                                <button type="button" className="bg-[#e4e4e2] text-[#333] px-3 py-1.5 rounded-full border border-[#d4d4d2] hover:bg-[#d4d4d2] transition-colors" onClick={() => setInputValue('Which region is performing the best?')}>Which region is performing the best?</button>
                            </div>
                            
                            <div className="w-full max-w-2xl mt-8">
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
                <div className="absolute bottom-0 left-0 right-0 bg-[#f4f4f2] border-t border-[#ddddda] pt-4 pb-4 px-4 md:px-0 z-10 w-full shrink-0">
                    <div className="max-w-3xl mx-auto">
                        {renderInputForm()}
                    </div>
                </div>
            )}
        </div>
    );
}
