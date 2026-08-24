import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Award, GitBranch, Search, AlertTriangle, Clock, GitCommit } from 'lucide-react';

// Display labels for the retrieval re-ranking variants. These must always
// name a real, existing technique - never an invented one. "dense_baseline"
// and "mmr_reranked" are produced by scripts/evaluation/evaluate_retrieval.py
// (src/reranker.py implements the MMR re-ranker). The old dashboard's
// "MultiFactor"/"CrossEncoder" comparison was retired because no such
// reranker existed anywhere in the codebase.
const VARIANT_LABELS = {
    dense_baseline: 'Dense-only Baseline',
    mmr_reranked: 'MMR Reranked',
};

const RETRIEVAL_SET_LABELS = {
    known_item_search: 'Known-Item Search (easy)',
    realistic_learner_phrased: 'Realistic, Learner-Phrased (harder)',
};

function findMetricKey(variantResults, prefix) {
    for (const result of variantResults) {
        if (result) {
            const key = Object.keys(result).find((k) => k.startsWith(prefix));
            if (key) return key;
        }
    }
    return null;
}

function buildRetrievalChartData(setResult) {
    if (!setResult) return null;
    const variantKeys = Object.keys(VARIANT_LABELS).filter((k) => k in setResult);
    const variantResults = variantKeys.map((k) => setResult[k]);
    if (variantResults.every((r) => !r)) return null;

    const recallKey = findMetricKey(variantResults, 'avg_recall@');
    const ndcgKey = findMetricKey(variantResults, 'avg_ndcg@');
    if (!recallKey && !ndcgKey) return null;

    const rows = [];
    if (recallKey) {
        const row = { name: recallKey.replace('avg_', '') };
        variantKeys.forEach((k) => { row[VARIANT_LABELS[k]] = setResult[k] ? setResult[k][recallKey] : null; });
        rows.push(row);
    }
    if (ndcgKey) {
        const row = { name: ndcgKey.replace('avg_', '') };
        variantKeys.forEach((k) => { row[VARIANT_LABELS[k]] = setResult[k] ? setResult[k][ndcgKey] : null; });
        rows.push(row);
    }
    return { rows, variantKeys };
}

const Evaluation = () => {
    const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'missing' | 'error'
    const [data, setData] = useState(null);
    const [errorDetail, setErrorDetail] = useState('');

    useEffect(() => {
        fetch('/eval-results.json')
            .then((res) => {
                if (res.status === 404) {
                    setStatus('missing');
                    return null;
                }
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }
                return res.json();
            })
            .then((json) => {
                if (json) {
                    setData(json);
                    setStatus('ready');
                }
            })
            .catch((err) => {
                setErrorDetail(err.message || String(err));
                setStatus('error');
            });
    }, []);

    if (status === 'loading') {
        return (
            <div className="flex-1 h-screen bg-slate-50 overflow-y-auto p-8">
                <p className="text-slate-500">Loading evaluation results...</p>
            </div>
        );
    }

    if (status === 'missing' || status === 'error') {
        return (
            <div className="flex-1 h-screen bg-slate-50 overflow-y-auto p-8">
                <header className="mb-8">
                    <h1 className="text-3xl font-bold text-slate-800 mb-2">Evaluation Dashboard</h1>
                </header>
                <div className="bg-white p-8 rounded-xl shadow-sm border border-amber-200 flex items-start gap-4 max-w-2xl">
                    <AlertTriangle className="text-amber-500 shrink-0 mt-1" />
                    <div>
                        <h2 className="text-lg font-semibold text-slate-800 mb-2">Evaluation not yet run in this environment</h2>
                        <p className="text-slate-600 mb-2">
                            No results file was found at <code className="bg-slate-100 px-1 rounded">/eval-results.json</code>.
                            Run <code className="bg-slate-100 px-1 rounded">python scripts/evaluation/run_evaluation.py</code> to
                            generate one.
                        </p>
                        {status === 'error' && (
                            <p className="text-sm text-red-600">Fetch error: {errorDetail}</p>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    const { generated_at, commit_sha, retrieval, generation, notes } = data;

    return (
        <div className="flex-1 h-screen bg-slate-50 overflow-y-auto p-8">
            <header className="mb-6">
                <h1 className="text-3xl font-bold text-slate-800 mb-2">Evaluation Dashboard</h1>
                <p className="text-slate-500">
                    A dated snapshot of retrieval and roadmap-generation quality - not a live claim.
                </p>
            </header>

            <div className="flex flex-wrap gap-4 mb-8 text-sm text-slate-600">
                <span className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-slate-200">
                    <Clock size={16} /> Generated: {generated_at ? new Date(generated_at).toLocaleString() : 'unknown'}
                </span>
                <span className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-slate-200 font-mono">
                    <GitCommit size={16} /> {commit_sha ? commit_sha.slice(0, 12) : 'unknown commit'}
                </span>
            </div>

            {/* Retrieval */}
            <section className="mb-10">
                <h2 className="text-2xl font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <Search className="text-blue-500" size={22} /> Retrieval
                </h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {Object.keys(RETRIEVAL_SET_LABELS).map((setKey) => {
                        const setResult = retrieval ? retrieval[setKey] : null;
                        const chart = buildRetrievalChartData(setResult);
                        return (
                            <div key={setKey} className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
                                <h3 className="text-lg font-semibold mb-1">{RETRIEVAL_SET_LABELS[setKey]}</h3>
                                {setResult?.description && (
                                    <p className="text-slate-500 text-sm mb-4">{setResult.description}</p>
                                )}
                                {chart ? (
                                    <div className="h-64 w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={chart.rows} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                                <XAxis dataKey="name" />
                                                <YAxis domain={[0, 1]} />
                                                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                                <Legend />
                                                {chart.variantKeys.map((k, i) => (
                                                    <Bar key={k} dataKey={VARIANT_LABELS[k]} fill={i === 0 ? '#3b82f6' : '#10b981'} radius={[4, 4, 0, 0]} />
                                                ))}
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                ) : (
                                    <EmptyMetric text="Not measured in this environment - requires a running Qdrant instance with an ingested corpus." />
                                )}
                            </div>
                        );
                    })}
                </div>
            </section>

            {/* Generation */}
            <section className="mb-10">
                <h2 className="text-2xl font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <GitBranch className="text-purple-500" size={22} /> Roadmap Generation Quality
                </h2>
                {generation ? (
                    <>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                            <MetricCard
                                title="Topic Coverage (primary)"
                                value={formatScore(generation.coverage)}
                                icon={<Award className="text-emerald-500" />}
                            />
                            <MetricCard
                                title="Topic Precision (primary)"
                                value={formatScore(generation.precision)}
                                icon={<Award className="text-emerald-500" />}
                            />
                        </div>
                        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
                            <p className="text-sm text-slate-500 mb-3">
                                Coverage/precision come from greedy bipartite topic alignment (embedding cosine similarity
                                between generated node titles and gold topics) - see <code className="bg-slate-100 px-1 rounded">src/metrics.py</code>.
                                ROUGE-L and BERTScore below are kept as <strong>secondary/reference metrics only</strong>: both
                                are order/length-sensitive sequence metrics applied to what is really a set-coverage comparison,
                                which is why ROUGE-L in particular reads as a misleadingly low number unrelated to actual quality.
                            </p>
                            <div className="flex flex-wrap gap-6 text-sm">
                                <span className="text-slate-600">ROUGE-L (secondary): <strong>{formatScore(generation.rouge_l)}</strong></span>
                                <span className="text-slate-600">BERTScore F1 (secondary): <strong>{formatScore(generation.bert_score)}</strong></span>
                                <span className="text-slate-600">Roadmaps evaluated: <strong>{generation.roadmaps_evaluated ?? 'n/a'}</strong></span>
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
                        <EmptyMetric text="Not measured in this environment - roadmap generation requires OPENAI_API_KEY." />
                    </div>
                )}
            </section>

            {/* Notes / caveats */}
            {notes && notes.length > 0 && (
                <section>
                    <h2 className="text-xl font-bold text-slate-800 mb-3">Notes</h2>
                    <ul className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 space-y-2 text-sm text-slate-600 list-disc list-inside">
                        {notes.map((note, i) => (
                            <li key={i}>{note}</li>
                        ))}
                    </ul>
                </section>
            )}
        </div>
    );
};

const formatScore = (value) => (typeof value === 'number' ? value.toFixed(4) : 'n/a');

const EmptyMetric = ({ text }) => (
    <div className="h-64 flex items-center justify-center text-center text-slate-400 text-sm p-6 border border-dashed border-slate-200 rounded-lg">
        {text}
    </div>
);

const MetricCard = ({ title, value, icon }) => (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex items-center justify-between">
        <div>
            <p className="text-slate-500 text-sm font-medium mb-1">{title}</p>
            <h3 className="text-2xl font-bold text-slate-800">{value}</h3>
        </div>
        <div className="p-3 bg-slate-50 rounded-lg">
            {icon}
        </div>
    </div>
);

export default Evaluation;
