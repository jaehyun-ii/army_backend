'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';

interface AuthContextType {
  isAuthenticated: boolean;
  token: string | null;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const router = useRouter();

  useEffect(() => {
    // 초기 로드 시 localStorage에서 토큰 확인
    const storedToken = localStorage.getItem('access_token');
    if (storedToken) {
      setToken(storedToken);
      setIsAuthenticated(true);
      // localStorage에만 있고 쿠키에 없는 경우 쿠키에도 저장
      document.cookie = `access_token=${storedToken}; path=/; max-age=86400`;
    }
  }, []);

  const login = (newToken: string) => {
    localStorage.setItem('access_token', newToken);
    // 쿠키에도 저장 (미들웨어에서 사용)
    document.cookie = `access_token=${newToken}; path=/; max-age=86400`; // 24시간
    setToken(newToken);
    setIsAuthenticated(true);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    // 쿠키도 삭제
    document.cookie = 'access_token=; path=/; max-age=0';
    setToken(null);
    setIsAuthenticated(false);
    router.push('/auth/login');
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
