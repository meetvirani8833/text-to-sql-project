import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Code2, Database } from 'lucide-react';
import type { Message } from '../hooks/useChatAPI';

interface MessageBubbleProps {
    message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user';

    return (
        <div className={`flex w-full mt-8 animate-fade-in`}>

            {/* AI Avatar */}
            {!isUser && (
                <div className="flex-shrink-0 mt-1 mr-4 h-8 w-8 rounded-full bg-[#111] flex items-center justify-center">
                    <Database size={14} className="text-[#f4f4f2]" />
                </div>
            )}

            <div className={`w-full flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                {isUser && (
                    <div className="text-xs font-bold uppercase tracking-widest text-[#888] mb-2 px-1">You</div>
                )}
                
                <div
                    className={`max-w-[85%] relative
                        ${isUser
                            ? 'bg-[#111] text-[#f4f4f2] px-6 py-4 rounded-2xl rounded-tr-sm'
                            : 'text-[#111] rounded-tl-sm w-full max-w-full'
                        }`}
                >
                    {message.content && (
                        <div className={`prose prose-sm md:prose-base max-w-none prose-p:leading-relaxed prose-pre:my-2 prose-a:text-indigo-600 ${isUser ? 'prose-invert' : 'prose-slate'}`}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {message.content}
                            </ReactMarkdown>
                        </div>
                    )}

                    {message.sql && (
                        <div className="mt-4 rounded-xl overflow-hidden border border-[#ddd] bg-[#1e1e1e]">
                            <div className="bg-[#2d2d2d] px-4 py-2 flex items-center space-x-2 border-b border-[#333]">
                                <Code2 size={14} className="text-[#a0a0a0]" />
                                <span className="text-xs font-mono text-[#a0a0a0] uppercase tracking-wider">Database query</span>
                            </div>
                            <SyntaxHighlighter
                                language="sql"
                                style={vscDarkPlus}
                                customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '0.85rem' }}
                                wrapLines={true}
                            >
                                {message.sql}
                            </SyntaxHighlighter>
                        </div>
                    )}

                    {message.status === 'error' && (
                        <div className="mt-4 text-red-600 text-sm font-medium border-l-2 border-red-500 pl-4 py-1 bg-red-50">
                            An error occurred while processing your request. Please try again or rephrase.
                        </div>
                    )}
                </div>

                {message.spreadsheetHtml && (
                    <div className="mt-6 w-full animate-slide-up bg-[#fff] rounded-none border border-[#ccc] overflow-hidden p-6 custom-html-table">
                        <div 
                            dangerouslySetInnerHTML={{ __html: message.spreadsheetHtml }} 
                            className="overflow-x-auto text-sm"
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
