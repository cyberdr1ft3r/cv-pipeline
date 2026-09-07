'use client';

import { useState } from 'react';
import { useApi } from './useApi';

interface JobCreateResponse {
  job_id: string;
  session_id: string;
  status: string;
}

interface JobActionResponse {
  job_id: string;
  status: string;
}

export function usePipeline() {
  const { get, error, setError } = useApi();
  const [loading, setLoading] = useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

  const createJob = async (
    cvFiles: File[],
    offerFile: File,
    archive: boolean = true
  ): Promise<JobCreateResponse> => {
    setLoading(true);
    try {
      const formData = new FormData();
      
      cvFiles.forEach((file) => {
        formData.append('cv_files', file);
      });
      
      formData.append('job_offer', offerFile);
      formData.append('archive', String(archive));

      const response = await fetch(`${apiBase}/jobs`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        const message = errorData.message || errorData.detail || `Error HTTP ${response.status}`;
        setError(message);
        throw new Error(message);
      }

      return await response.json();
    } finally {
      setLoading(false);
    }
  };

  const createJobWithExistingCVs = async (
    sessionId: string,
    offerFile: File
  ): Promise<JobCreateResponse> => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('job_offer', offerFile);
      formData.append('reuse_session_id', sessionId);

      const response = await fetch(`${apiBase}/jobs`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        const message = errorData.message || errorData.detail || `Error HTTP ${response.status}`;
        setError(message);
        throw new Error(message);
      }

      return await response.json();
    } finally {
      setLoading(false);
    }
  };

  const createJobOfferOnly = async (
    offerFile: File
  ): Promise<JobCreateResponse> => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('job_offer', offerFile);
      formData.append('offer_only', 'true');

      const response = await fetch(`${apiBase}/jobs`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        const message = errorData.message || errorData.detail || `Error HTTP ${response.status}`;
        setError(message);
        throw new Error(message);
      }

      return await response.json();
    } finally {
      setLoading(false);
    }
  };

  const getJobStatus = async (jobId: string) => {
    return get(`/jobs/${jobId}`);
  };

  const getJobResults = async (jobId: string) => {
    return get(`/jobs/${jobId}/results`);
  };

  const getMatchingResults = async (jobId: string) => {
    return get(`/jobs/${jobId}/matching`);
  };

  const getFinalResults = async (jobId: string) => {
    return get(`/jobs/${jobId}/final`);
  };

  const getSessions = async () => {
    return get('/sessions');
  };

  const runFinalPhase = async (jobId: string, testsFile?: File | null): Promise<JobActionResponse> => {
    const requestInit: RequestInit = { method: 'POST', credentials: 'include' };

    if (testsFile) {
      const formData = new FormData();
      formData.append('tests_file', testsFile, testsFile.name);
      requestInit.body = formData;
    }

    const response = await fetch(`${apiBase}/jobs/${jobId}/final`, requestInit);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      const message = errorData.message || errorData.detail || `Error HTTP ${response.status}`;
      setError(message);
      throw new Error(message);
    }

    return await response.json();
  };

  const runFormatPhase = async (
    jobId: string,
    template: string = 'classic',
    limit?: number | null,
  ): Promise<JobActionResponse> => {
    const formData = new FormData();
    formData.append('template', template);
    if (typeof limit === 'number') {
      formData.append('limit', String(limit));
    }

    const response = await fetch(`${apiBase}/jobs/${jobId}/format`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      const message = errorData.message || errorData.detail || `Error HTTP ${response.status}`;
      setError(message);
      throw new Error(message);
    }

    return await response.json();
  };

  const getArtifactDownloadUrl = (jobId: string, artifact: string) => {
    return `${apiBase}/jobs/${jobId}/download/${artifact}`;
  };

  const getJobProgress = async (jobId: string) => {
    const response = await fetch(`${apiBase}/jobs/${jobId}/progress`);
    if (!response.ok) {
      throw new Error(`Error HTTP ${response.status}`);
    }
    return response.json();
  };

  return {
    createJob,
    createJobWithExistingCVs,
    createJobOfferOnly,
    getJobStatus,
    getJobResults,
    getMatchingResults,
    getFinalResults,
    getSessions,
    runFinalPhase,
    runFormatPhase,
    getArtifactDownloadUrl,
    getJobProgress,
    loading,
    error,
    setError,
  };
}

