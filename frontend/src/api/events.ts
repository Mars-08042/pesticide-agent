import { API_BASE_URL } from './config';

export type EventType = 'kb_status_changed' | 'connected' | 'heartbeat';

export interface KBStatusChangedEvent {
  document_id: string;
  filename: string;
  status: 'active' | 'error';
  chunks_count?: number;
  error?: string;
}

export interface SSEEventData {
  type: EventType;
  data: KBStatusChangedEvent | Record<string, unknown>;
  timestamp: string;
}

type EventCallback = (event: SSEEventData) => void;

class EventStreamClient {
  private eventSource: EventSource | null = null;
  private callbacks: Map<EventType, EventCallback[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000;

  connect(): void {
    if (this.eventSource) {
      return; // 已连接
    }

    const url = `${API_BASE_URL}/api/events/stream`;
    this.eventSource = new EventSource(url);

    this.eventSource.onopen = () => {
      console.log('[SSE] 连接成功');
      this.reconnectAttempts = 0;
    };

    this.eventSource.onerror = (error) => {
      console.error('[SSE] 连接错误', error);
      this.handleReconnect();
    };

    // 监听连接事件
    this.eventSource.addEventListener('connected', (e) => {
      console.log('[SSE] 服务器确认连接');
    });

    // 监听心跳
    this.eventSource.addEventListener('heartbeat', () => {
      // 心跳，保持连接
    });

    // 监听知识库状态变化
    this.eventSource.addEventListener('kb_status_changed', (e) => {
      try {
        const data = JSON.parse(e.data) as SSEEventData;
        this.emit('kb_status_changed', data);
      } catch (err) {
        console.error('[SSE] 解析事件失败', err);
      }
    });
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      console.log('[SSE] 连接已断开');
    }
  }

  private handleReconnect(): void {
    this.disconnect();

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`[SSE] ${this.reconnectDelay / 1000}秒后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      setTimeout(() => this.connect(), this.reconnectDelay);
    } else {
      console.error('[SSE] 重连次数已达上限，停止重连');
    }
  }

  on(eventType: EventType, callback: EventCallback): void {
    if (!this.callbacks.has(eventType)) {
      this.callbacks.set(eventType, []);
    }
    this.callbacks.get(eventType)!.push(callback);
  }

  off(eventType: EventType, callback: EventCallback): void {
    const callbacks = this.callbacks.get(eventType);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  private emit(eventType: EventType, data: SSEEventData): void {
    const callbacks = this.callbacks.get(eventType);
    if (callbacks) {
      callbacks.forEach(cb => cb(data));
    }
  }
}

// 全局单例
export const eventStream = new EventStreamClient();
