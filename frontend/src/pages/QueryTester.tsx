// src/pages/QueryTester.tsx
import React from 'react';
import { QueryBuilder } from '../components/QueryBuilder';
import { PipelineVisualizer } from '../components/PipelineVisualizer';
import { ResultsViewer } from '../components/ResultsViewer';
import { PerformanceChart } from '../components/PerformanceChart';

export function QueryTester() {
  return (
    <div className="p-6 animate-fade-in">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left column: Query Builder + Pipeline */}
        <div className="xl:col-span-1 flex flex-col gap-6">
          <QueryBuilder />
          <PipelineVisualizer />
          <PerformanceChart />
        </div>

        {/* Right column: Results */}
        <div className="xl:col-span-2">
          <ResultsViewer />
        </div>
      </div>
    </div>
  );
}
