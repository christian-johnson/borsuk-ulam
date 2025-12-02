import React, { useEffect, useState } from 'react';

import LoadingOverlay from './components/LoadingOverlay';
import WeatherGlobe from './components/WeatherGlobe';
import ControlPanel from './components/ControlPanel';

import PYTHON_CODE from './main.py?raw';


const App = () => {
  // --- State ---
  const [pyodide, setPyodide] = useState<any>(null);
  const [pyLoaded, setPyLoaded] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("Starting Pyodide");
   
  // Data State
  const [hasData, setHasData] = useState(false);
  const [weatherData, setWeatherData] = useState<any>(null);
   
  // UI Controls
  const [displayMode, setDisplayMode] = useState<'temp' | 'press'>('temp');
  const [viewMode, setViewMode] = useState<'all' | 'single'>('all');
  const [pointIndex, setPointIndex] = useState(0); 

  // --- Initialization ---

  useEffect(() => {
    const loadPy = async () => {
      try {
        const py = await window.loadPyodide();
        await py.loadPackage(['numpy', 'pandas', 'matplotlib']);
        await py.runPythonAsync(PYTHON_CODE);
        setPyodide(py);
        setPyLoaded(true);
        setLoadingMsg(""); 
      } catch (e) {
        console.error("Pyodide failed to load", e);
        setLoadingMsg("Error loading Python environment.");
      }
    };
    loadPy();
  }, []);

  // --- Handlers ---

  const handleFetchData = async () => {
    if (!pyodide) return;
    setLoadingMsg("Processing data");
    
    try {
      setTimeout(async () => {
        const resultString = await pyodide.runPythonAsync(`process_data()`);
        const result = JSON.parse(resultString);
        console.log(result);
        
        setWeatherData(result);
        setHasData(true);
        setPointIndex(0); 
        setLoadingMsg("");
      }, 1500);
    } catch (e) {
      console.error(e);
      setLoadingMsg("Error processing GFS data.");
    }
  };

  const handleNextPoint = () => {
    if (!weatherData?.matches) return;
    setPointIndex((prev) => (prev + 1) % weatherData.matches.length);
  };

  const handlePrevPoint = () => {
    if (!weatherData?.matches) return;
    setPointIndex((prev) => (prev - 1 + weatherData.matches.length) % weatherData.matches.length);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-sans relative overflow-hidden flex flex-col">
      
      {/* 1. Loading Overlay handles its own absolute positioning */}
      <LoadingOverlay 
        loadingMsg={loadingMsg}
        hasData={hasData}
        pyLoaded={pyLoaded}
        onFetch={handleFetchData}
      />

      {/* 2. Main Content Wrapper */}
      <div className="flex-1 relative flex flex-col">
        
        <WeatherGlobe 
          data={weatherData}
          hasData={hasData}
          displayMode={displayMode}
          viewMode={viewMode}
          pointIndex={pointIndex}
        />

        {/* 3. Control Panel */}
        {hasData && !loadingMsg && (
          <ControlPanel 
            displayMode={displayMode}
            setDisplayMode={setDisplayMode}
            viewMode={viewMode}
            setViewMode={setViewMode}
            pointIndex={pointIndex}
            totalPoints={weatherData?.matches?.length || 0}
            onNext={handleNextPoint}
            onPrev={handlePrevPoint}
            // Pass timestamp string (assuming backend provides 'timestamp' or we fallback to now)
            dataTimestamp={weatherData?.timestamp || new Date().toISOString()}
          />
        )}
      </div>
    </div>
  );
};

export default App;
