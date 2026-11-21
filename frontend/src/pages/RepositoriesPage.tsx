import React, { useEffect, useState } from 'react';
import { FileCode, Folder, Hash, Search, Terminal } from 'lucide-react';
import { api } from '../services/api';
import { CodeSymbol, RepositorySummary } from '../types/api';

export const RepositoriesPage: React.FC = () => {
  const [repos, setRepos] = useState<RepositorySummary[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [symbols, setSymbols] = useState<CodeSymbol[]>([]);
  const [indexSnapshot, setIndexSnapshot] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getRepositories().then((res) => {
      setRepos(res);
      if (res.length > 0) {
        setSelectedRepo(res[0].repository_id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedRepo) return;
    setLoading(true);
    api.getRepositoryIndex(selectedRepo)
      .then((snap) => setIndexSnapshot(snap))
      .catch(() => setIndexSnapshot(null))
      .finally(() => setLoading(false));
  }, [selectedRepo]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepo || !searchQuery.trim()) return;
    try {
      const results = await api.searchSymbols(selectedRepo, searchQuery);
      setSymbols(results);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header and Repo Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>Repository Explorer</h2>
          <p style={{ margin: '0.25rem 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
            Inspect AST intelligence, symbols, and test inventory without host code execution.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Repository:</label>
          <select
            value={selectedRepo}
            onChange={(e) => setSelectedRepo(e.target.value)}
            style={{ padding: '0.4rem 0.8rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.375rem', color: '#f8fafc', fontSize: '0.875rem' }}
          >
            {repos.map((r) => (
              <option key={r.repository_id} value={r.repository_id}>
                {r.repository_id} ({r.chain_count} chains)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Snapshot Summary if loaded */}
      {indexSnapshot && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
          <div style={{ padding: '1rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
            <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Commit SHA</div>
            <div className="font-mono" style={{ fontSize: '0.9rem', color: '#38bdf8', marginTop: '0.25rem' }}>
              {indexSnapshot.commit_sha ? indexSnapshot.commit_sha.slice(0, 10) : 'HEAD'}
            </div>
          </div>
          <div style={{ padding: '1rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
            <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Indexed Python Files</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>
              {indexSnapshot.summary?.indexed_python_files || indexSnapshot.summary?.total_files || 0}
            </div>
          </div>
          <div style={{ padding: '1rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
            <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Extracted Symbols</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>
              {(indexSnapshot.summary?.total_classes || 0) + (indexSnapshot.summary?.total_functions || 0) + (indexSnapshot.summary?.total_methods || 0)}
            </div>
          </div>
          <div style={{ padding: '1rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}>
            <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Test Cases</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>
              {indexSnapshot.summary?.total_test_cases || 0}
            </div>
          </div>
        </div>
      )}

      {/* Symbol Search Form */}
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={18} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
          <input
            type="text"
            placeholder="Search code symbols by function or class name (e.g. multiply, subtract)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '0.6rem 0.75rem 0.6rem 2.25rem',
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '0.375rem',
              color: '#f8fafc',
              fontSize: '0.875rem',
              boxSizing: 'border-box',
            }}
          />
        </div>
        <button
          type="submit"
          style={{ padding: '0.6rem 1.25rem', backgroundColor: '#38bdf8', color: '#090d16', border: 'none', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
        >
          Search
        </button>
      </form>

      {/* Results List */}
      <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', overflow: 'hidden' }}>
        <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #334155', backgroundColor: '#0f172a', fontWeight: 600, fontSize: '0.85rem' }}>
          Symbol Results {symbols.length > 0 && `(${symbols.length} matches)`}
        </div>
        {symbols.length === 0 ? (
          <div style={{ padding: '2.5rem', textAlign: 'center', color: '#64748b' }}>
            <FileCode size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
            <p style={{ margin: 0 }}>Type a query and press Search to discover indexed functions and classes.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {symbols.map((s, idx) => (
              <div key={idx} style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="badge badge-blue">{s.kind}</span>
                    <strong className="font-mono" style={{ color: '#f8fafc' }}>{s.name}</strong>
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>in {s.file_path}</span>
                  </div>
                  {s.docstring && (
                    <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>{s.docstring}</p>
                  )}
                </div>
                <div className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  Lines {s.start_line}–{s.end_line}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
