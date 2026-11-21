import React, { useEffect, useState } from 'react';
import { CheckCircle2, Filter, ShieldCheck, XCircle } from 'lucide-react';
import { api } from '../services/api';
import { Obligation, TaskChainSummary } from '../types/api';

export const ObligationsPage: React.FC = () => {
  const [chains, setChains] = useState<TaskChainSummary[]>([]);
  const [selectedChainId, setSelectedChainId] = useState<string>('');
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [filter, setFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getTaskChains().then((res) => {
      setChains(res);
      if (res.length > 0) {
        setSelectedChainId(res[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedChainId) return;
    setLoading(true);
    api.getTaskChainObligations(selectedChainId)
      .then((obs) => setObligations(obs))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [selectedChainId]);

  const filtered = obligations.filter((o) => {
    if (filter === 'ALL') return true;
    return o.status === filter;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>Obligation Ledger</h2>
          <p style={{ margin: '0.25rem 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
            Non-negotiable acceptance obligations and regression invariants across the chain.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <select
            value={selectedChainId}
            onChange={(e) => setSelectedChainId(e.target.value)}
            style={{ padding: '0.4rem 0.8rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.375rem', color: '#f8fafc', fontSize: '0.875rem' }}
          >
            {chains.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} ({c.id})
              </option>
            ))}
          </select>

          <div style={{ display: 'flex', gap: '0.25rem', backgroundColor: '#0f172a', padding: '0.2rem', borderRadius: '0.375rem', border: '1px solid #334155' }}>
            {['ALL', 'ACTIVE', 'SUPERSEDED', 'WITHDRAWN'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: '0.25rem 0.6rem',
                  fontSize: '0.75rem',
                  borderRadius: '0.25rem',
                  border: 'none',
                  backgroundColor: filter === f ? '#38bdf8' : 'transparent',
                  color: filter === f ? '#090d16' : '#94a3b8',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Ledger Table */}
      <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ backgroundColor: '#0f172a', borderBottom: '1px solid #334155', color: '#94a3b8', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <th style={{ padding: '0.75rem 1rem' }}>Obligation ID</th>
              <th style={{ padding: '0.75rem 1rem' }}>Status</th>
              <th style={{ padding: '0.75rem 1rem' }}>Description</th>
              <th style={{ padding: '0.75rem 1rem' }}>Verifier Reference</th>
              <th style={{ padding: '0.75rem 1rem' }}>Source Task</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                  No obligations match current filter.
                </td>
              </tr>
            ) : (
              filtered.map((ob) => {
                const isActive = ob.status === 'ACTIVE';
                return (
                  <tr
                    key={ob.id}
                    style={{
                      borderBottom: '1px solid #334155',
                      backgroundColor: isActive ? 'rgba(56, 189, 248, 0.03)' : 'transparent',
                    }}
                  >
                    <td className="font-mono" style={{ padding: '0.75rem 1rem', fontSize: '0.8rem', color: isActive ? '#38bdf8' : '#94a3b8' }}>
                      {ob.id}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span className={`badge ${isActive ? 'badge-green' : ob.status === 'SUPERSEDED' ? 'badge-amber' : 'badge-slate'}`}>
                        {ob.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: isActive ? 600 : 400, color: isActive ? '#f8fafc' : '#94a3b8' }}>
                      {ob.description}
                      {ob.status_reason && (
                        <div style={{ fontSize: '0.75rem', color: '#f59e0b', marginTop: '0.2rem' }}>
                          Reason: {ob.status_reason}
                        </div>
                      )}
                    </td>
                    <td className="font-mono" style={{ padding: '0.75rem 1rem', fontSize: '0.8rem', color: '#a855f7' }}>
                      {ob.verifier_ref || 'None configured'}
                    </td>
                    <td className="font-mono" style={{ padding: '0.75rem 1rem', fontSize: '0.8rem', color: '#64748b' }}>
                      {ob.source_task_id}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
