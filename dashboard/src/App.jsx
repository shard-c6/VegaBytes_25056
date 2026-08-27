import { useState, useEffect } from 'react';
import { Plane, Activity, ShieldCheck, Database, Calendar } from 'lucide-react';
import { fetchLatestIndex, fetchPipelineStatus, fetchIndexHistory } from './services/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart
} from 'recharts';
import FaresExplorer from './components/FaresExplorer';
import ComplianceMonitor from './components/ComplianceMonitor';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [indexData, setIndexData] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [historyData, setHistoryData] = useState([]);

  useEffect(() => {
    const loadData = async () => {
      const [index, status, history] = await Promise.all([
        fetchLatestIndex(),
        fetchPipelineStatus(),
        fetchIndexHistory('2026-08-01', new Date().toISOString().split('T')[0])
      ]);
      setIndexData(index);
      setStatusData(status);
      setHistoryData(history.data);
    };
    loadData();
  }, []);

  const renderContent = () => {
    if (activeTab === 'overview') {
      return (
        <div className="animate-fade-in dashboard-grid">
          {/* Top KPI Cards */}
          <div className="kpi-row">
            <div className="glass-panel kpi-card">
              <div className="kpi-header">
                <span className="text-small">Latest APIx Value</span>
                <Activity size={20} className="text-accent" />
              </div>
              <h2>{indexData ? indexData.apix_value.toFixed(2) : '...'}</h2>
              <span className="text-small text-success">+1.2% from last week</span>
            </div>
            
            <div className="glass-panel kpi-card">
              <div className="kpi-header">
                <span className="text-small">Data Freshness</span>
                <ShieldCheck size={20} className="text-success" />
              </div>
              <h2 className="text-success">{statusData ? statusData.data_freshness.toUpperCase() : '...'}</h2>
              <span className="text-small">Last scrape: {statusData ? new Date(statusData.last_scrape).toLocaleTimeString() : '...'}</span>
            </div>
            
            <div className="glass-panel kpi-card">
              <div className="kpi-header">
                <span className="text-small">Fares Collected</span>
                <Database size={20} className="text-info" />
              </div>
              <h2>{statusData ? statusData.total_fares_collected.toLocaleString() : '...'}</h2>
              <span className="text-small">98.4% success rate</span>
            </div>
          </div>

          {/* Main Chart */}
          <div className="glass-panel chart-container">
            <div className="chart-header">
              <h3>APIx 30-Day Trend vs MoSPI Baseline</h3>
              <span className="text-small">Real-time inflation tracking</span>
            </div>
            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={historyData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#38bdf8" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} />
                  <YAxis domain={['dataMin - 5', 'dataMax + 5']} stroke="#94a3b8" fontSize={12} />
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }}
                  />
                  <Area type="monotone" dataKey="value" stroke="#38bdf8" fillOpacity={1} fill="url(#colorValue)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      );
    }
    
    if (activeTab === 'fares') {
      return <FaresExplorer />;
    }
    
    if (activeTab === 'compliance') {
      return <ComplianceMonitor />;
    }
    
    return null;
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar glass-panel">
        <div className="sidebar-brand">
          <Plane className="text-accent" size={28} />
          <h2 className="text-gradient">VegaBytes</h2>
        </div>
        
        <nav className="sidebar-nav">
          <button 
            className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <Activity size={18} /> APIx Overview
          </button>
          <button 
            className={`nav-item ${activeTab === 'fares' ? 'active' : ''}`}
            onClick={() => setActiveTab('fares')}
          >
            <Database size={18} /> Fares Explorer
          </button>
          <button 
            className={`nav-item ${activeTab === 'compliance' ? 'active' : ''}`}
            onClick={() => setActiveTab('compliance')}
          >
            <ShieldCheck size={18} /> Compliance
          </button>
        </nav>

        <div className="sidebar-footer">
          <span className="text-small">SIH PS 26056</span>
          <span className="text-small">Sprint 1</span>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="top-header">
          <div>
            <h1>Real-time Airfare Price Index</h1>
            <p className="text-secondary">High-frequency economic data pipeline for NSO/RBI</p>
          </div>
          <div className="glass-panel header-date">
            <Calendar size={16} />
            <span>{new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</span>
          </div>
        </header>

        {renderContent()}
      </main>
    </div>
  );
}

export default App;
