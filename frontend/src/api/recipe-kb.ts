// 类型定义
/**
 * 说明：本项目后端已移除“知识库相关接口”（如 `/api/recipe-kb/*`）。
 *
 * 前端 UI 可能暂时保留，但所有知识库相关 API 调用已被禁用。
 * 若后续需要重新启用，请恢复后端路由并替换此文件实现。
 */

export type DataType = string; // 动态知识库 ID，不再限制为固定类型
export type KBType = 'flat' | 'company'; // 知识库类型
export type SemanticType = 'A' | 'B' | 'C' | 'D' | 'E'; // 语义类型

export interface RecipeFile {
  id: string;
  filename: string;
  file_path: string;
  data_type: DataType;
  company?: string;
  file_size: number;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface Pagination {
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
}

export interface FileListResponse {
  success: boolean;
  data: {
    items: RecipeFile[];
    pagination: Pagination;
  };
}

export interface CompanyListResponse {
  success: boolean;
  data: {
    companies: string[];
  };
}

export interface StatsResponse {
  success: boolean;
  data: {
    total_count: number;
    by_type: Record<string, number>;
    by_company: Record<string, number>;
  };
}

// 知识库相关类型
export interface KnowledgeBase {
  id: string;
  name: string;
  dir_name: string;
  description?: string;
  icon_char: string;
  color_class: string;
  kb_type: KBType;
  semantic_type: SemanticType; // 语义类型: A=成熟配方, B=实验数据, C=助剂目录, D=通用知识/工艺, E=稳定性数据
  sort_order: number;
  created_at?: string;
  updated_at?: string;
  count: number; // 文件数量
}

export interface KnowledgeBaseListResponse {
  success: boolean;
  data: {
    items: KnowledgeBase[];
  };
}

export interface CreateKnowledgeBaseRequest {
  name: string;
  description?: string;
  kb_type: KBType;
  semantic_type: SemanticType; // 语义类型，必填
  icon_char?: string;
  color_class?: string;
}

export interface CreateKnowledgeBaseResponse {
  success: boolean;
  data: {
    id: string;
    name: string;
    dir_name: string;
    description?: string;
    kb_type: KBType;
    semantic_type: SemanticType;
    icon_char: string;
    color_class: string;
    created_at: string;
    message: string;
  };
}

export interface UpdateKnowledgeBaseRequest {
  name?: string;
  description?: string;
  icon_char?: string;
  color_class?: string;
}

const throwDisabled = (): never => {
  throw new Error('后端已移除知识库相关接口，当前不可用（UI 暂保留）。');
};

export const recipeKB = {
  getKnowledgeBases: async (): Promise<KnowledgeBaseListResponse> => throwDisabled(),
  createKnowledgeBase: async (_params: CreateKnowledgeBaseRequest): Promise<CreateKnowledgeBaseResponse> => throwDisabled(),
  getKnowledgeBase: async (_kbId: string): Promise<{ success: boolean; data: KnowledgeBase }> => throwDisabled(),
  updateKnowledgeBase: async (_kbId: string, _params: UpdateKnowledgeBaseRequest): Promise<{ success: boolean; data: KnowledgeBase; message: string }> => throwDisabled(),
  deleteKnowledgeBase: async (_kbId: string): Promise<{ success: boolean; message: string }> => throwDisabled(),
  initDefaultKnowledgeBases: async (): Promise<{ success: boolean; message: string }> => throwDisabled(),

  getFiles: async (_params: {
    data_type: DataType;
    company?: string;
    keyword?: string;
    page?: number;
    page_size?: number;
  }): Promise<FileListResponse> => throwDisabled(),
  getFile: async (_id: string): Promise<{ success: boolean; data: RecipeFile }> => throwDisabled(),
  deleteFile: async (_id: string): Promise<{ success: boolean; message: string }> => throwDisabled(),
  getCompanies: async (): Promise<CompanyListResponse> => throwDisabled(),
  getStats: async (): Promise<StatsResponse> => throwDisabled(),
};
