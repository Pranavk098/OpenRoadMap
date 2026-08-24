import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Book, Video, Globe, X, ArrowLeft, Link as LinkIcon, Loader2, AlertTriangle } from 'lucide-react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { generateRoadmap, describeApiError } from '../api/client';

// Turns a URL slug back into a best-effort topic string, e.g.
// "machine-learning" -> "Machine Learning". Used when a roadmap page is
// loaded directly (refresh / bookmark / shared link) with no cached data,
// so we can ask the API to regenerate it.
const deslugify = (slug) =>
    slug
        .replace(/-/g, ' ')
        .trim()
        .replace(/\b\w/g, (c) => c.toUpperCase());

const Roadmap = () => {
    const { slug } = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    const [roadmapData, setRoadmapData] = useState(null);
    const [topic, setTopic] = useState(null);
    // 'loading' | 'ready' | 'error'
    const [loadState, setLoadState] = useState('loading');
    const [loadError, setLoadError] = useState(null);
    const activeSlugRef = useRef(null);

    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState(null);
    const [copied, setCopied] = useState(false);

    // GitHub repo integration (from roadmapData.github_repo)
    const [githubRepo, setGithubRepo] = useState('');

    // Progress tracking (per node, stored in localStorage keyed by topic)
    const [progressMap, setProgressMap] = useState({});

    const loadRoadmap = useCallback(async (targetSlug) => {
        activeSlugRef.current = targetSlug;
        setLoadState('loading');
        setLoadError(null);

        const stored = targetSlug ? sessionStorage.getItem(`roadmap:${targetSlug}`) : null;
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                setRoadmapData(parsed.roadmapData);
                setTopic(parsed.topic);
                setLoadState('ready');
                return;
            } catch {
                // Corrupt sessionStorage entry - fall through and regenerate instead.
            }
        }

        if (!targetSlug) {
            setLoadError({ kind: 'missing' });
            setLoadState('error');
            return;
        }

        try {
            const bestEffortTopic = deslugify(targetSlug);
            const data = await generateRoadmap(bestEffortTopic);
            if (activeSlugRef.current !== targetSlug) return; // slug changed while awaiting

            sessionStorage.setItem(`roadmap:${targetSlug}`, JSON.stringify({ roadmapData: data, topic: bestEffortTopic }));
            setRoadmapData(data);
            setTopic(bestEffortTopic);
            setLoadState('ready');
        } catch (err) {
            if (activeSlugRef.current !== targetSlug) return;
            setLoadError(err);
            setLoadState('error');
        }
    }, []);

    // On mount / when the slug changes: prefer router state (fast path from
    // just navigating here from Landing), then sessionStorage, then fall
    // back to regenerating from the API. Never falls back to fake data.
    useEffect(() => {
        if (location.state?.roadmapData) {
            const { roadmapData: fastData, topic: fastTopic } = location.state;
            activeSlugRef.current = slug;
            setRoadmapData(fastData);
            setTopic(fastTopic);
            setLoadState('ready');
            if (slug) {
                sessionStorage.setItem(`roadmap:${slug}`, JSON.stringify({ roadmapData: fastData, topic: fastTopic }));
            }
            return;
        }

        loadRoadmap(slug);
        // Only re-run when the slug itself changes - location.state/loadRoadmap
        // are read at trigger time, not tracked as reactive deps here.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [slug]);

    useEffect(() => {
        setGithubRepo(roadmapData?.github_repo || '');
        setProgressMap(() => {
            if (!topic) return {};
            const saved = localStorage.getItem(`progress_${topic}`);
            return saved ? JSON.parse(saved) : {};
        });
    }, [roadmapData, topic]);

    useEffect(() => {
        document.title = topic ? `${topic} Roadmap · OpenRoadMap` : 'Roadmap · OpenRoadMap';
    }, [topic]);

    // Layout: computes nodes/edges from roadmapData only. Progress is merged
    // in separately (see displayNodes below) so dragging the progress slider
    // never re-runs this DFS or rebuilds the graph.
    useEffect(() => {
        if (!roadmapData || !roadmapData.nodes) {
            setNodes([]);
            setEdges([]);
            return;
        }

        const { nodes: apiNodes } = roadmapData;
        const newNodes = [];
        const newEdges = [];
        const nodeMap = new Map();

        apiNodes.forEach((node) => {
            nodeMap.set(node.id, node);
        });

        // Calculate levels for layout, guarding against prerequisite cycles.
        const levels = new Map();
        const visiting = new Set();
        const getLevel = (nodeId) => {
            if (levels.has(nodeId)) return levels.get(nodeId);

            const node = nodeMap.get(nodeId);
            if (!node || !node.prerequisites || node.prerequisites.length === 0) {
                levels.set(nodeId, 0);
                return 0;
            }

            if (visiting.has(nodeId)) {
                // Cycle detected (e.g. A depends on B depends on A). Break the
                // cycle by treating this node as having no further-back
                // prerequisites instead of recursing forever.
                return 0;
            }
            visiting.add(nodeId);

            let maxPrereqLevel = -1;
            node.prerequisites.forEach((prereqId) => {
                if (!nodeMap.has(prereqId)) return; // dangling prerequisite reference
                maxPrereqLevel = Math.max(maxPrereqLevel, getLevel(prereqId));
            });

            visiting.delete(nodeId);

            const level = maxPrereqLevel + 1;
            levels.set(nodeId, level);
            return level;
        };

        apiNodes.forEach((node) => getLevel(node.id));

        // Assign positions based on levels
        const levelCounts = new Map();
        apiNodes.forEach((node) => {
            const level = levels.get(node.id);
            const count = levelCounts.get(level) || 0;

            newNodes.push({
                id: node.id,
                position: { x: count * 250, y: level * 150 }, // Simple grid layout
                data: {
                    label: node.title,
                    description: node.description,
                    resources: node.resources,
                    baseProgress: node.progress || 0,
                },
                style: {
                    background: '#fef08a', // Yellow
                    border: '2px solid #000', // Black border
                    borderRadius: '4px',
                    padding: '10px',
                    width: 180,
                    fontWeight: 'bold',
                    color: '#000', // Black text
                    boxShadow: '4px 4px 0px 0px #000' // Retro shadow
                }
            });

            levelCounts.set(level, count + 1);

            // Create edges, skipping any that reference a node id that
            // doesn't exist (dangling prerequisite) so we never hand
            // ReactFlow an edge with a missing source/target.
            if (node.prerequisites) {
                node.prerequisites.forEach((prereqId) => {
                    if (!nodeMap.has(prereqId) || !nodeMap.has(node.id)) return;
                    newEdges.push({
                        id: `e${prereqId}-${node.id}`,
                        source: prereqId,
                        target: node.id,
                        markerEnd: { type: MarkerType.ArrowClosed, color: '#000' },
                        type: 'smoothstep',
                        animated: false,
                        style: { stroke: '#000', strokeWidth: 2 }
                    });
                });
            }
        });

        setNodes(newNodes);
        setEdges(newEdges);
    }, [roadmapData, setNodes, setEdges]);

    // Merge live progress into the nodes ReactFlow renders, without
    // re-running the layout effect above.
    const displayNodes = useMemo(
        () =>
            nodes.map((node) => ({
                ...node,
                data: {
                    ...node.data,
                    progress: progressMap[node.id] ?? node.data.baseProgress ?? 0,
                },
            })),
        [nodes, progressMap]
    );

    const overallProgress = useMemo(() => {
        if (nodes.length === 0) return 0;
        const total = nodes.reduce((sum, node) => sum + (progressMap[node.id] ?? node.data.baseProgress ?? 0), 0);
        return Math.round(total / nodes.length);
    }, [nodes, progressMap]);

    const onNodeClick = useCallback((event, node) => {
        if (node && node.data) {
            setSelectedNode(node);
        }
    }, []);

    const handleRetry = () => loadRoadmap(slug);

    const handleCopyLink = async () => {
        const url = `${window.location.origin}/roadmap/${slug}`;
        try {
            await navigator.clipboard.writeText(url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy link:', err);
        }
    };

    // Helper to safely get hostname
    const getHostname = (url) => {
        try {
            return new URL(url).hostname.replace('www.', '');
        } catch {
            return 'Resource';
        }
    };

    if (loadState === 'loading') {
        return (
            <div className="flex-1 h-screen flex flex-col items-center justify-center gap-4 bg-slate-50">
                <Loader2 className="animate-spin text-purple-600" size={40} />
                <p className="text-slate-500 font-medium">Generating your roadmap...</p>
            </div>
        );
    }

    if (loadState === 'error') {
        const message =
            loadError?.kind === 'missing'
                ? "We couldn't tell which roadmap you wanted."
                : describeApiError(loadError);

        return (
            <div className="flex-1 h-screen flex flex-col items-center justify-center gap-4 bg-slate-50 text-center px-6">
                <AlertTriangle className="text-red-500" size={40} />
                <h2 className="text-xl font-bold text-slate-800">{message}</h2>
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleRetry}
                        className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                    >
                        Retry
                    </button>
                    <button
                        onClick={() => navigate('/')}
                        className="bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 px-4 py-2 rounded-lg font-medium transition-colors"
                    >
                        Go home
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 h-screen relative bg-slate-50">
            {/* Header / Back Button */}
            <div className="absolute top-4 left-4 z-10 flex items-center gap-3 flex-wrap max-w-[70%]">
                <button
                    onClick={() => navigate('/')}
                    className="bg-white p-2 rounded-lg shadow-sm border border-slate-200 hover:bg-slate-50 flex items-center gap-2 text-slate-600"
                >
                    <ArrowLeft size={20} />
                    <span className="font-medium">Back</span>
                </button>
                {topic && (
                    <div className="bg-white px-4 py-2 rounded-lg shadow-sm border border-slate-200">
                        <h1 className="font-bold text-slate-800 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-500"></span>
                            {topic}
                        </h1>
                    </div>
                )}
                <button
                    onClick={handleCopyLink}
                    className="bg-white px-3 py-2 rounded-lg shadow-sm border border-slate-200 hover:bg-slate-50 flex items-center gap-2 text-slate-600 text-sm font-medium"
                >
                    <LinkIcon size={16} />
                    {copied ? 'Copied!' : 'Copy link'}
                </button>
                {nodes.length > 0 && (
                    <div className="bg-white px-4 py-2 rounded-lg shadow-sm border border-slate-200 flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-500 whitespace-nowrap">Progress</span>
                        <div className="w-24 h-2 rounded-full bg-slate-100 overflow-hidden">
                            <div className="h-full bg-green-500" style={{ width: `${overallProgress}%` }} />
                        </div>
                        <span className="text-xs font-semibold text-slate-600">{overallProgress}%</span>
                    </div>
                )}
            </div>

            <ReactFlow
                nodes={displayNodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodesDraggable={false}
                fitView
            >
                <Background color="#aaa" gap={16} />
                <Controls />
            </ReactFlow>

            {/* Resource Sidebar */}
            {selectedNode && (
                <div className="absolute right-0 top-0 h-full w-[450px] bg-white shadow-xl border-l border-slate-200 p-6 overflow-y-auto z-20 animate-in slide-in-from-right duration-300">
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-bold text-slate-800">{selectedNode.data.label}</h2>
                        <button onClick={() => setSelectedNode(null)} className="p-2 hover:bg-slate-100 rounded-full">
                            <X size={20} className="text-slate-500" />
                        </button>
                    </div>

                    <div className="space-y-6">
                        <div className="bg-primary-50 p-4 rounded-lg border border-primary-100">
                            <h3 className="font-semibold text-primary-800 mb-2">Description</h3>
                            <p className="text-sm text-primary-700 leading-relaxed">
                                {selectedNode.data.description}
                            </p>
                        </div>

                        {/* Progress Tracking UI */}
                        <div className="flex items-center gap-4">
                            <label className="font-semibold text-slate-700">Progress:</label>
                            <input
                                type="range"
                                min={0}
                                max={100}
                                step={10}
                                value={progressMap[selectedNode.id] ?? selectedNode.data.progress ?? 0}
                                onChange={e => {
                                    const val = parseInt(e.target.value, 10);
                                    setProgressMap(prev => {
                                        const updated = { ...prev, [selectedNode.id]: val };
                                        if (topic) {
                                            localStorage.setItem(`progress_${topic}`, JSON.stringify(updated));
                                        }
                                        return updated;
                                    });
                                }}
                                className="w-40"
                            />
                            <span className="text-slate-600 font-medium">{progressMap[selectedNode.id] ?? selectedNode.data.progress ?? 0}%</span>
                        </div>

                        <div>
                            <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
                                <Book size={18} /> Recommended Resources
                            </h3>
                            <div className="space-y-3">
                                {selectedNode.data.resources && selectedNode.data.resources.length > 0 ? (
                                    selectedNode.data.resources.map((res, idx) => (
                                        <ResourceCard
                                            key={idx}
                                            title={res.title}
                                            description={res.description}
                                            type={res.type || "Resource"}
                                            source={getHostname(res.url)}
                                            url={res.url}
                                            icon={<Globe size={16} className="text-blue-500" />}
                                        />
                                    ))
                                ) : (
                                    <p className="text-sm text-slate-400 italic">No resources found for this topic.</p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* GitHub Repo Integration UI */}
            <div className="absolute top-4 right-4 z-10">
                <div className="bg-white px-4 py-2 rounded-lg shadow border border-slate-200 flex items-center gap-2">
                    <span className="font-semibold text-slate-700">GitHub Repo:</span>
                    <input
                        type="text"
                        value={githubRepo}
                        onChange={e => setGithubRepo(e.target.value)}
                        placeholder="user/repo or URL"
                        className="border rounded px-2 py-1 text-sm w-56"
                    />
                    {githubRepo && (
                        <a
                            href={githubRepo.startsWith('http') ? githubRepo : `https://github.com/${githubRepo}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 underline text-sm"
                        >
                            View
                        </a>
                    )}
                </div>
            </div>
        </div>
    );
};

const ResourceCardContent = ({ type, source, title, description, icon, isValidUrl }) => (
    <>
        <div className="flex items-start justify-between mb-2">
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 group-hover:bg-primary-50 group-hover:text-primary-600 transition-colors capitalize">
                {type}
            </span>
            <span className="text-xs text-slate-400 truncate max-w-[120px]">{source}</span>
        </div>
        <h4 className="font-medium text-slate-800 mb-2 group-hover:text-primary-700 transition-colors leading-tight">{title}</h4>
        {description && (
            <p className="text-xs text-slate-500 mb-3 line-clamp-2 leading-relaxed">
                {description}
            </p>
        )}
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
            {icon}
            <span>{isValidUrl ? 'View Resource' : 'Link Unavailable'}</span>
        </div>
    </>
);

const ResourceCard = ({ title, description, type, source, url, icon }) => {
    const isValidUrl = url && (url.startsWith('http') || url.startsWith('https'));

    if (isValidUrl) {
        return (
            <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-4 rounded-xl border border-slate-200 hover:border-primary-300 hover:shadow-md transition-all bg-white group"
            >
                <ResourceCardContent type={type} source={source} title={title} description={description} icon={icon} isValidUrl={isValidUrl} />
            </a>
        );
    }

    return (
        <div className="block p-4 rounded-xl border border-slate-200 bg-slate-50 opacity-75 cursor-not-allowed">
            <ResourceCardContent type={type} source={source} title={title} description={description} icon={icon} isValidUrl={isValidUrl} />
        </div>
    );
};

export default Roadmap;
