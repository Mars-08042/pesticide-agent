import { useEffect } from 'react';
import { eventStream, SSEEventData, EventType } from '../api/events';

/**
 * 自定义 Hook 用于管理 SSE 连接和事件监听
 * @param eventType 可选，需要监听的事件类型
 * @param callback 可选，事件触发时的回调函数
 */
export const useEventStream = (eventType?: EventType, callback?: (data: SSEEventData) => void) => {
  // 仅在组件挂载时连接，卸载时断开（如果这是根组件行为，可以保留在 App 中）
  // 但考虑到 eventStream 是单例，多次调用 connect 是安全的
  useEffect(() => {
    eventStream.connect();

    return () => {
      // 只有在没有其他监听者时断开连接可能比较复杂，
      // 这里简化为：如果提供了 callback，只清理 callback
      // 真正的 disconnect 通常由最外层组件控制，或者 eventStream 内部引用计数
      // 在当前架构下，App.tsx 负责连接和断开。
    };
  }, []);

  // 监听特定事件
  useEffect(() => {
    if (eventType && callback) {
      const handler = (data: SSEEventData) => {
        callback(data);
      };

      eventStream.on(eventType, handler);

      return () => {
        eventStream.off(eventType, handler);
      };
    }
  }, [eventType, callback]);

  return eventStream;
};
