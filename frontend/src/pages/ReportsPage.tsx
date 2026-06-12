// src/pages/ReportsPage.tsx
import React, { useState } from 'react';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';

export function ReportsPage() {
  const [loading] = useState(false);

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Institutional Financial Reporting"
        subtitle="Generate, schedule, and review automated regulatory reports"
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        <ServiceUnavailable
          serviceName="Reporting & Audit Service"
          missingEndpoint="GET /audit/logs"
          method="GET"
          requiredRole="manager, admin"
        />
      </div>
    </div>
  );
}
