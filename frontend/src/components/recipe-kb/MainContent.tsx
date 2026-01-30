import React, { useState, useEffect } from 'react';
import {
  Search,
  Trash2,
  FileText,
  ChevronLeft,
  ChevronRight,
  Plus,
  ChevronDown,
  Upload,
  FolderPlus
} from 'lucide-react';
import { Category } from './types';
import { RecipeFile, Pagination, recipeKB, DataType } from '../../api/recipe-kb';
import { UploadModal } from './UploadModal';
import { BatchUploadModal } from './BatchUploadModal';
import { ConfirmModal } from './ConfirmModal';

interface MainContentProps {
  category: Category;
  companies: string[];
  onBack: () => void;
  onDataUpdate: () => void; // 回调通知父组件数据已更新
}

export const MainContent: React.FC<MainContentProps> = ({
  category,
  companies,
  onBack,
  onDataUpdate
}) => {
  const [files, setFiles] = useState<RecipeFile[]>([]);
  const [pagination, setPagination] = useState<Pagination>({
    page: 1,
    page_size: 10,
    total_count: 0,
    total_pages: 0
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCompany, setSelectedCompany] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showBatchUploadModal, setShowBatchUploadModal] = useState(false);

  // 删除确认相关状态
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // 检查是否需要显示公司筛选（根据知识库类型判断）
  const showCompanyFilter = category.kbType === 'company';

  // 加载数据
  const loadFiles = async (page = 1) => {
    setIsLoading(true);
    try {
      const response = await recipeKB.getFiles({
        data_type: category.id as DataType,
        company: selectedCompany || undefined,
        keyword: searchQuery || undefined,
        page,
        page_size: pagination.page_size
      });
      if (response.success) {
        setFiles(response.data.items);
        setPagination(response.data.pagination);
      }
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFiles(1);
  }, [category.id, selectedCompany, searchQuery]);

  const handleDeleteClick = (id: string) => {
    setDeleteId(id);
  };

  const handleConfirmDelete = async () => {
    if (!deleteId) return;

    try {
      const res = await recipeKB.deleteFile(deleteId);
      if (res.success) {
        loadFiles(pagination.page);
        onDataUpdate(); // 通知更新统计数据
      }
    } catch (error) {
      console.error('Failed to delete file:', error);
      // 这里可以添加一个 toast 提示，但为了简单起见，暂时不处理
    } finally {
      setDeleteId(null);
    }
  };

  const handlePageChange = (newPage: number) => {
    loadFiles(newPage);
  };

  const handleUploadSuccess = () => {
    loadFiles(1);
    onDataUpdate();
  };

  return (
    <div className="flex-1 bg-white rounded-2xl shadow-sm border border-gray-100 flex flex-col h-full overflow-hidden">
      {/* Header Area */}
      <div className="p-6 pb-2">
        <div className="flex items-center justify-between mb-6">
          <div className="flex flex-col">
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <button onClick={onBack} className="md:hidden p-1 -ml-2 text-gray-400">
                <ChevronLeft size={20} />
              </button>
              {category.name}
            </h1>
            <p className="text-xs text-gray-400 mt-1 line-clamp-1">
              {category.description}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowBatchUploadModal(true)}
              className="flex items-center gap-2 px-3 py-2 bg-emerald-50 hover:bg-emerald-100 text-emerald-600 text-sm font-medium rounded-lg transition-colors border border-emerald-200"
            >
              <FolderPlus size={16} />
              <span className="hidden sm:inline">批量上传</span>
            </button>
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-lg transition-colors shadow-sm shadow-emerald-200"
            >
              <Plus size={16} />
              <span className="hidden sm:inline">上传数据</span>
            </button>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              placeholder="搜索文件名..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all placeholder-gray-400 text-gray-700"
            />
          </div>

          {showCompanyFilter && (
            <div className="relative group w-full sm:w-48">
              <div className="relative">
                <select
                  value={selectedCompany}
                  onChange={(e) => setSelectedCompany(e.target.value)}
                  className="w-full appearance-none pl-4 pr-10 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all text-gray-700 cursor-pointer"
                >
                  <option value="">所有公司</option>
                  {companies.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Table Area */}
      <div className="flex-1 overflow-auto px-6">
        <table className="w-full">
          <thead className="sticky top-0 bg-white z-10">
            <tr className="bg-gray-50/50 border-b border-gray-100">
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 w-[45%]">文件名</th>
              {showCompanyFilter && (
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 w-[15%]">来源公司</th>
              )}
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500 w-[15%]">大小</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500 w-[15%]">时间</th>
              <th className="text-center py-3 px-4 text-xs font-semibold text-gray-500 w-[10%]">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {isLoading ? (
               <tr>
                <td colSpan={showCompanyFilter ? 5 : 4} className="py-12 text-center text-gray-400 text-sm">
                  加载中...
                </td>
              </tr>
            ) : files.length > 0 ? (
              files.map((file) => (
                <tr key={file.id} className="hover:bg-gray-50/80 transition-colors group">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="p-1.5 bg-gray-100 rounded text-gray-500">
                         <FileText size={16} />
                      </div>
                      <span className="text-sm text-gray-700 font-medium truncate max-w-[180px] sm:max-w-xs md:max-w-sm lg:max-w-md" title={file.filename}>
                        {file.filename}
                      </span>
                    </div>
                  </td>
                  {showCompanyFilter && (
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {file.company || '-'}
                    </td>
                  )}
                  <td className="py-3 px-4 text-right text-sm text-gray-500 font-mono">
                    {(file.file_size / 1024).toFixed(1)} KB
                  </td>
                  <td className="py-3 px-4 text-right text-sm text-gray-500 font-mono">
                    {new Date(file.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <button
                      onClick={() => handleDeleteClick(file.id)}
                      className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors opacity-0 group-hover:opacity-100"
                      title="删除文件"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={showCompanyFilter ? 5 : 4} className="py-12 text-center text-gray-400 text-sm">
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="p-4 border-t border-gray-100 bg-white">
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={() => handlePageChange(pagination.page - 1)}
            disabled={pagination.page <= 1}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-500 bg-white border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={14} />
            上一页
          </button>
          <span className="text-xs font-medium text-gray-600">
            第 {pagination.total_pages > 0 ? pagination.page : 0} / {pagination.total_pages} 页
          </span>
          <button
            onClick={() => handlePageChange(pagination.page + 1)}
            disabled={pagination.page >= pagination.total_pages}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-500 bg-white border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            下一页
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Modals */}
      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        category={category}
        companies={companies}
        onSuccess={handleUploadSuccess}
      />

      <BatchUploadModal
        isOpen={showBatchUploadModal}
        onClose={() => setShowBatchUploadModal(false)}
        category={category}
        companies={companies}
        onSuccess={handleUploadSuccess}
      />

      <ConfirmModal
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleConfirmDelete}
        title="确认删除"
        message="您确定要删除这个文件吗？此操作无法撤销。"
        confirmText="删除"
        isDestructive={true}
      />
    </div>
  );
};
