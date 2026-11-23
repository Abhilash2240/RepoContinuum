import React from 'react';
import {
  LayoutDashboard,
  FolderGit2,
  GitFork,
  ShieldCheck,
  Bot,
  FileCheck2,
  Github,
  GitPullRequest,
  BarChart3,
} from 'lucide-react';

export type NavTab =
  | 'overview'
  | 'repositories'
  | 'task-chains'
  | 'obligations'
  | 'agent-runs'
  | 'verification'
  | 'github'
  | 'publication'
  | 'benchmarks';

interface NavigationProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  githubConnected: boolean;
}

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onSelectTab, githubConnected }) => {
  const items: Array<{ id: NavTab; label: string; icon: React.ReactNode }> = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={18} /> },
    { id: 'repositories', label: 'Repository Explorer', icon: <FolderGit2 size={18} /> },
    { id: 'task-chains', label: 'Task Chains & DAG', icon: <GitFork size={18} /> },
    { id: 'obligations', label: 'Obligation Ledger', icon: <ShieldCheck size={18} /> },
    { id: 'agent-runs', label: 'Agent Runs', icon: <Bot size={18} /> },
    { id: 'verification', label: 'Patches & Verification', icon: <FileCheck2 size={18} /> },
    {
      id: 'github',
      label: 'GitHub Read',
      icon: (
        <span style={{ position: 'relative', display: 'inline-flex' }}>
          <Github size={18} />
          {githubConnected && (
            <span
              style={{
                position: 'absolute',
                top: -2,
                right: -2,
                width: 7,
                height: 7,
                borderRadius: '50%',
                backgroundColor: '#10b981',
              }}
            />
          )}
        </span>
      ),
    },
    { id: 'publication', label: 'PR Publishing', icon: <GitPullRequest size={18} /> },
    { id: 'benchmarks', label: 'Benchmarks', icon: <BarChart3 size={18} /> },
  ];

  return (
    <nav style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
      {items.map((item) => {
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onSelectTab(item.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.5rem 0.85rem',
              borderRadius: '0.375rem',
              border: isActive ? '1px solid #38bdf8' : '1px solid transparent',
              backgroundColor: isActive ? 'rgba(56, 189, 248, 0.12)' : '#0f172a',
              color: isActive ? '#38bdf8' : '#94a3b8',
              fontWeight: isActive ? 600 : 500,
              fontSize: '0.875rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            {item.icon}
            {item.label}
          </button>
        );
      })}
    </nav>
  );
};
