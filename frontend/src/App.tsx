// src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Layout/Sidebar';
import { Header } from './components/Layout/Header';
import { Dashboard } from './pages/Dashboard';
import { QueryTester } from './pages/QueryTester';
import { AgentMonitorPage } from './pages/AgentMonitorPage';
import { PerformanceMonitor } from './pages/PerformanceMonitor';
import { Settings } from './pages/Settings';
import { useWebSocket } from './hooks/useWebSocket';

function AppShell() {
  // Initialize WebSocket once at app level
  useWebSocket();

  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/"            element={<Dashboard />} />
            <Route path="/query"       element={<QueryTester />} />
            <Route path="/agents"      element={<AgentMonitorPage />} />
            <Route path="/performance" element={<PerformanceMonitor />} />
            <Route path="/settings"    element={<Settings />} />
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
