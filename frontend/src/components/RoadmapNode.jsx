import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Check, Layers } from 'lucide-react';
import { stageStyle, NODE_WIDTH } from './roadmapTheme';

// Custom ReactFlow node for a roadmap topic.
//
// Hierarchy, top to bottom: stage label (which depth tier this is) -> title ->
// description -> resource count. The stage accent lives in a left rail so a row
// of same-depth nodes reads as one band, and the progress bar is pinned to the
// bottom edge so scanning down the graph gives you a progress profile without
// opening anything.
const RoadmapNode = ({ data, selected }) => {
    const s = stageStyle(data.stage);
    const progress = Math.max(0, Math.min(100, data.progress ?? 0));
    const complete = progress >= 100;
    const count = data.resources?.length ?? 0;

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

            <span aria-hidden className={`absolute inset-y-0 left-0 w-1.5 ${s.rail}`} />

            <div className="py-3.5 pl-5 pr-4">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                    <span className={`text-[10px] font-semibold uppercase tracking-[0.09em] ${s.label}`}>
                        Stage {(data.stage ?? 0) + 1}
                    </span>
                    {complete ? (
                        <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200/70">
                            <Check size={10} strokeWidth={3} />
                            Done
                        </span>
                    ) : progress > 0 ? (
                        <span className="text-[10px] font-semibold tabular-nums text-slate-400">{progress}%</span>
                    ) : null}
                </div>

                <h3 className="mb-1 line-clamp-2 text-[15px] font-semibold leading-snug tracking-tight text-slate-900">
                    {data.label}
                </h3>

                {data.description && (
                    <p className="line-clamp-2 text-xs leading-relaxed text-slate-500">{data.description}</p>
                )}

                <div className="mt-3 flex items-center gap-1.5 text-[11px] font-medium text-slate-400">
                    <Layers size={12} className="shrink-0" />
                    <span className={count === 0 && !data.resolved ? 'animate-pulse' : undefined}>{resourceLabel}</span>
                </div>
            </div>

            {/* Progress rail along the bottom edge. Always rendered so every card
                has the same height and rows stay optically aligned. */}
            <div className="h-1 w-full bg-slate-100">
                <div
                    className={`h-full transition-[width] duration-300 ease-out ${complete ? 'bg-emerald-500' : s.bar}`}
                    style={{ width: `${progress}%` }}
                />
            </div>

            <Handle type="source" position={Position.Bottom} className="!h-1 !w-1 !border-0 !bg-transparent !opacity-0" />
        </div>
    );
};

export default memo(RoadmapNode);
