import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Check, Clock, Layers } from 'lucide-react';
import { nodeTypeStyle, stageStyle, NODE_WIDTH } from './roadmapTheme';

// Custom ReactFlow node for a roadmap topic.
//
// Hierarchy, top to bottom: type + stage label -> title -> description ->
// estimates/outcomes -> resource count. Colour comes from node_type
// (foundation/concept/project/capstone), not depth: depth already reads from
// vertical position + the "Stage N" suffix, so a depth rainbow was pure noise.
// The accent lives in a left rail so same-type nodes read as one band, and
// the progress bar is pinned to the bottom edge so scanning down the graph
// gives you a progress profile without opening anything.
const RoadmapNode = ({ data, selected }) => {
    // Prefer the backend's curriculum role; fall back to depth only for
    // roadmaps cached before node_type existed.
    const s = data.node_type ? nodeTypeStyle(data.node_type) : stageStyle(data.stage);
    const typeLabel = s.label || s.key || 'Concept';
    const progress = Math.max(0, Math.min(100, data.progress ?? 0));
    const complete = progress >= 100;
    const count = data.resources?.length ?? 0;
    const estHours = typeof data.est_hours === 'number' && data.est_hours > 0 ? data.est_hours : null;
    const outcomes = Array.isArray(data.outcomes) ? data.outcomes.filter(Boolean).slice(0, 3) : [];
    const stageLabel = `Stage ${(data.stage ?? 0) + 1}`;

    // Honest three-way resource state: we only say "no resources" once the
    // backend has actually answered for this node. While the stream is still
    // working through nodes, an empty list means "not yet", not "none".
    let resourceLabel;
    if (count > 0) {
        resourceLabel = `${count} resource${count === 1 ? '' : 's'}`;
    } else if (data.resolved) {
        resourceLabel = 'No resources found';
    } else {
        resourceLabel = 'Finding resources…';
    }

    return (
        <div
            style={{ width: NODE_WIDTH }}
            className={[
                'group relative overflow-hidden rounded-2xl border bg-white text-left',
                'transition-all duration-200 ease-out',
                'hover:-translate-y-0.5 hover:shadow-[0_12px_28px_-8px_rgba(15,23,42,0.18)]',
                selected
                    ? `border-transparent shadow-[0_12px_28px_-8px_rgba(15,23,42,0.22)] ring-2 ${s.ring}`
                    : `border-slate-200/80 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_6px_16px_-8px_rgba(15,23,42,0.12)] ${s.hover}`,
            ].join(' ')}
        >
            {/* Handles drive edge geometry only - the graph is read-only, so they
                stay invisible rather than adding two dots to every card. */}
            <Handle type="target" position={Position.Top} className="!h-1 !w-1 !border-0 !bg-transparent !opacity-0" />

            {/* Left rail: the node_type accent. aria-hidden — the type is also
                announced as text in the label row. */}
            <span aria-hidden className={`absolute inset-y-0 left-0 w-1.5 ${s.rail}`} />

            <div className="py-3.5 pl-5 pr-4">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                    <span className={`font-mono text-[10px] font-semibold uppercase tracking-[0.09em] ${s.text}`}>
                        {typeLabel} · {stageLabel}
                    </span>
                    {complete ? (
                        <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 ring-1 ring-inset ring-emerald-200/70">
                            <Check size={10} strokeWidth={3} aria-hidden />
                            Done
                        </span>
                    ) : progress > 0 ? (
                        <span className="font-mono text-[10px] font-semibold tabular-nums text-slate-600">{progress}%</span>
                    ) : null}
                </div>

                <h3 className="mb-1 line-clamp-2 font-display text-[15px] font-semibold leading-snug tracking-tight text-[#14213D]">
                    {data.label}
                </h3>

                {data.description && (
                    <p className="line-clamp-2 text-xs leading-relaxed text-slate-600">{data.description}</p>
                )}

                {/* Estimates + outcomes row. est_hours is a mono chip so it
                    scans as a metric; outcomes hide behind a hover/focus
                    tooltip so cards stay a uniform height. */}
                <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                    {estHours != null && (
                        <span
                            className="inline-flex items-center gap-1 rounded-full bg-[#14213D]/[0.06] px-2 py-0.5 font-mono text-[10px] font-medium tabular-nums text-[#14213D] ring-1 ring-inset ring-[#14213D]/15"
                            title={`Estimated effort: ${estHours} hour${estHours === 1 ? '' : 's'}`}
                        >
                            <Clock size={10} aria-hidden />
                            ~{Number.isInteger(estHours) ? estHours : estHours.toFixed(1)}h
                        </span>
                    )}
                    {outcomes.length > 0 && (
                        <span className="group/tip relative inline-flex">
                            <button
                                type="button"
                                aria-label={`Learning outcomes for ${data.label}: ${outcomes.join('; ')}`}
                                title={outcomes.map((o, i) => `${i + 1}. ${o}`).join('\n')}
                                className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 transition-colors hover:bg-slate-200 hover:text-[#14213D] focus-visible:outline-none"
                            >
                                {outcomes.length} outcome{outcomes.length === 1 ? '' : 's'}
                            </button>
                            <span
                                role="tooltip"
                                className="pointer-events-none absolute bottom-full left-0 z-10 mb-1.5 hidden w-52 rounded-lg border border-slate-200 bg-white p-2.5 text-left shadow-lg group-hover/tip:block group-focus-within/tip:block"
                            >
                                <span className="mb-1 block font-mono text-[9px] font-semibold uppercase tracking-[0.09em] text-slate-500">
                                    You&apos;ll be able to
                                </span>
                                <ul className="space-y-1">
                                    {outcomes.map((o, i) => (
                                        <li key={i} className="text-[11px] leading-snug text-slate-700">
                                            · {o}
                                        </li>
                                    ))}
                                </ul>
                            </span>
                        </span>
                    )}
                </div>

                <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
                    <Layers size={12} className="shrink-0" aria-hidden />
                    <span className={count === 0 && !data.resolved ? 'animate-pulse' : undefined}>{resourceLabel}</span>
                </div>
            </div>

            {/* Progress rail along the bottom edge. Always rendered so every card
                has the same height and rows stay optically aligned. */}
            <div className="h-1 w-full bg-slate-100">
                <div
                    className={`h-full transition-[width] duration-300 ease-out ${complete ? 'bg-emerald-600' : s.bar}`}
                    style={{ width: `${progress}%` }}
                />
            </div>

            <Handle type="source" position={Position.Bottom} className="!h-1 !w-1 !border-0 !bg-transparent !opacity-0" />
        </div>
    );
};

export default memo(RoadmapNode);
