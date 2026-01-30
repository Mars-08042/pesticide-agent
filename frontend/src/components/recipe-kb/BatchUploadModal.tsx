import React, { useState, useRef } from 'react';
import { ChevronLeft, FolderPlus, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { Category } from './types';
import { UploadConfirmModal } from './UploadConfirmModal';

interface BatchUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  category: Category;
  companies: string[];
  onSuccess: () => void;
}

export const BatchUploadModal: React.FC<BatchUploadModalProps> = ({
  isOpen,
  onClose,
  category,
  companies,
  onSuccess
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [folderName, setFolderName] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    setFiles([]);
    setFolderName('');
    setError(null);
    setResult(null);
    setIsUploading(false);
    setShowConfirm(false);
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

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    // 处理文件夹拖拽比较复杂，这里简化处理，只提示用户使用点击选择
    // 浏览器对于拖拽文件夹的支持不统一，webkittGetAsEntry 是非标准的
    setError('建议点击下方区域选择文件夹进行上传，以获得更好的兼容性');
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      const mdFiles = selectedFiles.filter(f => f.name.endsWith('.md'));

      if (mdFiles.length === 0) {
        setError('所选目录中没有找到 Markdown (.md) 文件');
        return;
      }

      if (selectedFiles.length !== mdFiles.length) {
        setError(`检测到 ${selectedFiles.length - mdFiles.length} 个非 Markdown 文件，将自动忽略`);
      } else {
        setError(null);
      }

      setFiles(mdFiles);

      // 尝试从文件路径获取文件夹名
      let folder = '';
      if (mdFiles.length > 0) {
        const relativePath = (mdFiles[0] as any).webkitRelativePath;
        if (relativePath) {
          folder = relativePath.split('/')[0];
          setFolderName(folder);
        }
      }

      // 显示自定义确认弹窗
      setShowConfirm(true);
    }
  };

  const handleConfirmUpload = async () => {
    if (files.length === 0) return;

    setShowConfirm(false);
    setIsUploading(false);
    setResult(null);
    setError('后端已移除文件上传接口，当前不可用（UI 暂保留）。');
  };

  const handleUploadClick = async () => {
    if (files.length === 0) return;

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
        className={`bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden transform transition-all m-4 ${isOpen ? 'animate-modal-in' : 'animate-modal-out'}`}
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
            批量上传到「{category.name}」
          </h3>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {!result ? (
            <>
              <div
                className={`relative flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-xl transition-all duration-200 cursor-pointer ${
                  dragActive
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-gray-300 bg-gray-50 hover:bg-gray-100'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  onChange={handleFileSelect}
                  // @ts-ignore - webkitdirectory is non-standard but supported by most browsers
                  webkitdirectory=""
                  directory=""
                  multiple
                />

                {files.length > 0 ? (
                  <div className="flex flex-col items-center text-center p-4">
                    <div className="bg-emerald-100 p-3 rounded-full mb-3">
                      <FolderPlus className="text-emerald-600" size={32} />
                    </div>
                    <p className="text-sm font-medium text-gray-900">
                      {folderName || '已选择目录'}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      包含 {files.length} 个 Markdown 文件
                    </p>
                    {needsCompany && (
                      <p className="text-xs text-emerald-600 mt-2 bg-emerald-50 px-2 py-1 rounded">
                        目录名将作为公司名称
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center text-center pointer-events-none">
                    <div className="text-gray-400 mb-3">
                      <FolderPlus size={48} strokeWidth={1.5} />
                    </div>
                    <p className="text-sm text-gray-600 font-medium">
                      点击选择文件夹进行上传
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      仅支持一级目录，且只上传 .md 文件
                    </p>
                  </div>
                )}
              </div>

              {needsCompany && files.length > 0 && (
                <div className="flex items-center gap-2 p-3 bg-blue-50 text-blue-700 rounded-lg text-xs">
                  <AlertCircle size={16} className="shrink-0" />
                  <span>
                    系统将以文件夹名称 <strong>"{folderName}"</strong> 作为公司分类。如果该公司已存在，将合并到现有目录；否则将创建新公司目录。
                  </span>
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
                  {result.skipped_count ? ` / 跳过: ${result.skipped_count} 个` : ''}
                </p>
                {needsCompany && (
                  <p className="text-xs text-emerald-600 mt-2">
                    归属公司: {result.company} {result.is_new_company ? '(新创建)' : ''}
                  </p>
                )}
              </div>

              {/* 多级目录警告 */}
              {result.has_nested_dirs && result.nested_dir_warning && (
                <div className="flex items-start gap-2 p-3 bg-amber-50 text-amber-700 rounded-lg text-xs">
                  <AlertCircle size={16} className="shrink-0 mt-0.5" />
                  <span>{result.nested_dir_warning}</span>
                </div>
              )}

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
                disabled={files.length === 0 || isUploading}
                className={`px-4 py-2 text-sm font-medium text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 flex items-center gap-2 ${
                  files.length > 0 && !isUploading
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
                  '开始批量上传'
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

      {/* 上传确认弹窗 */}
      <UploadConfirmModal
        isOpen={showConfirm}
        onClose={() => setShowConfirm(false)}
        onConfirm={handleConfirmUpload}
        fileCount={files.length}
        folderName={folderName}
        categoryName={category.name}
        needsCompany={needsCompany}
      />
    </div>
  );
};
