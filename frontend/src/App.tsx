import { useState } from 'react';
import { ChatPanel } from './components/ChatPanel';
import { LandingPage } from './components/LandingPage';
import { ArrowLeft } from 'lucide-react';
import { useChatAPI } from './hooks/useChatAPI';

function App() {
  const [currentView, setCurrentView] = useState<'landing' | 'chat'>('landing');

  // Using a default project ID for the MVP
  const PROJECT_ID = "default";
  const chatState = useChatAPI(PROJECT_ID);

  if (currentView === 'landing') {
    return <LandingPage onStartDemo={() => setCurrentView('chat')} />;
  }

  return (
    <div className="h-screen overflow-hidden bg-[#f4f4f2] text-[#111111] font-sans flex flex-col selection:bg-[#111] selection:text-[#f4f4f2]">

      {/* Minimal Header */}
      <header className="h-16 px-6 border-b border-[#ddddda] flex items-center justify-between shrink-0">
        <button
          onClick={() => setCurrentView('landing')}
          className="flex items-center space-x-2 text-[#111] hover:opacity-60 transition-opacity font-semibold"
        >
          <ArrowLeft size={16} />
          <span>Back</span>
        </button>

        <div className="flex items-center space-x-2 font-bold text-lg tracking-tighter">
          <span>Dfuse</span>
          <span className="text-[10px] uppercase tracking-widest bg-[#111] text-[#f4f4f2] px-1.5 py-0.5 rounded-sm">Data</span>
        </div>
      </header>

      {/* Main Chat Area Container */}
      <main className="flex-1 flex flex-col h-[calc(100vh-64px)] overflow-hidden">
        <ChatPanel 
          messages={chatState.messages}
          isLoading={chatState.isLoading}
          sendMessage={chatState.sendMessage}
        />
      </main>

    </div>
  );
}

export default App;
