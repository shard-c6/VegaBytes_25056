import React from 'react';
import styles from './compliance.module.css';

export default function ComplianceMonitor() {
  // Mock data for the dashboard as per the requirements
  const robotsCheck = [
    { source: 'IndiGo Direct', lastChecked: '2 mins ago', status: 'Allowed' },
    { source: 'MakeMyTrip', lastChecked: '5 mins ago', status: 'Allowed' },
    { source: 'Akasa Air', lastChecked: '12 mins ago', status: 'Allowed' },
  ];

  const rateLogs = [
    { ip: '192.168.1.104', reqPerMin: 1.2, status: 'safe' },
    { ip: '10.0.0.45', reqPerMin: 1.8, status: 'warning' },
    { ip: '172.16.0.8', reqPerMin: 0.5, status: 'safe' },
    { ip: '192.168.1.210', reqPerMin: 1.5, status: 'safe' },
  ];

  return (
    <main className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Compliance Monitor</h1>
        <p className={styles.subtitle}>
          Real-time tracking of scraping footprint and legal defensibility metrics
        </p>
      </header>

      <div className={styles.grid}>
        {/* Robots.txt Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Robots.txt Status</h2>
            <span className={`${styles.badge} ${styles.badgeSuccess}`}>Valid</span>
          </div>
          <div className={styles.statValue}>
            100<span className={styles.statUnit}>%</span>
          </div>
          <p className={styles.statDesc}>All sources currently permit crawling paths</p>
          
          <table className={styles.logTable} style={{ marginTop: '1.5rem' }}>
            <tbody>
              {robotsCheck.map((item, i) => (
                <tr key={i}>
                  <td>{item.source}</td>
                  <td style={{ color: '#94a3b8', fontSize: '0.9rem' }}>{item.lastChecked}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Request Rate Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Global Request Rate</h2>
            <span className={`${styles.badge} ${styles.badgeSuccess}`}>Optimal</span>
          </div>
          <div className={styles.statValue}>
            1.25<span className={styles.statUnit}>req/min/IP</span>
          </div>
          <p className={styles.statDesc}>Target: &lt; 2.0 req/min/IP to ensure zero server strain</p>
          
          <table className={styles.logTable} style={{ marginTop: '1.5rem' }}>
            <tbody>
              {rateLogs.map((log, i) => (
                <tr key={i}>
                  <td className={styles.ipCell}>{log.ip}</td>
                  <td>
                    <div className={`${styles.rateCell} ${log.status === 'warning' ? styles.rateWarning : ''}`}>
                      <div className={styles.rateBar}>
                        <div 
                          className={styles.rateFill} 
                          style={{ width: `${(log.reqPerMin / 2.5) * 100}%` }}
                        />
                      </div>
                      <span style={{ fontSize: '0.9rem', width: '30px' }}>{log.reqPerMin}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Footprint Summary Card */}
        <div className={`${styles.card} ${styles.fullWidthCard}`}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Scraper Footprint Summary</h2>
            <span className={`${styles.badge} ${styles.badgeSuccess}`}>Stealth Active</span>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '2rem', marginTop: '1.5rem' }}>
            <div>
              <div className={styles.statDesc}>Total Residential IPs in Rotation</div>
              <div className={styles.statValue} style={{ fontSize: '1.5rem', marginTop: '0.5rem' }}>142</div>
            </div>
            <div>
              <div className={styles.statDesc}>Average Session Duration</div>
              <div className={styles.statValue} style={{ fontSize: '1.5rem', marginTop: '0.5rem' }}>45s</div>
            </div>
            <div>
              <div className={styles.statDesc}>Headless Detection Evasions</div>
              <div className={styles.statValue} style={{ fontSize: '1.5rem', marginTop: '0.5rem' }}>100%</div>
            </div>
            <div>
              <div className={styles.statDesc}>PII Collected</div>
              <div className={styles.statValue} style={{ fontSize: '1.5rem', marginTop: '0.5rem', color: 'var(--success)' }}>0 Bytes</div>
            </div>
          </div>
          
          <div style={{ marginTop: '2rem', padding: '1rem', background: 'rgba(59, 130, 246, 0.1)', borderLeft: '4px solid var(--primary)', borderRadius: '4px' }}>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem' }}>Legal Framework Compliance</h3>
            <p style={{ margin: 0, color: '#cbd5e1', fontSize: '0.9rem', lineHeight: '1.5' }}>
              Operations are currently strictly within the parameters set by <strong>hiQ Labs v. LinkedIn</strong> for public data scraping. Data collection supports the <strong>MoSPI statistical mandate</strong> under the Collection of Statistics Act, 2008.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
