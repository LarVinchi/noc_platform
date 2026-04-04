import React from 'react'
import NocAppShell from './components/NocAppShell'

function App() {
  return (
    <NocAppShell>
      {/* This is a temporary placeholder for our Dashboard page */}
      <div className="grid grid-cols-3 gap-6">
        <div className="bg-charcoal-800 p-6 rounded-xl border border-charcoal-700">
          <h3 className="text-gray-400 text-sm mb-2">Active Services</h3>
          <p className="text-3xl font-bold text-white">1,204</p>
        </div>
        <div className="bg-charcoal-800 p-6 rounded-xl border border-charcoal-700">
          <h3 className="text-gray-400 text-sm mb-2">Open Incidents</h3>
          <p className="text-3xl font-bold text-cyan-400">3</p>
        </div>
        <div className="bg-charcoal-800 p-6 rounded-xl border border-charcoal-700">
          <h3 className="text-gray-400 text-sm mb-2">Network Health</h3>
          <p className="text-3xl font-bold text-lime-400">99.9%</p>
        </div>
      </div>
    </NocAppShell>
  )
}

export default App