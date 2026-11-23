import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  GitBranch,
  GitPullRequest,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  XCircle,
} from 'lucide-react';
import { api } from '../services/api';
import { PublicationApproval, PublishedPullRequest } from '../types/api';

export const PublicationReviewPage: React.FC = () => {
  const [approvals, setApprovals] = useState<PublicationApproval[]>([]);
  const [publishedPRs, setPublishedPRs] = useState<PublishedPullRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedApproval, setSelectedApproval] = useState<PublicationApproval | null>(null);
  const [approverName, setApproverName] = useState('senior-maintainer');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [apps, prs] = await Promise.all([
        api.getApprovals(),
        api.getPublishedPullRequests(),
      ]);
      setApprovals(apps);
      setPublishedPRs(prs);
      if (apps.length > 0 && !selectedApproval) {
        setSelectedApproval(apps[0]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load publication records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApprove = async () => {
    if (!selectedApproval) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const updated = await api.approvePublication(selectedApproval.id, approverName, 24);
      setSelectedApproval(updated);
      setActionMessage('✓ Human approval granted successfully.');
      await loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async () => {
    if (!selectedApproval) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const updated = await api.revokeApproval(selectedApproval.id, approverName, 'Reviewer requested revision');
      setSelectedApproval(updated);
      setActionMessage('✓ Approval revoked.');
      await loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!selectedApproval) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const pr = await api.publishApprovedPatch(selectedApproval.id, false);
      setActionMessage(`✓ PR #${pr.pr_number} successfully published to ${pr.html_url}`);
      await loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>
            Approved Pull-Request Publishing
          </h2>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>
            Human-gated GitHub publishing with cryptographic patch binding, least-privilege tokens, and zero auto-merge.
          </p>
        </div>
        <button
          onClick={loadData}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.5rem 0.85rem',
            background: '#1e293b',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: '0.375rem',
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', background: '#450a0a', border: '1px solid #991b1b', borderRadius: '0.5rem', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {actionMessage && (
        <div style={{ padding: '0.75rem 1rem', background: '#064e3b', border: '1px solid #059669', borderRadius: '0.5rem', color: '#a7f3d0' }}>
          {actionMessage}
        </div>
      )}

      {/* Main Split Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1.5rem' }}>
        {/* Left Column: Approval Records List */}
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #334155', fontWeight: 600, fontSize: '0.85rem', backgroundColor: '#0f172a' }}>
            Publication Requests ({approvals.length})
          </div>

          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>Loading approvals...</div>
          ) : approvals.length === 0 ? (
            <div style={{ padding: '2.5rem', textAlign: 'center', color: '#64748b' }}>
              <GitPullRequest size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
              <p style={{ margin: 0 }}>No publication approvals found.</p>
              <p style={{ fontSize: '0.75rem', margin: '0.25rem 0 0' }}>Request approval via CLI or task verification view.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {approvals.map((app) => {
                const isSelected = selectedApproval?.id === app.id;
                let badgeClass = 'badge-slate';
                if (app.status === 'APPROVED') badgeClass = 'badge-green';
                if (app.status === 'PR_CREATED') badgeClass = 'badge-purple';
                if (app.status === 'INVALIDATED' || app.status === 'CANCELLED') badgeClass = 'badge-red';

                return (
                  <div
                    key={app.id}
                    onClick={() => setSelectedApproval(app)}
                    style={{
                      padding: '0.85rem 1rem',
                      borderBottom: '1px solid #334155',
                      cursor: 'pointer',
                      backgroundColor: isSelected ? '#1e293b' : 'transparent',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="font-mono" style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8' }}>
                        {app.id}
                      </span>
                      <span className={`badge ${badgeClass}`}>{app.status}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, marginTop: '0.35rem', color: '#f8fafc' }}>
                      Task: {app.task_id}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                      Repo: {app.repository_id} · Base: {app.target_base_branch}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Selected Approval Inspector */}
        <div className="card" style={{ padding: 0 }}>
          {selectedApproval ? (
            <div>
              {/* Header */}
              <div style={{ padding: '1rem', borderBottom: '1px solid #334155', backgroundColor: '#0f172a', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                    Approval: {selectedApproval.id}
                  </h3>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                    Created at {new Date(selectedApproval.created_at).toLocaleString()}
                  </div>
                </div>
                <span className="badge badge-blue">{selectedApproval.status}</span>
              </div>

              {/* Binding Manifest Table */}
              <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.75rem' }}>
                  <div style={{ background: '#090d16', padding: '0.65rem 0.85rem', borderRadius: '0.375rem', border: '1px solid #1e293b' }}>
                    <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Target Repository</div>
                    <div className="font-mono" style={{ fontSize: '0.8rem', color: '#38bdf8', fontWeight: 600 }}>{selectedApproval.repository_id}</div>
                  </div>
                  <div style={{ background: '#090d16', padding: '0.65rem 0.85rem', borderRadius: '0.375rem', border: '1px solid #1e293b' }}>
                    <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Target Base Branch</div>
                    <div className="font-mono" style={{ fontSize: '0.8rem', color: '#f8fafc', fontWeight: 600 }}>{selectedApproval.target_base_branch}</div>
                  </div>
                  <div style={{ background: '#090d16', padding: '0.65rem 0.85rem', borderRadius: '0.375rem', border: '1px solid #1e293b' }}>
                    <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Base Commit SHA</div>
                    <div className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{selectedApproval.base_commit_sha}</div>
                  </div>
                  <div style={{ background: '#090d16', padding: '0.65rem 0.85rem', borderRadius: '0.375rem', border: '1px solid #1e293b' }}>
                    <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Proposed Head Branch</div>
                    <div className="font-mono" style={{ fontSize: '0.75rem', color: '#a855f7' }}>{selectedApproval.proposed_head_branch}</div>
                  </div>
                </div>

                {/* Cryptographic SHA Binding */}
                <div style={{ background: '#090d16', padding: '0.75rem', borderRadius: '0.375rem', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <ShieldCheck size={14} color="#10b981" />
                    <strong>Cryptographic Patch Binding (SHA-256):</strong>
                  </div>
                  <div className="font-mono" style={{ fontSize: '0.75rem', color: '#f8fafc', wordBreak: 'break-all', marginTop: '0.25rem' }}>
                    {selectedApproval.patch_hash}
                  </div>
                </div>

                {/* Verification Run & Evidence Link */}
                <div style={{ background: '#090d16', padding: '0.75rem', borderRadius: '0.375rem', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Verification Run & Evidence:</div>
                  <div style={{ fontSize: '0.8rem', marginTop: '0.25rem', display: 'flex', gap: '1rem' }}>
                    <span>Run ID: <code style={{ color: '#38bdf8' }}>{selectedApproval.verification_run_id}</code></span>
                    <span>Report ID: <code style={{ color: '#a855f7' }}>{selectedApproval.verification_report_id}</code></span>
                  </div>
                </div>

                {/* Approver Details */}
                {selectedApproval.approver_identity && (
                  <div style={{ padding: '0.75rem', background: '#064e3b', border: '1px solid #059669', borderRadius: '0.375rem', color: '#a7f3d0', fontSize: '0.8rem' }}>
                    <strong>Authorized by:</strong> {selectedApproval.approver_identity} at {new Date(selectedApproval.approved_at || '').toLocaleString()}
                    {selectedApproval.expires_at && <span> (valid until {new Date(selectedApproval.expires_at).toLocaleString()})</span>}
                  </div>
                )}

                {/* Invalidation Reason */}
                {selectedApproval.invalidation_reason && (
                  <div style={{ padding: '0.75rem', background: '#450a0a', border: '1px solid #991b1b', borderRadius: '0.375rem', color: '#fca5a5', fontSize: '0.8rem' }}>
                    <strong>Invalidation Reason:</strong> {selectedApproval.invalidation_reason}
                  </div>
                )}

                {/* Action Buttons */}
                <div style={{ borderTop: '1px solid #334155', paddingTop: '1rem', marginTop: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  {selectedApproval.status === 'AWAITING_APPROVAL' && (
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', width: '100%' }}>
                      <input
                        type="text"
                        value={approverName}
                        onChange={(e) => setApproverName(e.target.value)}
                        placeholder="Approver identity"
                        style={{ padding: '0.5rem', background: '#090d16', border: '1px solid #334155', color: '#f8fafc', borderRadius: '0.375rem', fontSize: '0.8rem' }}
                      />
                      <button
                        onClick={handleApprove}
                        disabled={actionLoading}
                        style={{ padding: '0.5rem 1rem', background: '#10b981', color: '#090d16', border: 'none', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
                      >
                        <UserCheck size={14} style={{ display: 'inline', marginRight: 4 }} /> Grant Human Approval
                      </button>
                    </div>
                  )}

                  {selectedApproval.status === 'APPROVED' && (
                    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                      <button
                        onClick={handlePublish}
                        disabled={actionLoading}
                        style={{ padding: '0.6rem 1.25rem', background: '#38bdf8', color: '#090d16', border: 'none', borderRadius: '0.375rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                      >
                        <Send size={15} /> Publish Pull Request to GitHub
                      </button>
                      <button
                        onClick={handleRevoke}
                        disabled={actionLoading}
                        style={{ padding: '0.6rem 1rem', background: '#dc2626', color: '#f8fafc', border: 'none', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
                      >
                        Revoke Approval
                      </button>
                    </div>
                  )}

                  {selectedApproval.status === 'PR_CREATED' && (
                    <div style={{ color: '#a855f7', fontSize: '0.85rem', fontWeight: 600 }}>
                      ✓ Pull Request has been created on GitHub.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
              Select an approval request to inspect its binding metadata and authorize publication.
            </div>
          )}
        </div>
      </div>

      {/* Published Pull Requests History Table */}
      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '0.85rem 1.25rem', borderBottom: '1px solid #334155', backgroundColor: '#0f172a', fontWeight: 600, fontSize: '0.9rem' }}>
          Published Pull Requests ({publishedPRs.length})
        </div>
        {publishedPRs.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
            No published pull requests recorded yet.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>PR #</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Title</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Branch Pair</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Head SHA</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Published At</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {publishedPRs.map((pr) => (
                  <tr key={pr.id} style={{ borderBottom: '1px solid #1e293b' }}>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 700, color: '#38bdf8' }}>
                      #{pr.pr_number}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#f8fafc', fontWeight: 600 }}>
                      {pr.title}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <code style={{ color: '#a855f7' }}>{pr.head_branch}</code> → <code style={{ color: '#94a3b8' }}>{pr.base_branch}</code>
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <code className="font-mono">{pr.head_sha.slice(0, 10)}</code>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#64748b' }}>
                      {new Date(pr.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <a
                        href={pr.html_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: '#38bdf8', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                      >
                        GitHub <ExternalLink size={12} />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
