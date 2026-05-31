// src/stores/uiStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  theme: 'dark' | 'light';
  sidebarCollapsed: boolean;
  notifications: Notification[];
  autoRefreshInterval: number; // minutes
}

interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

interface UIActions {
  toggleTheme: () => void;
  toggleSidebar: () => void;
  addNotification: (n: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  markNotificationRead: (id: string) => void;
  clearNotifications: () => void;
  setAutoRefreshInterval: (minutes: number) => void;
}

export const useUIStore = create<UIState & UIActions>()(
  persist(
    (set) => ({
      theme: 'dark',
      sidebarCollapsed: false,
      notifications: [],
      autoRefreshInterval: 60,
      toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      addNotification: (n) => set((s) => ({
        notifications: [{
          ...n,
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          read: false,
        }, ...s.notifications].slice(0, 50),
      })),
      markNotificationRead: (id) => set((s) => ({
        notifications: s.notifications.map((n) => n.id === id ? { ...n, read: true } : n),
      })),
      clearNotifications: () => set({ notifications: [] }),
      setAutoRefreshInterval: (autoRefreshInterval) => set({ autoRefreshInterval }),
    }),
    { name: 'banking-ui-prefs', partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed, autoRefreshInterval: s.autoRefreshInterval }) }
  )
);
