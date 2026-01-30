import { fetchApi, API_BASE_URL, formatApiError } from './config';
import { ChatHistoryResponse, DeleteHistoryResponse, StopResponse, ChatRequest, RegenerateRequest, SSEEvent } from '../types';

// 清理任务响应类型
interface ClearTasksResponse {
  success: boolean;
  cleared_count: number;
  message: string;
}

export const chatApi = {
  history: (sessionId: string, limit = 20, beforeId?: number) => {
    let query = `?session_id=${sessionId}&limit=${limit}`;
    if (beforeId) query += `&before_id=${beforeId}`;
    return fetchApi<ChatHistoryResponse>(`/api/chat/history${query}`);
  },

  deleteHistory: (sessionId: string) =>
    fetchApi<DeleteHistoryResponse>(`/api/chat/history?session_id=${sessionId}`, {
      method: 'DELETE',
    }),

  stop: (sessionId: string) =>
    fetchApi<StopResponse>('/api/chat/stop', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    }),

  // 清理所有任务锁（用于页面刷新后恢复）
  clearTasks: () =>
    fetchApi<ClearTasksResponse>('/api/chat/tasks', {
      method: 'DELETE',
    }),

  stream: async (data: ChatRequest, onMessage: (event: SSEEvent) => void) => {
    const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      // 区分不同错误类型
      if (response.status === 409) {
        throw new Error('该会话正在处理中，请等待完成');
      } else if (response.status === 503) {
        throw new Error('系统繁忙，请稍后重试');
      }

      let errorData: any = null;
      try {
        errorData = await response.clone().json();
      } catch {
        // ignore
      }

      let errorText = '';
      if (!errorData) {
        try {
          errorText = await response.text();
        } catch {
          // ignore
        }
      }

      const message = errorData ? formatApiError(errorData) : (errorText || `Chat stream failed: ${response.statusText}`);
      throw new Error(message);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    if (!reader) return;

    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            if (!dataStr) continue;

            try {
              const eventData = JSON.parse(dataStr);
              // Handle standard SSE format where type might be in the event name or data
              onMessage({
                type: (eventType || eventData.type) as any,
                content: eventData.content,
                metadata: eventData.metadata,
                created_at: eventData.created_at || new Date().toISOString()
              });
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }

            eventType = ''; // Reset for next event
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  regenerate: async (data: RegenerateRequest, onMessage: (event: SSEEvent) => void) => {
    // Similar implementation to stream but hitting regenerate endpoint
    const response = await fetch(`${API_BASE_URL}/api/chat/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      // 区分不同错误类型
      if (response.status === 409) {
        throw new Error('该会话正在处理中，请等待完成');
      } else if (response.status === 503) {
        throw new Error('系统繁忙，请稍后重试');
      }

      let errorData: any = null;
      try {
        errorData = await response.clone().json();
      } catch {
        // ignore
      }

      let errorText = '';
      if (!errorData) {
        try {
          errorText = await response.text();
        } catch {
          // ignore
        }
      }

      const message = errorData ? formatApiError(errorData) : (errorText || `Regenerate failed: ${response.statusText}`);
      throw new Error(message);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    if (!reader) return;

    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            if (!dataStr) continue;

            try {
              const eventData = JSON.parse(dataStr);
              onMessage({
                type: (eventType || eventData.type) as any,
                content: eventData.content,
                metadata: eventData.metadata,
                created_at: eventData.created_at || new Date().toISOString()
              });
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
            eventType = '';
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }
};
