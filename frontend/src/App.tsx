// src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { Sidebar } from './components/Layout/Sidebar';
import { Header } from './components/Layout/Header';
import { BankingSidebar } from './components/Layout/BankingSidebar';
import { Dashboard } from './pages/Dashboard';
import { QueryTester } from './pages/QueryTester';
import { AgentMonitorPage } from './pages/AgentMonitorPage';
import { PerformanceMonitor } from './pages/PerformanceMonitor';
import { Settings } from './pages/Settings';
import { LoginPage } from './components/auth/LoginPage';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { BankingDashboard } from './pages/BankingDashboard';
import { Branches } from './pages/Branches';
import { Assistant } from './pages/Assistant';
import { DebugPage } from './pages/DebugPage';
import { useWebSocket } from './hooks/useWebSocket';

function AppShell() {
  // Initialize WebSocket once at app level
  useWebSocket();
  const location = useLocation();
  const path = location.pathname;

  if (path === '/login') {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    );
  }

  const isBusinessRoute = ['/', '/dashboard', '/branches', '/assistant'].includes(path) || (path === '/settings' && localStorage.getItem('auth_token'));

  if (isBusinessRoute) {
    return (
      <div className="flex h-screen overflow-hidden bg-[#040711]">
        <BankingSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/" element={<ProtectedRoute><BankingDashboard /></ProtectedRoute>} />
              <Route path="/dashboard" element={<ProtectedRoute><BankingDashboard /></ProtectedRoute>} />
              <Route path="/branches"  element={<ProtectedRoute><Branches /></ProtectedRoute>} />
              <Route path="/assistant" element={<ProtectedRoute><Assistant /></ProtectedRoute>} />
              <Route path="/settings"  element={<ProtectedRoute><Settings /></ProtectedRoute>} />
            </Routes>
          </main>
        </div>
      </div>
    );
  }

  // Developer Layout
  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/dev"            element={<Dashboard />} />
            <Route path="/dev/query"       element={<QueryTester />} />
            <Route path="/dev/agents"      element={<AgentMonitorPage />} />
            <Route path="/dev/performance" element={<PerformanceMonitor />} />
            <Route path="/dev/settings"    element={<Settings />} />
            <Route path="/dev/debug"       element={<DebugPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
