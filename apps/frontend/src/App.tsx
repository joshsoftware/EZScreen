import React, { useState, useEffect } from 'react';
import { Shield, Cpu, Activity, RefreshCw } from 'lucide-react';

function App() {
  const [coreHealth, setCoreHealth] = useState<any>(null);
  const [aiHealth, setAiHealth] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const coreRes = await fetch('/api/v1/system/health').catch(() => null);
      if (coreRes && coreRes.ok) {
        setCoreHealth(await coreRes.json());
      } else {
        setCoreHealth({ status: 'unreachable' });
      }

      const aiRes = await fetch('/health').catch(() => null);
      if (aiRes && aiRes.ok) {
        setAiHealth(await aiRes.json());
      } else {
        setAiHealth({ status: 'unreachable' });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans antialiased selection:bg-teal-500 selection:text-slate-900">
      {/* Background radial highlight */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-gradient-radial from-teal-500/10 to-transparent blur-3xl pointer-events-none -z-10" />

      {/* Header */}
      <header className="border-b border-slate-900 bg-slate-950/80 backdrop-blur sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-gradient-to-tr from-teal-500 to-emerald-400 rounded-xl text-slate-950 shadow-lg shadow-teal-500/20">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-teal-200 to-emerald-400 bg-clip-text text-transparent">
              EZScreen
            </h1>
            <p className="text-[10px] text-slate-500 tracking-wider uppercase">AI-Powered Recruitment</p>
          </div>
        </div>

        <button 
          onClick={fetchHealth} 
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 active:scale-95 transition-all text-xs font-semibold rounded-lg border border-slate-800 text-teal-400"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh System Health</span>
        </button>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 md:p-8 flex flex-col justify-center">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <span className="px-3 py-1 bg-teal-500/10 text-teal-400 text-xs font-medium rounded-full border border-teal-500/20">
            Developer Environment Seeded
          </span>
          <h2 className="text-4xl md:text-5xl font-extrabold mt-6 tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            Autonomous Candidate Screening
          </h2>
          <p className="text-slate-400 mt-4 text-base md:text-lg leading-relaxed">
            EZScreen automates screening by parsing JDs, scoring resumes, and deploying headless meeting bots to interview candidates.
          </p>
        </div>

        {/* Status Dashboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* React Frontend */}
          <div className="bg-slate-900/40 border border-slate-900 hover:border-slate-800/80 transition-all rounded-2xl p-6 relative overflow-hidden backdrop-blur flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] uppercase font-bold tracking-widest text-slate-500">Service 1</span>
                <span className="flex items-center text-xs text-emerald-400 font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
                  Active
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-100">React Frontend</h3>
              <p className="text-slate-400 text-xs mt-2 leading-relaxed">
                Single Page Application providing the dashboard, candidate pipelines, and screening evaluations.
              </p>
            </div>
            <div className="mt-8 pt-4 border-t border-slate-950 flex items-center justify-between text-[11px] text-slate-500">
              <span>Port: 5173</span>
              <span>Vite + TypeScript</span>
            </div>
          </div>

          {/* Core API Backend */}
          <div className="bg-slate-900/40 border border-slate-900 hover:border-slate-800/80 transition-all rounded-2xl p-6 relative overflow-hidden backdrop-blur flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] uppercase font-bold tracking-widest text-slate-500">Service 2</span>
                <span className={`flex items-center text-xs font-semibold px-2.5 py-0.5 rounded-full ${
                  coreHealth?.status === 'healthy' 
                    ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20' 
                    : 'text-amber-400 bg-amber-500/10 border border-amber-500/20'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                    coreHealth?.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                  }`} />
                  {coreHealth?.status || 'checking...'}
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-100">Core API Backend</h3>
              <p className="text-slate-400 text-xs mt-2 leading-relaxed">
                Central backend managing RBAC database state, JD parsing pipelines, and interview scheduling workflows.
              </p>
            </div>
            <div className="mt-8 pt-4 border-t border-slate-950 flex flex-col space-y-1.5 text-[11px] text-slate-500">
              <div className="flex justify-between">
                <span>Port: 8000</span>
                <span>FastAPI + Python</span>
              </div>
              {coreHealth?.status === 'healthy' && (
                <div className="text-[10px] bg-slate-950 p-2 rounded border border-slate-900 text-slate-400 flex flex-col space-y-1">
                  <span>DB Connection: Connected</span>
                </div>
              )}
            </div>
          </div>

          {/* AI Screening Microservice */}
          <div className="bg-slate-900/40 border border-slate-900 hover:border-slate-800/80 transition-all rounded-2xl p-6 relative overflow-hidden backdrop-blur flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] uppercase font-bold tracking-widest text-slate-500">Service 3</span>
                <span className={`flex items-center text-xs font-semibold px-2.5 py-0.5 rounded-full ${
                  aiHealth?.status === 'healthy' 
                    ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20' 
                    : 'text-amber-400 bg-amber-500/10 border border-amber-500/20'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                    aiHealth?.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                  }`} />
                  {aiHealth?.status || 'checking...'}
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-100">AI Screening Service</h3>
              <p className="text-slate-400 text-xs mt-2 leading-relaxed">
                Independent microservice facilitating real-time WebSocket connections and STT-LLM-TTS speech chaining.
              </p>
            </div>
            <div className="mt-8 pt-4 border-t border-slate-950 flex items-center justify-between text-[11px] text-slate-500">
              <span>Port: 8001</span>
              <span>FastAPI + WebSockets</span>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-6 px-6 text-center text-xs text-slate-600 bg-slate-950 flex flex-col md:flex-row justify-between items-center space-y-2 md:space-y-0">
        <span>&copy; 2026 EZScreen. All rights reserved.</span>
        <div className="flex space-x-4">
          <a href="/docs" className="hover:text-teal-400 transition-colors">Documentation</a>
          <span>&middot;</span>
          <a href="#" className="hover:text-teal-400 transition-colors">System Health</a>
        </div>
      </footer>
    </div>
  );
}

export default App;
