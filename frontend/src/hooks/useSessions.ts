import { useState, useEffect, useCallback } from 'react';
import { Session } from '../types';
import { sessionApi } from '../api/session';

export const useSessions = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<Session[]>([]);
  const [isSearchMode, setIsSearchMode] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Confirm Modal State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    try {
      const res = await sessionApi.list();
      const mappedSessions = res.sessions.map(s => ({
        ...s,
        id: s.session_id,
        active: false
      }));
      setSessions(mappedSessions);
    } catch (error) {
      console.error('Failed to load sessions', error);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleSelectSession = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
    setSessions(prev => prev.map(s => ({ ...s, active: s.session_id === sessionId })));
  }, []);

  const handleCreateSession = useCallback(async (title: string) => {
    try {
      const res = await sessionApi.create({ title });
      const newSession: Session & { session_id?: string; created_at?: string; updated_at?: string } = {
          session_id: res.session_id,
          id: res.session_id,
          title: title,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          active: true
      };
      setSessions(prev => [newSession as Session, ...prev.map(s => ({...s, active: false}))]);
      setCurrentSessionId(res.session_id);
      return res.session_id;
    } catch (error) {
      console.error('Failed to create session', error);
      throw error;
    }
  }, []);

  const handleResetSession = useCallback(() => {
    setCurrentSessionId(null);
    setSessions(prev => prev.map(s => ({...s, active: false})));
  }, []);

  const handleDeleteSession = useCallback((sessionId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setSessionToDelete(sessionId);
    setIsDeleteModalOpen(true);
  }, []);

  const confirmDeleteSession = useCallback(async () => {
    if (!sessionToDelete) return;

    const sessionId = sessionToDelete;
    try {
      await sessionApi.delete(sessionId);
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
      setSearchResults(prev => prev.filter(s => s.session_id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
      }
      setIsDeleteModalOpen(false);
      setSessionToDelete(null);
    } catch (error) {
      console.error('Failed to delete session', error);
    }
  }, [sessionToDelete, currentSessionId]);

  const handleEditSession = useCallback(async (sessionId: string, newTitle: string) => {
    try {
      await sessionApi.update(sessionId, { title: newTitle });
      const updateList = (list: Session[]) => list.map(s =>
        s.session_id === sessionId ? { ...s, title: newTitle } : s
      );
      setSessions(prev => updateList(prev));
      setSearchResults(prev => updateList(prev));
    } catch (error) {
      console.error('Failed to update session', error);
    }
  }, []);

  const handleSearchSessions = useCallback(async (keyword: string) => {
    try {
      setIsLoadingHistory(true);
      const res = await sessionApi.search(keyword);
      const mappedSessions = res.sessions.map(s => ({
        ...s,
        id: s.session_id,
        active: s.session_id === currentSessionId
      }));
      setSearchResults(mappedSessions);
      setIsSearchMode(true);
    } catch (error) {
      console.error('Failed to search sessions', error);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [currentSessionId]);

  const handleClearSearch = useCallback(() => {
    setIsSearchMode(false);
    setSearchResults([]);
    loadSessions();
  }, [loadSessions]);

  return {
    sessions,
    setSessions,
    currentSessionId,
    setCurrentSessionId,
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
  };
};
