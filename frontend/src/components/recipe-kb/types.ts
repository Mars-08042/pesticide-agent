import { KnowledgeBase, KBType, SemanticType, RecipeFile } from '../../api/recipe-kb';

// 为了兼容性，Category 现在是 KnowledgeBase 的别名
export interface Category {
  id: string;
  name: string;
  count: number;
  description?: string;
  iconChar: string;
  colorClass: string;
  kbType: KBType;  // 'flat' 或 'company'
  semanticType: SemanticType;  // 语义类型: A/B/C/D/E
  lastUpdated?: string;
}

// 从 API 返回的 KnowledgeBase 转换为前端使用的 Category
export function knowledgeBaseToCategory(kb: KnowledgeBase): Category {
  return {
    id: kb.id,
    name: kb.name,
    count: kb.count,
    description: kb.description,
    iconChar: kb.icon_char,
    colorClass: kb.color_class,
    kbType: kb.kb_type,
    semanticType: kb.semantic_type,
  };
}

// 判断分类是否需要公司字段
export function needsCompany(category: Category): boolean {
  return category.kbType === 'company';
}

// 默认颜色选项
export const COLOR_OPTIONS = [
  { value: 'bg-blue-500', label: '蓝色' },
  { value: 'bg-purple-500', label: '紫色' },
  { value: 'bg-emerald-500', label: '翠绿' },
  { value: 'bg-orange-500', label: '橙色' },
  { value: 'bg-cyan-500', label: '青色' },
  { value: 'bg-rose-500', label: '玫红' },
  { value: 'bg-amber-500', label: '琥珀' },
  { value: 'bg-indigo-500', label: '靛蓝' },
  { value: 'bg-teal-500', label: '蓝绿' },
  { value: 'bg-pink-500', label: '粉色' },
];

// 默认图标选项
export const ICON_OPTIONS = [
  { value: '📚', label: '书籍' },
  { value: '🧪', label: '试管' },
  { value: '📋', label: '表格' },
  { value: '⚙️', label: '齿轮' },
  { value: '📊', label: '图表' },
  { value: '🔬', label: '显微镜' },
  { value: '💊', label: '药丸' },
  { value: '🌿', label: '植物' },
  { value: '📁', label: '文件夹' },
  { value: '📝', label: '笔记' },
];

// 语义类型选项（用于配方生成检索分类）
export const SEMANTIC_TYPE_OPTIONS: { value: SemanticType; label: string; description: string }[] = [
  { value: 'A', label: 'A - 成熟配方', description: '成熟的制剂配方，可直接参考' },
  { value: 'B', label: 'B - 实验数据', description: '配方实验记录和测试数据' },
  { value: 'C', label: 'C - 助剂目录', description: '助剂产品信息和选型指南' },
  { value: 'D', label: 'D - 通用知识', description: '农药基础知识、工艺操作等' },
  { value: 'E', label: 'E - 稳定性数据', description: '稳定性测试报告和数据' },
];

// 重新导出类型
export type { KnowledgeBase, KBType, SemanticType, RecipeFile };
