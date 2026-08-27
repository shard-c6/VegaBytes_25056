import { useState, useEffect } from 'react';
import { fetchFares } from '../services/api';
import { Search, ChevronLeft, ChevronRight, Filter } from 'lucide-react';

export default function FaresExplorer() {
  const [fares, setFares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    const loadFares = async () => {
      setLoading(true);
      const data = await fetchFares(null, page);
      setFares(data.data);
      setTotal(data.total);
      setLoading(false);
    };
    loadFares();
  }, [page]);

  return (
    <div className="animate-fade-in glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div className="kpi-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>Fares Explorer</h2>
          <p className="text-secondary">Raw fare data from ETL pipeline</p>
        </div>
        
        <div style={{ display: 'flex', gap: '1rem' }}>
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input 
              type="text" 
              placeholder="Search route (e.g. DEL-BOM)" 
              style={{
                background: 'rgba(0,0,0,0.2)',
                border: '1px solid var(--border-strong)',
                borderRadius: '8px',
                padding: '0.5rem 1rem 0.5rem 2.5rem',
                color: 'white',
                outline: 'none',
                width: '240px'
              }}
            />
          </div>
          <button style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid var(--border-strong)',
            borderRadius: '8px',
            padding: '0.5rem 1rem',
            color: 'white',
            cursor: 'pointer'
          }}>
            <Filter size={16} /> Filters
          </button>
        </div>
      </div>

      <div style={{ overflowX: 'auto', flex: 1 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-strong)', color: 'var(--text-secondary)' }}>
              <th style={{ padding: '1rem', fontWeight: 500 }}>Route</th>
              <th style={{ padding: '1rem', fontWeight: 500 }}>Airline</th>
              <th style={{ padding: '1rem', fontWeight: 500 }}>Departure Date</th>
              <th style={{ padding: '1rem', fontWeight: 500 }}>Total Fare</th>
              <th style={{ padding: '1rem', fontWeight: 500 }}>Source</th>
              <th style={{ padding: '1rem', fontWeight: 500 }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>Loading data...</td></tr>
            ) : fares.map((fare) => (
              <tr key={fare.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                <td style={{ padding: '1rem' }} className="font-bold">{fare.route}</td>
                <td style={{ padding: '1rem' }}>{fare.airline}</td>
                <td style={{ padding: '1rem' }}>{new Date(fare.departure_date).toLocaleDateString()}</td>
                <td style={{ padding: '1rem', color: 'var(--text-accent)' }}>₹{fare.total_fare.toLocaleString()}</td>
                <td style={{ padding: '1rem' }}>
                  <span style={{ 
                    padding: '0.25rem 0.5rem', 
                    borderRadius: '4px', 
                    background: 'rgba(255,255,255,0.1)',
                    fontSize: '0.875rem'
                  }}>
                    {fare.source}
                  </span>
                </td>
                <td style={{ padding: '1rem' }}>
                  <span style={{ color: 'var(--color-success)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--color-success)' }}></div> Valid
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '1.5rem', borderTop: '1px solid var(--border-strong)' }}>
        <span className="text-secondary">Showing {(page - 1) * 15 + 1} to {Math.min(page * 15, total)} of {total.toLocaleString()} records</span>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button 
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ padding: '0.5rem', background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '6px', color: 'white', cursor: page === 1 ? 'not-allowed' : 'pointer' }}
          ><ChevronLeft size={16} /></button>
          <button 
            onClick={() => setPage(p => p + 1)}
            style={{ padding: '0.5rem', background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '6px', color: 'white', cursor: 'pointer' }}
          ><ChevronRight size={16} /></button>
        </div>
      </div>
    </div>
  );
}
