import React, { useState } from 'react';
import { Message, Step, StepType } from '../types';
import { ChevronRight, ChevronDown, Terminal, Brain, AlertCircle, MessageSquare, ArrowRightLeft, GitFork, CheckCircle2, User, Bot, Copy, Pencil, RotateCcw, Check, Search, BookOpen, Zap, Sparkles, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
  message: Message;
  onEdit?: (messageId: string, newContent: string) => void;
  onRegenerate?: (messageId: string) => void;
  isGenerating?: boolean;
  isLast?: boolean;
}

interface GroupedStep {
  type: 'thought' | 'tool' | 'error' | 'answer';
  items: Step[];
}

const getToolIcon = (toolName: string) => {
  const icons: Record<string, React.ReactNode> = {
    'vector_search': <Search className="w-3.5 h-3.5" />,
    'web_search': <Search className="w-3.5 h-3.5" />,
    'recipe_lookup': <BookOpen className="w-3.5 h-3.5" />,
    'llm_generate': <Zap className="w-3.5 h-3.5" />,
    'chitchat_handler': <MessageSquare className="w-3.5 h-3.5" />,
  };
  return icons[toolName] || <Terminal className="w-3.5 h-3.5" />;
};

const getToolDisplayName = (content: string, metadata?: any): { name: string; args: string } => {
  const toolName = metadata?.tool || '';
  const toolNames: Record<string, string> = {
    'vector_search': '知识库检索',
    'web_search': '联网搜索',
    'recipe_lookup': '配方查询',
    'llm_generate': '生成回答',
    'chitchat_handler': '闲聊处理',
  };
  return {
    name: toolNames[toolName] || toolName || '工具调用',
    args: content
  };
};

// 生成配方文件名
const generateRecipeFilename = (metadata: any): string => {
  const requirements = metadata?.requirements;
  if (requirements) {
    const ingredients = requirements.active_ingredients?.join('_') || '';
    const concentration = requirements.concentration || '';
    const formulation = requirements.formulation_type || '';
    if (ingredients || concentration || formulation) {
      // 清理文件名中的非法字符
      const name = `${concentration}${ingredients}${formulation}配方`.replace(/[\\/:*?"<>|]/g, '');
      return `${name}.md`;
    }
  }
  // 兜底：使用时间戳
  const date = new Date().toISOString().slice(0, 10);
  return `配方_${date}.md`;
};

// 下载配方文件
const downloadRecipe = (content: string, filename: string) => {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

// 检查是否为可下载的配方
const isDownloadableRecipe = (step: Step): boolean => {
  return step.metadata?.type === 'recipe_design' && step.metadata?.status === 'approved';
};

const StepContent: React.FC<{ step: Step }> = ({ step }) => {
  if (step.type === 'router') {
    const reasoning = step.metadata?.reasoning;
    const entities = step.metadata?.entities;
    return (
      <div className="flex gap-3 text-sm mb-2">
        <div className="flex-none mt-0.5"><ArrowRightLeft className="w-4 h-4 text-violet-500" /></div>
        <div className="flex-1">
          <span className="font-semibold text-violet-700 block text-xs uppercase tracking-wide mb-1">意图识别</span>
          <div className="text-slate-700 bg-gradient-to-br from-violet-50 to-violet-100/50 p-2.5 rounded-xl border border-violet-200/50">
            <div className="font-medium">{step.content}</div>
            {entities && (entities.crop || entities.disease) && (
              <div className="text-xs text-violet-600 mt-1">
                {entities.crop && <span className="mr-2">作物: {entities.crop}</span>}
                {entities.disease && <span>病虫害: {entities.disease}</span>}
              </div>
            )}
            {reasoning && (
              <div className="text-xs text-slate-500 mt-2 pt-2 border-t border-violet-100">
                <span className="font-medium text-violet-600">理由: </span>{reasoning}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
  if (step.type === 'decision') {
    const reasoning = step.metadata?.reasoning;
    const confidence = step.metadata?.confidence;
    const missingInfo = step.metadata?.missing_info;
    return (
       <div className="flex gap-3 text-sm mb-2">
        <div className="flex-none mt-0.5"><GitFork className="w-4 h-4 text-indigo-500" /></div>
        <div className="flex-1">
          <span className="font-semibold text-indigo-700 block text-xs uppercase tracking-wide mb-1">决策</span>
          <div className="text-slate-700 bg-gradient-to-br from-indigo-50 to-indigo-100/50 p-2.5 rounded-xl border border-indigo-200/50">
            <div className="font-medium">{step.content}</div>
            {confidence !== undefined && (
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 h-1.5 bg-indigo-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${confidence >= 70 ? 'bg-green-500' : confidence >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${confidence}%` }}
                  />
                </div>
                <span className="text-xs text-indigo-600">{confidence}%</span>
              </div>
            )}
            {reasoning && (
              <div className="text-xs text-slate-500 mt-2 pt-2 border-t border-indigo-100">
                <span className="font-medium text-indigo-600">理由: </span>{reasoning}
              </div>
            )}
            {missingInfo && (
              <div className="text-xs text-orange-600 mt-1">
                <span className="font-medium">缺失信息: </span>{missingInfo}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
  if (step.type === 'thought') {
    return (
       <div className="flex gap-3 text-sm mb-2">
        <div className="flex-none mt-0.5"><Brain className="w-4 h-4 text-amber-500" /></div>
        <div className="flex-1">
          <span className="font-semibold text-amber-700 block text-xs uppercase tracking-wide mb-1">思考</span>
          <div className="text-slate-600 bg-gradient-to-br from-amber-50 to-amber-100/50 p-2.5 rounded-xl border border-amber-200/50 whitespace-pre-wrap">{step.content}</div>
        </div>
      </div>
    );
  }
  if (step.type === 'tool_req') {
    const { name, args } = getToolDisplayName(step.content, step.metadata);
    const toolName = step.metadata?.tool || '';
    return (
      <div className="mb-3">
        <div className="text-xs font-semibold text-sky-600 uppercase tracking-wide mb-1 flex items-center gap-1.5">
          {getToolIcon(toolName)}
          <span>{name}</span>
        </div>
        <pre className="bg-slate-800 text-sky-100 p-3 rounded-xl text-xs overflow-x-auto font-mono border border-slate-700 max-h-32 overflow-y-auto">
          {args}
        </pre>
      </div>
    );
  }
  if (step.type === 'tool_res') {
    const resultCount = step.metadata?.result_count;
    const success = step.metadata?.success !== false;
    const resultsPreview = step.metadata?.results_preview;
    const sources = step.metadata?.sources;
    return (
      <div className="mb-1">
        <div className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-1 flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>执行结果</span>
          {resultCount !== undefined && (
            <span className="text-green-500 font-normal">({resultCount} 条记录)</span>
          )}
          {!success && <span className="text-red-500 font-normal">(失败)</span>}
        </div>
        {sources && sources.length > 0 && (
          <div className="text-xs text-slate-500 mb-2">
            来源: {sources.slice(0, 3).join(', ')}{sources.length > 3 ? '...' : ''}
          </div>
        )}
        {resultsPreview ? (
          <pre className="bg-gradient-to-br from-green-50 to-emerald-50 text-green-800 p-3 rounded-xl text-xs overflow-x-auto font-mono border border-green-200/50 max-h-60 overflow-y-auto whitespace-pre-wrap">
            {resultsPreview}
          </pre>
        ) : (
          <pre className="bg-gradient-to-br from-green-50 to-emerald-50 text-green-800 p-3 rounded-xl text-xs overflow-x-auto font-mono border border-green-200/50 max-h-40 overflow-y-auto">
            {step.content}
          </pre>
        )}
      </div>
    );
  }
  if (step.type === 'error') {
     return (
        <div className="flex gap-2 items-start text-red-700 text-sm bg-gradient-to-br from-red-50 to-rose-50 p-2.5 rounded-xl border border-red-200/50">
          <AlertCircle className="w-4 h-4 flex-none mt-0.5" />
          <span>{step.content}</span>
        </div>
     );
  }
  return <div className="text-sm">{step.content}</div>;
};

const GroupCard: React.FC<{
  group: GroupedStep;
  onCopy: (text: string) => void;
  onRegenerate?: () => void;
  isCopied: boolean;
  isGenerating?: boolean;
}> = ({ group, onCopy, onRegenerate, isCopied, isGenerating }) => {
  const [isOpen, setIsOpen] = useState(group.type === 'thought');

  const config = {
    thought: {
      icon: Brain,
      title: '思考过程',
      headerClass: 'text-gray-600 hover:bg-gray-100/80',
      containerClass: 'bg-white/60 backdrop-blur-sm border-gray-200/50',
      contentClass: 'bg-gray-50/50 text-gray-700',
      iconColor: 'text-gray-500'
    },
    tool: {
      icon: Terminal,
      title: '工具调用',
      headerClass: 'text-sky-600 hover:bg-sky-50/80',
      containerClass: 'bg-white/60 backdrop-blur-sm border-sky-200/50',
      contentClass: 'bg-white/50',
      iconColor: 'text-sky-500'
    },
    error: {
      icon: AlertCircle,
      title: '发生错误',
      headerClass: 'text-red-600 hover:bg-red-50/80',
      containerClass: 'bg-red-50/60 backdrop-blur-sm border-red-200/50',
      contentClass: 'bg-red-50/50 text-red-800',
      iconColor: 'text-red-500'
    },
    answer: {
      icon: MessageSquare,
      title: '回答',
      headerClass: '',
      containerClass: '',
      contentClass: '',
      iconColor: ''
    }
  };

  if (group.type === 'answer') {
    return (
      <div className="relative group/message mb-4">
        <div className="bg-gradient-to-br from-white to-green-50/50 backdrop-blur-sm text-slate-800 rounded-2xl rounded-tl-sm px-5 py-4 shadow-soft-sm border border-green-100/60">
          {group.items.map(step => (
            <div key={step.id} className="leading-relaxed prose prose-slate max-w-none prose-headings:text-green-800 prose-a:text-green-600">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc pl-5 mb-3 last:mb-0 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 last:mb-0 space-y-1">{children}</ol>,
                  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-4">
                      <table className="min-w-full border-collapse border border-green-200 text-sm rounded-lg overflow-hidden">
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-green-50">{children}</thead>
                  ),
                  th: ({ children }) => (
                    <th className="border border-green-200 px-3 py-2 text-left font-semibold text-green-800">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-green-200 px-3 py-2 text-slate-600">
                      {children}
                    </td>
                  ),
                }}
              >{step.content}</ReactMarkdown>
              {isGenerating && step.metadata?.is_streaming && (
                <span className="inline-block w-2 h-5 ml-0.5 bg-green-500 animate-pulse rounded-sm" />
              )}
            </div>
          ))}
          <div className="flex justify-end gap-2 mt-2 opacity-0 group-hover/message:opacity-100 transition-opacity">
            {/* 下载配方按钮 - 仅对已审核通过的配方设计显示 */}
            {group.items.some(isDownloadableRecipe) && (
              <button
                title="下载配方"
                className="flex items-center justify-center p-1.5 bg-white/80 backdrop-blur-sm border border-green-200/50 rounded-lg shadow-soft-sm text-green-600 hover:text-green-700 hover:shadow-soft-md hover:border-green-300 transition-all active:scale-95"
                onClick={() => {
                  const recipeStep = group.items.find(isDownloadableRecipe);
                  if (recipeStep) {
                    const content = recipeStep.content;
                    const filename = generateRecipeFilename(recipeStep.metadata);
                    downloadRecipe(content, filename);
                  }
                }}
              >
                <Download className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              title="重新生成"
              className="flex items-center justify-center p-1.5 bg-white/80 backdrop-blur-sm border border-green-200/50 rounded-lg shadow-soft-sm text-green-600 hover:text-green-700 hover:shadow-soft-md hover:border-green-300 transition-all active:scale-95"
              onClick={onRegenerate}
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
            <button
              title="复制"
              className="flex items-center justify-center p-1.5 bg-white/80 backdrop-blur-sm border border-green-200/50 rounded-lg shadow-soft-sm text-green-600 hover:text-green-700 hover:shadow-soft-md hover:border-green-300 transition-all active:scale-95"
              onClick={() => {
                const content = group.items.map(item => item.content).join('\n');
                onCopy(content);
              }}
            >
              {isCopied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const c = config[group.type];
  const Icon = c.icon;

  return (
    <div className={`mb-4 w-full max-w-3xl border rounded-xl overflow-hidden transition-all ${c.containerClass}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center w-full px-4 py-2.5 text-xs font-bold uppercase tracking-wider transition-colors ${c.headerClass}`}
      >
        {isOpen ? (
          <ChevronDown className="w-4 h-4 mr-2 opacity-70" />
        ) : (
          <ChevronRight className="w-4 h-4 mr-2 opacity-70" />
        )}
        <Icon className={`w-4 h-4 mr-2 ${c.iconColor}`} />
        {c.title}
        <span className="ml-auto opacity-50 text-[10px] lowercase font-normal">
          {group.items.length} 步
        </span>
      </button>

      {isOpen && (
        <div className={`px-4 py-3 border-t border-inherit ${c.contentClass}`}>
          {group.items.map(step => (
             <div key={step.id} className="mb-3 last:mb-0">
               <StepContent step={step} />
             </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, onEdit, onRegenerate, isGenerating, isLast }) => {
  const isUser = message.role === 'user';
  const [isCopied, setIsCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content || '');

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    });
  };

  const handleUpdate = () => {
    if (editValue.trim()) {
      onEdit?.(message.id, editValue);
    }
    setIsEditing(false);
  };

  const groups: GroupedStep[] = [];
  if (!isUser && message.steps) {
    let currentGroup: GroupedStep | null = null;

    message.steps.forEach(step => {
      let groupType: GroupedStep['type'] = 'answer';
      if (['router', 'thought', 'decision'].includes(step.type)) groupType = 'thought';
      else if (['tool_req', 'tool_res'].includes(step.type)) groupType = 'tool';
      else if (step.type === 'error') groupType = 'error';
      else if (step.type === 'answer') groupType = 'answer';

      if (groupType === 'thought') {
        const existingThoughtGroup = groups.find(g => g.type === 'thought');
        if (existingThoughtGroup) {
          existingThoughtGroup.items.push(step);
          return;
        }
      }

      if (currentGroup && currentGroup.type === groupType) {
        currentGroup.items.push(step);
      } else {
        if (currentGroup) groups.push(currentGroup);
        currentGroup = { type: groupType, items: [step] };
      }
    });
    if (currentGroup) groups.push(currentGroup);
  }

  const hasThoughts = groups.some(g => g.type === 'thought');
  const hasAnswer = groups.some(g => g.type === 'answer' && g.items.some(i => i.content?.trim()));
  const showThinkingIndicator = isGenerating && !isUser && !hasAnswer;
  const shouldFallbackToContent = !isUser && message.steps && message.steps.length > 0 && !hasAnswer && message.content;

  if (isUser) {
    return (
      <div className="flex w-full mb-6 justify-end group">
        <div className="flex items-start gap-3 max-w-[85%] flex-row-reverse">
          {/* User Avatar */}
          <div className="flex-none w-8 h-8 rounded-full bg-gradient-to-br from-green-400 to-green-500 border border-green-500/20 flex items-center justify-center text-white shadow-soft-md mt-1">
            <User className="w-5 h-5" />
          </div>

          <div className="flex items-end gap-2">
            {!isEditing && (
              <div className="flex items-center gap-1 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  title="复制"
                  className="p-1.5 text-green-500 hover:text-green-600 hover:bg-green-100/50 rounded-lg transition-colors"
                  onClick={() => handleCopy(message.content || '')}
                >
                  {isCopied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                </button>
                <button
                  title="编辑"
                  className="p-1.5 text-green-500 hover:text-green-600 hover:bg-green-100/50 rounded-lg transition-colors"
                  onClick={() => setIsEditing(true)}
                >
                  <Pencil className="w-4 h-4" />
                </button>
              </div>
            )}
            {isEditing ? (
              <div className="flex flex-col items-end gap-3 w-full min-w-[300px] sm:min-w-[400px]">
                <div className="w-full rounded-2xl border-2 border-green-400 bg-white overflow-hidden shadow-soft-md">
                  <textarea
                    className="w-full p-4 text-base leading-relaxed focus:outline-none bg-transparent text-slate-800 resize-none min-h-[100px]"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    autoFocus
                  />
                </div>
                <div className="flex items-center gap-3 mr-1">
                  <button
                    onClick={() => { setIsEditing(false); setEditValue(message.content || ''); }}
                    className="text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleUpdate}
                    className={`px-4 py-1.5 text-xs font-semibold rounded-full transition-all active:scale-95 disabled:opacity-50 ${
                      !editValue.trim()
                        ? 'text-slate-400 bg-slate-100 cursor-not-allowed'
                        : 'text-white bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 shadow-soft-sm cursor-pointer'
                    }`}
                    disabled={!editValue.trim()}
                  >
                    发送
                  </button>
                </div>
              </div>
            ) : (
              <div className="px-5 py-4 text-base leading-relaxed rounded-2xl shadow-soft-sm bg-gradient-to-br from-green-400 to-green-500 text-white rounded-tr-sm border border-green-500/20">
                {message.content}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full mb-6 justify-start">
      <div className="flex items-start gap-3 max-w-[90%] w-full">
        {/* AI Avatar */}
        <div className="flex-none w-8 h-8 rounded-full bg-gradient-to-br from-green-100 to-green-200 border border-green-200/50 flex items-center justify-center text-green-600 shadow-soft-sm mt-1">
          <Bot className="w-5 h-5" />
        </div>

        <div className="flex flex-col w-full">
          {/* 思考状态指示器 */}
          {showThinkingIndicator && isLast && (
            <div className="flex items-center gap-3 mb-4 px-4 py-3 bg-gradient-to-r from-green-50/90 to-emerald-50/90 border border-green-100/50 rounded-2xl shadow-soft-sm backdrop-blur-sm animate-fade-in-up">
               <div className="relative flex items-center justify-center">
                 <div className="absolute inset-0 bg-green-400/20 rounded-full animate-ping [animation-duration:2s]" />
                 <div className="relative bg-white p-1 rounded-full shadow-soft-sm border border-green-50">
                     <Sparkles className="w-3.5 h-3.5 text-green-500 animate-pulse" />
                 </div>
               </div>
               <div className="flex items-center gap-2">
                 <span className="text-sm font-medium text-gradient-primary">
                   深度思考中
                 </span>
                 <div className="flex space-x-0.5 pt-1">
                    <span className="w-1 h-1 bg-green-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                    <span className="w-1 h-1 bg-green-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                    <span className="w-1 h-1 bg-green-500 rounded-full animate-bounce"></span>
                 </div>
               </div>
            </div>
          )}

          {/* Render content if no steps */}
          {(!message.steps || message.steps.length === 0) && message.content && (
             <div className="relative group/message mb-4">
                <div className="bg-gradient-to-br from-white to-green-50/50 backdrop-blur-sm text-slate-800 rounded-2xl rounded-tl-sm px-5 py-4 shadow-soft-sm border border-green-100/60">
                  <div className="leading-relaxed prose prose-slate max-w-none prose-headings:text-green-800 prose-a:text-green-600">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc pl-5 mb-3 last:mb-0 space-y-1">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 last:mb-0 space-y-1">{children}</ol>,
                        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                        table: ({ children }) => (
                          <div className="overflow-x-auto my-4">
                            <table className="min-w-full border-collapse border border-green-200 text-sm rounded-lg overflow-hidden">
                              {children}
                            </table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-green-50">{children}</thead>
                        ),
                        th: ({ children }) => (
                          <th className="border border-green-200 px-3 py-2 text-left font-semibold text-green-800">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="border border-green-200 px-3 py-2 text-slate-600">
                            {children}
                          </td>
                        ),
                      }}
                    >{message.content}</ReactMarkdown>
                  </div>
                  <div className="flex justify-end gap-2 mt-2 opacity-0 group-hover/message:opacity-100 transition-opacity">
                    <button
                      title="重新生成"
                      className="flex items-center justify-center p-1.5 bg-white/80 backdrop-blur-sm border border-green-200/50 rounded-lg shadow-soft-sm text-green-600 hover:text-green-700 hover:shadow-soft-md hover:border-green-300 transition-all active:scale-95"
                      onClick={() => onRegenerate?.(message.id)}
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                    <button
                      title="复制"
                      className="flex items-center justify-center p-1.5 bg-white/80 backdrop-blur-sm border border-green-200/50 rounded-lg shadow-soft-sm text-green-600 hover:text-green-700 hover:shadow-soft-md hover:border-green-300 transition-all active:scale-95"
                      onClick={() => handleCopy(message.content || '')}
                    >
                      {isCopied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
             </div>
          )}

          {groups.map((group, idx) => (
            <GroupCard
              key={idx}
              group={group}
              onCopy={handleCopy}
              onRegenerate={() => onRegenerate?.(message.id)}
              isCopied={isCopied}
              isGenerating={isGenerating && isLast}
            />
          ))}

          {/* Fallback content */}
          {shouldFallbackToContent && (
             <div className="relative group/message mb-4">
                <div className="bg-gradient-to-br from-white to-green-50/50 backdrop-blur-sm text-slate-800 rounded-2xl rounded-tl-sm px-5 py-4 shadow-soft-sm border border-green-100/60">
                  <div className="leading-relaxed prose prose-slate max-w-none prose-headings:text-green-800 prose-a:text-green-600">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc pl-5 mb-3 last:mb-0 space-y-1">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 last:mb-0 space-y-1">{children}</ol>,
                        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                        table: ({ children }) => (
                          <div className="overflow-x-auto my-4">
                            <table className="min-w-full border-collapse border border-green-200 text-sm rounded-lg overflow-hidden">
                              {children}
                            </table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-green-50">{children}</thead>
                        ),
                        th: ({ children }) => (
                          <th className="border border-green-200 px-3 py-2 text-left font-semibold text-green-800">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="border border-green-200 px-3 py-2 text-slate-600">
                            {children}
                          </td>
                        ),
                      }}
                    >{message.content}</ReactMarkdown>
                  </div>
                  <div className="flex justify-end gap-2 mt-2 opacity-0 group-hover/message:opacity-100 transition-opacity">
                    <button
                      title="重新生成"
                      className="flex items-center justify-center p-1.5 bg-white/80 backdrop-blur-sm border border-green-200/50 rounded-lg shadow-soft-sm text-green-600 hover:text-green-700 hover:shadow-soft-md hover:border-green-300 transition-all active:scale-95"
                      onClick={() => onRegenerate?.(message.id)}
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                    <button
                      title="复制"
                      className="flex items-center justify-center p-1.5 bg-white/80 backdrop-blur-sm border border-green-200/50 rounded-lg shadow-soft-sm text-green-600 hover:text-green-700 hover:shadow-soft-md hover:border-green-300 transition-all active:scale-95"
                      onClick={() => handleCopy(message.content || '')}
                    >
                      {isCopied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
             </div>
          )}
        </div>
      </div>
    </div>
  );
};
