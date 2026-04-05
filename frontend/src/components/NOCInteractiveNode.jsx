import React, { useState, useEffect, useRef } from 'react';

const NOCInteractiveNode = () => {
  const containerRef = useRef(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (event) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      // Calculate mouse position relative to the center (-1 to 1 range)
      const x = (event.clientX - rect.left - rect.width / 2) / (rect.width / 2);
      const y = (event.clientY - rect.top - rect.height / 2) / (rect.height / 2);
      setMousePos({ x, y });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Multiply by pixels to define how far the core "looks"
  const lookX = mousePos.x * 15;
  const lookY = mousePos.y * 15;

  return (
    <div ref={containerRef} className="relative w-64 h-64 flex items-center justify-center">
      {/* Outer Radar Ring */}
      <div className="absolute inset-0 border border-cyan-900/40 rounded-full border-dashed animate-[spin_20s_linear_infinite]" />
      <div className="absolute inset-4 border border-charcoal-700 rounded-full" />
      
      {/* Tracking Core Housing */}
      <div className="absolute w-32 h-32 border-2 border-charcoal-600 bg-charcoal-900 rounded-2xl flex items-center justify-center shadow-lg transform transition-transform duration-100 ease-out"
           style={{ transform: `translate(${mousePos.x * 5}px, ${mousePos.y * 5}px)` }}>
        
        {/* The Tracking 'Eye' */}
        <div className="w-12 h-12 bg-cyan-600 rounded-full shadow-[0_0_15px_rgba(6,182,212,0.4)] flex items-center justify-center transition-transform duration-75 ease-out"
             style={{ transform: `translate(${lookX}px, ${lookY}px)` }}>
          <div className="w-3 h-3 bg-white rounded-full animate-pulse" />
        </div>
        
      </div>
      
      {/* Decorative Grid Lines */}
      <div className="absolute w-full h-[1px] bg-cyan-900/30" />
      <div className="absolute h-full w-[1px] bg-cyan-900/30" />
    </div>
  );
};

export default NOCInteractiveNode;