// src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { Sidebar } from './components/Layout/Sidebar';
import { Header } from './components/Layout/Header';
import { BankingSidebar } from './components/Layout/BankingSidebar';
import { TopBar } from './components/Layout/TopBar';
import { CommandPalette } from './components/CommandPalette';
import { AiAssistantPanel } from './components/AiAssistantPanel';
import { Dashboard } from './pages/Dashboard';
import { QueryTester } from './pages/QueryTester';
import { AgentMonitorPage } from './pages/AgentMonitorPage';
import { PerformanceMonitor } from './pages/PerformanceMonitor';
import { Settings } from './pages/Settings';
import { LoginPage } from './components/auth/LoginPage';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { PERMISSIONS } from './lib/permissions';
import { BankingDashboard } from './pages/BankingDashboard';
import { Branches } from './pages/Branches';
import { Assistant } from './pages/Assistant';
import { DebugPage } from './pages/DebugPage';
import { KpiPage } from './pages/KpiPage';
import { KpiGovernancePage } from './pages/KpiGovernancePage';
import { RiskPage } from './pages/RiskPage';
import { CompliancePage } from './pages/CompliancePage';
import { AlertQueuePage } from './components/alerts/AlertQueuePage';
import { AlertDetailPage } from './components/alerts/AlertDetailPage';
import { InvestigationQueuePage } from './components/investigations/InvestigationQueuePage';
import { InvestigationDetailPage } from './components/investigations/InvestigationDetailPage';
import { CaseQueuePage } from './components/cases/CaseQueuePage';
import { CaseDetailPage } from './components/cases/CaseDetailPage';
import { IRInboxPage } from './components/informationRequests/IRInboxPage';
import { ApprovalQueuePage } from './components/approvals/ApprovalQueuePage';
import { NotificationsPanel } from './components/notifications/NotificationsPanel';
import { OutboxMonitor } from './components/admin/OutboxMonitor';
import { ReportsPage } from './pages/ReportsPage';
import { Customer360Page } from './components/customers/Customer360Page';
import { CustomerSearchPage } from './components/customers/CustomerSearchPage';
import { AdminPage } from './pages/AdminPage';
import { ProfilePage } from './pages/ProfilePage';
import { UnauthorizedPage } from './pages/UnauthorizedPage';
import { useWebSocket } from './hooks/useWebSocket';

function AppContent() {
  useWebSocket();
  const location = useLocation();
  const isDevRoute = location.pathname.startsWith('/dev');
  const isAuthRoute = location.pathname === '/login' || location.pathname === '/unauthorized';

  if (isAuthRoute) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
      </Routes>
    );
  }

  if (isDevRoute) {
    return (
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-auto bg-[#0F172A] p-6">
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

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
      <BankingSidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/"               element={<ProtectedRoute><BankingDashboard /></ProtectedRoute>} />
            <Route path="/dashboard"       element={<ProtectedRoute><BankingDashboard /></ProtectedRoute>} />
            <Route path="/branches"        element={<ProtectedRoute><Branches /></ProtectedRoute>} />
            <Route path="/assistant"       element={<ProtectedRoute><Assistant /></ProtectedRoute>} />
            <Route path="/kpi"             element={<ProtectedRoute><KpiPage /></ProtectedRoute>} />
            <Route path="/kpi-governance"  element={<ProtectedRoute requiredRole={['analyst', 'manager', 'compliance', 'admin']} requiredPermission="workbench:access"><KpiGovernancePage /></ProtectedRoute>} />
            <Route path="/risk"            element={<ProtectedRoute requiredRole={['analyst', 'manager', 'compliance', 'admin']} requiredPermission="workbench:access"><RiskPage /></ProtectedRoute>} />
            <Route path="/workbench/alerts"        element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission={[PERMISSIONS.ALERT_READ_ASSIGNED, PERMISSIONS.ALERT_READ]}><AlertQueuePage /></ProtectedRoute>} />
            <Route path="/workbench/alerts/:alertId" element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission={[PERMISSIONS.ALERT_READ_ASSIGNED, PERMISSIONS.ALERT_READ]}><AlertDetailPage /></ProtectedRoute>} />
            <Route path="/workbench/investigations" element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission={[PERMISSIONS.INVESTIGATION_READ_OWN, PERMISSIONS.INVESTIGATION_READ]}><InvestigationQueuePage /></ProtectedRoute>} />
            <Route path="/workbench/investigations/:investigationId" element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission={[PERMISSIONS.INVESTIGATION_READ_OWN, PERMISSIONS.INVESTIGATION_READ]}><InvestigationDetailPage /></ProtectedRoute>} />
            <Route path="/workbench/cases" element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission={[PERMISSIONS.CASE_READ_ASSIGNED, PERMISSIONS.CASE_READ]}><CaseQueuePage /></ProtectedRoute>} />
            <Route path="/workbench/cases/:caseId" element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission={[PERMISSIONS.CASE_READ_ASSIGNED, PERMISSIONS.CASE_READ]}><CaseDetailPage /></ProtectedRoute>} />
            <Route path="/workbench/information-requests" element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission={[PERMISSIONS.INFO_REQUEST_READ_ASSIGNED, PERMISSIONS.INFO_REQUEST_READ]}><IRInboxPage /></ProtectedRoute>} />
            <Route path="/workbench/approvals" element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission="approval:read"><ApprovalQueuePage /></ProtectedRoute>} />
            <Route path="/workbench/customers" element={<ProtectedRoute requiredPermission="customer:read_basic"><CustomerSearchPage /></ProtectedRoute>} />
            <Route path="/workbench/customers/:customerId" element={<ProtectedRoute requiredPermission="customer:read_basic"><Customer360Page /></ProtectedRoute>} />
            <Route path="/notifications" element={<ProtectedRoute requiredRole={['analyst', 'compliance', 'admin']} requiredPermission="notification:read"><NotificationsPanel /></ProtectedRoute>} />
            <Route path="/workbench/admin/outbox" element={<ProtectedRoute requiredRole="admin" requiredPermission="admin:outbox_monitor"><OutboxMonitor /></ProtectedRoute>} />
            <Route path="/compliance"      element={<ProtectedRoute requiredRole={['compliance', 'manager', 'admin']} requiredPermission="workbench:access"><CompliancePage /></ProtectedRoute>} />
            <Route path="/reports"         element={<ProtectedRoute requiredRole={['manager', 'admin']} requiredPermission="workbench:access"><ReportsPage /></ProtectedRoute>} />
            <Route path="/admin"           element={<ProtectedRoute requiredRole="admin"><AdminPage /></ProtectedRoute>} />
            <Route path="/profile"         element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
            <Route path="/settings"        element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          </Routes>
        </main>
      </div>
      <CommandPalette />
      <AiAssistantPanel />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}
