import React, { useState } from 'react';
import { ChevronLeft, Loader2, FolderPlus, Info } from 'lucide-react';
import { KBType, SemanticType, SEMANTIC_TYPE_OPTIONS } from './types';
import { COLOR_OPTIONS } from './types';

interface CreateKBModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (params: {
    name: string;
    description?: string;
    kb_type: KBType;
    semantic_type: SemanticType;
    icon_char: string;
    color_class: string;
  }) => Promise<void>;
}

export const CreateKBModal: React.FC<CreateKBModalProps> = ({
  isOpen,
  onClose,
  onSubmit
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [kbType, setKbType] = useState<KBType>('flat');
  const [semanticType, setSemanticType] = useState<SemanticType | ''>('');
  const [iconChar, setIconChar] = useState('');
  const [colorClass, setColorClass] = useState('bg-emerald-500');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [render, setRender] = useState(isOpen);

  React.useEffect(() => {
    if (isOpen) setRender(true);
  }, [isOpen]);

  const onAnimationEnd = () => {
    if (!isOpen) setRender(false);
  };

  const resetForm = () => {
    setName('');
    setDescription('');
    setKbType('flat');
    setSemanticType('');
    setIconChar('');
    setColorClass('bg-emerald-500');
    setError(null);
  };

  if (!render) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('知识库名称不能为空');
      return;
    }
    if (!semanticType) {
      setError('请选择语义类型');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || undefined,
        kb_type: kbType,
        semantic_type: semanticType,
        icon_char: iconChar || name[0],
        color_class: colorClass,
      });
      // Reset and close on success
      resetForm();
      onClose();
    } catch (err: any) {
      setError(err.message || '创建失败，请重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm transition-opacity ${isOpen ? 'animate-backdrop-in' : 'animate-backdrop-out'}`}
      onAnimationEnd={onAnimationEnd}
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
            <div className="p-1.5 bg-emerald-100 rounded-lg">
              <FolderPlus size={20} className="text-emerald-600" />
            </div>
            <h3 className="text-lg font-bold">创建新知识库</h3>
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
              className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all text-gray-700"
              autoFocus
            />
          </div>

          {/* 知识库类型 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              存储结构 <span className="text-red-500">*</span>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setKbType('flat')}
                className={`p-3 rounded-xl border-2 text-left transition-all ${
                  kbType === 'flat'
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="font-medium text-gray-800 mb-1">扁平结构</div>
                <div className="text-xs text-gray-500">文件直接存放，无子目录</div>
              </button>
              <button
                type="button"
                onClick={() => setKbType('company')}
                className={`p-3 rounded-xl border-2 text-left transition-all ${
                  kbType === 'company'
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="font-medium text-gray-800 mb-1">按公司分类</div>
                <div className="text-xs text-gray-500">按公司名创建子目录</div>
              </button>
            </div>
          </div>

          {/* 语义类型 */}
          <div>
            <label htmlFor="kb-semantic-type" className="block text-sm font-medium text-gray-700 mb-1">
              语义类型 <span className="text-red-500">*</span>
            </label>
            <select
              id="kb-semantic-type"
              value={semanticType}
              onChange={(e) => setSemanticType(e.target.value as SemanticType)}
              className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all text-gray-700"
            >
              <option value="">请选择语义类型...</option>
              {SEMANTIC_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} - {option.description}
                </option>
              ))}
            </select>
            <div className="mt-1.5 flex items-start gap-1.5 text-xs text-gray-500">
              <Info size={14} className="flex-shrink-0 mt-0.5" />
              <span>语义类型决定该知识库在配方生成时的检索角色</span>
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
                className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all text-gray-700 text-center text-lg"
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
              className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all text-gray-700 resize-none"
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
              disabled={!name.trim() || !semanticType || isSubmitting}
              className={`px-4 py-2 text-sm font-medium text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 flex items-center gap-2 ${
                name.trim() && semanticType && !isSubmitting
                  ? 'bg-emerald-500 hover:bg-emerald-600'
                  : 'bg-emerald-300 cursor-not-allowed'
              }`}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  创建中...
                </>
              ) : (
                '立即创建'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
