import React, { useState } from 'react';
import { Search, Plus, Trash2, Edit2, X, Check } from 'lucide-react';
import { Session } from '../types';

interface LeftSidebarProps {
  isOpen: boolean;
  sessions: Session[];
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onCreateSession: () => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
  onEditSession: (id: string, newTitle: string) => void;
  onSearch: (keyword: string) => void;
  onClearSearch: () => void;
  isSearchMode: boolean;
}

export const LeftSidebar: React.FC<LeftSidebarProps> = ({
  isOpen,
  sessions,
  currentSessionId,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
  onEditSession,
  onSearch,
  onClearSearch,
  isSearchMode
}) => {
  const [searchValue, setSearchValue] = useState('');
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const handleSearch = () => {
    if (searchValue.trim()) {
      onSearch(searchValue.trim());
    }
  };

  const handleClearSearch = () => {
    setSearchValue('');
    onClearSearch();
  };

  const handleStartEdit = (session: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(session.session_id || session.id);
    setEditTitle(session.title);
  };

  const handleSaveEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (editingSessionId && editTitle.trim()) {
      onEditSession(editingSessionId, editTitle.trim());
    }
    setEditingSessionId(null);
  };

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(null);
  };

  return (
    <div
      className={`
        bg-gradient-sidebar backdrop-blur-md border-r border-green-200/40 h-full flex flex-col
        transition-all duration-500 ease-[cubic-bezier(0.25,1,0.5,1)] overflow-hidden
        ${isOpen ? 'w-80 opacity-100 translate-x-0' : 'w-0 opacity-0 -translate-x-10'}
      `}
    >
      <div className="w-80 h-full flex flex-col p-5">

        {/* Search */}
        <div className="relative mb-4 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-400" />
            <input
              type="text"
              placeholder="搜索..."
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full pl-9 pr-4 py-2.5 bg-white/70 backdrop-blur-sm rounded-xl border border-green-200/50 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-100 transition-all text-sm text-slate-700 placeholder:text-green-300"
            />
            {searchValue && (
              <button
                onClick={handleClearSearch}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-green-400 hover:text-green-600 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          {isSearchMode ? (
            <button
              onClick={handleClearSearch}
              className="px-3 py-2 text-xs font-semibold text-green-600 hover:text-green-700 bg-white/60 hover:bg-white rounded-xl transition-all border border-green-200/50"
            >
              取消
            </button>
          ) : (
            <button
              onClick={handleSearch}
              disabled={!searchValue.trim()}
              className="px-3 py-2 text-xs font-semibold text-white bg-gradient-to-r from-green-400 to-green-500 hover:from-green-500 hover:to-green-600 rounded-xl transition-all disabled:opacity-60 disabled:from-green-200 disabled:to-green-300 disabled:text-green-500 shadow-soft-sm"
            >
              搜索
            </button>
          )}
        </div>

        {/* New Session Button */}
        <button
          onClick={onCreateSession}
          className="w-full bg-gradient-to-r from-green-400 to-green-500 hover:from-green-500 hover:to-green-600 text-white font-semibold py-3 px-4 rounded-xl shadow-soft-md hover:shadow-soft-lg active:scale-[0.98] transition-all mb-8 flex items-center justify-center gap-2"
        >
          <Plus className="w-5 h-5" />
          新建会话
        </button>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar">
          <h3 className="text-xs font-bold text-green-700 uppercase tracking-wider mb-3">会话列表</h3>
          <div className="space-y-2">
            {sessions.map((session, index) => (
              <div
                key={session.session_id}
                onClick={() => onSelectSession(session.session_id!)}
                className={`
                  group relative flex items-center px-3 py-3 rounded-xl cursor-pointer border transition-all duration-200
                  animate-stagger-in
                  ${session.session_id === currentSessionId
                    ? 'bg-gradient-to-r from-green-100 to-green-50 border-green-200/70 font-medium shadow-soft-sm'
                    : 'bg-white/40 border-transparent hover:bg-white/70 hover:border-green-100 text-slate-600'
                  }
                `}
                style={{ animationDelay: `${index * 30}ms` }}
              >
                {editingSessionId === (session.session_id || session.id) ? (
                  <div className="flex-1 flex items-center gap-1 mr-2" onClick={e => e.stopPropagation()}>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="flex-1 min-w-0 px-2 py-1 text-xs border-2 rounded-lg border-green-400 focus:outline-none bg-white"
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveEdit(e as any);
                        if (e.key === 'Escape') handleCancelEdit(e as any);
                      }}
                    />
                    <button onClick={handleSaveEdit} className="p-1 text-green-500 hover:bg-green-50 rounded-lg transition-colors">
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={handleCancelEdit} className="p-1 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className={`flex-1 truncate pr-8 text-sm ${session.session_id === currentSessionId ? 'text-green-700' : 'text-slate-700'}`}>
                    {session.title}
                  </div>
                )}

                {/* Actions */}
                <div className={`absolute right-2 flex gap-1 ${session.session_id === currentSessionId ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}>
                   {session.session_id === currentSessionId && !editingSessionId && (
                     <>
                        <button
                          onClick={(e) => handleStartEdit(session, e)}
                          className="p-1.5 hover:bg-white/80 rounded-lg text-green-500 hover:text-green-600 transition-colors"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={(e) => onDeleteSession(session.session_id!, e)}
                          className="p-1.5 hover:bg-red-50 rounded-lg text-green-500 hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                     </>
                   )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
