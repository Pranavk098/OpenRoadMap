import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import ReactFlow, {
    Controls,
    Background,
    BackgroundVariant,
    MiniMap,
    Panel,
    useNodesState,
    useEdgesState,
    MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
// Imported capitalised so the flat ESLint config (no eslint-plugin-react) still
// sees `<Motion.div>` member-expression JSX as a use of the binding.
import { motion as Motion, AnimatePresence } from 'framer-motion';
import {
    BookOpen,
    Video,
    Globe,
    FileText,
    GraduationCap,
    Search,
    X,
    ArrowLeft,
    Link as LinkIcon,
    Loader2,
    AlertTriangle,
    Check,
    Sparkles,
} from 'lucide-react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { streamRoadmap, describeApiError } from '../api/client';
import RoadmapNode from '../components/RoadmapNode';
import { stageStyle, NODE_WIDTH, NODE_GAP_X, NODE_GAP_Y } from '../components/roadmapTheme';

// Defined once at module scope: ReactFlow warns (and remounts every node) if
// this object identity changes between renders.
const nodeTypes = { roadmapTopic: RoadmapNode };

const FIT_VIEW_OPTIONS = { padding: 0.28, maxZoom: 1 };

// Turns a URL slug back into a best-effort topic string, e.g.
// "machine-learning" -> "Machine Learning". Used when a roadmap page is
// loaded directly (refresh / bookmark / shared link) with no cached data,
// so we can ask the API to regenerate it.
const deslugify = (slug) =>
    slug
        .replace(/-/g, ' ')
        .trim()
        .replace(/\b\w/g, (c) => c.toUpperCase());

// The backend tags each resource with a coarse type ("Video", "Course",
// "Official Documentation", "Search Link", ...). Give each one a matching
// glyph instead of showing the same globe on every card.
const ResourceTypeIcon = ({ type = '', size = 11 }) => {
    if (/video|youtube/i.test(type)) return <Video size={size} />;
    if (/course|class|tutorial|lecture/i.test(type)) return <GraduationCap size={size} />;
    if (/doc|reference|official|spec/i.test(type)) return <FileText size={size} />;
    if (/book|article|blog|paper|guide/i.test(type)) return <BookOpen size={size} />;
    if (/search/i.test(type)) return <Search size={size} />;
    return <Globe size={size} />;
};

const Roadmap = () => {
    const { slug } = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    const [roadmapData, setRoadmapData] = useState(null);
    const [topic, setTopic] = useState(null);
    // 'loading' | 'ready' | 'error'
    const [loadState, setLoadState] = useState('loading');
    const [loadError, setLoadError] = useState(null);
    // True only while an SSE stream is still filling in per-node resources.
    // Drives the "N of M" pill and the per-node "Finding resources..." state,
    // so an empty resource list never gets reported as "none found" early.
    const [streaming, setStreaming] = useState(false);
    const activeSlugRef = useRef(null);
    const streamRef = useRef(null);

    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNodeId, setSelectedNodeId] = useState(null);
    const [copied, setCopied] = useState(false);

    // Progress tracking (per node, stored in localStorage keyed by topic)
    const [progressMap, setProgressMap] = useState({});

    // Streams the roadmap instead of waiting for the full response: the DAG
    // structure typically arrives in ~1-2s, so the graph renders almost
    // immediately and resources fill in per-node afterward, instead of a
    // blank loading state for the whole ~10-15s generation.
    const loadRoadmap = useCallback((targetSlug) => {
        activeSlugRef.current = targetSlug;
        streamRef.current?.close();
        setLoadState('loading');
        setLoadError(null);
        setStreaming(false);

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

        const bestEffortTopic = deslugify(targetSlug);
        // Local mirror of the in-progress roadmap, updated synchronously in
        // each handler - avoids reading back potentially-stale React state
        // from inside these event callbacks.
        let liveData = null;
        // Once the stream ends, any node that never received a resources event
        // isn't "still loading" - it's answered (with nothing). Flip them all so
        // the UI stops implying more is coming.
        const settleAll = () => {
            if (!liveData) return;
            liveData = { ...liveData, nodes: liveData.nodes.map((n) => ({ ...n, resolved: true })) };
            setRoadmapData(liveData);
        };
        setStreaming(true);

        streamRef.current = streamRoadmap(bestEffortTopic, {
            onStructure: (structureNodes) => {
                if (activeSlugRef.current !== targetSlug) return;
                liveData = {
                    goal: bestEffortTopic,
                    nodes: structureNodes.map((n) => ({ ...n, resources: [], resolved: false })),
                };
                setRoadmapData(liveData);
                setTopic(bestEffortTopic);
                setLoadState('ready');
            },
            onResources: (id, resources) => {
                if (activeSlugRef.current !== targetSlug || !liveData) return;
                liveData = {
                    ...liveData,
                    nodes: liveData.nodes.map((n) => (n.id === id ? { ...n, resources, resolved: true } : n)),
                };
                setRoadmapData(liveData);
            },
            onDone: () => {
                if (activeSlugRef.current !== targetSlug || !liveData) return;
                settleAll();
                setStreaming(false);
                sessionStorage.setItem(`roadmap:${targetSlug}`, JSON.stringify({ roadmapData: liveData, topic: bestEffortTopic }));
            },
            onError: (err) => {
                if (activeSlugRef.current !== targetSlug) return;
                setStreaming(false);
                if (!liveData) {
                    // Never got a structure event - nothing rendered yet, full failure.
                    setLoadError(err);
                    setLoadState('error');
                } else {
                    settleAll();
                    console.error('Roadmap stream error after structure loaded:', err);
                }
            },
        });
    }, []);

    // Close the active stream on unmount so a slow/never-finishing
    // generation doesn't keep updating state after the page is gone.
    useEffect(() => () => streamRef.current?.close(), []);

    // On mount / when the slug changes: prefer router state (fast path from
    // just navigating here from Landing), then sessionStorage, then fall
    // back to regenerating from the API. Never falls back to fake data.
    useEffect(() => {
        if (location.state?.roadmapData) {
            const { roadmapData: fastData, topic: fastTopic } = location.state;
            activeSlugRef.current = slug;
            setRoadmapData(fastData);
            setTopic(fastTopic);
            setStreaming(false);
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
        setSelectedNodeId(null);
        setProgressMap(() => {
            if (!topic) return {};
            const saved = localStorage.getItem(`progress_${topic}`);
            return saved ? JSON.parse(saved) : {};
        });
    }, [topic]);

    useEffect(() => {
        document.title = topic ? `${topic} Roadmap · OpenRoadMap` : 'Roadmap · OpenRoadMap';
    }, [topic]);

    // Layout: derives node positions and edges from the DAG *structure* only.
    // Resource payloads stream in one node at a time, which would otherwise
    // re-run this DFS (and reset ReactFlow's selection/viewport) on every
    // event - so the effect short-circuits unless ids/prerequisites changed.
    // Resources and progress are merged in later, in displayNodes.
    const layoutKeyRef = useRef(null);
    useEffect(() => {
        const apiNodes = roadmapData?.nodes;
        if (!apiNodes || apiNodes.length === 0) {
            layoutKeyRef.current = null;
            setNodes([]);
            setEdges([]);
            return;
        }

        const structureKey = apiNodes.map((n) => `${n.id}>${(n.prerequisites || []).join(',')}`).join('|');
        if (structureKey === layoutKeyRef.current) return;
        layoutKeyRef.current = structureKey;

        const nodeMap = new Map();
        apiNodes.forEach((node) => nodeMap.set(node.id, node));

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

        // Group by depth, preserving API order within each row as the tiebreak.
        const rows = new Map();
        apiNodes.forEach((node) => {
            const level = levels.get(node.id);
            if (!rows.has(level)) rows.set(level, []);
            rows.get(level).push(node.id);
        });
        const maxLevel = Math.max(...rows.keys());

        // One barycentre pass: order each row by the mean position of its
        // prerequisites in the row above. Cheap, and it stops edges from
        // criss-crossing the whole canvas the way a raw insertion-order grid did.
        const columnOf = new Map();
        (rows.get(0) || []).forEach((id, i) => columnOf.set(id, i));
        for (let level = 1; level <= maxLevel; level += 1) {
            const row = rows.get(level) || [];
            const ranked = row.map((id, i) => {
                const prereqs = (nodeMap.get(id).prerequisites || []).filter((p) => columnOf.has(p));
                const barycentre = prereqs.length
                    ? prereqs.reduce((sum, p) => sum + columnOf.get(p), 0) / prereqs.length
                    : i;
                return { id, barycentre, i };
            });
            ranked.sort((a, b) => a.barycentre - b.barycentre || a.i - b.i);
            rows.set(level, ranked.map((r) => r.id));
            ranked.forEach((r, i) => columnOf.set(r.id, i));
        }

        // Centre every row on x=0 so the graph reads as a symmetric tree rather
        // than a left-ragged staircase.
        const newNodes = [];
        const newEdges = [];
        rows.forEach((row, level) => {
            const rowWidth = row.length * NODE_WIDTH + (row.length - 1) * NODE_GAP_X;
            row.forEach((id, index) => {
                const node = nodeMap.get(id);
                newNodes.push({
                    id,
                    type: 'roadmapTopic',
                    position: {
                        x: -rowWidth / 2 + index * (NODE_WIDTH + NODE_GAP_X),
                        y: level * NODE_GAP_Y,
                    },
                    data: {
                        label: node.title,
                        description: node.description,
                        stage: level,
                        baseProgress: node.progress || 0,
                    },
                });

                // Create edges, skipping any that reference a node id that
                // doesn't exist (dangling prerequisite) so we never hand
                // ReactFlow an edge with a missing source/target.
                const accent = stageStyle(level).hex;
                (node.prerequisites || []).forEach((prereqId) => {
                    if (!nodeMap.has(prereqId)) return;
                    newEdges.push({
                        id: `e${prereqId}-${id}`,
                        source: prereqId,
                        target: id,
                        type: 'smoothstep',
                        pathOptions: { borderRadius: 28 },
                        markerEnd: { type: MarkerType.ArrowClosed, color: accent, width: 16, height: 16 },
                        // Edges take the colour of the stage they lead *into*, so
                        // following a path visually announces the next tier.
                        style: { stroke: accent, strokeWidth: 1.75, opacity: 0.45 },
                    });
                });
            });
        });

        setNodes(newNodes);
        setEdges(newEdges);
    }, [roadmapData, setNodes, setEdges]);

    const sourceById = useMemo(() => {
        const map = new Map();
        (roadmapData?.nodes || []).forEach((n) => map.set(n.id, n));
        return map;
    }, [roadmapData]);

    // Merge streamed resources and live progress into the nodes ReactFlow
    // renders, without re-running the layout effect above.
    const displayNodes = useMemo(
        () =>
            nodes.map((node) => {
                const source = sourceById.get(node.id);
                return {
                    ...node,
                    // Drive the selected ring off the open panel rather than
                    // ReactFlow's internal selection, so closing the panel
                    // (Escape / X) always clears the highlight too.
                    selected: node.id === selectedNodeId,
                    data: {
                        ...node.data,
                        resources: source?.resources || [],
                        resolved: source?.resolved !== false,
                        progress: progressMap[node.id] ?? node.data.baseProgress ?? 0,
                    },
                };
            }),
        [nodes, sourceById, progressMap, selectedNodeId]
    );

    // The sidebar reads from displayNodes rather than holding its own copy of
    // the clicked node, so resources arriving mid-stream appear in an already
    // open panel instead of leaving it stuck on a stale snapshot.
    const selectedNode = useMemo(
        () => displayNodes.find((n) => n.id === selectedNodeId) || null,
        [displayNodes, selectedNodeId]
    );

    const overallProgress = useMemo(() => {
        if (nodes.length === 0) return 0;
        const total = nodes.reduce((sum, node) => sum + (progressMap[node.id] ?? node.data.baseProgress ?? 0), 0);
        return Math.round(total / nodes.length);
    }, [nodes, progressMap]);

    const stageCount = useMemo(
        () => (nodes.length ? Math.max(...nodes.map((n) => n.data.stage ?? 0)) + 1 : 0),
        [nodes]
    );

    const resolvedCount = useMemo(
        () => (roadmapData?.nodes || []).filter((n) => n.resolved !== false).length,
        [roadmapData]
    );

    const onNodeClick = useCallback((event, node) => {
        if (node?.id) setSelectedNodeId(node.id);
    }, []);

    const closeSidebar = useCallback(() => setSelectedNodeId(null), []);

    // Escape closes the resource panel - the only modal-ish surface here.
    useEffect(() => {
        if (!selectedNodeId) return undefined;
        const onKeyDown = (e) => {
            if (e.key === 'Escape') setSelectedNodeId(null);
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [selectedNodeId]);

    const setProgress = useCallback(
        (nodeId, value) => {
            setProgressMap((prev) => {
                const updated = { ...prev, [nodeId]: value };
                if (topic) {
                    localStorage.setItem(`progress_${topic}`, JSON.stringify(updated));
                }
                return updated;
            });
        },
        [topic]
    );

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
            <div className="flex-1 h-screen flex flex-col items-center justify-center gap-5 bg-slate-50 px-6 text-center">
                <div className="relative">
                    <div className="absolute inset-0 rounded-2xl bg-primary-500/25 blur-xl" />
                    <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-indigo-600 shadow-lg shadow-primary-500/25">
                        <Loader2 className="animate-spin text-white" size={26} />
                    </div>
                </div>
                <div>
                    <p className="text-base font-semibold text-slate-800">Mapping out your roadmap</p>
                    <p className="mt-1 text-sm text-slate-500">
                        Working out the topics and what depends on what — this usually takes a couple of seconds.
                    </p>
                </div>
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
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 ring-1 ring-inset ring-red-100">
                    <AlertTriangle className="text-red-500" size={26} />
                </div>
                <h2 className="max-w-md text-xl font-semibold tracking-tight text-slate-900">{message}</h2>
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleRetry}
                        className="rounded-xl bg-primary-600 px-4 py-2 font-medium text-white shadow-sm shadow-primary-600/20 transition-colors hover:bg-primary-700"
                    >
                        Retry
                    </button>
                    <button
                        onClick={() => navigate('/')}
                        className="rounded-xl border border-slate-200 bg-white px-4 py-2 font-medium text-slate-600 transition-colors hover:bg-slate-50"
                    >
                        Go home
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 h-screen relative bg-slate-50">
            {/* Floating chrome. One toolbar instead of four competing cards, so
                the graph itself is the loudest thing on the page. */}
            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-3 p-4">
                <div className="pointer-events-auto flex flex-wrap items-center gap-1 rounded-2xl border border-slate-200/80 bg-white/85 p-1.5 shadow-lg shadow-slate-900/[0.06] backdrop-blur-md">
                    <button
                        onClick={() => navigate('/')}
                        className="flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                    >
                        <ArrowLeft size={16} />
                        Back
                    </button>

                    {topic && (
                        <>
                            <span aria-hidden className="mx-1 h-6 w-px bg-slate-200" />
                            <div className="px-1.5">
                                <h1 className="max-w-[16rem] truncate text-sm font-semibold tracking-tight text-slate-900">
                                    {topic}
                                </h1>
                                <p className="text-[11px] leading-tight text-slate-400">
                                    {nodes.length} topic{nodes.length === 1 ? '' : 's'} · {stageCount} stage
                                    {stageCount === 1 ? '' : 's'}
                                </p>
                            </div>
                        </>
                    )}

                    {nodes.length > 0 && (
                        <>
                            <span aria-hidden className="mx-1 h-6 w-px bg-slate-200" />
                            <div className="flex items-center gap-2 px-1.5">
                                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
                                    <div
                                        className="h-full rounded-full bg-emerald-500 transition-[width] duration-300"
                                        style={{ width: `${overallProgress}%` }}
                                    />
                                </div>
                                <span className="text-xs font-semibold tabular-nums text-slate-600">
                                    {overallProgress}%
                                </span>
                            </div>
                        </>
                    )}

                    <span aria-hidden className="mx-1 h-6 w-px bg-slate-200" />
                    <button
                        onClick={handleCopyLink}
                        className="flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                    >
                        {copied ? <Check size={16} className="text-emerald-600" /> : <LinkIcon size={16} />}
                        {copied ? 'Copied' : 'Copy link'}
                    </button>
                </div>

                {/* Replaces the old unwired "GitHub Repo" box: real, live stream
                    telemetry instead of decoration. */}
                <AnimatePresence>
                    {streaming && (
                        <Motion.div
                            initial={{ opacity: 0, y: -6 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -6 }}
                            className="pointer-events-auto flex shrink-0 items-center gap-2 rounded-full border border-slate-200/80 bg-white/85 px-3 py-1.5 text-xs font-medium text-slate-600 shadow-lg shadow-slate-900/[0.06] backdrop-blur-md"
                        >
                            <Loader2 size={13} className="animate-spin text-primary-600" />
                            Curating resources
                            <span className="tabular-nums text-slate-400">
                                {resolvedCount}/{roadmapData?.nodes?.length ?? 0}
                            </span>
                        </Motion.div>
                    )}
                </AnimatePresence>
            </div>

            <ReactFlow
                nodes={displayNodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onPaneClick={closeSidebar}
                nodesDraggable={false}
                nodesConnectable={false}
                minZoom={0.2}
                fitView
                fitViewOptions={FIT_VIEW_OPTIONS}
                className="bg-slate-50"
            >
                <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="#cbd5e1" />
                <Controls showInteractive={false} className="roadmap-controls" />
                {nodes.length > 6 && (
                    <MiniMap
                        pannable
                        zoomable
                        nodeStrokeWidth={0}
                        nodeBorderRadius={4}
                        nodeColor={(n) => stageStyle(n.data?.stage).hex}
                        maskColor="rgba(241,245,249,0.7)"
                        className="roadmap-minimap"
                    />
                )}
                {stageCount > 1 && (
                    <Panel position="bottom-center" className="!mb-5">
                        <div className="flex items-center gap-2.5 rounded-full border border-slate-200/80 bg-white/85 px-3.5 py-1.5 shadow-sm backdrop-blur-md">
                            <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-slate-400">
                                Stages
                            </span>
                            {Array.from({ length: stageCount }, (_, i) => (
                                <span key={i} className="flex items-center gap-1 text-[11px] font-medium text-slate-500">
                                    <span className={`h-2 w-2 rounded-full ${stageStyle(i).dot}`} />
                                    {i + 1}
                                </span>
                            ))}
                        </div>
                    </Panel>
                )}
            </ReactFlow>

            {/* Resource Sidebar */}
            <AnimatePresence>
                {selectedNode && (
                    <Motion.aside
                        key="resource-panel"
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        transition={{ type: 'spring', stiffness: 380, damping: 38 }}
                        className="absolute right-0 top-0 z-20 flex h-full w-full max-w-[440px] flex-col border-l border-slate-200 bg-white shadow-[-16px_0_48px_-24px_rgba(15,23,42,0.3)]"
                    >
                        <SidebarBody
                            node={selectedNode}
                            onClose={closeSidebar}
                            onProgressChange={setProgress}
                            getHostname={getHostname}
                        />
                    </Motion.aside>
                )}
            </AnimatePresence>
        </div>
    );
};

const SidebarBody = ({ node, onClose, onProgressChange, getHostname }) => {
    const s = stageStyle(node.data.stage);
    const progress = node.data.progress ?? 0;
    const resources = node.data.resources || [];
    const awaitingResources = resources.length === 0 && !node.data.resolved;

    return (
        <>
            <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-6 pb-4 pt-6">
                <div className="min-w-0">
                    <span
                        className={`mb-2 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.09em] ring-1 ring-inset ${s.chip}`}
                    >
                        Stage {(node.data.stage ?? 0) + 1}
                    </span>
                    <h2 className="text-lg font-semibold leading-snug tracking-tight text-slate-900">
                        {node.data.label}
                    </h2>
                </div>
                <button
                    onClick={onClose}
                    aria-label="Close panel"
                    className="shrink-0 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                >
                    <X size={18} />
                </button>
            </header>

            <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
                {node.data.description && (
                    <p className="text-sm leading-relaxed text-slate-600">{node.data.description}</p>
                )}

                <section className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                    <div className="mb-3 flex items-center justify-between">
                        <label htmlFor="node-progress" className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Your progress
                        </label>
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold tabular-nums text-slate-700">{progress}%</span>
                            <button
                                onClick={() => onProgressChange(node.id, progress >= 100 ? 0 : 100)}
                                className={`rounded-lg px-2 py-1 text-[11px] font-semibold transition-colors ${
                                    progress >= 100
                                        ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                                        : 'bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50'
                                }`}
                            >
                                {progress >= 100 ? 'Reset' : 'Mark done'}
                            </button>
                        </div>
                    </div>
                    <input
                        id="node-progress"
                        type="range"
                        min={0}
                        max={100}
                        step={10}
                        value={progress}
                        onChange={(e) => onProgressChange(node.id, parseInt(e.target.value, 10))}
                        className={`w-full cursor-pointer ${s.accent}`}
                    />
                    <p className="mt-2 text-[11px] text-slate-400">Saved in this browser, per roadmap.</p>
                </section>

                <section>
                    <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <BookOpen size={14} />
                        Learning resources
                        {resources.length > 0 && (
                            <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] tabular-nums text-slate-500">
                                {resources.length}
                            </span>
                        )}
                    </h3>

                    {awaitingResources ? (
                        <div className="space-y-3" aria-live="polite">
                            <p className="flex items-center gap-2 text-xs text-slate-400">
                                <Sparkles size={13} className="animate-pulse" />
                                Searching for resources…
                            </p>
                            {[0, 1, 2].map((i) => (
                                <div key={i} className="animate-pulse rounded-xl border border-slate-100 bg-white p-4">
                                    <div className="mb-3 h-3 w-16 rounded-full bg-slate-100" />
                                    <div className="mb-2 h-3.5 w-3/4 rounded bg-slate-100" />
                                    <div className="h-3 w-1/2 rounded bg-slate-100" />
                                </div>
                            ))}
                        </div>
                    ) : resources.length > 0 ? (
                        <div className="space-y-3">
                            {resources.map((res, idx) => (
                                <ResourceCard
                                    key={`${res.url || 'no-url'}-${idx}`}
                                    title={res.title}
                                    description={res.description}
                                    type={res.type || 'Resource'}
                                    source={getHostname(res.url)}
                                    url={res.url}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="rounded-xl border border-dashed border-slate-200 p-5 text-center">
                            <p className="text-sm text-slate-500">No resources found for this topic.</p>
                            <p className="mt-1 text-xs text-slate-400">
                                Retrieval came back empty rather than guessing — try the topic name in your usual search
                                engine.
                            </p>
                        </div>
                    )}
                </section>
            </div>
        </>
    );
};

const ResourceCardContent = ({ type, source, title, description, isValidUrl }) => {
    return (
        <>
            <div className="mb-2 flex items-start justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500 transition-colors group-hover:bg-primary-50 group-hover:text-primary-700">
                    <ResourceTypeIcon type={type} />
                    {type}
                </span>
                <span className="max-w-[130px] truncate text-[11px] text-slate-400">{source}</span>
            </div>
            <h4 className="mb-1.5 text-sm font-medium leading-snug text-slate-800 transition-colors group-hover:text-primary-700">
                {title}
            </h4>
            {description && (
                <p className="line-clamp-2 text-xs leading-relaxed text-slate-500">{description}</p>
            )}
            {!isValidUrl && <p className="mt-2 text-[11px] font-medium text-slate-400">Link unavailable</p>}
        </>
    );
};

const ResourceCard = ({ title, description, type, source, url }) => {
    const isValidUrl = url && (url.startsWith('http') || url.startsWith('https'));

    if (isValidUrl) {
        return (
            <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="group block rounded-xl border border-slate-200 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-primary-200 hover:shadow-md hover:shadow-slate-900/5"
            >
                <ResourceCardContent type={type} source={source} title={title} description={description} isValidUrl />
            </a>
        );
    }

    return (
        <div className="block cursor-not-allowed rounded-xl border border-slate-200 bg-slate-50 p-4 opacity-70">
            <ResourceCardContent
                type={type}
                source={source}
                title={title}
                description={description}
                isValidUrl={false}
            />
        </div>
    );
};

export default Roadmap;
