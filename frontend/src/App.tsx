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

      {/* Minimal Header — responsive */}
      <header className="h-12 sm:h-14 px-3 sm:px-6 border-b border-[#e5e5e3] flex items-center justify-between shrink-0">
        <button
          onClick={() => setCurrentView('landing')}
          className="flex items-center space-x-1.5 text-[#111] hover:opacity-60 transition-opacity font-semibold text-sm"
        >
          <ArrowLeft size={15} />
          <span className="hidden sm:inline">Back</span>
        </button>

        <div className="flex items-center space-x-1.5 font-bold text-base sm:text-lg tracking-tighter">
          <span>Dfuse</span>
          <span className="text-[9px] sm:text-[10px] uppercase tracking-widest bg-[#111] text-[#f4f4f2] px-1.5 py-0.5 rounded-sm">Data</span>
        </div>

        {/* Spacer to center logo */}
        <div className="w-12 sm:w-16" />
      </header>

      {/* Main Chat Area Container */}
      <main className="flex-1 flex flex-col overflow-hidden">
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
