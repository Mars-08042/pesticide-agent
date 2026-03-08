const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
export const API_BASE_URL = rawApiBaseUrl
  ? rawApiBaseUrl.replace(/\/+$/, '')
  : 'http://localhost:8000';

export function formatApiError(errorData: any): string {
  const detail = errorData?.detail;
  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item: any) => {
        const loc = Array.isArray(item?.loc) ? item.loc.join('.') : '';
        const msg = typeof item?.msg === 'string' ? item.msg : JSON.stringify(item);
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join('; ');
  }

  if (detail != null) return typeof detail === 'object' ? JSON.stringify(detail) : String(detail);
  if (errorData?.message) return String(errorData.message);
  return 'Unknown error';
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorData: any = null;
    try {
      errorData = await response.clone().json();
    } catch {
      // ignore
    }

    let errorText = '';
    if (!errorData) {
      try {
        errorText = await response.text();
      } catch {
        // ignore
      }
    }

    const message = errorData ? formatApiError(errorData) : (errorText || `Request failed with status ${response.status}`);
    throw new Error(message);
  }

  return response.json();
}
