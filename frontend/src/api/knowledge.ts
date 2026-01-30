/**
 * 说明：本项目后端已移除“知识库相关接口”（如 `/api/knowledge/*`）。
 *
 * 前端 UI 可能暂时保留，但所有知识库相关 API 调用已被禁用。
 */

import type { DocumentListResponse, DocumentInfo, DeleteDocumentResponse } from '../types';

export const knowledgeApi = {
  list: async (_status?: string, _limit = 100, _offset = 0): Promise<DocumentListResponse> => {
    throw new Error('后端已移除知识库相关接口，当前不可用（UI 暂保留）。');
  },

  get: async (_documentId: string): Promise<DocumentInfo> => {
    throw new Error('后端已移除知识库相关接口，当前不可用（UI 暂保留）。');
  },

  delete: async (_documentId: string): Promise<DeleteDocumentResponse> => {
    throw new Error('后端已移除知识库相关接口，当前不可用（UI 暂保留）。');
  },
};
