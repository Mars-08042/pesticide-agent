import React from 'react';
import { Category } from './types';

interface SidebarProps {
  categories: Category[];
  selectedCategoryId: string | null;
  onSelectCategory: (id: string) => void;
  onGoHome: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  categories,
  selectedCategoryId,
  onSelectCategory,
  onGoHome
}) => {
  return (
    <div className="w-64 bg-white rounded-2xl shadow-sm p-4 flex flex-col h-full border border-gray-100">
      <div
        onClick={onGoHome}
        className="flex items-center gap-2 mb-6 px-2 cursor-pointer hover:opacity-80 transition-opacity"
      >
        <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center text-white font-bold text-lg">
          研
        </div>
        <h2 className="text-lg font-bold text-gray-800">配方知识库</h2>
      </div>

      <nav className="flex-1 space-y-1">
        {categories.map((category) => {
          const isSelected = category.id === selectedCategoryId;
          return (
            <button
              key={category.id}
              onClick={() => onSelectCategory(category.id)}
              className={`w-full flex items-center justify-between px-4 py-3 text-sm font-medium rounded-lg transition-colors duration-200 ${
                isSelected
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-2.5 h-2.5 rounded-full ${
                    isSelected ? 'bg-emerald-500' : 'bg-gray-300'
                  }`}
                />
                <span>{category.name}</span>
              </div>
              <span className={isSelected ? 'text-emerald-700' : 'text-gray-400'}>
                ({category.count})
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
};
