import React, { useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { MainContent } from './MainContent';
import { Dashboard } from './Dashboard';
import { Category, knowledgeBaseToCategory } from './types';
import { recipeKB } from '../../api/recipe-kb';
import { ChevronLeft, Loader2 } from 'lucide-react';

interface RecipeKBManagerProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const RecipeKBManager: React.FC<RecipeKBManagerProps> = ({ onClose, isOpen = true }) => {
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [companies, setCompanies] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [render, setRender] = useState(isOpen);

  React.useEffect(() => {
    if (isOpen) setRender(true);
  }, [isOpen]);

  const onAnimationEnd = () => {
    if (!isOpen) setRender(false);
  };

  // 从 API 加载知识库列表和公司列表
  const loadData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [kbsRes, companiesRes] = await Promise.all([
        recipeKB.getKnowledgeBases(),
        recipeKB.getCompanies()
      ]);

      if (kbsRes.success) {
        // 将 API 返回的 KnowledgeBase 转换为 Category
        const cats = kbsRes.data.items.map(knowledgeBaseToCategory);
        setCategories(cats);
      }

      if (companiesRes.success) {
        setCompanies(companiesRes.data.companies);
      }
    } catch (err: any) {
      console.error('Failed to load KB data:', err);
      setError(err.message || '加载知识库失败');

      // 如果 API 失败，尝试初始化默认知识库
      try {
        await recipeKB.initDefaultKnowledgeBases();
        // 重新加载
        const kbsRes = await recipeKB.getKnowledgeBases();
        if (kbsRes.success) {
          const cats = kbsRes.data.items.map(knowledgeBaseToCategory);
          setCategories(cats);
          setError(null);
        }
      } catch (initErr) {
        console.error('Failed to init default KBs:', initErr);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (!render) return null;

  const selectedCategory = categories.find(c => c.id === selectedCategoryId);

  return (
    <div
      className={`fixed inset-0 z-40 bg-gradient-main flex flex-col overflow-hidden ${isOpen ? 'animate-backdrop-in' : 'animate-backdrop-out'}`}
      onAnimationEnd={onAnimationEnd}
    >
      {/* 背景装饰光斑 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-32 -left-32 w-96 h-96 bg-gradient-radial from-green-200/30 to-transparent rounded-full blur-3xl animate-float-blob" />
        <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-gradient-radial from-emerald-200/25 to-transparent rounded-full blur-3xl animate-float-blob animation-delay-1000" />
      </div>

      {/* 顶部导航栏 */}
      <div className="relative z-10 flex-none h-14 px-4 sm:px-6 flex items-center bg-white/50 backdrop-blur-md border-b border-green-100/50">
        {selectedCategory ? (
          // 详情页：返回概览
          <button
            onClick={() => setSelectedCategoryId(null)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-green-700 hover:text-green-800 bg-white/80 backdrop-blur-sm rounded-xl text-sm font-medium border border-green-200/50 hover:border-green-300 hover:shadow-soft-sm transition-all"
          >
            <ChevronLeft size={18} />
            返回概览
          </button>
        ) : onClose ? (
          // 概览页：返回聊天
          <button
            onClick={onClose}
            className="flex items-center gap-1.5 px-3 py-1.5 text-green-700 hover:text-green-800 bg-white/80 backdrop-blur-sm rounded-xl text-sm font-medium border border-green-200/50 hover:border-green-300 hover:shadow-soft-sm transition-all"
          >
            <ChevronLeft size={18} />
            返回聊天
          </button>
        ) : null}
      </div>

      <div className="relative z-10 flex-1 flex overflow-hidden pb-4 px-4">
        {/* Sidebar - 仅在详情页显示 */}
        {selectedCategory && (
          <div className="hidden md:flex flex-col w-64 mr-4 h-full">
            <Sidebar
              categories={categories}
              selectedCategoryId={selectedCategoryId}
              onSelectCategory={setSelectedCategoryId}
              onGoHome={() => setSelectedCategoryId(null)}
            />
          </div>
        )}

        {/* Main Content Area */}
        <div className="flex-1 h-full overflow-hidden bg-white/60 backdrop-blur-md rounded-2xl border border-green-100/50 shadow-soft-lg">
          {isLoading ? (
            // 加载中状态
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
              <Loader2 size={48} className="animate-spin text-green-500 mb-4" />
              <p className="text-sm">正在加载知识库...</p>
            </div>
          ) : error && categories.length === 0 ? (
            // 错误状态（且没有数据）
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
              <p className="text-red-500 mb-4">{error}</p>
              <button
                onClick={loadData}
                className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors"
              >
                重试
              </button>
            </div>
          ) : selectedCategory ? (
            <MainContent
              category={selectedCategory}
              companies={companies}
              onBack={() => setSelectedCategoryId(null)}
              onDataUpdate={loadData}
            />
          ) : (
            <Dashboard
              categories={categories}
              onSelectCategory={setSelectedCategoryId}
              onRefresh={loadData}
            />
          )}
        </div>
      </div>
    </div>
  );
};
