import React from 'react';
import { KBItem } from '../types';
import { Beaker, Check, FileText, FlaskConical, Loader2, X } from 'lucide-react';

interface RightSidebarProps {
  isOpen: boolean;
  kbItems: KBItem[];
  onToggleKB: (id: string) => void;
  onOpenManager: (type: 'pesticide' | 'adjuvant') => void;
}

export const RightSidebar: React.FC<RightSidebarProps> = ({
  isOpen,
  kbItems,
  onToggleKB,
  onOpenManager,
}) => {
  const activeKbItems = kbItems.filter(kb => kb.status === 'active');
  const indexingKbItems = kbItems.filter(kb => kb.status === 'indexing' || kb.status === 'processing');

  return (
    <div
      className={`
        bg-gradient-sidebar backdrop-blur-md border-l border-green-200/40 h-full flex flex-col
        transition-all duration-500 ease-[cubic-bezier(0.25,1,0.5,1)] overflow-hidden
        ${isOpen ? 'w-80 opacity-100 translate-x-0' : 'w-0 opacity-0 translate-x-10'}
      `}
    >
      <div className="w-80 h-full flex flex-col p-5">

        <div className="mb-5 rounded-2xl border border-green-100/80 bg-white/70 p-3.5 shadow-soft-sm">
          <div className="mb-3">
            <h3 className="font-bold text-green-700">知识数据管理</h3>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              进入原药或助剂管理界面，支持分页查询、增删改查和 JSON 自动填充。
            </p>
          </div>
          <div className="grid grid-cols-1 gap-2">
            <button
              onClick={() => onOpenManager('pesticide')}
              className="flex items-center justify-between rounded-2xl border border-green-200/80 bg-gradient-to-r from-white to-green-50 px-3.5 py-3 text-left transition-all duration-200 hover:border-green-300 hover:shadow-soft-sm"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-green-100 p-2 text-green-600">
                  <FlaskConical className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-700">管理原药</div>
                </div>
              </div>
            </button>

            <button
              onClick={() => onOpenManager('adjuvant')}
              className="flex items-center justify-between rounded-2xl border border-green-200/80 bg-gradient-to-r from-white to-green-50 px-3.5 py-3 text-left transition-all duration-200 hover:border-green-300 hover:shadow-soft-sm"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-emerald-100 p-2 text-emerald-600">
                  <Beaker className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-700">管理助剂</div>
                </div>
              </div>
            </button>
          </div>
        </div>

        {/* Selected KBs Section */}
        <div className="mb-6 pt-2">
          <div className="flex flex-wrap gap-2">
            {kbItems.filter(i => i.selected && i.status === 'active').map(kb => (
              <div key={kb.id} className="flex items-center gap-1 bg-gradient-to-r from-green-400 to-green-500 text-white px-3 py-1.5 rounded-full text-xs font-medium shadow-soft-sm">
                <span>{kb.name}</span>
                <button
                  onClick={() => onToggleKB(kb.id)}
                  className="hover:bg-white/20 rounded-full p-0.5 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* List of Active KBs */}
        <div className="flex-1 overflow-y-auto mb-4 border-t border-dashed border-green-200/50 pt-4 custom-scrollbar">
          {/* Indexing items notice */}
          {indexingKbItems.length > 0 && (
            <div className="mb-3 p-2.5 bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl border border-amber-200/50">
              <div className="flex items-center gap-2 text-xs text-amber-700">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>{indexingKbItems.length} 个文档正在索引中...</span>
              </div>
            </div>
          )}

          <div className="space-y-1">
            {activeKbItems.map((kb, index) => (
              <label
                key={kb.id}
                className="flex items-center p-2.5 rounded-xl hover:bg-white/60 cursor-pointer group transition-all duration-200 animate-stagger-in"
                style={{ animationDelay: `${index * 30}ms` }}
              >
                <div
                  onClick={() => onToggleKB(kb.id)}
                  className={`
                    w-5 h-5 rounded-lg border mr-3 flex items-center justify-center transition-all duration-200
                    ${kb.selected
                        ? 'bg-gradient-to-br from-green-400 to-green-500 border-green-500 shadow-soft-sm'
                        : 'border-green-300 bg-white group-hover:border-green-400'
                    }
                `}>
                    {kb.selected && <Check className="w-3.5 h-3.5 text-white" />}
                </div>

                <FileText className="w-4 h-4 text-green-400 mr-2" />
                <span className="text-sm font-medium text-slate-700 truncate flex-1">{kb.name}</span>

                {/* Status Badge */}
                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold ml-2 bg-gradient-to-r from-green-100 to-emerald-100 text-green-700">
                  活跃
                </span>
              </label>
            ))}

            {/* Show indexing items as disabled */}
            {indexingKbItems.map((kb) => (
              <div
                key={kb.id}
                className="flex items-center p-2.5 rounded-xl opacity-50 cursor-not-allowed"
                title="正在索引中，完成后可选择"
              >
                <div className="w-5 h-5 rounded-lg border mr-3 flex items-center justify-center border-gray-200 bg-gray-100">
                  <Loader2 className="w-3 h-3 text-gray-400 animate-spin" />
                </div>

                <FileText className="w-4 h-4 text-gray-300 mr-2" />
                <span className="text-sm font-medium text-slate-400 truncate flex-1">{kb.name}</span>

                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold ml-2 bg-gradient-to-r from-amber-100 to-orange-100 text-amber-700">
                  索引中
                </span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
};
