import axios from 'axios';
import { useAuth } from '@clerk/clerk-react';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    headers: { 'Content-Type': 'application/json' },
});

// Hook that returns an api instance with the Clerk JWT attached to every request
export function useApi() {
    const { getToken } = useAuth();

    api.interceptors.request.use(async (config) => {
        const token = await getToken();
        if (token) config.headers.Authorization = `Bearer ${token}`;
        return config;
    });

    return api;
}

export default api;
