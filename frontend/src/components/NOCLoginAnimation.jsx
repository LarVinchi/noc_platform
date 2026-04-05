import React, { useState, useEffect } from 'react';

const NOCLoginAnimation = ({ engineerName, onComplete }) => {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    // Starts the implosion IMMEDIATELY (no pause)
    const t1 = setTimeout(() => setStage(1), 50); 
    
    // The Expansion / Shockwave & Text Reveal
    const t2 = setTimeout(() => setStage(2), 1200);
    
    // Smooth fade out into the application
    const t3 = setTimeout(() => setStage(3), 4000);
    const t4 = setTimeout(() => onComplete(), 4800);

    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4); };
  }, [onComplete]);

  return (
    <div className={`fixed inset-0 z-[100] flex items-center justify-center bg-charcoal-950 overflow-hidden transition-opacity duration-700 ease-in-out ${stage === 3 ? 'opacity-0' : 'opacity-100'}`}>
      
      {/* PHASE 1: IMPLOSION RINGS (Lower Glow) */}
      <div 
        className="absolute rounded-full border-[2px] border-cyan-600/50 border-dashed"
        style={{
          width: stage === 0 ? '120vw' : '0px',
          height: stage === 0 ? '120vw' : '0px',
          opacity: stage >= 2 ? 0 : 1,
          transform: stage === 0 ? 'rotate(0deg)' : 'rotate(180deg)',
          transition: 'all 1.1s cubic-bezier(0.5, 0, 0.2, 1)'
        }}
      />
      <div 
        className="absolute rounded-full border-[6px] border-cyan-500 shadow-[0_0_50px_rgba(6,182,212,0.6)]"
        style={{
          width: stage === 0 ? '80vw' : '0px',
          height: stage === 0 ? '80vw' : '0px',
          opacity: stage >= 2 ? 0 : 1,
          transform: stage === 0 ? 'rotate(0deg)' : 'rotate(-90deg)',
          transition: 'all 1s cubic-bezier(0.6, -0.28, 0.735, 0.045)'
        }}
      />

      {/* PHASE 2: EXPANSION SHOCKWAVE (Softer) */}
      <div 
        className="absolute rounded-full bg-cyan-500 pointer-events-none"
        style={{
          width: stage >= 2 ? '200vw' : '0px',
          height: stage >= 2 ? '200vw' : '0px',
          opacity: stage === 2 ? 0 : 0.4, 
          transition: 'width 0.8s cubic-bezier(0.1, 0.9, 0.2, 1), height 0.8s cubic-bezier(0.1, 0.9, 0.2, 1), opacity 0.6s ease-out'
        }}
      />

      {/* PHASE 3: TEXT REVEAL */}
      <div 
        className="relative z-10 flex flex-col items-center justify-center"
        style={{
          transform: stage >= 2 ? 'scale(1)' : 'scale(0.8)',
          opacity: stage >= 2 ? 1 : 0,
          transition: 'all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)'
        }}
      >
        <h1 className="text-xl md:text-2xl font-bold tracking-[0.4em] text-gray-500 uppercase mb-4">
          Authentication Verified
        </h1>
        
        <div className="flex items-center space-x-4">
          <span className="text-cyan-600 font-mono text-3xl md:text-4xl">&gt;</span>
          <div className="flex items-baseline space-x-3">
            <span className="text-gray-400 italic font-light text-3xl md:text-5xl">
              Welcome back,
            </span>
            <span className="uppercase font-black text-white text-4xl md:text-6xl tracking-wider drop-shadow-[0_0_10px_rgba(6,182,212,0.4)]">
              {engineerName}
            </span>
          </div>
          <span className="w-3 h-10 bg-cyan-500 animate-pulse"></span>
        </div>
      </div>
    </div>
  );
};

export default NOCLoginAnimation;