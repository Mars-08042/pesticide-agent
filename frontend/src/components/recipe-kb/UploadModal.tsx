import React, { useState } from 'react';
import { ChevronLeft, FileText, Upload, AlertCircle, X, CheckCircle, Loader2 } from 'lucide-react';
import { Category } from './types';
import { CompanyInput } from './CompanyInput';

const MAX_FILES = 10;

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  category: Category;
  companies: string[];
  onSuccess: () => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  category,
  companies,
  onSuccess
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [company, setCompany] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  const [render, setRender] = useState(isOpen);

  React.useEffect(() => {
    if (isOpen) setRender(true);
  }, [isOpen]);

  const onAnimationEnd = () => {
    if (!isOpen) setRender(false);
  };

  if (!render) return null;

  // 根据知识库类型判断是否需要公司字段
  const needsCompany = category.kbType === 'company';

  const resetState = () => {
    setSelectedFiles([]);
    setCompany('');
    setError(null);
    setResult(null);
    setIsUploading(false);
  };

  const handleClose = () => {
    if (result) {
      onSuccess();
    }
    resetState();
    onClose();
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const addFiles = (newFiles: File[]) => {
    const mdFiles = newFiles.filter(f => f.name.endsWith('.md'));
    if (mdFiles.length === 0) {
      setError('仅支持 .md 格式的文件');
      return;
    }

    const totalFiles = [...selectedFiles, ...mdFiles];
    if (totalFiles.length > MAX_FILES) {
      setError(`最多只能选择 ${MAX_FILES} 个文件`);
      return;
    }

    // 去重
    const existingNames = new Set(selectedFiles.map(f => f.name));
    const uniqueNewFiles = mdFiles.filter(f => !existingNames.has(f.name));

    if (uniqueNewFiles.length < mdFiles.length) {
      setError(`已跳过 ${mdFiles.length - uniqueNewFiles.length} 个重复文件`);
    } else {
      setError(null);
    }

    setSelectedFiles(prev => [...prev, ...uniqueNewFiles].slice(0, MAX_FILES));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files.length > 0) {
      addFiles(Array.from(e.target.files));
    }
    // 清空 input 以允许再次选择相同文件
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    setError(null);
  };

  const handleUploadClick = async () => {
    if (selectedFiles.length === 0) return;

    setIsUploading(false);
    setResult(null);
    setError('后端已移除文件上传接口，当前不可用（UI 暂保留）。');
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
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-full hover:bg-gray-100 mr-2 -ml-2"
            title="返回"
          >
            <ChevronLeft size={24} />
          </button>
          <h3 className="text-lg font-bold text-gray-800">
            上传数据到「{category.name}」
          </h3>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {!result ? (
            <>
              {needsCompany && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">来源公司（可选）</label>
                  <CompanyInput
                    value={company}
                    onChange={setCompany}
                    companies={companies}
                    placeholder="输入或选择公司，留空则归为'其他'"
                  />
                </div>
              )}

              <div
                className={`relative flex flex-col items-center justify-center w-full h-36 border-2 border-dashed rounded-xl transition-all duration-200 ${
                  dragActive
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-300 bg-gray-50 hover:bg-gray-100'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <input
                  type="file"
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  onChange={handleChange}
                  accept=".md"
                  multiple
                />

                <div className="flex flex-col items-center text-center pointer-events-none">
                  <div className="text-gray-400 mb-2">
                    <Upload size={36} strokeWidth={1.5} />
                  </div>
                  <p className="text-sm text-gray-600 font-medium">
                    拖拽文件到此处 或 <span className="text-emerald-600">点击选择</span>
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    支持格式: .md（最多 {MAX_FILES} 个）
                  </p>
                </div>
              </div>

              {/* 已选文件列表 */}
              {selectedFiles.length > 0 && (
                <div className="bg-gray-50 rounded-lg p-3 max-h-48 overflow-y-auto">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">
                      已选择 {selectedFiles.length} 个文件
                    </span>
                    <button
                      onClick={() => setSelectedFiles([])}
                      className="text-xs text-red-500 hover:text-red-600"
                    >
                      清空
                    </button>
                  </div>
                  <ul className="space-y-1">
                    {selectedFiles.map((file, index) => (
                      <li key={index} className="flex items-center justify-between text-sm text-gray-600 bg-white rounded px-2 py-1">
                        <div className="flex items-center gap-2 overflow-hidden">
                          <FileText size={14} className="text-emerald-500 shrink-0" />
                          <span className="truncate">{file.name}</span>
                          <span className="text-xs text-gray-400 shrink-0">
                            ({(file.size / 1024).toFixed(1)} KB)
                          </span>
                        </div>
                        <button
                          onClick={() => removeFile(index)}
                          className="text-gray-400 hover:text-red-500 shrink-0 ml-2"
                        >
                          <X size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-col items-center justify-center p-6 bg-emerald-50 rounded-xl">
                <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mb-3">
                  <CheckCircle className="text-emerald-500" size={24} />
                </div>
                <h4 className="text-lg font-bold text-gray-900 mb-1">上传完成</h4>
                <p className="text-sm text-gray-600 text-center">
                  成功: {result.success_count} 个 / 失败: {result.failed_count} 个
                </p>
              </div>

              {result.files.some(f => f.status === 'failed') && (
                <div className="bg-red-50 rounded-lg p-4 max-h-40 overflow-y-auto">
                  <h5 className="text-xs font-bold text-red-700 mb-2">失败文件列表:</h5>
                  <ul className="space-y-1">
                    {result.files.filter(f => f.status === 'failed').map((f, i) => (
                      <li key={i} className="text-xs text-red-600 flex justify-between">
                        <span>{f.filename}</span>
                        <span>{f.error}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-500 bg-red-50 p-3 rounded-lg">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50/50">
          {!result ? (
            <>
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200"
              >
                取消
              </button>
              <button
                onClick={handleUploadClick}
                disabled={selectedFiles.length === 0 || isUploading}
                className={`px-4 py-2 text-sm font-medium text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 flex items-center gap-2 ${
                    selectedFiles.length > 0 && !isUploading
                    ? 'bg-emerald-500 hover:bg-emerald-600'
                    : 'bg-emerald-300 cursor-not-allowed'
                }`}
              >
                {isUploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    上传中...
                  </>
                ) : (
                  `上传 (${selectedFiles.length})`
                )}
              </button>
            </>
          ) : (
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-white bg-emerald-500 hover:bg-emerald-600 rounded-lg"
            >
              完成
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
