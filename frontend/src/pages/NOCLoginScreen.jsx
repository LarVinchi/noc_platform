import React, { useState } from 'react';
import NOCInteractiveNode from '../components/NOCInteractiveNode';
import NOCLoginAnimation from '../components/NOCLoginAnimation';

const NOCLoginScreen = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [showAnimation, setShowAnimation] = useState(false);

  const handleLogin = (e) => {
    e.preventDefault();
    if (!username) return;
    
    setIsAuthenticating(true);
    // Simulate network delay for authentication
    setTimeout(() => {
      setIsAuthenticating(false);
      setShowAnimation(true);
    }, 1200);
  };

  if (showAnimation) {
    return <NOCLoginAnimation engineerName={username} onComplete={onLoginSuccess} />;
  }

  return (
    <div className="h-screen w-screen flex bg-charcoal-950 text-gray-200 overflow-hidden">
      
      {/* Left Panel: The Interactive Tracker */}
      <div className="hidden lg:flex w-1/2 bg-charcoal-900 relative items-center justify-center border-r border-charcoal-800 flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-charcoal-800/50 to-transparent"></div>
        <NOCInteractiveNode />
        <div className="mt-12 text-charcoal-500 font-mono text-sm tracking-widest uppercase">
          NOC Core Node Online // System V3.1
        </div>
      </div>

      {/* Right Panel: Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 lg:p-24 relative">
        <div className="w-full max-w-md relative z-10">
          
          <div className="mb-10">
            <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">Access Grid</h1>
            <p className="text-gray-400 font-mono text-sm">Enter operator credentials to proceed.</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="block text-gray-400 text-xs font-bold uppercase tracking-wider mb-2">Operator ID</label>
              <input 
                type="text" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. Mike"
                className="w-full bg-charcoal-900 border border-charcoal-700 text-white px-4 py-3 rounded focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                required
              />
            </div>
            
            <div>
              <label className="block text-gray-400 text-xs font-bold uppercase tracking-wider mb-2">Passcode</label>
              <input 
                type="password" 
                placeholder="••••••••"
                className="w-full bg-charcoal-900 border border-charcoal-700 text-white px-4 py-3 rounded focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                required
              />
            </div>

            <button 
              type="submit" 
              disabled={isAuthenticating}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-3 px-4 rounded transition-colors flex items-center justify-center uppercase tracking-widest mt-4"
            >
              {isAuthenticating ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                'Authenticate'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default NOCLoginScreen;