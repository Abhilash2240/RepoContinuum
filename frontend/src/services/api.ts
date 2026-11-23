import {
  AgentRun,
  BenchmarkRun,
  BenchmarkSummary,
  CodeSymbol,
  DAGGraph,
  DashboardSummary,
  EvidenceReport,
  GitHubIssue,
  GitHubPullRequest,
  GitHubRepo,
  Obligation,
  PublicationApproval,
  PublicationRun,
  PublishedPullRequest,
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

  // Publication endpoints
  getApprovals: (taskId?: string) => {
    const q = taskId ? `?task_id=${encodeURIComponent(taskId)}` : '';
    return fetchJson<PublicationApproval[]>(`${API_BASE}/publications/approvals${q}`);
  },

  getApproval: (approvalId: string) =>
    fetchJson<PublicationApproval>(`${API_BASE}/publications/approvals/${encodeURIComponent(approvalId)}`),

  requestApproval: (payload: {
    task_id: string;
    chain_id: string;
    patch_id: string;
    verification_run_id: string;
    repo_owner: string;
    repo_name: string;
    target_base_branch?: string;
  }) =>
    fetchJson<PublicationApproval>(`${API_BASE}/publications/approvals/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  approvePublication: (approvalId: string, approverIdentity: string, validityHours: number = 24) =>
    fetchJson<PublicationApproval>(`${API_BASE}/publications/approvals/${encodeURIComponent(approvalId)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approver_identity: approverIdentity, validity_hours: validityHours }),
    }),

  revokeApproval: (approvalId: string, revokerIdentity: string, reason: string) =>
    fetchJson<PublicationApproval>(`${API_BASE}/publications/approvals/${encodeURIComponent(approvalId)}/revoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ revoker_identity: revokerIdentity, reason: reason }),
    }),

  publishApprovedPatch: (approvalId: string, requireRealSandbox: boolean = false) =>
    fetchJson<PublishedPullRequest>(`${API_BASE}/publications/approvals/${encodeURIComponent(approvalId)}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ require_real_sandbox: requireRealSandbox }),
    }),

  getPublicationRuns: (approvalId?: string) => {
    const q = approvalId ? `?approval_id=${encodeURIComponent(approvalId)}` : '';
    return fetchJson<PublicationRun[]>(`${API_BASE}/publications/runs${q}`);
  },

  getPublishedPullRequests: () =>
    fetchJson<PublishedPullRequest[]>(`${API_BASE}/publications/pull-requests`),

  // Benchmark endpoints
  getBenchmarkSummary: () =>
    fetchJson<BenchmarkSummary>(`${API_BASE}/benchmarks/summary`),

  getBenchmarkReport: () =>
    fetchJson<{ markdown: string }>(`${API_BASE}/benchmarks/report`),

  getBenchmarkRuns: () =>
    fetchJson<BenchmarkRun[]>(`${API_BASE}/benchmarks/runs`),

  triggerBenchmark: (baseline: string = 'all', seed: number = 42) =>
    fetchJson<BenchmarkSummary>(`${API_BASE}/benchmarks/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ baseline, seed }),
    }),
};
