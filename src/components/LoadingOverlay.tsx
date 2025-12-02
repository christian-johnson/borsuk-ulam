import { Loader2, Globe as GlobeIcon } from 'lucide-react';

interface LoadingOverlayProps {
  loadingMsg: string;
  hasData: boolean;
  pyLoaded: boolean;
  onFetch: () => void;
}

const LoadingOverlay: React.FC<LoadingOverlayProps> = ({ 
  loadingMsg, 
  hasData, 
  pyLoaded, 
  onFetch 
}) => {
  if (hasData && !loadingMsg) return null;

  return (
    <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex flex-col items-center justify-center p-4">
      <div className="bg-slate-800 p-8 rounded-2xl shadow-2xl border border-slate-700 max-w-md w-full text-center">
        {loadingMsg ? (
          <div className="flex flex-col items-center space-y-4">
            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">Loading...</h3>
              <p className="text-slate-400 text-sm">{loadingMsg}</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-6">
            <div className="p-4 bg-blue-500/10 rounded-full text-blue-400">
              <GlobeIcon size={48} strokeWidth={1.5} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white mb-2">
                {!pyLoaded ? "Initializing Environment..." : "Ready!"}
              </h2>
              <p className="text-slate-400">
                {!pyLoaded 
                  ? "Loading Python environment and libraries..." 
                  : "Fetch the latest GFS data to visualize temperature and pressure pairs."}
              </p>
            </div>
            {pyLoaded && (
              <button 
                onClick={onFetch}
                className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-lg shadow-blue-500/20 transition-all transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center gap-2"
              >
                Fetch & Display Data
              </button>
            )}
            {!pyLoaded && (
              <div className="flex items-center gap-2 text-slate-500 text-sm">
                <Loader2 className="animate-spin" size={16} />
                <span>Preparing Pyodide...</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default LoadingOverlay;

