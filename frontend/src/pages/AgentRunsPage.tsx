import React, { useEffect, useState } from 'react';
import { Bot, CheckCircle2, ChevronRight, Clock, Cpu, FileCode2, ShieldAlert } from 'lucide-react';
import { api } from '../services/api';
import { AgentRun } from '../types/api';

export const AgentRunsPage: React.FC = () => {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.getAgentRuns()
      .then((res) => {
        setRuns(res);
        if (res.length > 0) {
          setSelectedRun(res[0]);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
        <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>Agent Runs Explorer</h2>
        <p style={{ margin: '0.25rem 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
          Inspect autonomous analysis, planning, patch proposals, and token telemetry.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(320px, 1.2fr)', gap: '1.5rem' }}>
        {/* Runs Table */}
        <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', overflow: 'hidden' }}>
          <div style={{ padding: '0.75rem 1rem', backgroundColor: '#0f172a', borderBottom: '1px solid #334155', fontWeight: 600, fontSize: '0.85rem' }}>
            Agent Execution History ({runs.length})
          </div>
          {runs.length === 0 ? (
            <div style={{ padding: '2.5rem', textAlign: 'center', color: '#64748b' }}>
              No agent runs executed yet. Run `repocontinuum agent analyze` to trigger an agent run.
            </div>
          ) : (
            <div>
              {runs.map((r) => {
                const isSelected = selectedRun?.id === r.id;
                const isFake = r.provider === 'fake';
                return (
                  <div
                    key={r.id}
                    onClick={() => setSelectedRun(r)}
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
                        <span className={`badge ${r.status === 'VERIFICATION_PASSED' ? 'badge-green' : r.status === 'BUDGET_EXHAUSTED' ? 'badge-red' : 'badge-blue'}`}>
                          {r.status}
                        </span>
                        <strong className="font-mono" style={{ fontSize: '0.85rem' }}>{r.id}</strong>
                        <span className={`badge ${isFake ? 'badge-slate' : 'badge-purple'}`}>
                          {isFake ? 'TEST DOUBLE (FAKE)' : r.provider}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.35rem' }}>
                        Task: <span className="font-mono">{r.task_id}</span> · Tokens: {r.total_tokens} · Attempts: {r.attempt_number}/{r.max_repair_attempts}
                      </div>
                    </div>
                    <ChevronRight size={18} color={isSelected ? '#38bdf8' : '#64748b'} />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Detail Panel */}
        <div style={{ padding: '1.25rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', height: 'fit-content' }}>
          {selectedRun ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, borderBottom: '1px solid #334155', paddingBottom: '0.5rem' }}>
                Run Telemetry & Contracts
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Provider & Model</div>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{selectedRun.provider} ({selectedRun.model})</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Latency</div>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{selectedRun.latency_ms} ms</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Token Consumption</div>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{selectedRun.prompt_tokens} in / {selectedRun.completion_tokens} out</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Human Approval Gate</div>
                  <div style={{ fontSize: '0.85rem', color: selectedRun.plan_approved_by ? '#10b981' : '#f59e0b', fontWeight: 600 }}>
                    {selectedRun.plan_approved_by ? `Approved by @${selectedRun.plan_approved_by}` : 'Pending Approval'}
                  </div>
                </div>
              </div>

              {/* Task Plan Steps if available */}
              {selectedRun.task_plan_json && (
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#38bdf8', marginBottom: '0.35rem' }}>Structured Task Plan:</div>
                  <div style={{ backgroundColor: '#0f172a', padding: '0.6rem', borderRadius: '0.375rem', fontSize: '0.75rem', color: '#cbd5e1' }}>
                    <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{selectedRun.task_plan_json.objective}</div>
                    <ol style={{ margin: 0, paddingLeft: '1.2rem' }}>
                      {(selectedRun.task_plan_json.ordered_steps || []).map((st: string, idx: number) => (
                        <li key={idx}>{st}</li>
                      ))}
                    </ol>
                  </div>
                </div>
              )}

              {/* Associated Patch & Verification */}
              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Associated Patch ID</div>
                <div className="font-mono" style={{ fontSize: '0.8rem', color: '#38bdf8' }}>{selectedRun.proposed_patch_id || 'None'}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Verification Run ID</div>
                <div className="font-mono" style={{ fontSize: '0.8rem', color: '#a855f7' }}>{selectedRun.verification_run_id || 'None'}</div>
              </div>
            </div>
          ) : (
            <p style={{ color: '#64748b', fontSize: '0.85rem' }}>Select a run to view its telemetry.</p>
          )}
        </div>
      </div>
    </div>
  );
};
