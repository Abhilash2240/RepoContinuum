import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronRight, FileCode, ShieldAlert, ShieldCheck, Terminal, XCircle } from 'lucide-react';
import { api } from '../services/api';
import { EvidenceReport, VerificationRun } from '../types/api';

export const VerificationViewerPage: React.FC = () => {
  const [runs, setRuns] = useState<VerificationRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<VerificationRun | null>(null);
  const [evidence, setEvidence] = useState<EvidenceReport | null>(null);

  useEffect(() => {
    api.getVerificationRuns().then((res) => {
      setRuns(res);
      if (res.length > 0) {
        setSelectedRun(res[0]);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedRun) return;
    api.getVerificationEvidence(selectedRun.id)
      .then((ev) => setEvidence(ev))
      .catch(() => setEvidence(null));
  }, [selectedRun]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
        <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>Patches & Verification Viewer</h2>
        <p style={{ margin: '0.25rem 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
          Inspect isolated sandbox verification runs, checks execution, regressions, and unified diffs.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.6fr) minmax(360px, 1.4fr)', gap: '1.5rem' }}>
        {/* Verification Runs List */}
        <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', overflow: 'hidden' }}>
          <div style={{ padding: '0.75rem 1rem', backgroundColor: '#0f172a', borderBottom: '1px solid #334155', fontWeight: 600, fontSize: '0.85rem' }}>
            Verification Pipeline Runs ({runs.length})
          </div>
          {runs.length === 0 ? (
            <div style={{ padding: '2.5rem', textAlign: 'center', color: '#64748b' }}>
              No verification runs recorded yet.
            </div>
          ) : (
            <div>
              {runs.map((v) => {
                const isSelected = selectedRun?.id === v.id;
                const isDocker = v.sandbox_type === 'docker';
                return (
                  <div
                    key={v.id}
                    onClick={() => setSelectedRun(v)}
                    style={{
                      padding: '0.85rem 1rem',
                      borderBottom: '1px solid #334155',
                      backgroundColor: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className={`badge ${v.status === 'COMPLETED' && !v.has_regressions ? 'badge-green' : 'badge-red'}`}>
                          {v.status}
                        </span>
                        <strong className="font-mono" style={{ fontSize: '0.85rem' }}>{v.id}</strong>
                        <span className={`badge ${isDocker ? 'badge-blue' : 'badge-slate'}`}>
                          {isDocker ? 'DOCKER CONTAINER' : 'TEST DOUBLE (FAKE)'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.35rem' }}>
                        Task: <span className="font-mono">{v.task_id}</span> · Patch: <span className="font-mono">{v.patch_id}</span>
                        {v.has_regressions && <span style={{ color: '#ef4444', marginLeft: '0.5rem' }}>⚠️ Regressions Detected</span>}
                      </div>
                    </div>
                    <ChevronRight size={18} color={isSelected ? '#38bdf8' : '#64748b'} />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Evidence & Checks Details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {selectedRun ? (
            <>
              {/* Checks Card */}
              <div style={{ padding: '1.25rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
                <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 600 }}>Executed Checks</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {selectedRun.checks.map((c, i) => (
                    <div key={i} style={{ padding: '0.6rem', backgroundColor: '#0f172a', borderRadius: '0.375rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                      <span className="font-mono">{c.name || c.check_name}</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ color: '#94a3b8' }}>{c.duration_ms} ms</span>
                        <span className={`badge ${c.status === 'PASSED' ? 'badge-green' : c.status === 'FAILED' ? 'badge-red' : 'badge-slate'}`}>
                          {c.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Evidence Markdown Excerpt */}
              {evidence && (
                <div style={{ padding: '1.25rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
                  <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem', fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}>
                    <span>Evidence Report</span>
                    <span className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{evidence.report_id}</span>
                  </h3>
                  <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '0.375rem', fontSize: '0.75rem', whiteSpace: 'pre-wrap', maxHeight: '220px', overflowY: 'auto' }}>
                    {evidence.summary_markdown}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ padding: '2rem', backgroundColor: '#1e293b', borderRadius: '0.5rem', color: '#64748b' }}>
              Select a verification run to inspect its check results and evidence report.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
