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
import { KpiPage } from './pages/KpiPage';
import { RiskPage } from './pages/RiskPage';
import { CompliancePage } from './pages/CompliancePage';
import { ReportsPage } from './pages/ReportsPage';
import { AdminPage } from './pages/AdminPage';
import { ProfilePage } from './pages/ProfilePage';
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

  const isDevRoute = path === '/dev' || path.startsWith('/dev/');

  if (isDevRoute) {
    // Developer Layout - Gated to admin users only
    return (
      <div className="flex h-screen overflow-hidden bg-bg-primary">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/dev"            element={<ProtectedRoute requiredRole="admin"><Dashboard /></ProtectedRoute>} />
              <Route path="/dev/query"       element={<ProtectedRoute requiredRole="admin"><QueryTester /></ProtectedRoute>} />
              <Route path="/dev/agents"      element={<ProtectedRoute requiredRole="admin"><AgentMonitorPage /></ProtectedRoute>} />
              <Route path="/dev/performance" element={<ProtectedRoute requiredRole="admin"><PerformanceMonitor /></ProtectedRoute>} />
              <Route path="/dev/settings"    element={<ProtectedRoute requiredRole="admin"><Settings /></ProtectedRoute>} />
              <Route path="/dev/debug"       element={<ProtectedRoute requiredRole="admin"><DebugPage /></ProtectedRoute>} />
            </Routes>
          </main>
        </div>
      </div>
    );
  }

  // Business Banking Portal Layout
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
            <Route path="/kpi"       element={<ProtectedRoute><KpiPage /></ProtectedRoute>} />
            <Route path="/risk"       element={<ProtectedRoute requiredRole={['analyst', 'manager', 'compliance', 'admin']}><RiskPage /></ProtectedRoute>} />
            <Route path="/compliance" element={<ProtectedRoute requiredRole={['compliance', 'manager', 'admin']}><CompliancePage /></ProtectedRoute>} />
            <Route path="/reports"    element={<ProtectedRoute requiredRole={['manager', 'admin']}><ReportsPage /></ProtectedRoute>} />
            <Route path="/admin"      element={<ProtectedRoute requiredRole="admin"><AdminPage /></ProtectedRoute>} />
            <Route path="/profile"    element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
            <Route path="/settings"  element={<ProtectedRoute><Settings /></ProtectedRoute>} />
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
