export interface DashboardSummary {
  total_chains: number;
  total_tasks: number;
  task_status_counts: Record<string, number>;
  total_obligations: number;
  active_obligations: number;
  superseded_obligations: number;
  withdrawn_obligations: number;
  recent_agent_runs_count: number;
  recent_verification_runs_count: number;
  regressions_detected_recent: number;
  registered_repositories: string[];
  github: {
    configured: boolean;
    mode: string;
    connected: boolean;
    installation_id?: number;
    authenticated?: boolean;
    permissions?: Record<string, string>;
    error?: string;
  };
}

export interface RepositorySummary {
  repository_id: string;
  chain_count: number;
  status: string;
}

export interface CodeSymbol {
  name: string;
  qualified_name: string;
  kind: string;
  file_path: string;
  start_line: number;
  end_line: number;
  docstring?: string | null;
}

export interface TaskChainSummary {
  id: string;
  repository_id: string;
  title: string;
  description: string;
  status: string;
  task_count: number;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceTask {
  id: string;
  chain_id: string;
  title: string;
  description: string;
  status: string;
  order_index: number;
  acceptance_criteria?: string[];
  candidate_files?: string[];
  candidate_symbols?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface DAGNode {
  id: string;
  title: string;
  description: string;
  status: string;
  order_index: number;
  acceptance_criteria?: string[];
  is_blocked: boolean;
  unmet_predecessors: string[];
}

export interface DAGEdge {
  id: string;
  from: string;
  to: string;
  source: string;
}

export interface DAGGraph {
  chain_id: string;
  is_valid: boolean;
  topological_order: string[];
  nodes: DAGNode[];
  edges: DAGEdge[];
  blocked_tasks: Record<string, string[]>;
}

export interface Obligation {
  id: string;
  chain_id: string;
  source_task_id: string;
  description: string;
  status: 'ACTIVE' | 'SUPERSEDED' | 'WITHDRAWN';
  verifier_ref?: string;
  status_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface AgentRun {
  id: string;
  chain_id: string;
  task_id: string;
  provider: string;
  model: string;
  status: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  attempt_number: number;
  max_repair_attempts: number;
  proposed_patch_id?: string | null;
  proposed_patch_hash?: string | null;
  verification_run_id?: string | null;
  plan_approved_by?: string | null;
  plan_approved_at?: string | null;
  issue_analysis_json?: any;
  task_plan_json?: any;
  patch_proposal_json?: any;
  created_at: string;
  completed_at?: string | null;
}

export interface VerificationCheck {
  id?: string;
  name?: string;
  check_name?: string;
  command?: string[];
  status: 'PASSED' | 'FAILED' | 'SKIPPED' | 'NOT_RUN' | 'INCONCLUSIVE' | 'TIMED_OUT' | 'CANCELLED';
  exit_code?: number;
  duration_ms: number;
  stdout?: string;
  stderr?: string;
  message?: string;
}

export interface VerificationRun {
  id: string;
  patch_id: string;
  task_id: string;
  sandbox_type: 'docker' | 'fake';
  image_tag?: string;
  status: string;
  has_regressions: boolean;
  started_at: string;
  completed_at?: string;
  checks: VerificationCheck[];
  error_message?: string | null;
}

export interface EvidenceReport {
  report_id: string;
  task_id: string;
  patch_id: string;
  base_sha: string;
  patch_hash?: string;
  patch_content_hash?: string;
  sandbox_type?: string;
  sandbox_runner_type?: string;
  verification_conclusion?: string;
  conclusion?: string;
  summary_markdown: string;
  generated_at?: string;
}

export interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  private: boolean;
  description?: string;
  html_url: string;
  default_branch: string;
  open_issues_count: number;
}

export interface GitHubIssue {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: string;
  html_url: string;
  user?: { login: string; id: number };
  comments_count: number;
  created_at: string;
  updated_at: string;
  comments?: Array<{
    id: number;
    body: string;
    user?: { login: string };
    created_at: string;
  }>;
}

export interface GitHubPullRequest {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: string;
  html_url: string;
  user?: { login: string };
  head_ref: string;
  head_sha: string;
  base_ref: string;
  base_sha: string;
  draft: boolean;
  created_at: string;
  updated_at: string;
}
