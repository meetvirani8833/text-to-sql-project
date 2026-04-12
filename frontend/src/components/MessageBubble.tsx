import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Code2, Database, BarChart3, Table2, ChevronDown, ChevronUp } from 'lucide-react';
import type { Message } from '../hooks/useChatAPI';
import { DynamicChart } from './DynamicChart';

interface MessageBubbleProps {
    message: Message;
    isLast?: boolean;
    onSend?: (content: string) => void;
}

export function MessageBubble({ message, isLast, onSend }: MessageBubbleProps) {
    const isUser = message.role === 'user';
    const [showChart, setShowChart] = useState(false);
    const [showTable, setShowTable] = useState(true);
    const [showSql, setShowSql] = useState(false);
    const chartRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to chart when it becomes visible
    useEffect(() => {
        if (showChart && chartRef.current) {
            // Short delay to let the chart render first
            setTimeout(() => {
                chartRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 100);
        }
    }, [showChart]);

    if (isUser) {
        return (
            <div className="flex w-full mt-6 justify-end animate-fade-in">
                <div className="max-w-[85%] sm:max-w-[75%]">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-[#999] mb-1.5 text-right pr-1">You</div>
                    <div className="bg-[#111] text-[#f4f4f2] px-4 sm:px-5 py-3 sm:py-3.5 rounded-2xl rounded-tr-sm text-[15px] leading-relaxed font-medium">
                        {message.content}
                    </div>
                </div>
            </div>
        );
    }

    /* ─── Assistant message ─── */
    return (
        <div className="flex w-full mt-6 animate-fade-in gap-3">
            {/* Avatar */}
            <div className="flex-shrink-0 mt-0.5 h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-[#111] flex items-center justify-center">
                <Database size={13} className="text-[#f4f4f2]" />
            </div>

            <div className="flex-1 min-w-0">
                {/* Summary text */}
                {message.content && (
                    <div className="prose prose-sm max-w-none
                        prose-p:text-[#333] prose-p:leading-[1.7] prose-p:text-[14px] prose-p:sm:text-[15px] prose-p:tracking-[-0.01em]
                        prose-strong:text-[#111] prose-strong:font-semibold
                        prose-ul:mt-2 prose-ul:mb-2 prose-li:text-[14px] prose-li:sm:text-[15px] prose-li:text-[#333] prose-li:leading-[1.7]
                        prose-a:text-[#111] prose-a:underline prose-a:decoration-[#999] hover:prose-a:decoration-[#111]
                        prose-headings:tracking-tight prose-headings:text-[#111]">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.content}
                        </ReactMarkdown>
                    </div>
                )}

                {/* SQL collapsible */}
                {message.sql && (
                    <div className="mt-4">
                        <button
                            type="button"
                            onClick={() => setShowSql(!showSql)}
                            className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-[#999] hover:text-[#666] transition-colors"
                        >
                            <Code2 size={13} />
                            <span>SQL Query</span>
                            {showSql ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                        {showSql && (
                            <div className="mt-2 rounded-lg overflow-hidden border border-[#e0e0de] bg-[#1e1e1e]">
                                <SyntaxHighlighter
                                    language="sql"
                                    style={vscDarkPlus}
                                    customStyle={{
                                        margin: 0,
                                        padding: '0.875rem 1rem',
                                        background: 'transparent',
                                        fontSize: '0.8rem',
                                        lineHeight: '1.6',
                                    }}
                                    wrapLines
                                    wrapLongLines
                                >
                                    {message.sql}
                                </SyntaxHighlighter>
                            </div>
                        )}
                    </div>
                )}

                {/* Error state */}
                {message.status === 'error' && (
                    <div className="mt-4 text-[13px] text-red-700 font-medium border-l-2 border-red-400 pl-3 py-1.5 bg-red-50/50 rounded-r-md">
                        Something went wrong processing your request. Try rephrasing or ask a simpler question.
                    </div>
                )}

                {/* Clarification buttons */}
                {message.status === 'awaiting_clarification' && message.clarificationOptions && (
                    <div className="mt-5 flex flex-col gap-2 w-full max-w-sm animate-fade-in">
                        {message.clarificationOptions.map((opt, idx) => (
                            <button
                                key={idx}
                                disabled={!isLast}
                                onClick={() => onSend && onSend(String(idx + 1))}
                                className={`w-full text-left px-4 py-2.5 rounded-lg text-[14px] font-medium transition-all flex items-center justify-between border
                                    ${!isLast
                                        ? 'bg-transparent border-[#e8e8e6] text-[#bbb] cursor-not-allowed'
                                        : 'bg-white border-[#ddd] text-[#111] hover:border-[#111] hover:bg-[#111] hover:text-white group shadow-sm'
                                    }`}
                            >
                                <span className="truncate">{opt}</span>
                                {isLast && (
                                    <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px] uppercase tracking-widest font-bold ml-2 shrink-0">
                                        Select&rarr;
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                )}

                {/* Data table */}
                {message.spreadsheetHtml && (
                    <div className="mt-5 w-full animate-slide-up">
                        <button
                            type="button"
                            onClick={() => setShowTable(!showTable)}
                            className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-[#999] hover:text-[#666] transition-colors mb-2"
                        >
                            <Table2 size={13} />
                            <span>Data Table</span>
                            {showTable ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                        {showTable && (
                            <div className="bg-white rounded-lg border border-[#e0e0de] overflow-hidden shadow-sm custom-html-table">
                                <div
                                    dangerouslySetInnerHTML={{ __html: message.spreadsheetHtml }}
                                    className="overflow-x-auto text-[13px]"
                                />
                            </div>
                        )}
                    </div>
                )}

                {/* Visualization toggle + chart */}
                {message.visualizationConfig && message.queryResult && (
                    <div className="mt-5 w-full animate-fade-in flex flex-col items-start">
                        <button
                            type="button"
                            onClick={() => setShowChart(!showChart)}
                            className="flex items-center space-x-2 bg-[#f4f4f2] text-[#333] border border-[#ddd] hover:border-[#111] hover:bg-[#111] hover:text-[#f4f4f2] transition-all py-2 px-4 rounded-lg text-xs font-bold uppercase tracking-wider"
                        >
                            <BarChart3 size={14} />
                            <span>{showChart ? 'Hide Visualization' : 'Visualize Data'}</span>
                        </button>

                        {showChart && (
                            <div className="w-full" ref={chartRef}>
                                <DynamicChart config={message.visualizationConfig} data={message.queryResult} />
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
