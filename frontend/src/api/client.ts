// API client for the Financial Planning backend

const API_BASE_URL = 'http://localhost:8000';

export interface ApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
  request_id?: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const defaultOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, { ...defaultOptions, ...options });
      
      if (!response.ok) {
        // Handle error responses
        if (response.headers.get('content-type')?.includes('application/json')) {
          const errorData = await response.json();
          return {
            ok: false,
            error: errorData.error || {
              code: 'HTTP_ERROR',
              message: `HTTP ${response.status}: ${response.statusText}`,
            },
            request_id: errorData.request_id,
          };
        } else {
          return {
            ok: false,
            error: {
              code: 'HTTP_ERROR',
              message: `HTTP ${response.status}: ${response.statusText}`,
            },
          };
        }
      }

      const data = await response.json();
      return {
        ok: true,
        data,
      };
    } catch (error) {
      return {
        ok: false,
        error: {
          code: 'NETWORK_ERROR',
          message: error instanceof Error ? error.message : 'Network request failed',
        },
      };
    }
  }

  // Generic CRUD operations
  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  // System endpoints
  async getHealth() {
    return this.get('/');
  }

  async getApiStatus() {
    return this.get('/api/status');
  }
}

export const apiClient = new ApiClient();
export default apiClient;
