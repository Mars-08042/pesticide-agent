import React, { useRef, useState } from 'react';
import { X, Trash2, FileText, Calendar, Layers, UploadCloud, Loader2 } from 'lucide-react';
import { KBItem } from '../types';
import { useToast } from './Toast';

interface KBManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  kbItems: KBItem[];
  onDelete: (id: string) => void;
  onUploadSuccess: () => void;
}

export const KBManagerModal: React.FC<KBManagerModalProps> = ({
  isOpen,
  onClose,
  kbItems,
  onDelete,
  onUploadSuccess
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const toast = useToast();

  const [render, setRender] = useState(isOpen);

  React.useEffect(() => {
    if (isOpen) setRender(true);
  }, [isOpen]);

  const onAnimationEnd = () => {
    if (!isOpen) setRender(false);
  };

  if (!render) return null;

  const handleUploadClick = () => {
    toast.warning('后端已移除文件上传接口，上传功能当前不可用（UI 暂保留）。');
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    toast.warning('后端已移除文件上传接口，上传功能当前不可用（UI 暂保留）。');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // 获取状态显示
  const getStatusDisplay = (status: string) => {
    switch (status) {
      case 'active':
        return { text: '活跃', className: 'bg-green-50 text-green-700 border-green-200', dotClass: 'bg-green-500' };
      case 'indexing':
      case 'processing':
        return { text: '索引中', className: 'bg-amber-50 text-amber-700 border-amber-200', dotClass: 'bg-amber-500 animate-pulse' };
      case 'error':
        return { text: '错误', className: 'bg-red-50 text-red-700 border-red-200', dotClass: 'bg-red-500' };
      default:
        return { text: status, className: 'bg-gray-50 text-gray-700 border-gray-200', dotClass: 'bg-gray-500' };
    }
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 ${isOpen ? 'animate-backdrop-in' : 'animate-backdrop-out'}`}
      onAnimationEnd={onAnimationEnd}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      ></div>

      {/* Modal Content */}
      <div className={`relative w-full max-w-4xl bg-white rounded-2xl border-2 border-slate-900 shadow-[8px_8px_0px_0px_rgba(30,41,59,0.2)] flex flex-col max-h-[85vh] overflow-hidden ${isOpen ? 'animate-modal-in' : 'animate-modal-out'}`}>

        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-100 bg-white">
          <div>
            <h2 className="text-xl font-bold text-slate-900">知识库管理</h2>
            <p className="text-slate-500 text-sm mt-1">管理您上传的文档和索引状态</p>
          </div>
          <div className="flex items-center gap-3">
             <button
               onClick={handleUploadClick}
               disabled={isUploading}
               className="flex items-center gap-2 bg-brand-green hover:bg-brand-green-dark text-white px-4 py-2 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
             >
                {isUploading ? (
                    <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>上传中...</span>
                    </>
                ) : (
                    <>
                        <UploadCloud className="w-4 h-4" />
                        <span>上传 Markdown</span>
                    </>
                )}
             </button>
             <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".md"
                className="hidden"
             />

             <button
                onClick={onClose}
                className="p-2 hover:bg-gray-100 rounded-lg text-slate-500 transition-colors"
             >
                <X className="w-5 h-5" />
             </button>
          </div>
        </div>

        {/* Table Container */}
        <div className="overflow-y-auto p-6 bg-[#fdfbf7]">
          <div className="bg-white border-2 border-slate-900/10 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50/80 border-b border-gray-100">
                  <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider">文件名</th>
                  <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider">状态</th>
                  <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider text-center">块数</th>
                  <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider">创建时间</th>
                  <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {kbItems.map((kb) => {
                  const statusDisplay = getStatusDisplay(kb.status);
                  return (
                  <tr key={kb.id} className="hover:bg-gray-50/50 transition-colors group">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-50 text-blue-600 rounded-lg border border-blue-100">
                          <FileText className="w-4 h-4" />
                        </div>
                        <span className="font-semibold text-slate-700">{kb.name}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <span className={`
                        inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border
                        ${statusDisplay.className}
                      `}>
                        <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${statusDisplay.dotClass}`}></span>
                        {statusDisplay.text}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center">
                      <div className="inline-flex items-center gap-1.5 text-slate-600 font-medium bg-gray-100/50 px-2 py-1 rounded-md">
                        <Layers className="w-3.5 h-3.5 text-slate-400" />
                        {kb.chunks}
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <Calendar className="w-3.5 h-3.5" />
                        {new Date(kb.createdAt).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <button
                        onClick={() => onDelete(kb.id)}
                        className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all border border-transparent hover:border-red-200 active:scale-95"
                        title="删除知识库"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                )})}

                {kbItems.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-slate-400">
                      未找到知识库。请上传 Markdown 文件以开始使用。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-100 bg-gray-50/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2.5 bg-white border border-gray-300 text-slate-700 font-semibold rounded-xl hover:bg-gray-50 transition-colors shadow-sm"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
};
