import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, UserCheck, AlertCircle, Loader2, X, ArrowRight } from 'lucide-react';
import {
  customer360Api,
  CustomerSearchResultItem,
  parseCustomer360Error,
} from '../../api/customer360Api';

export const CustomerSearchPage: React.FC = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState<string>('');
  const [debouncedQuery, setDebouncedQuery] = useState<string>('');
  const [results, setResults] = useState<CustomerSearchResultItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState<boolean>(false);

  // Debounce input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Execute search when debounced query changes
  useEffect(() => {
    if (debouncedQuery.length < 2) {
      setResults([]);
      setTotal(0);
      setError(null);
      setLoading(false);
      setHasSearched(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);
    setHasSearched(true);

    customer360Api
      .searchCustomers({ q: debouncedQuery, limit: 20, offset: 0 })
      .then((res) => {
        if (isMounted) {
          setResults(res.items);
          setTotal(res.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          const parsed = parseCustomer360Error(err);
          setError(parsed.message);
          setResults([]);
          setTotal(0);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [debouncedQuery]);

  const handleClear = () => {
    setQuery('');
    setDebouncedQuery('');
    setResults([]);
    setTotal(0);
    setError(null);
    setLoading(false);
    setHasSearched(false);
  };

  const handleSelectCustomer = (customerId: string) => {
    navigate(`/workbench/customers/${encodeURIComponent(customerId)}`);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Customer 360</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Search for an authorized customer to open their consolidated profile.
        </p>
      </div>

      {/* Search Input Box */}
      <div className="relative max-w-2xl">
        <div className="relative flex items-center">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            id="search-input"
            data-testid="customer-search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by customer ID or name (minimum 2 characters)..."
            className="w-full pl-11 pr-10 py-2.5 text-sm bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500"
            autoComplete="off"
          />
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-full"
              aria-label="Clear search"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        {query.trim().length > 0 && query.trim().length < 2 && (
          <p className="text-xs text-amber-600 dark:text-amber-400 mt-1.5 ml-1">
            Please enter at least 2 characters to search.
          </p>
        )}
      </div>

      {/* States & Results */}
      <div className="space-y-4">
        {loading && (
          <div className="flex items-center space-x-2 py-8 justify-center text-slate-500 dark:text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            <span className="text-sm">Searching authorized customers...</span>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 flex items-start space-x-3 text-red-800 dark:text-red-200">
            <AlertCircle className="w-5 h-5 mt-0.5 shrink-0 text-red-600 dark:text-red-400" />
            <div className="text-sm">
              <span className="font-semibold">Search Error: </span>
              {error}
            </div>
          </div>
        )}

        {!loading && !error && hasSearched && results.length === 0 && (
          <div className="p-8 text-center bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg">
            <UserCheck className="w-10 h-10 mx-auto text-slate-400 mb-2" />
            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
              No matching customers found
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-md mx-auto">
              No authorized customer matched "{debouncedQuery}". Verify the customer ID or name, or check your scope permissions.
            </p>
          </div>
        )}

        {!loading && !error && !hasSearched && (
          <div className="p-8 text-center bg-slate-50 dark:bg-slate-900/50 border border-dashed border-slate-300 dark:border-slate-700 rounded-lg">
            <Search className="w-10 h-10 mx-auto text-slate-400 mb-2" />
            <h3 className="text-base font-semibold text-slate-700 dark:text-slate-300">
              Find a Customer
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-md mx-auto">
              Enter a customer ID (e.g. CUST_00001) or name to search across your authorized organizational scope.
            </p>
          </div>
        )}

        {!loading && !error && results.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 px-1">
              <span>
                Showing {results.length} of {total} customer{total !== 1 ? 's' : ''}
              </span>
            </div>

            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg divide-y divide-slate-100 dark:divide-slate-700/50 shadow-sm overflow-hidden">
              {results.map((item) => (
                <div
                  key={item.customer_id}
                  className="p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
                  data-testid={`customer-result-${item.customer_id}`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-slate-900 dark:text-white text-base">
                        {item.name}
                      </span>
                      {item.segment && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                          {item.segment}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                      ID: {item.customer_id}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleSelectCustomer(item.customer_id)}
                    className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 bg-blue-50 dark:bg-blue-950/50 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-md transition-colors"
                    data-testid={`open-customer-360-${item.customer_id}`}
                  >
                    <span>Open Customer 360</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
