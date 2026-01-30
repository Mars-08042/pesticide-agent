import { fetchApi } from './config';
import { SessionListResponse, SessionCreate, SessionCreateResponse, SessionUpdate, SessionInfo, DeleteResponse } from '../types';

export const sessionApi = {
  list: (limit = 50, offset = 0) =>
    fetchApi<SessionListResponse>(`/api/session/list?limit=${limit}&offset=${offset}`),

  create: (data: SessionCreate = {}) =>
    fetchApi<SessionCreateResponse>('/api/session/create', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (sessionId: string) =>
    fetchApi<SessionInfo>(`/api/session/${sessionId}`),

  update: (sessionId: string, data: SessionUpdate) =>
    fetchApi<SessionInfo>(`/api/session/${sessionId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (sessionId: string) =>
    fetchApi<DeleteResponse>(`/api/session/${sessionId}`, {
      method: 'DELETE',
    }),

  search: (keyword: string, limit = 50, offset = 0) =>
    fetchApi<SessionListResponse>(`/api/session/search?keyword=${encodeURIComponent(keyword)}&limit=${limit}&offset=${offset}`),
};
