import React, { useState, useEffect } from 'react';
import { Terminal } from 'lucide-react';

const NOCGreeting = ({ engineerName, onComplete }) => {
  const [text, setText] = useState('');
  const [isFading, setIsFading] = useState(false);
  
  const fullText = `[AUTH SUCCESS] Welcome back, Engineer ${engineerName}... Securing FTTH Provisioning Session...`;

  useEffect(() => {
    let currentIndex = 0;
    const typingInterval = setInterval(() => {
      setText(fullText.slice(0, currentIndex + 1));
      currentIndex++;
      
      if (currentIndex === fullText.length) {
        clearInterval(typingInterval);
        // Wait 1.5 seconds, trigger fade out, then unmount
        setTimeout(() => setIsFading(true), 1500);
        setTimeout(() => onComplete(), 2000); 
      }
    }, 40); // Typing speed

    return () => clearInterval(typingInterval);
  }, [engineerName, fullText, onComplete]);

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-charcoal-950 transition-opacity duration-500 ease-in-out ${isFading ? 'opacity-0' : 'opacity-100'}`}>
      <div className="flex flex-col items-center">
        <div className="flex items-center space-x-4 text-cyan-400 font-mono text-xl sm:text-2xl shadow-cyan-glow p-6 rounded-lg border border-cyan-500/20 bg-charcoal-900/50">
          <Terminal className="animate-pulse" size={32} />
          <p>
            {text}
            <span className="animate-pulse inline-block w-3 h-6 bg-cyan-400 ml-1 align-middle"></span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default NOCGreeting;