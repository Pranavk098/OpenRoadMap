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
    BookOpenText,
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
    Clock,
    ListOrdered,
    GitBranch,
    RotateCcw,
} from 'lucide-react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { streamRoadmap, describeApiError } from '../api/client';
import RoadmapNode from '../components/RoadmapNode';
import { nodeTypeStyle, stageStyle, NODE_WIDTH, NODE_GAP_X, NODE_GAP_Y, NODE_TYPES } from '../components/roadmapTheme';

// Defined once at module scope: ReactFlow warns (and remounts every node) if
// this object identity changes between renders.
const nodeTypes = { roadmapTopic: RoadmapNode };

const FIT_VIEW_OPTIONS = { padding: 0.28, maxZoom: 1 };

const VALID_LEVELS = ['beginner', 'intermediate', 'advanced'];

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
    if (/video|youtube/i.test(type)) return <Video size={size} aria-hidden />;
    if (/course|class|tutorial|lecture/i.test(type)) return <GraduationCap size={size} aria-hidden />;
    if (/doc|reference|official|spec/i.test(type)) return <FileText size={size} aria-hidden />;
    if (/book|article|blog|paper|guide/i.test(type)) return <BookOpen size={size} aria-hidden />;
    if (/search/i.test(type)) return <Search size={size} aria-hidden />;
    return <Globe size={size} aria-hidden />;
};

const formatDuration = (durationMin) => {
    if (durationMin == null || Number.isNaN(Number(durationMin))) return null;
    const mins = Number(durationMin);
    if (mins <= 0) return null;
    if (mins < 60) return `${Math.round(mins)} min`;
    const hours = mins / 60;
    return `${Number.isInteger(hours) ? hours : hours.toFixed(1)}h`;
};

const formatEstHours = (estHours) => {
    if (estHours == null || Number.isNaN(Number(estHours))) return null;
    const h = Number(estHours);
    if (h <= 0) return null;
    return `~${Number.isInteger(h) ? h : h.toFixed(1)}h`;
};

const Roadmap = () => {
    const { slug } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const levelParam = (searchParams.get('level') || 'beginner').toLowerCase();
    const level = VALID_LEVELS.includes(levelParam) ? levelParam : 'beginner';

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

    // Timeline (vertical phase-grouped list, mobile-first) vs graph
    // (existing ReactFlow canvas). Timeline is the default on narrow screens
    // so the page is usable at 375px without pinching around a canvas.
    const [view, setView] = useState(() =>
        typeof window !== 'undefined' && window.innerWidth < 768 ? 'timeline' : 'graph'
    );

    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNodeId, setSelectedNodeId] = useState(null);
    const [copied, setCopied] = useState(false);

    // Progress tracking (per node, stored in localStorage keyed by topic)
    const [progressMap, setProgressMap] = useState({});

    const cacheKey = slug ? `roadmap:${slug}:${level}` : null;

    // Streams the roadmap instead of waiting for the full response: the DAG
    // structure typically arrives in ~1-2s, so the graph renders almost
    // immediately and resources fill in per-node afterward, instead of a
    // blank loading state for the whole ~10-15s generation.
    const loadRoadmap = useCallback((targetSlug, targetLevel = 'beginner') => {
        const normalizedLevel = VALID_LEVELS.includes((targetLevel || '').toLowerCase())
            ? targetLevel.toLowerCase()
            : 'beginner';
        activeSlugRef.current = `${targetSlug}:${normalizedLevel}`;
        streamRef.current?.close();
        setLoadState('loading');
        setLoadError(null);
        setStreaming(false);

        const key = targetSlug ? `roadmap:${targetSlug}:${normalizedLevel}` : null;
        const stored = key ? sessionStorage.getItem(key) : null;
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
            level: normalizedLevel,
            onStructure: (structureNodes) => {
                if (activeSlugRef.current !== `${targetSlug}:${normalizedLevel}`) return;
                liveData = {
                    goal: bestEffortTopic,
                    level: normalizedLevel,
                    nodes: structureNodes.map((n) => ({ ...n, resources: [], resolved: false })),
                };
                setRoadmapData(liveData);
                setTopic(bestEffortTopic);
                setLoadState('ready');
            },
            onResources: (id, resources) => {
                if (activeSlugRef.current !== `${targetSlug}:${normalizedLevel}` || !liveData) return;
                liveData = {
                    ...liveData,
                    nodes: liveData.nodes.map((n) => (n.id === id ? { ...n, resources, resolved: true } : n)),
                };
                setRoadmapData(liveData);
            },
            onDone: () => {
                if (activeSlugRef.current !== `${targetSlug}:${normalizedLevel}` || !liveData) return;
                settleAll();
                setStreaming(false);
                try {
                    sessionStorage.setItem(key, JSON.stringify({ roadmapData: liveData, topic: bestEffortTopic }));
                } catch {
                    // sessionStorage full / unavailable - roadmap still renders.
                }
            },
            onError: (err) => {
                if (activeSlugRef.current !== `${targetSlug}:${normalizedLevel}`) return;
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

    // On mount / when the slug or level changes: prefer router state (fast
    // path from just navigating here from Landing), then sessionStorage, then
    // fall back to regenerating from the API. Never falls back to fake data.
    useEffect(() => {
        if (location.state?.roadmapData) {
            const { roadmapData: fastData, topic: fastTopic } = location.state;
            activeSlugRef.current = `${slug}:${level}`;
            setRoadmapData(fastData);
            setTopic(fastTopic);
            setStreaming(false);
            setLoadState('ready');
            if (cacheKey) {
                try {
                    sessionStorage.setItem(cacheKey, JSON.stringify({ roadmapData: fastData, topic: fastTopic }));
                } catch {
                    // Non-fatal.
                }
            }
            return;
        }

        loadRoadmap(slug, level);
        // Only re-run when the slug or level itself changes.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [slug, level]);

    useEffect(() => {
        setSelectedNodeId(null);
        setProgressMap(() => {
            if (!topic) return {};
            try {
                const saved = localStorage.getItem(`progress_${topic}`);
                return saved ? JSON.parse(saved) : {};
            } catch {
                return {};
            }
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

            const lvl = maxPrereqLevel + 1;
            levels.set(nodeId, lvl);
            return lvl;
        };

        apiNodes.forEach((node) => getLevel(node.id));

        // Group by depth, preserving API order within each row as the tiebreak.
        const rows = new Map();
        apiNodes.forEach((node) => {
            const lvl = levels.get(node.id);
            if (!rows.has(lvl)) rows.set(lvl, []);
            rows.get(lvl).push(node.id);
        });
        const maxLevel = Math.max(...rows.keys());

        // One barycentre pass: order each row by the mean position of its
        // prerequisites in the row above. Cheap, and it stops edges from
        // criss-crossing the whole canvas the way a raw insertion-order grid did.
        const columnOf = new Map();
        (rows.get(0) || []).forEach((id, i) => columnOf.set(id, i));
        for (let lvl = 1; lvl <= maxLevel; lvl += 1) {
            const row = rows.get(lvl) || [];
            const ranked = row.map((id, i) => {
                const prereqs = (nodeMap.get(id).prerequisites || []).filter((p) => columnOf.has(p));
                const barycentre = prereqs.length
                    ? prereqs.reduce((sum, p) => sum + columnOf.get(p), 0) / prereqs.length
                    : i;
                return { id, barycentre, i };
            });
            ranked.sort((a, b) => a.barycentre - b.barycentre || a.i - b.i);
            rows.set(lvl, ranked.map((r) => r.id));
            ranked.forEach((r, i) => columnOf.set(r.id, i));
        }

        // Centre every row on x=0 so the graph reads as a symmetric tree rather
        // than a left-ragged staircase.
        const newNodes = [];
        const newEdges = [];
        rows.forEach((row, lvl) => {
            const rowWidth = row.length * NODE_WIDTH + (row.length - 1) * NODE_GAP_X;
            row.forEach((id, index) => {
                const node = nodeMap.get(id);
                newNodes.push({
                    id,
                    type: 'roadmapTopic',
                    position: {
                        x: -rowWidth / 2 + index * (NODE_WIDTH + NODE_GAP_X),
                        y: lvl * NODE_GAP_Y,
                    },
                    data: {
                        label: node.title,
                        description: node.description,
                        stage: lvl,
                        node_type: node.node_type,
                        est_hours: node.est_hours,
                        outcomes: node.outcomes || [],
                        baseProgress: node.progress || 0,
                    },
                });

                // Create edges, skipping any that reference a node id that
                // doesn't exist (dangling prerequisite) so we never hand
                // ReactFlow an edge with a missing source/target.
                const accent = (node.node_type ? nodeTypeStyle(node.node_type) : stageStyle(lvl)).hex;
                (node.prerequisites || []).forEach((prereqId) => {
                    if (!nodeMap.has(prereqId)) return;
                    newEdges.push({
                        id: `e${prereqId}-${id}`,
                        source: prereqId,
                        target: id,
                        type: 'smoothstep',
                        pathOptions: { borderRadius: 28 },
                        markerEnd: { type: MarkerType.ArrowClosed, color: accent, width: 16, height: 16 },
                        // Edges take the colour of the node they lead *into*.
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

    const totalHours = useMemo(
        () =>
            (roadmapData?.nodes || []).reduce(
                (sum, n) => sum + (typeof n.est_hours === 'number' && n.est_hours > 0 ? n.est_hours : 0),
                0
            ),
        [roadmapData]
    );

    // Timeline grouping: same depth tiers as the graph, in API order.
    const timelinePhases = useMemo(() => {
        if (displayNodes.length === 0) return [];
        const byStage = new Map();
        displayNodes.forEach((n) => {
            const stage = n.data.stage ?? 0;
            if (!byStage.has(stage)) byStage.set(stage, []);
            byStage.get(stage).push(n);
        });
        return [...byStage.entries()]
            .sort((a, b) => a[0] - b[0])
            .map(([stage, items]) => {
                const hours = items.reduce(
                    (sum, n) => sum + (typeof n.data.est_hours === 'number' && n.data.est_hours > 0 ? n.data.est_hours : 0),
                    0
                );
                return { stage, items, hours };
            });
    }, [displayNodes]);

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
                    try {
                        localStorage.setItem(`progress_${topic}`, JSON.stringify(updated));
                    } catch {
                        // Private mode / quota — progress still works in-memory.
                    }
                }
                return updated;
            });
        },
        [topic]
    );

    const handleRetry = () => loadRoadmap(slug, level);

    const handleCopyLink = async () => {
        const url = `${window.location.origin}/roadmap/${slug}?level=${level}`;
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
            <div className="flex-1 min-h-[calc(100vh-69px)] flex flex-col bg-paper px-6 py-10">
                <main id="main-content" className="mx-auto w-full max-w-3xl">
                    <div className="flex items-center gap-4" aria-live="polite" aria-busy="true">
                        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-ink">
                            <Loader2 className="animate-spin text-white" size={26} aria-hidden />
                        </div>
                        <div>
                            <p className="font-display text-base font-semibold text-ink">Mapping out your roadmap</p>
                            <p className="mt-1 text-sm text-slate-600">
                                Working out the topics and what depends on what — this usually takes a couple of seconds.
                            </p>
                        </div>
                    </div>
                    {/* Skeleton shimmer placeholders keep the page shape while
                        the DAG streams in — never a bare spinner. */}
                    <div className="mt-8 space-y-3" aria-hidden>
                        {[0, 1, 2].map((i) => (
                            <div key={i} className="rounded-2xl border border-ink/10 bg-white p-5">
                                <div className="skeleton-shimmer mb-3 h-3 w-24 rounded-full" />
                                <div className="skeleton-shimmer mb-2 h-4 w-2/3 rounded" />
                                <div className="skeleton-shimmer h-3 w-1/2 rounded" />
                            </div>
                        ))}
                    </div>
                    <span className="sr-only">Loading roadmap…</span>
                </main>
            </div>
        );
    }

    if (loadState === 'error') {
        const message =
            loadError?.kind === 'missing'
                ? "We couldn't tell which roadmap you wanted."
                : describeApiError(loadError);

        return (
            <div className="flex-1 min-h-[calc(100vh-69px)] flex flex-col items-center justify-center gap-4 bg-paper text-center px-6">
                <main id="main-content" className="flex flex-col items-center gap-4">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 ring-1 ring-inset ring-red-100">
                        <AlertTriangle className="text-red-600" size={26} aria-hidden />
                    </div>
                    <h2 className="max-w-md font-display text-xl font-semibold tracking-tight text-ink">{message}</h2>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={handleRetry}
                            className="rounded-xl bg-ink px-4 py-2 font-medium text-white transition-colors hover:bg-[#0e1930]"
                        >
                            Retry
                        </button>
                        <button
                            onClick={() => navigate('/')}
                            className="rounded-xl border border-ink/15 bg-white px-4 py-2 font-medium text-slate-600 transition-colors hover:bg-paper"
                        >
                            Go home
                        </button>
                    </div>
                </main>
            </div>
        );
    }

    return (
        <div className="flex-1 min-h-[calc(100vh-69px)] relative bg-paper flex flex-col">
            <a href="#roadmap-main" className="skip-link">
                Skip to roadmap content
            </a>
            {/* Floating chrome. One toolbar instead of four competing cards, so
                the roadmap itself is the loudest thing on the page. */}
            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-wrap items-start justify-between gap-2 p-3 sm:p-4">
                <div className="pointer-events-auto flex max-w-full flex-wrap items-center gap-1 rounded-2xl border border-ink/10 bg-white/90 p-1.5 shadow-lg shadow-slate-900/[0.06] backdrop-blur-md">
                    <button
                        onClick={() => navigate('/')}
                        aria-label="Back to home"
                        className="flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-ink/[0.06] hover:text-ink"
                    >
                        <ArrowLeft size={16} aria-hidden />
                        Back
                    </button>

                    {topic && (
                        <>
                            <span aria-hidden className="mx-1 h-6 w-px bg-ink/10" />
                            <div className="px-1.5">
                                <h1 className="max-w-[10rem] truncate font-display text-sm font-semibold tracking-tight text-ink sm:max-w-[16rem]">
                                    {topic}
                                </h1>
                                <p className="font-mono text-[11px] leading-tight text-slate-600">
                                    {nodes.length} topic{nodes.length === 1 ? '' : 's'} · {stageCount} stage
                                    {stageCount === 1 ? '' : 's'} · {level}
                                    {totalHours > 0 && ` · ~${Number.isInteger(totalHours) ? totalHours : totalHours.toFixed(1)}h`}
                                </p>
                            </div>
                        </>
                    )}

                    {nodes.length > 0 && (
                        <>
                            <span aria-hidden className="mx-1 hidden h-6 w-px bg-ink/10 sm:block" />
                            <div className="hidden items-center gap-2 px-1.5 sm:flex">
                                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-ink/10" role="progressbar" aria-valuenow={overallProgress} aria-valuemin={0} aria-valuemax={100} aria-label="Overall progress">
                                    <div
                                        className="h-full rounded-full bg-emerald-600 transition-[width] duration-300"
                                        style={{ width: `${overallProgress}%` }}
                                    />
                                </div>
                                <span className="font-mono text-xs font-semibold tabular-nums text-slate-600">
                                    {overallProgress}%
                                </span>
                            </div>
                        </>
                    )}

                    <span aria-hidden className="mx-1 h-6 w-px bg-ink/10" />
                    {/* View toggle: timeline list <-> graph canvas. */}
                    <div role="group" aria-label="Roadmap view" className="flex items-center gap-0.5 rounded-xl bg-ink/[0.05] p-0.5">
                        <button
                            onClick={() => setView('timeline')}
                            aria-pressed={view === 'timeline'}
                            aria-label="Timeline view"
                            title="Timeline view"
                            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
                                view === 'timeline' ? 'bg-white text-ink shadow-sm' : 'text-slate-500 hover:text-ink'
                            }`}
                        >
                            <ListOrdered size={15} aria-hidden />
                            <span className="hidden md:inline">Timeline</span>
                        </button>
                        <button
                            onClick={() => setView('graph')}
                            aria-pressed={view === 'graph'}
                            aria-label="Graph view"
                            title="Graph view"
                            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
                                view === 'graph' ? 'bg-white text-ink shadow-sm' : 'text-slate-500 hover:text-ink'
                            }`}
                        >
                            <GitBranch size={15} aria-hidden />
                            <span className="hidden md:inline">Graph</span>
                        </button>
                    </div>

                    <span aria-hidden className="mx-1 h-6 w-px bg-ink/10" />
                    <span aria-live="polite" role="status">
                        <button
                            onClick={handleCopyLink}
                            aria-label={copied ? 'Link copied to clipboard' : 'Copy link to this roadmap'}
                            className="flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-ink/[0.06] hover:text-ink"
                        >
                            {copied ? <Check size={16} className="text-emerald-600" aria-hidden /> : <LinkIcon size={16} aria-hidden />}
                            {copied ? 'Copied!' : 'Copy link'}
                        </button>
                    </span>
                </div>

                {/* Replaces the old unwired "GitHub Repo" box: real, live stream
                    telemetry instead of decoration. */}
                <AnimatePresence>
                    {streaming && (
                        <Motion.div
                            initial={{ opacity: 0, y: -6 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -6 }}
                            className="pointer-events-auto flex shrink-0 items-center gap-2 rounded-full border border-ink/10 bg-white/90 px-3 py-1.5 font-mono text-xs font-medium text-slate-600 shadow-lg shadow-slate-900/[0.06] backdrop-blur-md"
                            role="status"
                            aria-live="polite"
                        >
                            <Loader2 size={13} className="animate-spin text-signal" aria-hidden />
                            Curating resources
                            <span className="tabular-nums text-slate-500">
                                {resolvedCount}/{roadmapData?.nodes?.length ?? 0}
                            </span>
                        </Motion.div>
                    )}
                </AnimatePresence>
            </div>

            <main id="roadmap-main" className="flex flex-1 flex-col pt-[76px]">
                {view === 'graph' ? (
                    <div className="relative flex-1" style={{ minHeight: 'calc(100vh - 69px - 76px)' }}>
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
                            className="bg-paper"
                            aria-label={`Roadmap graph for ${topic || 'topic'}`}
                        >
                            <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="#c9cfdd" />
                            <Controls showInteractive={false} className="roadmap-controls" />
                            {nodes.length > 6 && (
                                <MiniMap
                                    pannable
                                    zoomable
                                    nodeStrokeWidth={0}
                                    nodeBorderRadius={4}
                                    nodeColor={(n) =>
                                        (n.data?.node_type
                                            ? nodeTypeStyle(n.data.node_type)
                                            : stageStyle(n.data?.stage)
                                        ).hex
                                    }
                                    maskColor="rgba(250,250,248,0.7)"
                                    className="roadmap-minimap"
                                    aria-label="Roadmap minimap"
                                />
                            )}
                            <Panel position="bottom-center" className="!mb-5">
                                <div className="flex items-center gap-2.5 rounded-full border border-ink/10 bg-white/90 px-3.5 py-1.5 shadow-sm backdrop-blur-md">
                                    <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.09em] text-slate-500">
                                        Types
                                    </span>
                                    {Object.values(NODE_TYPES).map((t) => (
                                        <span key={t.key} className="flex items-center gap-1 text-[11px] font-medium text-slate-600">
                                            <span aria-hidden className={`h-2 w-2 rounded-full ${t.dot}`} />
                                            {t.label}
                                        </span>
                                    ))}
                                </div>
                            </Panel>
                        </ReactFlow>
                    </div>
                ) : (
                    <div className="mx-auto w-full max-w-3xl flex-1 px-4 pb-16 sm:px-6">
                        {timelinePhases.map((phase) => (
                            <section key={phase.stage} aria-labelledby={`phase-${phase.stage}-heading`} className="relative mt-8 first:mt-4">
                                <header className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-ink/10 pb-2">
                                    <h2 id={`phase-${phase.stage}-heading`} className="font-display text-lg font-semibold tracking-tight text-ink">
                                        Stage {phase.stage + 1}
                                    </h2>
                                    <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-slate-500">
                                        {phase.items.length} topic{phase.items.length === 1 ? '' : 's'}
                                        {phase.hours > 0 && ` · ~${Number.isInteger(phase.hours) ? phase.hours : phase.hours.toFixed(1)}h`}
                                    </p>
                                </header>
                                <ol className="relative space-y-3 border-l-2 border-ink/10 pl-4 sm:pl-5">
                                    {phase.items.map((node) => (
                                        <TimelineCard
                                            key={node.id}
                                            node={node}
                                            selected={node.id === selectedNodeId}
                                            onSelect={() => setSelectedNodeId(node.id)}
                                            onProgressChange={setProgress}
                                            getHostname={getHostname}
                                            onRetry={handleRetry}
                                        />
                                    ))}
                                </ol>
                            </section>
                        ))}
                    </div>
                )}
            </main>

            {/* Resource Sidebar */}
            <AnimatePresence>
                {selectedNode && (
                    <Motion.aside
                        key="resource-panel"
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        transition={{ type: 'spring', stiffness: 380, damping: 38 }}
                        className="absolute right-0 top-0 z-20 flex h-full w-full max-w-[440px] flex-col border-l border-ink/10 bg-white shadow-[-16px_0_48px_-24px_rgba(15,23,42,0.3)]"
                        role="dialog"
                        aria-modal="false"
                        aria-label={`Resources for ${selectedNode.data.label}`}
                    >
                        <SidebarBody
                            node={selectedNode}
                            onClose={closeSidebar}
                            onProgressChange={setProgress}
                            getHostname={getHostname}
                            onRetry={handleRetry}
                        />
                    </Motion.aside>
                )}
            </AnimatePresence>
        </div>
    );
};

/* Timeline card: the same data as a graph node, laid out as a vertical
   list row — type badge, est_hours chip, outcomes, and resource cards
   inline so mobile readers never need the canvas. */
const TimelineCard = ({ node, selected, onSelect, onProgressChange, getHostname, onRetry }) => {
    const s = node.data.node_type ? nodeTypeStyle(node.data.node_type) : stageStyle(node.data.stage);
    const progress = node.data.progress ?? 0;
    const complete = progress >= 100;
    const resources = node.data.resources || [];
    const awaiting = resources.length === 0 && !node.data.resolved;
    const est = formatEstHours(node.data.est_hours);
    const outcomes = Array.isArray(node.data.outcomes) ? node.data.outcomes.filter(Boolean).slice(0, 3) : [];

    return (
        <li>
            <article
                aria-current={selected ? 'true' : undefined}
                className={[
                    'relative rounded-2xl border bg-white p-4 transition-all sm:p-5',
                    selected
                        ? `border-transparent shadow-md ring-2 ${s.ring}`
                        : 'border-ink/10 shadow-sm hover:border-ink/25 hover:shadow-md',
                ].join(' ')}
            >
                <span aria-hidden className={`absolute inset-y-0 left-0 w-1.5 rounded-l-2xl ${s.rail}`} />
                <div className="pl-2">
                    <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.09em] ring-1 ring-inset ${s.chip}`}>
                            {(s.label || s.key || 'Concept')} · Stage {(node.data.stage ?? 0) + 1}
                        </span>
                        {est && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-ink/[0.05] px-2 py-0.5 font-mono text-[10px] font-medium tabular-nums text-ink ring-1 ring-inset ring-ink/10">
                                <Clock size={10} aria-hidden />
                                {est}
                            </span>
                        )}
                        <span className="ml-auto flex items-center gap-2">
                            <span className="font-mono text-[11px] font-semibold tabular-nums text-slate-600">{progress}%</span>
                            <button
                                onClick={() => onProgressChange(node.id, progress >= 100 ? 0 : 100)}
                                aria-label={progress >= 100 ? `Reset progress for ${node.data.label}` : `Mark ${node.data.label} as done`}
                                className={`rounded-lg px-2 py-1 text-[11px] font-semibold transition-colors ${
                                    complete
                                        ? 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                                        : 'bg-white text-slate-600 ring-1 ring-inset ring-ink/15 hover:bg-paper'
                                }`}
                            >
                                {complete ? 'Reset' : 'Mark done'}
                            </button>
                        </span>
                    </div>
                    <button onClick={onSelect} className="block w-full text-left" aria-label={`Open resources for ${node.data.label}`}>
                        <h3 className="mb-1 font-display text-[16px] font-semibold leading-snug tracking-tight text-ink">
                            {node.data.label}
                        </h3>
                        {node.data.description && (
                            <p className="text-sm leading-relaxed text-slate-600">{node.data.description}</p>
                        )}
                    </button>
                    {outcomes.length > 0 && (
                        <ul className="mt-2.5 space-y-1 border-t border-ink/[0.07] pt-2.5" aria-label={`Outcomes for ${node.data.label}`}>
                            {outcomes.map((o, i) => (
                                <li key={i} className="flex gap-1.5 text-[13px] leading-snug text-slate-600">
                                    <Check size={13} aria-hidden className="mt-0.5 shrink-0 text-emerald-700" />
                                    {o}
                                </li>
                            ))}
                        </ul>
                    )}
                    <div className="mt-3">
                        {awaiting ? (
                            <TimelineSkeleton />
                        ) : resources.length > 0 ? (
                            <div className="space-y-2">
                                {resources.map((res, idx) => (
                                    <ResourceCard
                                        key={`${res.url || 'no-url'}-${idx}`}
                                        title={res.title}
                                        description={res.description}
                                        type={res.type || 'Resource'}
                                        source={getHostname(res.url)}
                                        url={res.url}
                                        durationMin={res.duration_min}
                                        resourceLevel={res.level}
                                        free={res.free}
                                    />
                                ))}
                            </div>
                        ) : (
                            <EmptyResources compact onRetry={onRetry} topicLabel={node.data.label} />
                        )}
                    </div>
                </div>
                <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-ink/[0.07]" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label={`Progress for ${node.data.label}`}>
                    <div
                        className={`h-full rounded-full transition-[width] duration-300 ${complete ? 'bg-emerald-600' : s.bar}`}
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </article>
        </li>
    );
};

const TimelineSkeleton = () => (
    <div className="space-y-2" aria-live="polite" aria-label="Finding resources">
        <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-slate-500">Finding resources…</p>
        {[0, 1].map((i) => (
            <div key={i} className="rounded-xl border border-ink/[0.07] bg-white p-3.5" aria-hidden>
                <div className="skeleton-shimmer mb-2.5 h-3 w-16 rounded-full" />
                <div className="skeleton-shimmer mb-2 h-3.5 w-3/4 rounded" />
                <div className="skeleton-shimmer h-3 w-1/2 rounded" />
            </div>
        ))}
        <span className="sr-only">Searching for resources…</span>
    </div>
);

/* Honest empty state: retrieval came back with nothing rather than guessing.
   Illustration is a simple ink line-icon composition (no stock art), plus a
   real retry action. */
const EmptyResources = ({ compact = false, onRetry, topicLabel }) => (
    <div className={`rounded-xl border border-dashed border-ink/20 bg-paper text-center ${compact ? 'p-4' : 'p-5'}`}>
        <span className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-full bg-ink/[0.06] text-ink" aria-hidden>
            <BookOpenText size={17} />
        </span>
        <p className="text-sm font-medium text-ink">No resources found{topicLabel ? ` for “${topicLabel}”` : ''}.</p>
        <p className="mx-auto mt-1 max-w-xs text-xs leading-relaxed text-slate-600">
            Retrieval came back empty rather than guessing — try the topic name in your usual search engine.
        </p>
        {onRetry && (
            <button
                onClick={onRetry}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-ink/15 bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:bg-ink hover:text-white"
            >
                <RotateCcw size={12} aria-hidden />
                Retry
            </button>
        )}
    </div>
);

const SidebarBody = ({ node, onClose, onProgressChange, getHostname, onRetry }) => {
    const s = node.data.node_type ? nodeTypeStyle(node.data.node_type) : stageStyle(node.data.stage);
    const progress = node.data.progress ?? 0;
    const resources = node.data.resources || [];
    const awaitingResources = resources.length === 0 && !node.data.resolved;
    const est = formatEstHours(node.data.est_hours);
    const outcomes = Array.isArray(node.data.outcomes) ? node.data.outcomes.filter(Boolean).slice(0, 3) : [];

    return (
        <>
            <header className="flex items-start justify-between gap-3 border-b border-ink/10 px-6 pb-4 pt-6">
                <div className="min-w-0">
                    <span className="mb-2 flex flex-wrap items-center gap-1.5">
                        <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.09em] ring-1 ring-inset ${s.chip}`}
                        >
                            {(s.label || s.key || 'Concept')} · Stage {(node.data.stage ?? 0) + 1}
                        </span>
                        {est && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-ink/[0.05] px-2 py-0.5 font-mono text-[10px] font-medium tabular-nums text-ink ring-1 ring-inset ring-ink/10">
                                <Clock size={10} aria-hidden />
                                {est} estimated
                            </span>
                        )}
                    </span>
                    <h2 className="font-display text-lg font-semibold leading-snug tracking-tight text-ink">
                        {node.data.label}
                    </h2>
                </div>
                <button
                    onClick={onClose}
                    aria-label="Close panel"
                    className="shrink-0 rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-ink/[0.06] hover:text-ink"
                >
                    <X size={18} aria-hidden />
                </button>
            </header>

            <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
                {node.data.description && (
                    <p className="text-sm leading-relaxed text-slate-600">{node.data.description}</p>
                )}

                {outcomes.length > 0 && (
                    <section aria-label={`Outcomes for ${node.data.label}`} className="rounded-xl border border-ink/10 bg-paper p-4">
                        <h3 className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-600">
                            You&apos;ll be able to
                        </h3>
                        <ul className="space-y-1.5">
                            {outcomes.map((o, i) => (
                                <li key={i} className="flex gap-1.5 text-[13px] leading-snug text-slate-700">
                                    <Check size={13} aria-hidden className="mt-0.5 shrink-0 text-emerald-700" />
                                    {o}
                                </li>
                            ))}
                        </ul>
                    </section>
                )}

                <section className="rounded-xl border border-ink/10 bg-paper p-4">
                    <div className="mb-3 flex items-center justify-between">
                        <label htmlFor="node-progress" className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-600">
                            Your progress
                        </label>
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-semibold tabular-nums text-ink">{progress}%</span>
                            <button
                                onClick={() => onProgressChange(node.id, progress >= 100 ? 0 : 100)}
                                className={`rounded-lg px-2 py-1 text-[11px] font-semibold transition-colors ${
                                    progress >= 100
                                        ? 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                                        : 'bg-white text-slate-600 ring-1 ring-inset ring-ink/15 hover:bg-paper'
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
                    <p className="mt-2 text-[11px] text-slate-500">Saved in this browser, per roadmap.</p>
                </section>

                <section>
                    <h3 className="mb-3 flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-600">
                        <BookOpen size={14} aria-hidden />
                        Learning resources
                        {resources.length > 0 && (
                            <span className="rounded-full bg-ink/[0.06] px-1.5 py-0.5 text-[10px] tabular-nums text-ink">
                                {resources.length}
                            </span>
                        )}
                    </h3>

                    {awaitingResources ? (
                        <div className="space-y-3" aria-live="polite">
                            <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-slate-500">
                                Searching for resources…
                            </p>
                            {[0, 1, 2].map((i) => (
                                <div key={i} className="rounded-xl border border-ink/[0.07] bg-white p-4" aria-hidden>
                                    <div className="skeleton-shimmer mb-3 h-3 w-16 rounded-full" />
                                    <div className="skeleton-shimmer mb-2 h-3.5 w-3/4 rounded" />
                                    <div className="skeleton-shimmer h-3 w-1/2 rounded" />
                                </div>
                            ))}
                            <span className="sr-only">Searching for resources…</span>
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
                                    durationMin={res.duration_min}
                                    resourceLevel={res.level}
                                    free={res.free}
                                />
                            ))}
                        </div>
                    ) : (
                        <EmptyResources onRetry={onRetry} topicLabel={node.data.label} />
                    )}
                </section>
            </div>
        </>
    );
};

const ResourceCardContent = ({ type, source, title, description, isValidUrl, durationMin, resourceLevel, free }) => {
    const duration = formatDuration(durationMin);
    const letter = (source || 'R').charAt(0).toUpperCase();
    return (
        <span className="flex gap-3">
            {/* Favicon letter: hostname initial in an ink tile, so every card
                carries a source cue even without fetching favicons. */}
            <span
                aria-hidden
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink font-display text-sm font-semibold text-white"
            >
                {letter}
            </span>
            <span className="min-w-0 flex-1">
                <span className="mb-1.5 flex flex-wrap items-center gap-1">
                    <span className="inline-flex items-center gap-1 rounded-full bg-ink/[0.06] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink transition-colors group-hover:bg-signal-soft group-hover:text-signal-dark">
                        <ResourceTypeIcon type={type} />
                        {type}
                    </span>
                    {resourceLevel && VALID_LEVELS.includes(String(resourceLevel).toLowerCase()) && (
                        <span className="inline-flex items-center rounded-full bg-white px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide text-slate-600 ring-1 ring-inset ring-ink/15">
                            {resourceLevel}
                        </span>
                    )}
                    {duration && (
                        <span className="inline-flex items-center gap-0.5 rounded-full bg-white px-2 py-0.5 font-mono text-[10px] font-medium tabular-nums text-slate-600 ring-1 ring-inset ring-ink/15">
                            <Clock size={10} aria-hidden />
                            {duration}
                        </span>
                    )}
                    {free === true && (
                        <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-800 ring-1 ring-inset ring-emerald-200/70">
                            Free
                        </span>
                    )}
                </span>
                <span className="mb-1 block text-sm font-medium leading-snug text-ink transition-colors group-hover:text-signal-dark">
                    {title}
                </span>
                {description && (
                    <span className="line-clamp-2 block text-xs leading-relaxed text-slate-600">{description}</span>
                )}
                <span className="mt-1.5 block max-w-full truncate font-mono text-[11px] text-slate-500">{source}</span>
                {!isValidUrl && <span className="mt-1 block text-[11px] font-medium text-slate-500">Link unavailable</span>}
            </span>
        </span>
    );
};

const ResourceCard = ({ title, description, type, source, url, durationMin, resourceLevel, free }) => {
    const isValidUrl = url && (url.startsWith('http') || url.startsWith('https'));

    if (isValidUrl) {
        return (
            <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`${title} (${type}${source ? `, ${source}` : ''})`}
                className="group block rounded-xl border border-ink/10 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-signal/50 hover:shadow-md hover:shadow-slate-900/5"
            >
                <ResourceCardContent type={type} source={source} title={title} description={description} isValidUrl durationMin={durationMin} resourceLevel={resourceLevel} free={free} />
            </a>
        );
    }

    return (
        <div className="block cursor-not-allowed rounded-xl border border-ink/10 bg-paper p-4 opacity-70">
            <ResourceCardContent
                type={type}
                source={source}
                title={title}
                description={description}
                isValidUrl={false}
                durationMin={durationMin}
                resourceLevel={resourceLevel}
                free={free}
            />
        </div>
    );
};

export default Roadmap;
