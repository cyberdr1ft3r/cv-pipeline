'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export function useApi() {
  const [error, setError] = useState<string | null>(null);

  const request = async (
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    endpoint: string,
    data?: any
  ) => {
    try {
      setError(null);
      const url = `${API_BASE}${endpoint}`;
      
      const options: RequestInit = {
        method,
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
      };

      if (data) {
        options.body = JSON.stringify(data);
      }

      const response = await fetch(url, options);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        setError(errorData.message || errorData.detail || `Error: ${response.status}`);
        throw new Error(errorData.message || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    }
  };

  return {
    get: (endpoint: string) => request('GET', endpoint),
    post: (endpoint: string, data?: any) => request('POST', endpoint, data),
    put: (endpoint: string, data?: any) => request('PUT', endpoint, data),
    delete: (endpoint: string) => request('DELETE', endpoint),
    error,
    setError,
  };
}

