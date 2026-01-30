import { useState, useEffect, useCallback } from 'react';
import { KBItem } from '../types';
import { knowledgeApi } from '../api/knowledge';
import { useEventStream } from './useEventStream';
import { useToast } from '../components/Toast';

export const useKnowledgeBase = () => {
  const [kbItems, setKbItems] = useState<KBItem[]>([]);
  const [isKBManagerOpen, setIsKBManagerOpen] = useState(false);
  const [isRecipeKBOpen, setIsRecipeKBOpen] = useState(false);
  const toast = useToast();

  const loadKnowledgeBase = useCallback(async () => {
    try {
      const res = await knowledgeApi.list();
      const mappedKBs: KBItem[] = res.documents.map(doc => ({
        id: doc.id,
        name: doc.filename,
        selected: false, // Default not selected
        status: doc.status,
        chunks: doc.chunk_count,
        createdAt: doc.created_at,
        filename: doc.filename,
        chunk_count: doc.chunk_count,
        created_at: doc.created_at
      }));
      // 保留之前的选中状态
      setKbItems(prev => {
        const selectedIds = new Set(prev.filter(item => item.selected).map(item => item.id));
        return mappedKBs.map(item => ({
          ...item,
          selected: selectedIds.has(item.id)
        }));
      });
    } catch (error) {
      // 知识库接口已移除：保持 UI 可用，但不再加载数据
      setKbItems([]);
    }
  }, []);

  // 监听知识库状态变化事件
  useEventStream('kb_status_changed', useCallback(() => {
    console.log('[SSE] 收到知识库状态变化事件，刷新列表');
    loadKnowledgeBase();
  }, [loadKnowledgeBase]));

  useEffect(() => {
    loadKnowledgeBase();
  }, [loadKnowledgeBase]);

  const handleDeleteKB = async (id: string) => {
    try {
      await knowledgeApi.delete(id);
      setKbItems(prev => prev.filter(item => item.id !== id));
    } catch (error) {
      toast.warning('后端已移除知识库相关接口，删除操作不可用。');
    }
  };

  const toggleKBSelection = (id: string) => {
    setKbItems(prev => prev.map(item =>
      item.id === id ? { ...item, selected: !item.selected } : item
    ));
  };

  return {
    kbItems,
    isKBManagerOpen,
    setIsKBManagerOpen,
    isRecipeKBOpen,
    setIsRecipeKBOpen,
    loadKnowledgeBase,
    handleDeleteKB,
    toggleKBSelection
  };
};
