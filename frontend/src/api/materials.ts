import { fetchApi } from './config';
import {
  AdjuvantListResponse,
  AdjuvantOptionsResponse,
  AdjuvantPayload,
  AdjuvantRecord,
  DeleteResponse,
  PesticideListResponse,
  PesticideOptionsResponse,
  PesticidePayload,
  PesticideRecord,
} from '../types';

type QueryValue = string | number | undefined | null;

function buildQuery(params: Record<string, QueryValue>) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    searchParams.set(key, String(value));
  });

  const query = searchParams.toString();
  return query ? `?${query}` : '';
}

export const materialsApi = {
  pesticides: {
    list: (params: {
      keyword?: string;
      chemical_class?: string;
      page?: number;
      page_size?: number;
    }) =>
      fetchApi<PesticideListResponse>(`/api/materials/pesticides${buildQuery(params)}`),

    options: () =>
      fetchApi<PesticideOptionsResponse>('/api/materials/pesticides/options'),

    get: (id: number) =>
      fetchApi<PesticideRecord>(`/api/materials/pesticides/${id}`),

    create: (data: PesticidePayload) =>
      fetchApi<PesticideRecord>('/api/materials/pesticides', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    update: (id: number, data: PesticidePayload) =>
      fetchApi<PesticideRecord>(`/api/materials/pesticides/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    delete: (id: number) =>
      fetchApi<DeleteResponse>(`/api/materials/pesticides/${id}`, {
        method: 'DELETE',
      }),
  },

  adjuvants: {
    list: (params: {
      keyword?: string;
      formulation_type?: string;
      function?: string;
      company?: string;
      page?: number;
      page_size?: number;
    }) =>
      fetchApi<AdjuvantListResponse>(`/api/materials/adjuvants${buildQuery(params)}`),

    options: () =>
      fetchApi<AdjuvantOptionsResponse>('/api/materials/adjuvants/options'),

    get: (id: number) =>
      fetchApi<AdjuvantRecord>(`/api/materials/adjuvants/${id}`),

    create: (data: AdjuvantPayload) =>
      fetchApi<AdjuvantRecord>('/api/materials/adjuvants', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    update: (id: number, data: AdjuvantPayload) =>
      fetchApi<AdjuvantRecord>(`/api/materials/adjuvants/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    delete: (id: number) =>
      fetchApi<DeleteResponse>(`/api/materials/adjuvants/${id}`, {
        method: 'DELETE',
      }),
  },
};
