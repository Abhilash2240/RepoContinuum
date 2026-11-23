import React, { useEffect, useState } from 'react';
import { NavTab, Navigation } from './components/Navigation';
import { OverviewPage } from './pages/OverviewPage';
import { RepositoriesPage } from './pages/RepositoriesPage';
import { TaskChainsPage } from './pages/TaskChainsPage';
import { ObligationsPage } from './pages/ObligationsPage';
import { AgentRunsPage } from './pages/AgentRunsPage';
import { VerificationViewerPage } from './pages/VerificationViewerPage';
import { GitHubExplorerPage } from './pages/GitHubExplorerPage';
import { PublicationReviewPage } from './pages/PublicationReviewPage';
import { BenchmarkDashboardPage } from './pages/BenchmarkDashboardPage';
import { api } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('overview');
  const [githubConnected, setGithubConnected] = useState(false);

  useEffect(() => {
    api.getGitHubStatus()
      .then((st) => setGithubConnected(Boolean(st.connected)))
      .catch(() => setGithubConnected(false));
  }, []);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Header */}
      <header
        style={{
          borderBottom: '1px solid #1e293b',
          backgroundColor: '#090d16',
          padding: '0.85rem 1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          position: 'sticky',
          top: 0,
          zIndex: 40,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: '0.375rem',
              backgroundColor: '#38bdf8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#090d16',
              fontWeight: 800,
              fontSize: '1.1rem',
            }}
          >
            RC
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, letterSpacing: '-0.025em' }}>
              RepoContinuum
            </h1>
            <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
              Maintenance Agent Dashboard · Milestone 6 (Final)
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.8rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#10b981' }} />
            <span style={{ color: '#94a3b8' }}>API Online (127.0.0.1:8000)</span>
          </div>
          <span className="badge badge-purple font-mono">v1.0.0</span>
        </div>
      </header>

      {/* Navigation Bar */}
      <div style={{ borderBottom: '1px solid #1e293b', backgroundColor: '#090d16', padding: '0.5rem 1.5rem' }}>
        <Navigation activeTab={activeTab} onSelectTab={setActiveTab} githubConnected={githubConnected} />
      </div>

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: '1.5rem', maxWidth: '1440px', width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>
        {activeTab === 'overview' && <OverviewPage onNavigate={setActiveTab} />}
        {activeTab === 'repositories' && <RepositoriesPage />}
        {activeTab === 'task-chains' && <TaskChainsPage />}
        {activeTab === 'obligations' && <ObligationsPage />}
        {activeTab === 'agent-runs' && <AgentRunsPage />}
        {activeTab === 'verification' && <VerificationViewerPage />}
        {activeTab === 'github' && <GitHubExplorerPage />}
        {activeTab === 'publication' && <PublicationReviewPage />}
        {activeTab === 'benchmarks' && <BenchmarkDashboardPage />}
      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid #1e293b', padding: '1rem 1.5rem', textAlign: 'center', fontSize: '0.75rem', color: '#64748b' }}>
        RepoContinuum · Local-first, repository-aware software maintenance agent · Approved PR Publishing & Benchmark Evaluation
      </footer>
    </div>
  );
};
