import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { Activity, ServerOff } from 'lucide-react';

const CrmServices = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch data from your FastAPI backend
    apiClient.get('/customers/')
      .then((response) => {
        setCustomers(response.data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("API Error:", err);
        setError("Failed to connect to the backend API.");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div className="text-cyan-400 animate-pulse flex items-center gap-2"><Activity size={20} /> Loading network data...</div>;
  }

  if (error) {
    return <div className="text-red-400 flex items-center gap-2 bg-red-400/10 p-4 rounded-lg border border-red-400/20"><ServerOff size={20} /> {error}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-semibold text-white">Customer Services</h2>
        <button className="bg-cyan-500 hover:bg-cyan-400 text-charcoal-900 font-bold py-2 px-4 rounded transition-colors shadow-cyan-glow">
          + Provision Service
        </button>
      </div>

      <div className="bg-charcoal-800 rounded-xl border border-charcoal-700 overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-charcoal-900/50 text-gray-400 text-sm uppercase tracking-wider border-b border-charcoal-700">
              <th className="p-4 font-medium">Customer Name</th>
              <th className="p-4 font-medium">Type</th>
              <th className="p-4 font-medium">Service ID</th>
              <th className="p-4 font-medium">Address</th>
              <th className="p-4 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-charcoal-700 text-gray-200">
            {customers.map((cust) => (
              <tr key={cust.customer_id} className="hover:bg-charcoal-700/50 transition-colors">
                <td className="p-4 font-medium text-cyan-400">{cust.customer_name}</td>
                <td className="p-4">
                  <span className={`px-2 py-1 text-xs rounded-full font-medium ${
                    cust.customer_type === 'ISP' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                  }`}>
                    {cust.customer_type}
                  </span>
                </td>
                <td className="p-4 font-mono text-sm text-gray-400">{cust.service_id_code}</td>
                <td className="p-4 text-sm">{cust.address}</td>
                <td className="p-4">
                  <span className="flex items-center gap-2 text-sm text-lime-400">
                    <span className="w-2 h-2 rounded-full bg-lime-500 shadow-lime-glow"></span> Active
                  </span>
                </td>
              </tr>
            ))}
            {customers.length === 0 && (
              <tr>
                <td colSpan="5" className="p-8 text-center text-gray-500">No customers found in database.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default CrmServices;