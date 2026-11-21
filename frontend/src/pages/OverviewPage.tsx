import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock,
  FolderGit2,
  GitFork,
  Github,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { api } from '../services/api';
import { DashboardSummary } from '../types/api';

export const OverviewPage: React.FC<{ onNavigate: (tab: any) => void }> = ({ onNavigate }) => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getDashboardSummary();
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard summary.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: '#94a3b8' }}>
        <RefreshCw size={28} className="animate-spin" style={{ margin: '0 auto 1rem' }} />
        <p>Loading real-time engineering metrics from canonical storage...</p>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div style={{ padding: '2rem', backgroundColor: '#1e293b', borderRadius: '0.5rem', border: '1px solid #ef4444' }}>
        <h3 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <AlertTriangle size={20} /> Error Loading Dashboard
        </h3>
        <p style={{ color: '#94a3b8' }}>{error}</p>
        <button onClick={loadData} style={{ marginTop: '1rem', padding: '0.5rem 1rem', background: '#38bdf8', border: 'none', borderRadius: '0.375rem', cursor: 'pointer', fontWeight: 600 }}>
          Retry
        </button>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    COMPLETED: '#10b981',
    VERIFICATION_PASSED: '#10b981',
    IN_PROGRESS: '#38bdf8',
    READY: '#06b6d4',
    PLANNED: '#a855f7',
    CREATED: '#64748b',
    BLOCKED: '#f59e0b',
    FAILED: '#ef4444',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner: Regression Warning if any */}
      {summary.regressions_detected_recent > 0 && (
        <div style={{ padding: '1rem 1.25rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', borderRadius: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <ShieldAlert size={22} color="#ef4444" />
          <div>
            <strong style={{ color: '#f87171' }}>Regression Detected!</strong>
            <p style={{ margin: 0, fontSize: '0.875rem', color: '#fca5a5' }}>
              {summary.regressions_detected_recent} recent verification run broke earlier acceptance obligations. Inspect the verification viewer for failure evidence.
            </p>
          </div>
        </div>
      )}

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <div style={{ padding: '1.25rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.85rem' }}>
            <span>Task Chains</span>
            <GitFork size={18} color="#38bdf8" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, marginTop: '0.5rem' }}>{summary.total_chains}</div>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>{summary.registered_repositories.length} registered repositories</div>
        </div>

        <div style={{ padding: '1.25rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.85rem' }}>
            <span>Total Tasks</span>
            <CheckCircle2 size={18} color="#10b981" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, marginTop: '0.5rem' }}>{summary.total_tasks}</div>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
            {summary.task_status_counts['COMPLETED'] || 0} completed · {summary.task_status_counts['BLOCKED'] || 0} blocked
          </div>
        </div>

        <div style={{ padding: '1.25rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.85rem' }}>
            <span>Active Obligations</span>
            <ShieldCheck size={18} color="#06b6d4" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, marginTop: '0.5rem', color: '#38bdf8' }}>{summary.active_obligations}</div>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
            {summary.superseded_obligations} superseded · {summary.withdrawn_obligations} withdrawn
          </div>
        </div>

        <div style={{ padding: '1.25rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.85rem' }}>
            <span>Recent Agent Runs</span>
            <Bot size={18} color="#a855f7" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, marginTop: '0.5rem' }}>{summary.recent_agent_runs_count}</div>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>{summary.recent_verification_runs_count} verification runs</div>
        </div>
      </div>

      {/* Two Column Layout: Task Status Breakdown + GitHub Sync Status */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
        {/* Task Status Breakdown */}
        <div style={{ padding: '1.5rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>Maintenance Task Lifecycle</span>
            <button onClick={() => onNavigate('task-chains')} style={{ background: 'none', border: 'none', color: '#38bdf8', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              View DAG <ArrowRight size={14} />
            </button>
          </h3>

          {summary.total_tasks === 0 ? (
            <p style={{ color: '#64748b', fontSize: '0.875rem' }}>No maintenance tasks created yet. Create a task chain or import a GitHub issue to begin.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {Object.entries(summary.task_status_counts).map(([st, cnt]) => {
                const pct = Math.round((cnt / summary.total_tasks) * 100);
                const color = statusColors[st] || '#94a3b8';
                return (
                  <div key={st}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.25rem' }}>
                      <span style={{ fontWeight: 500 }}>{st}</span>
                      <span style={{ color: '#94a3b8' }}>{cnt} ({pct}%)</span>
                    </div>
                    <div style={{ height: '6px', backgroundColor: '#0f172a', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{ width: `${pct}%`, height: '100%', backgroundColor: color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* GitHub Sync Status Card */}
        <div style={{ padding: '1.5rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Github size={18} /> GitHub Read Integration
            </span>
            <button onClick={() => onNavigate('github')} style={{ background: 'none', border: 'none', color: '#38bdf8', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              Explorer <ArrowRight size={14} />
            </button>
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#94a3b8' }}>Connection State:</span>
              <span className={`badge ${summary.github.connected ? 'badge-green' : 'badge-amber'}`}>
                {summary.github.connected ? 'Connected' : 'Offline / Standalone'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#94a3b8' }}>Adapter Mode:</span>
              <span className="badge badge-purple font-mono">{summary.github.mode}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#94a3b8' }}>Permissions:</span>
              <span style={{ fontSize: '0.8rem', color: '#38bdf8' }}>Strictly Read-Only (0 writes)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#94a3b8' }}>Webhook HMAC Verification:</span>
              <span className="badge badge-green">Enforced</span>
            </div>
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.75rem', color: '#64748b', lineHeight: 1.5 }}>
              GitHub App credentials allow reading issues, discussions, and pull requests into untrusted maintenance tasks. No branches, PRs, or merges can be initiated from this interface.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
