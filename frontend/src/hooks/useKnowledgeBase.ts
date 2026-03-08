import { useState } from 'react';
import { KBItem } from '../types';

export const useKnowledgeBase = () => {
  const [kbItems, setKbItems] = useState<KBItem[]>([]);

  const toggleKBSelection = (id: string) => {
    setKbItems(prev => prev.map(item =>
      item.id === id ? { ...item, selected: !item.selected } : item
    ));
  };

  return {
    kbItems,
    toggleKBSelection
  };
};
