import React, { useState } from 'react';
import { FileText, Plus, Trash2, Pencil } from 'lucide-react';
import { Category, KBType, SemanticType } from './types';
import { recipeKB } from '../../api/recipe-kb';
import { CreateKBModal } from './CreateKBModal';
import { ConfirmModal } from './ConfirmModal';
import { EditKBModal } from './EditKBModal';

interface DashboardProps {
  categories: Category[];
  onSelectCategory: (id: string) => void;
  onRefresh: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  categories,
  onSelectCategory,
  onRefresh
}) => {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [deleteKbId, setDeleteKbId] = useState<string | null>(null);
  const [deleteKbName, setDeleteKbName] = useState<string>('');
  const [editCategory, setEditCategory] = useState<Category | null>(null);

  const handleCreateSubmit = async (params: {
    name: string;
    description?: string;
    kb_type: KBType;
    semantic_type: SemanticType;
    icon_char: string;
    color_class: string;
  }) => {
    await recipeKB.createKnowledgeBase({
      name: params.name,
      description: params.description,
      kb_type: params.kb_type,
      semantic_type: params.semantic_type,
      icon_char: params.icon_char,
      color_class: params.color_class,
    });
    onRefresh();
  };

  const handleDeleteClick = (e: React.MouseEvent, category: Category) => {
    e.stopPropagation(); // 阻止事件冒泡，防止触发卡片点击
    setDeleteKbId(category.id);
    setDeleteKbName(category.name);
  };

  const handleEditClick = (e: React.MouseEvent, category: Category) => {
    e.stopPropagation(); // 阻止事件冒泡，防止触发卡片点击
    setEditCategory(category);
  };

  const handleEditSubmit = async (params: {
    name: string;
    description?: string;
    icon_char: string;
    color_class: string;
  }) => {
    if (!editCategory) return;
    await recipeKB.updateKnowledgeBase(editCategory.id, params);
    onRefresh();
  };

  const handleConfirmDelete = async () => {
    if (deleteKbId) {
      try {
        await recipeKB.deleteKnowledgeBase(deleteKbId);
        onRefresh();
      } catch (error) {
        console.error('删除知识库失败:', error);
      }
    }
    setDeleteKbId(null);
    setDeleteKbName('');
  };

  return (
    <div className="w-full h-full overflow-y-auto p-6 sm:p-8 custom-scrollbar">
      {/* 页面标题区 */}
      <div className="max-w-6xl mx-auto mb-8 pt-2">
        <div className="inline-flex items-center gap-3 mb-4">
          <div className="w-12 h-12 bg-gradient-to-br from-green-400 to-green-500 rounded-xl shadow-soft-md flex items-center justify-center text-white text-xl font-bold">
            研
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gradient-primary tracking-tight">配方知识库</h1>
        </div>
        <p className="text-slate-500 text-base max-w-xl leading-relaxed">
          管理农药配方生成的各类知识数据，支持分类存储与智能检索。
        </p>
      </div>

      {/* 卡片网格 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 max-w-6xl mx-auto">
        {categories.map((category, index) => (
          <div
            key={category.id}
            onClick={() => onSelectCategory(category.id)}
            className="group relative bg-white/70 backdrop-blur-sm rounded-2xl p-5 border border-green-100/50 shadow-soft-sm hover:bg-white hover:border-green-200/70 hover:shadow-soft-lg hover:-translate-y-1 hover:scale-[1.01] transition-all duration-300 cursor-pointer flex flex-col h-56 overflow-hidden animate-stagger-in"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            {/* 悬浮时的绿色光晕 */}
            <div className="absolute inset-0 bg-gradient-to-br from-green-100/0 to-green-200/0 group-hover:from-green-100/30 group-hover:to-green-200/20 transition-all duration-300 pointer-events-none rounded-2xl" />

            {/* 卡片头部 */}
            <div className="relative z-10 flex items-start justify-between mb-4">
              <div className={`w-12 h-12 ${category.colorClass} rounded-xl shadow-soft-sm group-hover:shadow-soft-md group-hover:scale-105 flex items-center justify-center text-white text-xl font-bold transition-all duration-300`}>
                {category.iconChar}
              </div>
              <div className="flex items-center gap-2">
                {/* 知识库类型标签 */}
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  category.kbType === 'company'
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-blue-100 text-blue-700'
                }`}>
                  {category.kbType === 'company' ? '按公司' : '扁平'}
                </span>
                <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-r from-green-400 to-green-500 text-white px-3 py-1 rounded-full text-xs font-semibold shadow-soft-sm">
                  进入
                </div>
              </div>
            </div>

            {/* 卡片标题 */}
            <h3 className="relative z-10 text-lg font-bold text-slate-800 mb-1.5 group-hover:text-green-700 transition-colors">
              {category.name}
            </h3>

            {/* 卡片描述 */}
            <p className="relative z-10 text-sm text-slate-500 line-clamp-2 mb-auto leading-relaxed">
              {category.description}
            </p>

            {/* 卡片底部 */}
            <div className="relative z-10 flex items-center justify-between mt-4 pt-4 border-t border-green-100/50 text-xs text-slate-500">
              <div className="flex items-center gap-1.5 font-semibold">
                <FileText size={14} className="text-green-500" />
                <span>{category.count} 个文档</span>
              </div>
              <div className="flex items-center gap-2">
                {/* 编辑和删除按钮 */}
                <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-all">
                  <button
                    onClick={(e) => handleEditClick(e, category)}
                    className="p-1.5 rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 transition-all"
                    title="编辑知识库"
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    onClick={(e) => handleDeleteClick(e, category)}
                    className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
                    title="删除知识库"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                {category.lastUpdated && (
                  <span className="font-medium bg-gradient-to-r from-green-50 to-emerald-50 px-2.5 py-1 rounded-lg text-green-700 border border-green-100/50">
                    {category.lastUpdated}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* 创建新知识库卡片 */}
        <button
          onClick={() => setShowCreateModal(true)}
          className="h-56 border-2 border-dashed border-green-200/50 rounded-2xl flex flex-col items-center justify-center text-green-400 hover:border-green-400 hover:text-green-600 hover:bg-white/80 hover:shadow-soft-md transition-all duration-300 gap-3 group bg-green-50/30 animate-stagger-in"
          style={{ animationDelay: `${categories.length * 50}ms` }}
        >
          <div className="w-14 h-14 bg-white/80 backdrop-blur-sm rounded-xl border border-green-200/50 group-hover:border-green-400 group-hover:shadow-soft-md group-hover:scale-105 flex items-center justify-center transition-all duration-300">
            <Plus size={28} className="text-green-300 group-hover:text-green-500 transition-colors" />
          </div>
          <span className="font-semibold text-sm">创建新知识库</span>
        </button>
      </div>

      <CreateKBModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSubmit={handleCreateSubmit}
      />

      <ConfirmModal
        isOpen={deleteKbId !== null}
        onClose={() => {
          setDeleteKbId(null);
          setDeleteKbName('');
        }}
        onConfirm={handleConfirmDelete}
        title="删除知识库"
        message={`确定要删除知识库「${deleteKbName}」吗？此操作将同时删除该知识库下的所有文件，且无法撤销。`}
        confirmText="删除"
        isDestructive={true}
      />

      {editCategory && (
        <EditKBModal
          isOpen={editCategory !== null}
          onClose={() => setEditCategory(null)}
          onSubmit={handleEditSubmit}
          category={editCategory}
        />
      )}
    </div>
  );
};
