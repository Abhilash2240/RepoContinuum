import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, ChevronRight, GitFork, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from '../services/api';
import { DAGGraph, DAGNode, TaskChainSummary } from '../types/api';

export const TaskChainsPage: React.FC = () => {
  const [chains, setChains] = useState<TaskChainSummary[]>([]);
  const [selectedChainId, setSelectedChainId] = useState<string>('');
  const [graph, setGraph] = useState<DAGGraph | null>(null);
  const [selectedNode, setSelectedNode] = useState<DAGNode | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getTaskChains().then((res) => {
      setChains(res);
      if (res.length > 0) {
        setSelectedChainId(res[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedChainId) return;
    setLoading(true);
    api.getTaskChainGraph(selectedChainId)
      .then((g) => {
        setGraph(g);
        if (g.nodes.length > 0) {
          setSelectedNode(g.nodes[0]);
        } else {
          setSelectedNode(null);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [selectedChainId]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Selector Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>Task Chain & DAG Visualizer</h2>
          <p style={{ margin: '0.25rem 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
            Topologically ordered dependency graph and prerequisite state management.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Chain:</label>
          <select
            value={selectedChainId}
            onChange={(e) => setSelectedChainId(e.target.value)}
            style={{ padding: '0.4rem 0.8rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.375rem', color: '#f8fafc', fontSize: '0.875rem' }}
          >
            {chains.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} ({c.id})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>
          <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem' }} />
          <p>Evaluating dependency DAG...</p>
        </div>
      ) : !graph ? (
        <div style={{ padding: '2rem', backgroundColor: '#1e293b', borderRadius: '0.5rem', textAlign: 'center', color: '#64748b' }}>
          Select a task chain to view its dependency visualizer.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(280px, 1fr)', gap: '1.5rem' }}>
          {/* Left: DAG Execution Order & Graph Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ padding: '0.75rem 1rem', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '0.375rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
              <span>
                <strong>Topological Order:</strong> {graph.topological_order.join(' → ') || 'No tasks'}
              </span>
              <span className={`badge ${graph.is_valid ? 'badge-green' : 'badge-red'}`}>
                {graph.is_valid ? 'Valid DAG (No Cycles)' : 'Invalid DAG'}
              </span>
            </div>

            {/* Nodes Stack */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {graph.nodes.map((node, index) => {
                const isSelected = selectedNode?.id === node.id;
                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    style={{
                      padding: '1rem',
                      backgroundColor: isSelected ? 'rgba(56, 189, 248, 0.08)' : '#1e293b',
                      border: isSelected ? '1px solid #38bdf8' : '1px solid #334155',
                      borderRadius: '0.5rem',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      position: 'relative',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>#{index + 1}</span>
                          <span className={`badge ${node.is_blocked ? 'badge-amber' : node.status === 'COMPLETED' ? 'badge-green' : 'badge-blue'}`}>
                            {node.status}
                          </span>
                          <strong style={{ fontSize: '0.95rem' }}>{node.title}</strong>
                        </div>
                        <div className="font-mono" style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                          ID: {node.id}
                        </div>
                      </div>
                      <ChevronRight size={18} color={isSelected ? '#38bdf8' : '#64748b'} />
                    </div>

                    {node.is_blocked && (
                      <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: '#fbbf24' }}>
                        <AlertCircle size={14} /> Unmet Prerequisites: {node.unmet_predecessors.join(', ')}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Selected Node Details Drawer */}
          <div style={{ padding: '1.25rem', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', height: 'fit-content' }}>
            {selectedNode ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, borderBottom: '1px solid #334155', paddingBottom: '0.5rem' }}>
                  Task Details
                </h3>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Task Title</div>
                  <div style={{ fontWeight: 600, marginTop: '0.15rem' }}>{selectedNode.title}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Task ID</div>
                  <div className="font-mono" style={{ fontSize: '0.8rem', color: '#38bdf8' }}>{selectedNode.id}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Status</div>
                  <span className={`badge ${selectedNode.is_blocked ? 'badge-amber' : selectedNode.status === 'COMPLETED' ? 'badge-green' : 'badge-blue'}`}>
                    {selectedNode.status}
                  </span>
                </div>
                {selectedNode.acceptance_criteria && selectedNode.acceptance_criteria.length > 0 && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>Acceptance Criteria</div>
                    <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.85rem', color: '#cbd5e1' }}>
                      {selectedNode.acceptance_criteria.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {selectedNode.description && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>Description</div>
                    <div style={{ fontSize: '0.8rem', color: '#cbd5e1', backgroundColor: '#0f172a', padding: '0.5rem', borderRadius: '0.25rem', whiteSpace: 'pre-wrap', maxHeight: '180px', overflowY: 'auto' }}>
                      {selectedNode.description}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p style={{ color: '#64748b', fontSize: '0.85rem', margin: 0 }}>Select a node to inspect its criteria and prerequisites.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
