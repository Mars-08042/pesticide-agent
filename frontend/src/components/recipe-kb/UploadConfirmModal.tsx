import React, { useState } from 'react';
import { ChevronLeft, Upload, FolderOpen, AlertCircle } from 'lucide-react';

interface UploadConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  fileCount: number;
  folderName: string;
  categoryName: string;
  needsCompany: boolean;
}

export const UploadConfirmModal: React.FC<UploadConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  fileCount,
  folderName,
  categoryName,
  needsCompany
}) => {
  const [render, setRender] = useState(isOpen);

  React.useEffect(() => {
    if (isOpen) setRender(true);
  }, [isOpen]);

  const onAnimationEnd = () => {
    if (!isOpen) setRender(false);
  };

  if (!render) return null;

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
            <div className="p-1.5 bg-emerald-100 rounded-lg">
              <Upload size={20} className="text-emerald-600" />
            </div>
            <h3 className="text-lg font-bold">确认上传</h3>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* 文件信息卡片 */}
          <div className="flex items-center gap-4 p-4 bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl border border-emerald-100">
            <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center">
              <FolderOpen className="text-emerald-600" size={24} />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-800">{folderName}</p>
              <p className="text-xs text-gray-500 mt-0.5">
                包含 <span className="font-medium text-emerald-600">{fileCount}</span> 个 Markdown 文件
              </p>
            </div>
          </div>

          {/* 上传说明 */}
          <div className="text-sm text-gray-600 leading-relaxed">
            <p>
              将上传 <strong className="text-gray-800">{fileCount}</strong> 个文件到知识库
              「<strong className="text-emerald-600">{categoryName}</strong>」
            </p>
          </div>

          {/* 公司名称提示 */}
          {needsCompany && (
            <div className="flex items-start gap-2 p-3 bg-blue-50 text-blue-700 rounded-lg text-xs">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <span>
                文件夹名称「<strong>{folderName}</strong>」将作为公司分类名称。
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200"
          >
            取消
          </button>
          <button
            onClick={() => {
              onConfirm();
              onClose();
            }}
            className="px-4 py-2 text-sm font-medium text-white bg-emerald-500 hover:bg-emerald-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 flex items-center gap-2"
          >
            <Upload size={16} />
            确认上传
          </button>
        </div>
      </div>
    </div>
  );
};
