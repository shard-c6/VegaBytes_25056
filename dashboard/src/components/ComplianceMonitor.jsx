import { ShieldCheck, Server, Clock, AlertTriangle } from 'lucide-react';

export default function ComplianceMonitor() {
  const logs = [
    { time: '12:45:10', type: 'info', msg: 'IndiGo direct scraper initiated. Rotating to IP 45.x.x.x' },
    { time: '12:45:12', type: 'success', msg: 'robots.txt respected. Crawl delay 30s.' },
    { time: '12:45:42', type: 'info', msg: 'Rate limit OK (<2 req/min). Scraping DEL-BOM T+1.' },
    { time: '12:45:48', type: 'success', msg: 'DEL-BOM parsed via stealth browser. Base fare extracted.' },
    { time: '12:46:18', type: 'warning', msg: 'MakeMyTrip structural change detected. Firing Gemini DOM parser fallback.' },
    { time: '12:46:21', type: 'success', msg: 'AI parser recovered price successfully.' },
  ];

  return (
    <div className="animate-fade-in dashboard-grid">
      <div className="kpi-row">
        <div className="glass-panel kpi-card">
          <div className="kpi-header">
            <span className="text-small">Rate Limiting</span>
            <Clock size={20} className="text-info" />
          </div>
          <h2 className="text-info">{'< 2 req/m'}</h2>
          <span className="text-small">Per IP average over 24h</span>
        </div>
        
        <div className="glass-panel kpi-card">
          <div className="kpi-header">
            <span className="text-small">Statutory Compliance</span>
            <ShieldCheck size={20} className="text-success" />
          </div>
          <h2 className="text-success">Active</h2>
          <span className="text-small">No PII collected. (Act 2008)</span>
        </div>

        <div className="glass-panel kpi-card">
          <div className="kpi-header">
            <span className="text-small">Bans / Blocks</span>
            <AlertTriangle size={20} className="text-warning" />
          </div>
          <h2 className="text-warning">0</h2>
          <span className="text-small">In last 7 days</span>
        </div>
      </div>

      <div className="glass-panel" style={{ flex: 1, minHeight: '400px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <Server size={20} className="text-accent" />
          <h3 style={{ margin: 0 }}>Live Scraper Activity Log</h3>
        </div>

        <div style={{ 
          background: 'rgba(0,0,0,0.3)', 
          borderRadius: '8px', 
          padding: '1.5rem',
          fontFamily: 'monospace',
          fontSize: '0.9rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem'
        }}>
          {logs.map((log, i) => (
            <div key={i} style={{ display: 'flex', gap: '1rem' }}>
              <span style={{ color: '#64748b' }}>{log.time}</span>
              <span style={{ 
                color: log.type === 'success' ? 'var(--color-success)' : 
                       log.type === 'warning' ? 'var(--color-warning)' : 
                       'var(--color-info)' 
              }}>
                [{log.type.toUpperCase()}]
              </span>
              <span style={{ color: '#e2e8f0' }}>{log.msg}</span>
            </div>
          ))}
          <div className="animate-pulse" style={{ display: 'flex', gap: '1rem', opacity: 0.5 }}>
            <span style={{ color: '#64748b' }}>12:46:51</span>
            <span style={{ color: 'var(--color-info)' }}>[INFO]</span>
            <span style={{ color: '#e2e8f0' }}>Waiting for crawl delay (30s)...</span>
          </div>
        </div>
      </div>
    </div>
  );
}
