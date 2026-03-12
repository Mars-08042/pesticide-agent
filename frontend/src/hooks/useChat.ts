import { useState, useRef, useEffect, useCallback } from 'react';
import { Message, AgentStep, StepType, SSEEvent, KBItem, RouteMode, OptimizationTarget } from '../types';
import { chatApi } from '../api/chat';
import { useToast } from '../components/Toast';

export const useChat = (
  currentSessionId: string | null,
  setIsLoadingHistory: (loading: boolean) => void,
  handleCreateSession: (title: string) => Promise<string>
) => {
  const { warning, error: showError } = useToast();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [generatingSessions, setGeneratingSessions] = useState<Set<string>>(new Set());
  const [isUserScrolling, setIsUserScrolling] = useState(false);
  const [routeMode, setRouteMode] = useState<RouteMode>('generation');
  const [enableWebSearch, setEnableWebSearch] = useState(false);

  // 优化模式专用状态
  const [originalRecipe, setOriginalRecipe] = useState<string>('');
  const [optimizationTargets, setOptimizationTargets] = useState<OptimizationTarget[]>([]);

  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const shownToastKeysRef = useRef<Set<string>>(new Set());

  // 会话消息缓存：存储每个会话的实时消息状态（包括正在生成的消息）
  const sessionMessagesCacheRef = useRef<Map<string, Message[]>>(new Map());
  // 记录上一个会话 ID，用于在切换时保存缓存
  const prevSessionIdRef = useRef<string | null>(null);
  // 标记正在创建新会话（用于跳过 useEffect 中的历史加载）
  const isCreatingNewSessionRef = useRef<string | null>(null);

  const isGenerating = currentSessionId ? generatingSessions.has(currentSessionId) : false;

  const startGenerating = useCallback((sessionId: string) => {
    setGeneratingSessions(prev => new Set(prev).add(sessionId));
  }, []);

  const stopGenerating = useCallback((sessionId: string) => {
    setGeneratingSessions(prev => {
      const next = new Set(prev);
      next.delete(sessionId);
      return next;
    });
  }, []);

  // 加载聊天历史
  useEffect(() => {
    // 切换会话前，保存当前会话的消息到缓存
    if (prevSessionIdRef.current && prevSessionIdRef.current !== currentSessionId) {
      sessionMessagesCacheRef.current.set(prevSessionIdRef.current, messages);
    }
    prevSessionIdRef.current = currentSessionId;

    if (!currentSessionId) {
      setMessages([]);
      return;
    }

    // 如果是正在创建的新会话，跳过历史加载（等待消息添加）
    if (isCreatingNewSessionRef.current === 'pending') {
      return;
    }

    // 如果匹配到刚创建的会话 ID，说明这是创建后的首次 useEffect，跳过加载并清除标记
    if (isCreatingNewSessionRef.current === currentSessionId) {
      isCreatingNewSessionRef.current = null;
      return;
    }

    // 如果该会话正在生成中，优先使用缓存的消息（保持实时状态）
    if (generatingSessions.has(currentSessionId)) {
      const cachedMessages = sessionMessagesCacheRef.current.get(currentSessionId);
      if (cachedMessages && cachedMessages.length > 0) {
        setMessages(cachedMessages);
        return;
      }
    }

    const loadHistory = async () => {
      setIsLoadingHistory(true);
      try {
        const res = await chatApi.history(currentSessionId, 50);
        const historyMessages = res.messages.map(m => ({
          id: m.id.toString(),
          role: m.role,
          content: m.content,
          message_type: m.message_type,
          thinking: m.thinking,
          steps: m.steps || [],
          created_at: m.created_at,
        }));
        setMessages(historyMessages);
        // 更新缓存
        sessionMessagesCacheRef.current.set(currentSessionId, historyMessages);
      } catch (error) {
        console.error('Failed to load chat history', error);
        setMessages([]);
      } finally {
        setIsLoadingHistory(false);
      }
    };

    loadHistory();
  }, [currentSessionId, setIsLoadingHistory]);

  // 滚动到底部
  useEffect(() => {
    if (!isUserScrolling) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isGenerating, isUserScrolling]);

  // 同步更新消息缓存：当 messages 变化时，更新当前会话的缓存
  useEffect(() => {
    if (currentSessionId && messages.length > 0) {
      sessionMessagesCacheRef.current.set(currentSessionId, messages);
    }
  }, [currentSessionId, messages]);

  // 页面加载时清理残留任务锁
  useEffect(() => {
    chatApi.clearTasks().catch(err => {
      console.warn('清理任务锁失败:', err);
    });
  }, []);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    const isAtBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 100;

    if (!isAtBottom && isGenerating) {
      setIsUserScrolling(true);
      if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    } else if (isAtBottom) {
      setIsUserScrolling(false);
    }
  };

  const validateModeConfig = useCallback(() => {
    if (routeMode !== 'optimization') return true;
    if (!originalRecipe.trim()) {
      showError('优化模式需要先填写原始配方');
      return false;
    }
    if (optimizationTargets.length === 0) {
      showError('优化模式需要至少选择一个优化目标');
      return false;
    }
    return true;
  }, [routeMode, originalRecipe, optimizationTargets, showError]);

  const handleStreamEvent = useCallback((event: SSEEvent, assistantMsgId: string) => {
    const toastMessage = event.metadata?.toast_message;
    const toastType = event.metadata?.toast_type;
    const toastKey = toastMessage ? `${event.type}:${event.created_at}:${toastMessage}` : '';
    if (toastMessage && !shownToastKeysRef.current.has(toastKey)) {
      shownToastKeysRef.current.add(toastKey);
      if (toastType === 'error') {
        showError(toastMessage);
      } else {
        warning(toastMessage);
      }
    }

    setMessages(prev => {
      const newMessages = [...prev];
      const lastMsgIndex = newMessages.findIndex(m => m.id === assistantMsgId);
      if (lastMsgIndex === -1) return prev;

      const lastMsg = { ...newMessages[lastMsgIndex] };

      if (event.type === 'answer') {
        const existingSteps = [...(lastMsg.steps || [])];
        const lastStepIndex = existingSteps.length - 1;
        if (lastStepIndex >= 0 && existingSteps[lastStepIndex].type === 'answer') {
          const updatedStep: AgentStep = {
            ...existingSteps[lastStepIndex],
            content: (existingSteps[lastStepIndex].content || '') + event.content,
            metadata: event.metadata
          };
          lastMsg.steps = [...existingSteps.slice(0, -1), updatedStep];
        } else {
          const answerStep: AgentStep = {
            type: 'answer' as StepType,
            content: event.content,
            metadata: event.metadata,
            created_at: event.created_at
          };
          lastMsg.steps = [...existingSteps, answerStep];
        }

        const answerContent = lastMsg.steps
          .filter((s: AgentStep) => s.type === 'answer')
          .map((s: AgentStep) => s.content)
          .join('');
        lastMsg.content = answerContent;

      } else if (event.type === 'error') {
        lastMsg.content = (lastMsg.content || '') + `\n\n[Error: ${event.content}]`;
        const step: AgentStep = {
          type: 'error' as StepType,
          content: event.content,
          metadata: event.metadata,
          created_at: event.created_at
        };
        lastMsg.steps = [...(lastMsg.steps || []), step];
      } else if (event.type === 'cancelled') {
        if (!lastMsg.content) {
          lastMsg.content = '[生成已停止]';
        }
      } else if (['router', 'thought', 'decision', 'tool_req', 'tool_res'].includes(event.type)) {
        const step: AgentStep = {
          type: event.type as StepType,
          content: event.content,
          metadata: event.metadata,
          created_at: event.created_at
        };
        lastMsg.steps = [...(lastMsg.steps || []), step];
      }

      newMessages[lastMsgIndex] = lastMsg;
      return newMessages;
    });
  }, [showError, warning]);

  const handleChatRequest = useCallback(async (sessionId: string, query: string, selectedKBs: KBItem[]) => {
     if (!validateModeConfig()) return;
     startGenerating(sessionId);

     const assistantMsgId = (Date.now() + 1).toString();
     const assistantMessage: Message & { message_type?: string; created_at?: string } = {
       id: assistantMsgId,
       role: 'assistant',
       content: '',
       message_type: 'answer',
       steps: [],
       created_at: new Date().toISOString()
     };

     // 更新消息并同步更新缓存
     setMessages(prev => {
       const next = [...prev, assistantMessage];
       sessionMessagesCacheRef.current.set(sessionId, next);
       return next;
     });

     const selectedKbIds = selectedKBs.filter(kb => kb.selected).map(kb => kb.id);

     try {
       await chatApi.stream({
         session_id: sessionId,
         query: query,
         kb_ids: selectedKbIds.length > 0 ? selectedKbIds : undefined,
         route_mode: routeMode,
         enable_web_search: enableWebSearch,
         original_recipe: routeMode === 'optimization' ? originalRecipe : undefined,
         optimization_targets: routeMode === 'optimization' ? optimizationTargets : undefined
       }, (event) => {
         handleStreamEvent(event, assistantMsgId);
       });
     } catch (error) {
       console.error('Chat stream error', error);
       const errorMessage = error instanceof Error ? error.message : '未知错误';
       setMessages(prev => {
         const newMessages = [...prev];
         const lastMsg = newMessages.find(m => m.id === assistantMsgId);
         if (lastMsg) {
           lastMsg.content = `[错误] ${errorMessage}`;
           lastMsg.steps = [...(lastMsg.steps || []), {
             type: 'error' as StepType,
             content: errorMessage,
             created_at: new Date().toISOString()
           }];
         }
         return newMessages;
       });
     } finally {
       stopGenerating(sessionId);
     }
  }, [routeMode, enableWebSearch, originalRecipe, optimizationTargets, startGenerating, stopGenerating, handleStreamEvent, validateModeConfig]);

  const handleSendMessage = useCallback(async (selectedKBs: KBItem[]) => {
    if (!inputValue.trim()) return;
    if (!validateModeConfig()) return;

    let sessionId = currentSessionId;
    const query = inputValue; // 保存输入内容，因为后面会清空

    // 如果没有会话，先创建
    if (!sessionId) {
      const sessionTitle = query.trim().slice(0, 20);
      try {
        // 在创建会话前设置标记，防止 useEffect 触发历史加载
        // 注意：handleCreateSession 内部会调用 setCurrentSessionId，触发 useEffect
        isCreatingNewSessionRef.current = 'pending';
        sessionId = await handleCreateSession(sessionTitle);
        // 更新标记为实际的会话 ID
        isCreatingNewSessionRef.current = sessionId;
        // 标记为正在生成
        startGenerating(sessionId);
      } catch (error) {
        console.error('Failed to create session automatically', error);
        isCreatingNewSessionRef.current = null;
        return;
      }
    }

    if (!sessionId) return;

    const userMessage: Message & { message_type?: string; created_at?: string } = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      message_type: 'text',
      created_at: new Date().toISOString()
    };

    setMessages(prev => {
      const next = [...prev, userMessage];
      // 立即更新缓存，防止竞态条件下的历史加载覆盖
      if (sessionId) {
        sessionMessagesCacheRef.current.set(sessionId, next);
      }
      return next;
    });
    setInputValue('');

    // 注意：不要在这里清除 isCreatingNewSessionRef.current
    // 让 useEffect 来处理清除，以确保它能拦截到状态变更引起的作用

    handleChatRequest(sessionId, query, selectedKBs);
  }, [inputValue, currentSessionId, handleCreateSession, handleChatRequest, startGenerating, validateModeConfig]);

  const handleEditMessage = useCallback(async (messageId: string, newContent: string, selectedKBs: KBItem[]) => {
    if (isGenerating || !currentSessionId) return;

    const msgIndex = messages.findIndex(m => m.id === messageId);
    if (msgIndex === -1) return;

    const msg = messages[msgIndex];
    if (msg.role !== 'user') return;

    const nextAssistantMsg = messages.slice(msgIndex + 1).find(m => m.role === 'assistant');

    const newMessages = messages.slice(0, msgIndex + 1);
    newMessages[msgIndex] = { ...newMessages[msgIndex], content: newContent };
    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMessage: Message & { message_type?: string; created_at?: string } = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      message_type: 'answer',
      steps: [],
      created_at: new Date().toISOString()
    };

    try {
      const selectedKbIds = selectedKBs.filter(kb => kb.selected).map(kb => kb.id);
      const numericId = nextAssistantMsg ? parseInt(nextAssistantMsg.id, 10) : NaN;
      const isValidDbId = !isNaN(numericId) && numericId < 1000000000;

      if (!isValidDbId && !validateModeConfig()) {
        return;
      }

      setMessages(newMessages);
      startGenerating(currentSessionId);
      setMessages(prev => [...prev, assistantMessage]);

      if (isValidDbId) {
        await chatApi.regenerate({
          session_id: currentSessionId,
          message_id: numericId
        }, (event) => {
          handleStreamEvent(event, assistantMsgId);
        });
      } else {
        await chatApi.stream({
          session_id: currentSessionId,
          query: newContent,
          kb_ids: selectedKbIds.length > 0 ? selectedKbIds : undefined,
          route_mode: routeMode,
          enable_web_search: enableWebSearch,
          original_recipe: routeMode === 'optimization' ? originalRecipe : undefined,
          optimization_targets: routeMode === 'optimization' ? optimizationTargets : undefined
        }, (event) => {
          handleStreamEvent(event, assistantMsgId);
        });
      }
    } catch (error) {
      console.error('Edit message error', error);
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setMessages(prev => {
        const newMsgs = [...prev];
        const lastMsg = newMsgs.find(m => m.id === assistantMsgId);
        if (lastMsg) {
          lastMsg.content = `[错误] ${errorMessage}`;
          lastMsg.steps = [...(lastMsg.steps || []), {
            type: 'error' as StepType,
            content: errorMessage,
            created_at: new Date().toISOString()
          }];
        }
        return newMsgs;
      });
    } finally {
      stopGenerating(currentSessionId);
    }
  }, [isGenerating, currentSessionId, messages, startGenerating, stopGenerating, handleStreamEvent, routeMode, enableWebSearch, originalRecipe, optimizationTargets, validateModeConfig]);

  const handleRegenerate = useCallback(async (messageId: string) => {
    if (isGenerating || !currentSessionId) return;

    const msgIndex = messages.findIndex(m => m.id === messageId);
    if (msgIndex === -1) return;

    const msg = messages[msgIndex];
    let newMessages: Message[] = [];
    let targetMessageId = messageId;

    if (msg.role === 'assistant') {
      const prevUserMsg = messages.slice(0, msgIndex).reverse().find(m => m.role === 'user');
      if (!prevUserMsg) return;
      newMessages = messages.slice(0, msgIndex);
    } else {
      const nextAssistantMsg = messages.slice(msgIndex + 1).find(m => m.role === 'assistant');
      if (nextAssistantMsg) {
        targetMessageId = nextAssistantMsg.id;
      }
      newMessages = messages.slice(0, msgIndex + 1);
    }

    setMessages(newMessages);
    startGenerating(currentSessionId);

    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMessage: Message & { message_type?: string; created_at?: string } = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      message_type: 'answer',
      steps: [],
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const numericId = parseInt(targetMessageId, 10);
      const isValidDbId = !isNaN(numericId) && numericId < 1000000000;

      await chatApi.regenerate({
        session_id: currentSessionId,
        message_id: isValidDbId ? numericId : undefined
      }, (event) => {
        handleStreamEvent(event, assistantMsgId);
      });
    } catch (error) {
      console.error('Regenerate error', error);
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setMessages(prev => {
        const newMsgs = [...prev];
        const lastMsg = newMsgs.find(m => m.id === assistantMsgId);
        if (lastMsg) {
          lastMsg.content = `[错误] ${errorMessage}`;
          lastMsg.steps = [...(lastMsg.steps || []), {
            type: 'error' as StepType,
            content: errorMessage,
            created_at: new Date().toISOString()
          }];
        }
        return newMsgs;
      });
    } finally {
      stopGenerating(currentSessionId);
    }
  }, [isGenerating, currentSessionId, messages, startGenerating, stopGenerating, handleStreamEvent]);

  const handleStopGeneration = useCallback(async () => {
    if (currentSessionId && isGenerating) {
      try {
        await chatApi.stop(currentSessionId);
        stopGenerating(currentSessionId);
      } catch (error) {
        console.error('Failed to stop generation', error);
      }
    }
  }, [currentSessionId, isGenerating, stopGenerating]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent, selectedKBs: KBItem[]) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(selectedKBs);
    }
  }, [handleSendMessage]);

  return {
    messages,
    setMessages,
    inputValue,
    setInputValue,
    isGenerating,
    isUserScrolling,
    enableWebSearch,
    setEnableWebSearch,
    routeMode,
    setRouteMode,
    originalRecipe,
    setOriginalRecipe,
    optimizationTargets,
    setOptimizationTargets,
    messagesEndRef,
    chatContainerRef,
    handleScroll,
    handleSendMessage,
    handleEditMessage,
    handleRegenerate,
    handleStopGeneration,
    handleKeyDown
  };
};
