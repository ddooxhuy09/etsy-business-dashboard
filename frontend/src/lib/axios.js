import axios from 'axios';
import { supabase } from './supabase';
import { message } from 'antd';

// Create axios instance with base config
const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '' });

// Add interceptor to include JWT token in all requests
api.interceptors.request.use(
  async (config) => {
    // Retry up to 3 times to get session (in case it's still being persisted)
    let session = null;
    for (let i = 0; i < 3; i++) {
      const { data } = await supabase.auth.getSession();
      if (data?.session?.access_token) {
        session = data.session;
        break;
      }
      if (i < 2) {
        // Wait a bit before retry (only if not last attempt)
        await new Promise(resolve => setTimeout(resolve, 50));
      }
    }
    
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
      console.log('[Axios Request] Token attached for:', config.url);
    } else {
      console.warn('[Axios Request] No session token found for:', config.url);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add interceptor to handle 401 errors (token expired)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const { data: { session } } = await supabase.auth.getSession();
      const hasToken = !!session?.access_token;
      const errorDetail = error.response?.data?.detail || 'Unauthorized';
      const requestUrl = error.config?.url || 'unknown';
      
      // Log detailed error
      console.error('[401 Unauthorized]', {
        url: requestUrl,
        hasToken,
        tokenLength: session?.access_token?.length || 0,
        errorDetail,
        headers: error.config?.headers
      });
      
      // Show detailed error message
      const errorMsg = hasToken 
        ? `Lỗi xác thực (401): Token không hợp lệ hoặc đã hết hạn.\nURL: ${requestUrl}\nChi tiết: ${errorDetail}\n\nVui lòng đăng nhập lại.`
        : `Lỗi xác thực (401): Chưa có token trong session.\nURL: ${requestUrl}\nChi tiết: ${errorDetail}\n\nVui lòng đăng nhập lại.`;
      
      message.error(errorMsg, 5);
      
      // Sign out and redirect
      await supabase.auth.signOut();
      
      // Small delay to show message, then redirect
      setTimeout(() => {
        window.location.href = '/login';
      }, 2000);
    }
    return Promise.reject(error);
  }
);

export default api;
