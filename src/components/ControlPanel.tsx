import React, { useRef, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Clock, Calendar, ExternalLink, Github, ChevronDown, ChevronUp } from 'lucide-react';

interface ControlPanelProps {
  displayMode: 'temp' | 'press';
  setDisplayMode: (mode: 'temp' | 'press') => void;
  pointIndex: number;
  totalPoints: number;
  onNext: () => void;
  onPrev: () => void;
  dataTimestamp?: string;
  currentPair?: { lat: number; lon: number };
}

// Helper for Rapid-Fire Buttons
const LongPressButton: React.FC<{ 
  onClick: () => void, 
  icon: React.ReactNode,
  className?: string 
}> = ({ onClick, icon, className }) => {
  const timerRef = useRef<number | null>(null);
  const intervalRef = useRef<number | null>(null);

  const startPress = () => {
    onClick();
    timerRef.current = window.setTimeout(() => {
      intervalRef.current = window.setInterval(() => {
        onClick();
      }, 50); 
    }, 400);
  };

  const stopPress = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (intervalRef.current) clearInterval(intervalRef.current);
  };

  return (
    <button
      onMouseDown={startPress}
      onMouseUp={stopPress}
      onMouseLeave={stopPress}
      onTouchStart={startPress}
      onTouchEnd={stopPress}
      className={className}
    >
      {icon}
    </button>
  );
};

const ControlPanel: React.FC<ControlPanelProps> = ({
  displayMode,
  setDisplayMode,
  pointIndex,
  totalPoints,
  onNext,
  onPrev,
  dataTimestamp,
  currentPair
}) => {
  const [timeInfo, setTimeInfo] = useState({ label: 'Loading...', age: '' });
  const [isExpanded, setIsExpanded] = useState(true);

  // 1. Parse GFS Date Format
  useEffect(() => {
    if (!dataTimestamp) return;

    try {
      // Handle new format: "Run: YYYY-MM-DD HHoz | Valid: YYYY-MM-DD HHz"
      // Or old format: "YYYY-MM-DD HHz"
      let dateToParse = dataTimestamp;
      if (dataTimestamp.includes("Valid:")) {
        const parts = dataTimestamp.split("Valid: ");
        if (parts[1]) {
            dateToParse = parts[1].trim();
        }
      }

      // Format expected: "2025-12-02 06z" or "2025-12-02 14:00z"
      // Remove 'z' and replace space with T if needed
      let cleanDate = dateToParse.replace(/z/i, '').trim();
      
      // If space exists, replace with T for ISO parsing
      if (cleanDate.includes(' ')) {
          cleanDate = cleanDate.replace(' ', 'T');
      }
      
      // Append :00:00Z if only hour is present (e.g. 2025-12-02T06)
      if (cleanDate.split(':').length === 1) {
          cleanDate += ":00:00Z";
      } else if (cleanDate.split(':').length === 2) {
          cleanDate += ":00Z";
      } else {
          cleanDate += "Z";
      }

      const dateObj = new Date(cleanDate);

      if (isNaN(dateObj.getTime())) throw new Error("Invalid Date");

      const now = new Date();
      const diffMs = now.getTime() - dateObj.getTime();
      const diffHrs = Math.floor(Math.abs(diffMs) / (1000 * 60 * 60));
      const diffMins = Math.floor((Math.abs(diffMs) % (1000 * 60 * 60)) / (1000 * 60));
      
      let ageStr = "";
      const direction = diffMs > 0 ? "ago" : "future";
      if (diffHrs > 0) ageStr = `${diffHrs}h ${diffMins}m ${direction}`;
      else ageStr = `${diffMins}m ${direction}`;

      // Simplify label if it's the long format
      const shortLabel = dataTimestamp.length > 30 ? "Latest GFS Run" : dataTimestamp;

      setTimeInfo({
        label: dataTimestamp, // Keep full info in label for details
        age: ageStr
      });

    } catch (e) {
      console.error("Date parsing error", e);
      setTimeInfo({ label: dataTimestamp, age: '-' });
    }
  }, [dataTimestamp]);

  // Shared styles for the toggles to ensure they look identical
  const toggleContainerClass = "flex bg-slate-700 rounded-lg p-1 mb-2";
  const toggleBtnBase = "flex-1 py-1.5 text-xs font-bold uppercase tracking-wider rounded-md transition-all";
  const toggleBtnInactive = "text-slate-400 hover:text-white";

  return (
    <div className={`absolute bottom-6 left-6 z-40 bg-slate-800/90 backdrop-blur-sm rounded-xl border border-slate-700 shadow-xl text-slate-100 font-sans transition-all duration-300 ${isExpanded ? 'w-80 p-5' : 'w-auto p-2'}`}>
      
      {/* HEADER / TOGGLE */}
      <div className={`flex items-center ${isExpanded ? 'justify-between mb-3' : 'justify-center'}`}>
        {isExpanded && (
            <h3 className="text-lg font-bold text-white tracking-tight">
            Borsuk-Ulam
            </h3>
        )}
        <button 
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
        >
            {isExpanded ? <ChevronDown size={20} /> : <ChevronUp size={24} />}
        </button>
      </div>

      {isExpanded && (
      <>
        {/* DATE & AGE */}
        <div className="mb-5 flex flex-col gap-1 bg-slate-700/30 p-2 rounded-md border border-slate-700/50">
            <div className="flex items-start gap-2 text-xs text-blue-200 font-mono">
                <Calendar size={12} className="shrink-0 mt-0.5"/>
                <div className="flex flex-col">
                    {timeInfo.label.split(' | ').map((part, i) => (
                        <span key={i}>{part}</span>
                    ))}
                </div>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-400 pl-5">
                <Clock size={11} />
                <span>{timeInfo.age}</span>
            </div>
        </div>

        {/* --- DATA LAYER TOGGLE --- */}
        <div className={toggleContainerClass}>
            <button
            onClick={() => setDisplayMode('temp')}
            className={`${toggleBtnBase} ${
                displayMode === 'temp' ? 'bg-blue-600 text-white shadow-sm' : toggleBtnInactive
            }`}
            >
            Temperature
            </button>
            <button
            onClick={() => setDisplayMode('press')}
            className={`${toggleBtnBase} ${
                displayMode === 'press' ? 'bg-emerald-600 text-white shadow-sm' : toggleBtnInactive
            }`}
            >
            Pressure
            </button>
        </div>

        {/* COLOR BAR & LABELS */}
        <div className="mb-6">
            <div 
            className="h-1.5 w-full rounded-full opacity-90 mb-1"
            style={{
                background: displayMode === 'temp'
                ? 'linear-gradient(to right, #313695, #4575b4, #74add1, #abd9e9, #e0f3f8, #ffffbf, #fee090, #fdae61, #f46d43, #d73027, #a50026)'
                : 'linear-gradient(to right, #440154, #31688e, #35b779, #fde725)'
            }}
            />
            <div className="flex justify-between text-[10px] text-slate-400 font-medium uppercase tracking-wide">
            <span>
                {displayMode === 'temp' ? '-40 °C' : '0.5 atm'}
            </span>
            <span>
                {displayMode === 'temp' ? '40 °C' : '1.05 atm'}
            </span>
            </div>
        </div>


        {/* --- PAIRS FOUND DIAGNOSTIC --- */}
        <div className={`rounded-lg p-2.5 mb-3 flex flex-col items-center justify-center border text-xs shadow-inner ${
            totalPoints > 0 
            ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-100' 
            : 'bg-red-500/10 border-red-500/50 text-red-200'
        }`}>
           {totalPoints > 0 ? (
             <div className="flex items-center">
                <span className="font-mono text-sm font-bold text-white bg-emerald-600/50 px-2 py-0.5 rounded mr-2 border border-emerald-400/30">
                  {totalPoints}
                </span>
                <span className="font-medium">pairs found</span>
             </div>
           ) : (
             <div className="text-center leading-relaxed opacity-90">
                <div className="font-bold mb-1 text-red-400">0 pairs found</div>
                This is impossible from a mathematical standpoint. But the GFS model used here is coarse-grained, so it can't be 100% sure of finding a successful pair.
             </div>
           )}
        </div>

        {/* PAGING WIDGET */}
        {totalPoints > 0 ? (
            <div className="bg-slate-700/40 rounded-lg p-3 flex flex-col gap-3 border border-slate-600/50">
                <div className="flex items-center justify-between">
                    <LongPressButton 
                        onClick={onPrev}
                        className="p-2 rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors border border-slate-600 hover:border-slate-500 active:scale-95"
                        icon={<ChevronLeft size={16} />}
                    />
                    
                    <div className="text-sm font-mono text-slate-300 bg-slate-900/40 px-3 py-1 rounded-full border border-slate-700/50">
                        <span className="text-white font-bold text-base">{pointIndex + 1}</span> 
                        <span className="mx-2 opacity-30">/</span> 
                        {totalPoints}
                    </div>
                    
                    <LongPressButton 
                        onClick={onNext}
                        className="p-2 rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors border border-slate-600 hover:border-slate-500 active:scale-95"
                        icon={<ChevronRight size={16} />}
                    />
                </div>

                {currentPair && (
                    <div className="space-y-1.5 pt-1 border-t border-slate-600/30">
                        {[
                            { label: 'Point 1', lat: currentPair.lat, lon: currentPair.lon },
                            { label: 'Point 2', lat: -currentPair.lat, lon: currentPair.lon + 180 > 180 ? currentPair.lon + 180 - 360 : currentPair.lon + 180 }
                        ].map((p, i) => (
                            <div key={i} className="flex justify-between items-center text-[10px] font-mono">
                                <span className="text-slate-500 uppercase tracking-tighter">{p.label}:</span>
                                <span className="text-slate-300">
                                    {Math.abs(p.lon).toFixed(1)}° {p.lon >= 0 ? 'E' : 'W'}, {Math.abs(p.lat).toFixed(1)}° {p.lat >= 0 ? 'N' : 'S'}
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        ) : null}



        {/* GitHub Link */}
            <div className="mt-4 pt-3 border-t border-slate-700/50 flex justify-center">
            <a 
                href="https://github.com/christian-johnson/borsuk-ulam" 
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
            >
                <Github size={10} />
                <span>Created by Christian Johnson</span>
            </a>
            </div>
      </>
      )}
    </div>
  );
};

export default ControlPanel;
