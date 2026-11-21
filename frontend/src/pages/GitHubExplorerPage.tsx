import React, { useEffect, useState } from 'react';
import { Download, FolderGit2, GitPullRequest, Github, MessageSquare, RefreshCw, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';
import { GitHubIssue, GitHubPullRequest, GitHubRepo, TaskChainSummary } from '../types/api';

export const GitHubExplorerPage: React.FC = () => {
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [tab, setTab] = useState<'issues' | 'pulls'>('issues');
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [pulls, setPulls] = useState<GitHubPullRequest[]>([]);
  const [chains, setChains] = useState<TaskChainSummary[]>([]);
  const [selectedChainId, setSelectedChainId] = useState<string>('');
  const [importingIssue, setImportingIssue] = useState<GitHubIssue | null>(null);
  const [importNotice, setImportNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getGitHubRepositories().then((res) => {
      setRepos(res);
      if (res.length > 0) {
        setSelectedRepo(res[0].full_name);
      }
    });
    api.getTaskChains().then((res) => {
      setChains(res);
      if (res.length > 0) {
        setSelectedChainId(res[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedRepo) return;
    const [owner, name] = selectedRepo.split('/');
    setLoading(true);
    if (tab === 'issues') {
      api.getGitHubIssues(owner, name)
        .then((res) => setIssues(res))
        .catch((err) => console.error(err))
        .finally(() => setLoading(false));
    } else {
      api.getGitHubPullRequests(owner, name)
        .then((res) => setPulls(res))
        .catch((err) => console.error(err))
        .finally(() => setLoading(false));
    }
  }, [selectedRepo, tab]);

  const handleImport = async () => {
    if (!importingIssue || !selectedChainId || !selectedRepo) return;
    const [owner, name] = selectedRepo.split('/');
    try {
      await api.importGitHubIssue(selectedChainId, owner, name, importingIssue.number);
      setImportNotice(`Successfully imported Issue #${importingIssue.number} into task chain ${selectedChainId}`);
      setImportingIssue(null);
    } catch (err: any) {
      alert(`Import failed: ${err.message}`);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Github size={22} /> GitHub Read-Only Explorer
          </h2>
          <p style={{ margin: '0.25rem 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
            Synchronize issues and pull requests as untrusted data into RepoContinuum maintenance tasks.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <select
            value={selectedRepo}
            onChange={(e) => setSelectedRepo(e.target.value)}
            style={{ padding: '0.4rem 0.8rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.375rem', color: '#f8fafc', fontSize: '0.875rem' }}
          >
            {repos.map((r) => (
              <option key={r.full_name} value={r.full_name}>
                {r.full_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {importNotice && (
        <div style={{ padding: '0.75rem 1rem', backgroundColor: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', borderRadius: '0.375rem', color: '#34d399', fontSize: '0.85rem' }}>
          {importNotice}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid #334155', paddingBottom: '0.5rem' }}>
        <button
          onClick={() => setTab('issues')}
          style={{ padding: '0.4rem 0.8rem', background: tab === 'issues' ? '#38bdf8' : 'transparent', color: tab === 'issues' ? '#090d16' : '#94a3b8', border: 'none', borderRadius: '0.25rem', fontWeight: 600, cursor: 'pointer' }}
        >
          Issues
        </button>
        <button
          onClick={() => setTab('pulls')}
          style={{ padding: '0.4rem 0.8rem', background: tab === 'pulls' ? '#38bdf8' : 'transparent', color: tab === 'pulls' ? '#090d16' : '#94a3b8', border: 'none', borderRadius: '0.25rem', fontWeight: 600, cursor: 'pointer' }}
        >
          Pull Requests
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>
          <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem' }} />
          <p>Fetching from GitHub...</p>
        </div>
      ) : tab === 'issues' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {issues.map((i) => (
            <div key={i.id} style={{ padding: '1rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className="badge badge-green">#{i.number}</span>
                  <strong style={{ fontSize: '0.95rem' }}>{i.title}</strong>
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.35rem' }}>
                  By @{i.user?.login || 'unknown'} · {i.comments_count} comments
                </div>
                {i.body && (
                  <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: '#94a3b8', maxHeight: '60px', overflow: 'hidden' }}>{i.body}</p>
                )}
              </div>
              <button
                onClick={() => setImportingIssue(i)}
                style={{ padding: '0.4rem 0.8rem', backgroundColor: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid #38bdf8', borderRadius: '0.375rem', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', whiteSpace: 'nowrap' }}
              >
                <Download size={14} /> Import to Task
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {pulls.map((p) => (
            <div key={p.id} style={{ padding: '1rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span className="badge badge-purple">PR #{p.number}</span>
                <strong style={{ fontSize: '0.95rem' }}>{p.title}</strong>
                {p.draft && <span className="badge badge-slate">Draft</span>}
              </div>
              <div className="font-mono" style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.35rem' }}>
                {p.head_ref} ({p.head_sha.slice(0, 8)}) → {p.base_ref}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Import Modal */}
      {importingIssue && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
          <div style={{ width: '100%', maxWidth: '480px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Import Issue #{importingIssue.number} into Chain</h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8' }}>
              Issue will be wrapped inside untrusted data tags and appended to the selected task chain.
            </p>
            <div>
              <label style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Target Task Chain:</label>
              <select
                value={selectedChainId}
                onChange={(e) => setSelectedChainId(e.target.value)}
                style={{ width: '100%', marginTop: '0.25rem', padding: '0.5rem', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '0.375rem', color: '#f8fafc' }}
              >
                {chains.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title} ({c.id})
                  </option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }}>
              <button
                onClick={() => setImportingIssue(null)}
                style={{ padding: '0.5rem 1rem', background: '#334155', color: '#f8fafc', border: 'none', borderRadius: '0.375rem', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleImport}
                style={{ padding: '0.5rem 1rem', background: '#38bdf8', color: '#090d16', border: 'none', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
              >
                Confirm Import
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
