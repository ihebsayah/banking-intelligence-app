// src/pages/CompliancePage.tsx
import React, { useEffect, useState } from 'react';
import { complianceApi } from '../api/complianceApi';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import type { ComplianceReportResponse } from '../types/api';

export function CompliancePage() {
  const [report, setReport] = useState<ComplianceReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  const fetchCompliance = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      const data = await complianceApi.getComplianceReport();
      setReport(data);
    } catch (err) {
      console.error('Failed to fetch compliance report:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompliance();
  }, []);

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Regulatory Compliance Control"
        subtitle="GDPR PII tracking, AML monitoring flags, and compliance rule assertions"
        onRefresh={fetchCompliance}
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <ServiceUnavailable
            serviceName="GDPR & AML Compliance Agent"
            missingEndpoint="GET /compliance/report"
            method="GET"
            requiredRole="compliance, manager, admin"
          />
        ) : loading ? (
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066CC]"></div>
          </div>
        ) : (
          <div className="text-slate-400 text-sm text-center">
            Compliance Violations: {report?.active_violations_count}
          </div>
        )}
      </div>
    </div>
  );
}
