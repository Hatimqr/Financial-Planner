// Custom hooks for API data fetching

import { useState, useEffect, useCallback } from 'react';
import type { ApiResponse } from '../api/client';

// Generic hook for API calls
export function useApi<T>(
  apiCall: () => Promise<ApiResponse<T>>,
  dependencies: any[] = []
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiCall();
      if (response.ok && response.data) {
        setData(response.data);
      } else {
        setError(response.error?.message || 'Unknown error occurred');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setLoading(false);
    }
  }, dependencies);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    loading,
    error,
    refetch: fetchData,
  };
}

// Hook for API calls with manual trigger
export function useApiMutation<T, P = any>() {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(async (
    apiCall: (params: P) => Promise<ApiResponse<T>>,
    params: P
  ) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiCall(params);
      if (response.ok && response.data) {
        setData(response.data);
        return { success: true, data: response.data };
      } else {
        const errorMessage = response.error?.message || 'Unknown error occurred';
        setError(errorMessage);
        return { success: false, error: errorMessage };
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Network error';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    data,
    loading,
    error,
    mutate,
    reset: () => {
      setData(null);
      setError(null);
    },
  };
}

// Utility hook for form state management
export function useFormState<T>(initialState: T) {
  const [formData, setFormData] = useState<T>(initialState);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});

  const updateField = useCallback(<K extends keyof T>(
    field: K,
    value: T[K]
  ) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when field is updated
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  }, [errors]);

  const setFieldError = useCallback(<K extends keyof T>(
    field: K,
    error: string
  ) => {
    setErrors(prev => ({ ...prev, [field]: error }));
  }, []);

  const reset = useCallback(() => {
    setFormData(initialState);
    setErrors({});
  }, [initialState]);

  const hasErrors = Object.values(errors).some(error => error);

  return {
    formData,
    errors,
    hasErrors,
    updateField,
    setFieldError,
    setFormData,
    setErrors,
    reset,
  };
}
