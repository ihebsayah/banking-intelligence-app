// src/lib/navigation.ts
import React from 'react';
import {
  LayoutDashboard,
  GitBranch,
  Bot,
  BarChart3,
  ShieldAlert,
  Scale,
  FileText,
  Settings2,
  Shield,
  BellRing,
  FileSearch,
  MessageSquare,
  ClipboardCheck,
  Users,
  User,
  Settings,
  type LucideProps,
} from 'lucide-react';
import { PERMISSIONS, type Permission } from './permissions';

export interface NavItem {
  id: string;
  to: string;
  label: string;
  icon: React.ComponentType<LucideProps>;
  category: string;
  requiredPermissions?: Permission | Permission[];
  requiredRoles?: string | string[];
}

export interface NavGroup {
  id: string;
  title?: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'general',
    title: 'General',
    items: [
      { id: 'dashboard', to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, category: 'Navigate' },
      { id: 'branches',  to: '/branches',  label: 'Branches',  icon: GitBranch,       category: 'Navigate' },
    ],
  },
  {
    id: 'workbench',
    title: 'Operational Workbench',
    items: [
      {
        id: 'customer360',
        to: '/workbench/customers',
        label: 'Customer 360',
        icon: Users,
        category: 'Navigate',
        requiredPermissions: PERMISSIONS.CUSTOMER_READ_BASIC,
      },
      {
        id: 'alerts',
        to: '/workbench/alerts',
        label: 'Alert Queue',
        icon: BellRing,
        category: 'Navigate',
        requiredPermissions: [PERMISSIONS.ALERT_READ_ASSIGNED, PERMISSIONS.ALERT_READ],
      },
      {
        id: 'investigations',
        to: '/workbench/investigations',
        label: 'Investigations',
        icon: FileSearch,
        category: 'Navigate',
        requiredPermissions: [PERMISSIONS.INVESTIGATION_READ_OWN, PERMISSIONS.INVESTIGATION_READ],
      },
      {
        id: 'cases',
        to: '/workbench/cases',
        label: 'Cases',
        icon: Scale,
        category: 'Navigate',
        requiredPermissions: [PERMISSIONS.CASE_READ_ASSIGNED, PERMISSIONS.CASE_READ],
      },
      {
        id: 'information-requests',
        to: '/workbench/information-requests',
        label: 'Information Requests',
        icon: MessageSquare,
        category: 'Navigate',
        requiredPermissions: [PERMISSIONS.INFO_REQUEST_READ_ASSIGNED, PERMISSIONS.INFO_REQUEST_READ],
      },
      {
        id: 'approvals',
        to: '/workbench/approvals',
        label: 'Approvals',
        icon: ClipboardCheck,
        category: 'Navigate',
        requiredPermissions: PERMISSIONS.APPROVAL_READ,
      },
    ],
  },
  {
    id: 'analytics',
    title: 'Intelligence & Analytics',
    items: [
      { id: 'assistant', to: '/assistant', label: 'AI Assistant', icon: Bot, category: 'Navigate' },
      { id: 'kpi',       to: '/kpi',       label: 'KPI Analytics', icon: BarChart3, category: 'Navigate' },
      {
        id: 'kpi-governance',
        to: '/kpi-governance',
        label: 'KPI Governance',
        icon: Shield,
        category: 'Navigate',
        requiredPermissions: PERMISSIONS.WORKBENCH_ACCESS,
        requiredRoles: ['analyst', 'manager', 'compliance', 'admin'],
      },
      {
        id: 'risk',
        to: '/risk',
        label: 'Risk Monitor',
        icon: ShieldAlert,
        category: 'Navigate',
        requiredPermissions: PERMISSIONS.WORKBENCH_ACCESS,
        requiredRoles: ['analyst', 'manager', 'compliance', 'admin'],
      },
      {
        id: 'compliance',
        to: '/compliance',
        label: 'Compliance',
        icon: Shield,
        category: 'Navigate',
        requiredPermissions: PERMISSIONS.WORKBENCH_ACCESS,
        requiredRoles: ['compliance', 'manager', 'admin'],
      },
      {
        id: 'reports',
        to: '/reports',
        label: 'Reports',
        icon: FileText,
        category: 'Navigate',
        requiredPermissions: PERMISSIONS.WORKBENCH_ACCESS,
        requiredRoles: ['manager', 'admin'],
      },
    ],
  },
  {
    id: 'admin',
    title: 'Administration',
    items: [
      {
        id: 'outbox-monitor',
        to: '/workbench/admin/outbox',
        label: 'Outbox Monitor',
        icon: FileText,
        category: 'Navigate',
        requiredPermissions: PERMISSIONS.ADMIN_OUTBOX_MONITOR,
        requiredRoles: ['admin'],
      },
      {
        id: 'admin',
        to: '/admin',
        label: 'Admin',
        icon: Settings2,
        category: 'Navigate',
        requiredPermissions: PERMISSIONS.ADMIN_OUTBOX_MONITOR,
        requiredRoles: ['admin'],
      },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export const BOTTOM_NAV_ITEMS: NavItem[] = [
  { id: 'profile',  to: '/profile',  label: 'Profile',  icon: User,     category: 'Navigate' },
  { id: 'settings', to: '/settings', label: 'Settings', icon: Settings, category: 'Navigate' },
];
