import React, { useState } from 'react';
import { LeftSidebar } from './components/LeftSidebar';
import { RightSidebar } from './components/RightSidebar';
import { ChatMessage } from './components/ChatMessage';
import { ConfirmModal } from './components/ConfirmModal';
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Square, Send, Globe, ChevronDown } from 'lucide-react';
import { ROUTE_MODE_OPTIONS, RouteMode } from './types';

// Custom Hooks
import { useSessions } from './hooks/useSessions';
import { useKnowledgeBase } from './hooks/useKnowledgeBase';
import { useChat } from './hooks/useChat';

const App: React.FC = () => {
  // UI Layout State
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);

  // Custom Hooks - State & Logic
  const {
    sessions,
    currentSessionId,
    searchResults,
    isSearchMode,
    isLoadingHistory,
    setIsLoadingHistory,
    isDeleteModalOpen,
    setIsDeleteModalOpen,
    handleSelectSession,
    handleCreateSession,
    handleResetSession,
    handleDeleteSession,
    confirmDeleteSession,
    handleEditSession,
    handleSearchSessions,
    handleClearSearch
  } = useSessions();

  const {
    kbItems,
    toggleKBSelection
  } = useKnowledgeBase();

  const {
    messages,
    inputValue,
    setInputValue,
    isGenerating,
    isUserScrolling,
    enableWebSearch,
    setEnableWebSearch,
    routeMode,
    setRouteMode,
    messagesEndRef,
    chatContainerRef,
    handleScroll,
    handleSendMessage,
    handleEditMessage,
    handleRegenerate,
    handleStopGeneration,
    handleKeyDown
  } = useChat(currentSessionId, setIsLoadingHistory, handleCreateSession);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-gradient-main p-2 sm:p-4 gap-4 relative">

      {/* 背景装饰光斑 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {/* 左上光斑 */}
        <div className="
          absolute -top-20 -left-20 w-64 h-64
          bg-gradient-radial from-green-200/30 to-transparent
          rounded-full blur-3xl
          animate-float-blob
        " />
        {/* 右下光斑 */}
        <div className="
          absolute -bottom-32 -right-32 w-96 h-96
          bg-gradient-radial from-green-300/20 to-transparent
          rounded-full blur-3xl
          animate-float-blob animation-delay-1000
        " />
        {/* 中间右侧光斑 */}
        <div className="
          absolute top-1/2 -right-20 w-72 h-72
          bg-gradient-radial from-emerald-200/25 to-transparent
          rounded-full blur-3xl
          animate-float-blob animation-delay-500
        " />
      </div>

      <div className="flex-1 flex w-full h-full max-w-[1920px] mx-auto overflow-hidden rounded-[32px] bg-gradient-to-br from-white/80 to-green-50/60 backdrop-blur-md border border-green-200/40 shadow-soft-xl relative transition-shadow duration-300 hover:shadow-2xl">

        {/* Left Sidebar */}
        <LeftSidebar
          isOpen={isLeftSidebarOpen}
          sessions={isSearchMode ? searchResults : sessions}
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onCreateSession={handleResetSession}
          onDeleteSession={handleDeleteSession}
          onEditSession={handleEditSession}
          onSearch={handleSearchSessions}
          onClearSearch={handleClearSearch}
          isSearchMode={isSearchMode}
        />

        {/* Main Content */}
        <div className="flex-1 flex flex-col h-full bg-gradient-to-b from-cream-100/80 to-cream-200/50 relative min-w-0">

          {/* Header */}
          <div className="h-14 flex items-center justify-between px-6 border-b border-green-100/50 bg-white/50 backdrop-blur-sm">
             <div className="flex items-center">
                <button
                  onClick={() => setIsLeftSidebarOpen(!isLeftSidebarOpen)}
                  className="p-2 hover:bg-green-50 rounded-xl text-green-600 transition-all duration-200 hover:shadow-sm"
                  title="Toggle Sidebar"
                >
                  {isLeftSidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
                </button>
             </div>
             <div className="font-semibold text-green-700">
                {sessions.find(s => s.session_id === currentSessionId)?.title || '新会话'}
             </div>
             <div className="flex items-center">
                <button
                  onClick={() => setIsRightSidebarOpen(!isRightSidebarOpen)}
                  className="p-2 hover:bg-green-50 rounded-xl text-green-600 transition-all duration-200 hover:shadow-sm"
                  title="Toggle Knowledge Base"
                >
                  {isRightSidebarOpen ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
                </button>
             </div>
          </div>

          {/* Chat Messages Area */}
          <div
            ref={chatContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-6 sm:p-8 space-y-6 custom-scrollbar"
          >
            {messages.length === 0 && !isLoadingHistory && (
               <div className="flex flex-col items-center justify-center h-full text-green-400 opacity-60">
                  <div className="bg-gradient-to-br from-green-100 to-green-50 p-6 rounded-2xl mb-4 shadow-soft-md">
                     <Square className="w-12 h-12 text-green-300" />
                  </div>
                  <p className="text-lg font-medium text-green-600">开始新对话</p>
               </div>
            )}

            {messages.map((msg, index) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                onEdit={(msgId, content) => handleEditMessage(msgId, content, kbItems)}
                onRegenerate={handleRegenerate}
                isGenerating={isGenerating}
                isLast={index === messages.length - 1}
              />
            ))}

            <div ref={messagesEndRef} className="h-24"></div>
          </div>

          {/* Chat Input Area */}
          <div className="absolute bottom-6 left-0 right-0 px-6 sm:px-8">
            {/* 控制选项栏：联网搜索 + 路由模式 */}
            <div className="flex items-center gap-2 mb-2">
              {/* 联网搜索开关 */}
              <button
                onClick={() => setEnableWebSearch(!enableWebSearch)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium transition-all duration-200 border ${
                  enableWebSearch
                    ? 'bg-sky-50 text-sky-600 border-sky-200 hover:bg-sky-100 shadow-sm'
                    : 'bg-white/50 text-slate-400 border-transparent hover:bg-white hover:text-slate-600 hover:border-green-100'
                }`}
                title={enableWebSearch ? '点击禁用联网搜索' : '点击启用联网搜索'}
              >
                <Globe className={`w-4 h-4 ${enableWebSearch ? 'text-sky-500' : 'text-slate-400'}`} />
                <span>联网搜索</span>
              </button>

              {/* 路由模式选择 */}
              <div className="relative group">
                <select
                  value={routeMode}
                  onChange={(e) => setRouteMode(e.target.value as RouteMode)}
                  className="appearance-none pl-3 pr-8 py-1.5 rounded-xl text-sm font-medium transition-all duration-200 bg-white/60 backdrop-blur-sm text-slate-600 border border-green-100/50 hover:bg-white/80 hover:border-green-200 hover:shadow-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-green-200/50 focus:border-green-300"
                  title="选择路由模式"
                >
                  {ROUTE_MODE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-green-400 pointer-events-none transition-transform duration-200 group-hover:text-green-500" />
              </div>
            </div>
            <div className="group relative bg-white/90 backdrop-blur-md border border-green-200/50 rounded-2xl shadow-soft-md p-2 flex items-end gap-3 transition-all duration-300 focus-within:shadow-soft-lg focus-within:border-green-300 focus-within:ring-4 focus-within:ring-green-100/50">
              {/* 聚焦时的流光边框效果 */}
              <div className="
                absolute inset-0 rounded-2xl
                bg-gradient-to-r from-green-300/0 via-green-400/20 to-green-300/0
                opacity-0 group-focus-within:opacity-100
                transition-opacity duration-500
                pointer-events-none
                bg-[length:200%_100%]
                animate-border-shimmer
              " />
              <textarea
                className={`relative z-10 flex-1 bg-transparent border-none focus:ring-0 focus:outline-none resize-none p-3 text-slate-700 placeholder:text-slate-400 font-medium transition-all duration-200 ${isGenerating ? 'cursor-not-allowed opacity-60' : ''}`}
                placeholder={isGenerating ? "正在生成回复..." : "输入消息..."}
                style={{ height: '52px', minHeight: '52px', maxHeight: '192px' }}
                value={inputValue}
                onChange={(e) => {
                  setInputValue(e.target.value);
                  e.target.style.height = '52px';
                  if (e.target.value.trim()) {
                    const newHeight = Math.min(Math.max(52, e.target.scrollHeight), 192);
                    e.target.style.height = `${newHeight}px`;
                  }
                }}
                onKeyDown={(e) => handleKeyDown(e, kbItems)}
                disabled={isGenerating}
              />

              {isGenerating ? (
                <button
                  onClick={handleStopGeneration}
                  className="relative z-10 h-[40px] px-4 bg-gradient-to-r from-rose-400 to-rose-500 hover:from-rose-500 hover:to-rose-600 text-white font-semibold rounded-xl transition-all duration-200 flex items-center gap-2 mb-[6px] shadow-sm active:scale-95 text-sm"
                >
                   <Square className="w-3.5 h-3.5 fill-current" />
                   <span>停止</span>
                </button>
              ) : (
                <button
                  onClick={() => handleSendMessage(kbItems)}
                  disabled={!inputValue.trim()}
                  className="relative z-10 h-[40px] px-4 bg-gradient-to-r from-green-400 to-green-500 hover:from-green-500 hover:to-green-600 text-white font-semibold rounded-xl transition-all duration-200 flex items-center gap-2 mb-[6px] shadow-sm active:scale-95 text-sm disabled:opacity-60 disabled:cursor-not-allowed disabled:from-green-200 disabled:to-green-300 disabled:text-green-500"
                >
                   <Send className="w-3.5 h-3.5" />
                   <span>发送</span>
                </button>
              )}
            </div>
          </div>

        </div>

        {/* Right Sidebar */}
        <RightSidebar
          isOpen={isRightSidebarOpen}
          kbItems={kbItems}
          onToggleKB={toggleKBSelection}
        />

        {/* Delete Session Confirm Modal */}
        <ConfirmModal
          isOpen={isDeleteModalOpen}
          onClose={() => setIsDeleteModalOpen(false)}
          onConfirm={confirmDeleteSession}
          title="删除会话"
          message="确定要删除此会话吗？此操作无法撤销。"
          isDestructive={true}
          confirmText="删除"
        />

      </div>
    </div>
  );
};

export default App;
