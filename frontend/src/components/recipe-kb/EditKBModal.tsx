import React, { useState, useEffect } from 'react';
import { ChevronLeft, Loader2, Settings, AlertCircle } from 'lucide-react';
import { Category, SEMANTIC_TYPE_OPTIONS } from './types';
import { COLOR_OPTIONS } from './types';

interface EditKBModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (params: {
    name: string;
    description?: string;
    icon_char: string;
    color_class: string;
  }) => Promise<void>;
  category: Category;
}

export const EditKBModal: React.FC<EditKBModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  category
}) => {
  const [name, setName] = useState(category.name);
  const [description, setDescription] = useState(category.description || '');
  const [iconChar, setIconChar] = useState(category.iconChar);
  const [colorClass, setColorClass] = useState(category.colorClass);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [render, setRender] = useState(isOpen);

  // 当 category 变化时重置表单
  useEffect(() => {
    setName(category.name);
    setDescription(category.description || '');
    setIconChar(category.iconChar);
    setColorClass(category.colorClass);
    setError(null);
  }, [category]);

  useEffect(() => {
    if (isOpen) setRender(true);
  }, [isOpen]);

  const onAnimationEnd = () => {
    if (!isOpen) setRender(false);
  };

  if (!render) return null;

  // 获取语义类型的显示名称
  const semanticTypeOption = SEMANTIC_TYPE_OPTIONS.find(opt => opt.value === category.semanticType);
  const semanticTypeLabel = semanticTypeOption
    ? `${semanticTypeOption.label}`
    : category.semanticType;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('知识库名称不能为空');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || undefined,
        icon_char: iconChar || name[0],
        color_class: colorClass,
      });
      onClose();
    } catch (err: any) {
      setError(err.message || '更新失败，请重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm transition-opacity ${isOpen ? 'animate-backdrop-in' : 'animate-backdrop-out'}`}
      onAnimationEnd={onAnimationEnd}
      onClick={onClose}
    >
      <div
        className={`bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden transform transition-all m-4 ${isOpen ? 'animate-modal-in' : 'animate-modal-out'}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center px-6 py-4 border-b border-gray-100">
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-full hover:bg-gray-100 mr-2 -ml-2"
            title="返回"
          >
            <ChevronLeft size={24} />
          </button>
          <div className="flex items-center gap-2 text-gray-800">
            <div className="p-1.5 bg-blue-100 rounded-lg">
              <Settings size={20} className="text-blue-600" />
            </div>
            <h3 className="text-lg font-bold">编辑知识库</h3>
          </div>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* 知识库名称 */}
          <div>
            <label htmlFor="kb-name" className="block text-sm font-medium text-gray-700 mb-1">
              知识库名称 <span className="text-red-500">*</span>
            </label>
            <input
              id="kb-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：杀菌剂配方库"
              className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-gray-700"
              autoFocus
            />
          </div>

          {/* 不可修改的信息 */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <div className="flex items-start gap-2 text-amber-700">
              <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
              <div className="text-xs">
                <p className="font-medium mb-1">以下属性创建后不可修改：</p>
                <ul className="space-y-0.5 text-amber-600">
                  <li>• 存储结构：<span className="font-medium">{category.kbType === 'company' ? '按公司分类' : '扁平结构'}</span></li>
                  <li>• 语义类型：<span className="font-medium">{semanticTypeLabel}</span></li>
                </ul>
              </div>
            </div>
          </div>

          {/* 图标和颜色 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="kb-icon" className="block text-sm font-medium text-gray-700 mb-1">
                图标字符
              </label>
              <input
                id="kb-icon"
                type="text"
                value={iconChar}
                onChange={(e) => setIconChar(e.target.value.slice(0, 2))}
                placeholder={name ? name[0] : "如：配"}
                maxLength={2}
                className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-gray-700 text-center text-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                主题颜色
              </label>
              <div className="flex flex-wrap gap-1.5">
                {COLOR_OPTIONS.slice(0, 6).map((color) => (
                  <button
                    key={color.value}
                    type="button"
                    onClick={() => setColorClass(color.value)}
                    className={`w-7 h-7 rounded-lg ${color.value} transition-all ${
                      colorClass === color.value
                        ? 'ring-2 ring-offset-2 ring-gray-400 scale-110'
                        : 'hover:scale-105'
                    }`}
                    title={color.label}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* 描述 */}
          <div>
            <label htmlFor="kb-desc" className="block text-sm font-medium text-gray-700 mb-1">
              描述（可选）
            </label>
            <textarea
              id="kb-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="简要描述该知识库的用途..."
              rows={2}
              className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-gray-700 resize-none"
            />
          </div>

          {error && (
            <div className="text-sm text-red-500 bg-red-50 p-3 rounded-lg border border-red-100">
              {error}
            </div>
          )}

          {/* Footer inside form to handle submit */}
          <div className="flex items-center justify-end gap-3 pt-4 mt-2 border-t border-gray-50">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isSubmitting}
              className={`px-4 py-2 text-sm font-medium text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 flex items-center gap-2 ${
                name.trim() && !isSubmitting
                  ? 'bg-blue-500 hover:bg-blue-600'
                  : 'bg-blue-300 cursor-not-allowed'
              }`}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  保存中...
                </>
              ) : (
                '保存修改'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
