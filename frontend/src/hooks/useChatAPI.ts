import { useState, useCallback } from 'react';

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    status?: 'completed' | 'awaiting_clarification' | 'error';
    spreadsheetHtml?: string | null;
    sql?: string | null;
    queryResult?: any[] | null;
    visualizationConfig?: any | null;
    clarificationOptions?: string[] | null;
    timestamp: Date;
}

export function useChatAPI(projectId: string) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [backendHistory, setBackendHistory] = useState<any[]>([]);
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const sendMessage = useCallback(async (content: string) => {
        // 1. Add user message to UI
        const userMsg: Message = {
            id: crypto.randomUUID(),
            role: 'user',
            content,
            timestamp: new Date()
        };
        setMessages(prev => [...prev, userMsg]);
        setIsLoading(true);

        try {
            // 2. Make API call
            const payload = {
                text: content,
                history: backendHistory,
                conversation_id: conversationId,
                project_id: projectId
            };

            const response = await fetch('http://localhost:8000/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const data = await response.json();

            // 3. Update internal state based on response
            setConversationId(data.conversation_id);
            setBackendHistory(data.history || []);

            // 4. Add assistant message to UI
            const assistantMsg: Message = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: data.Agent_response || "No response text.",
                status: data.status,
                spreadsheetHtml: data.spreadsheet_structure,
                sql: data.generated_sql,
                queryResult: data.query_result,
                visualizationConfig: data.visualization_config,
                clarificationOptions: data.clarification_options,
                timestamp: new Date()
            };
            
            setMessages(prev => [...prev, assistantMsg]);

        } catch (err: any) {
            console.error('Chat API Error:', err);
            
            const errorMsg: Message = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: `Error: ${err.message}`,
                status: 'error',
                timestamp: new Date()
            };
            setMessages(prev => [...prev, errorMsg]);
        } finally {
            setIsLoading(false);
        }
    }, [backendHistory, conversationId, projectId]);

    const sendQuestionChange = useCallback((content: string) => {
        // If the user wants to completely start over with a new question
        setConversationId(null);
        setBackendHistory([]);
        sendMessage(content);
    }, [sendMessage]);

    return {
        messages,
        isLoading,
        sendMessage,
        sendQuestionChange
    };
}
