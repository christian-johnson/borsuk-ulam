import React, { useRef, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Clock, Calendar } from 'lucide-react';

interface ControlPanelProps {
  displayMode: 'temp' | 'press';
  setDisplayMode: (mode: 'temp' | 'press') => void;
  viewMode: 'all' | 'single';
  setViewMode: (mode: 'all' | 'single') => void;
  pointIndex: number;
  totalPoints: number;
  onNext: () => void;
  onPrev: () => void;
  dataTimestamp?: string;
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
  viewMode,
  setViewMode,
  pointIndex,
  totalPoints,
  onNext,
  onPrev,
  dataTimestamp
}) => {
  const [timeInfo, setTimeInfo] = useState({ label: 'Loading...', age: '' });

  // 1. Parse GFS Date Format: "2025-12-02 06z"
  useEffect(() => {
    if (!dataTimestamp) return;

    try {
      const parts = dataTimestamp.split(' ');
      if (parts.length === 2) {
        const datePart = parts[0];
        const hourPart = parts[1].replace('z', ''); 
        const isoString = `${datePart}T${hourPart}:00:00Z`;
        const dateObj = new Date(isoString);

        if (isNaN(dateObj.getTime())) throw new Error("Invalid Date");

        const now = new Date();
        const diffMs = now.getTime() - dateObj.getTime();
        const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
        const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        
        let ageStr = "";
        if (diffHrs > 0) ageStr = `${diffHrs}h ${diffMins}m old`;
        else ageStr = `${diffMins}m old`;

        setTimeInfo({
          label: `${dataTimestamp}`,
          age: ageStr
        });
      } else {
        setTimeInfo({ label: dataTimestamp, age: 'Unknown age' });
      }
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
    <div className="absolute bottom-6 left-6 w-80 z-40 bg-slate-800/90 backdrop-blur-sm p-5 rounded-xl border border-slate-700 shadow-xl text-slate-100 font-sans">
      
      {/* HEADER */}
      <div className="mb-3">
        <h3 className="text-lg font-bold text-white tracking-tight">
          Borsuk-Ulam Visualizer
        </h3>
      </div>

      {/* DATE & AGE */}
      <div className="mb-5 flex flex-col gap-1 bg-slate-700/30 p-2 rounded-md border border-slate-700/50">
        <div className="flex items-center gap-2 text-xs text-blue-200 font-mono">
          <Calendar size={12} />
          <span>GFS RUN: {timeInfo.label}</span>
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
              ? 'linear-gradient(to right, #0000ff, #00ffff, #ffff00, #ff0000)'
              : 'linear-gradient(to right, #440154, #31688e, #35b779, #fde725)'
          }}
        />
        <div className="flex justify-between text-[10px] text-slate-400 font-medium uppercase tracking-wide">
          <span>Low</span>
          <span>High</span>
        </div>
      </div>

      <div className="h-px bg-slate-700 w-full mb-5"></div>

      {/* --- VIEW MODE TOGGLE (Identical styling to Data Layer) --- */}
      <div className={toggleContainerClass}>
        <button
          onClick={() => setViewMode('single')}
          className={`${toggleBtnBase} ${
            viewMode === 'single' ? 'bg-slate-500 text-white shadow-sm' : toggleBtnInactive
          }`}
        >
          One Pair
        </button>
        <button
          onClick={() => setViewMode('all')}
          className={`${toggleBtnBase} ${
            viewMode === 'all' ? 'bg-slate-500 text-white shadow-sm' : toggleBtnInactive
          }`}
        >
          All Pairs
        </button>
      </div>

      {/* PAGING WIDGET (Only in Single Mode) */}
      {viewMode === 'single' && totalPoints > 0 ? (
        <div className="bg-slate-700/40 rounded-lg p-2 flex items-center justify-between border border-slate-600/50">
          <LongPressButton 
            onClick={onPrev}
            className="p-2 rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors border border-slate-600 hover:border-slate-500 active:scale-95"
            icon={<ChevronLeft size={16} />}
          />
          
          <div className="text-sm font-mono text-slate-300">
            <span className="text-white font-bold text-base">{pointIndex + 1}</span> 
            <span className="mx-2 opacity-50">/</span> 
            {totalPoints}
          </div>
          
          <LongPressButton 
            onClick={onNext}
            className="p-2 rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors border border-slate-600 hover:border-slate-500 active:scale-95"
            icon={<ChevronRight size={16} />}
          />
        </div>
      ) : viewMode === 'single' ? (
         <div className="text-center text-xs text-slate-500 py-2">No matching points found</div>
      ) : null}

    </div>
  );
};

export default ControlPanel;
