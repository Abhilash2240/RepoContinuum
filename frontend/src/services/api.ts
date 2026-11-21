import {
  AgentRun,
  CodeSymbol,
  DAGGraph,
  DashboardSummary,
  EvidenceReport,
  GitHubIssue,
  GitHubPullRequest,
  GitHubRepo,
  Obligation,
  RepositorySummary,
  TaskChainSummary,
  VerificationRun,
} from '../types/api';

const API_BASE = '/api/v1';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const errorText = await resp.text();
    throw new Error(`API Error [${resp.status}]: ${errorText || resp.statusText}`);
  }
  return resp.json();
}

export const api = {
  getDashboardSummary: () => fetchJson<DashboardSummary>(`${API_BASE}/dashboard/summary`),

  getRepositories: () => fetchJson<RepositorySummary[]>(`${API_BASE}/repositories`),

  getRepositoryIndex: (repoId: string, path?: string) => {
    const q = path ? `?path=${encodeURIComponent(path)}` : '';
    return fetchJson<any>(`${API_BASE}/repositories/${encodeURIComponent(repoId)}/index${q}`);
  },

  searchSymbols: (repoId: string, query: string, kind?: string, path?: string) => {
    const params = new URLSearchParams({ query });
    if (kind) params.append('kind', kind);
    if (path) params.append('path', path);
    return fetchJson<CodeSymbol[]>(`${API_BASE}/repositories/${encodeURIComponent(repoId)}/symbols?${params.toString()}`);
  },

  getTaskChains: () => fetchJson<TaskChainSummary[]>(`${API_BASE}/chains`),

  getTaskChainDetails: (chainId: string) => fetchJson<any>(`${API_BASE}/chains/${encodeURIComponent(chainId)}`),

  getTaskChainGraph: (chainId: string) => fetchJson<DAGGraph>(`${API_BASE}/chains/${encodeURIComponent(chainId)}/graph`),

  getTaskChainObligations: (chainId: string) =>
    fetchJson<Obligation[]>(`${API_BASE}/chains/${encodeURIComponent(chainId)}/obligations`),

  importGitHubIssue: (chainId: string, owner: string, repo: string, issueNumber: number, criterion?: string) =>
    fetchJson<any>(`${API_BASE}/chains/${encodeURIComponent(chainId)}/tasks/import-github-issue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        owner,
        repo,
        issue_number: issueNumber,
        acceptance_criterion: criterion,
      }),
    }),

  getAgentRuns: (taskId?: string) => {
    const q = taskId ? `?task_id=${encodeURIComponent(taskId)}` : '';
    return fetchJson<AgentRun[]>(`${API_BASE}/agent-runs${q}`);
  },

  getAgentRun: (runId: string) => fetchJson<AgentRun>(`${API_BASE}/agent-runs/${encodeURIComponent(runId)}`),

  getVerificationRuns: () => fetchJson<VerificationRun[]>(`${API_BASE}/verification-runs`),

  getVerificationRun: (runId: string) => fetchJson<VerificationRun>(`${API_BASE}/verification-runs/${encodeURIComponent(runId)}`),

  getVerificationEvidence: (runId: string) =>
    fetchJson<EvidenceReport>(`${API_BASE}/verification-runs/${encodeURIComponent(runId)}/evidence`),

  getGitHubStatus: () => fetchJson<any>(`${API_BASE}/github/status`),

  getGitHubRepositories: () => fetchJson<GitHubRepo[]>(`${API_BASE}/github/repositories`),

  getGitHubIssues: (owner: string, repo: string, state: string = 'open') =>
    fetchJson<GitHubIssue[]>(`${API_BASE}/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/issues?state=${state}`),

  getGitHubIssue: (owner: string, repo: string, number: number) =>
    fetchJson<GitHubIssue>(`${API_BASE}/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/issues/${number}`),

  getGitHubPullRequests: (owner: string, repo: string, state: string = 'open') =>
    fetchJson<GitHubPullRequest[]>(`${API_BASE}/github/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/pulls?state=${state}`),
};
