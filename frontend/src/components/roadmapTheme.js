// Visual language for the roadmap graph.
//
// A roadmap is a DAG laid out in depth tiers ("stages"): stage 0 holds the
// topics with no prerequisites, stage 1 holds everything that only depends on
// stage 0, and so on. Without a per-stage cue, every node in a row reads as one
// undifferentiated cluster, so each stage gets its own accent that runs through
// the node's left rail, its stage label, its progress bar, the edges leading
// into it, and its minimap dot.
//
// The ramp is deliberately ordered cool -> warm so depth reads as a journey
// (foundations -> mastery) rather than as an arbitrary rainbow. Node bodies stay
// white; the accent only ever appears in small, structural doses.
//
// Class strings are written out in full (never interpolated) so Tailwind's
// content scanner can see them.
export const STAGES = [
    {
        key: 'violet',
        hex: '#7c3aed',
        rail: 'bg-violet-500',
        dot: 'bg-violet-500',
        label: 'text-violet-600',
        chip: 'bg-violet-50 text-violet-700 ring-violet-200/70',
        bar: 'bg-violet-500',
        ring: 'ring-violet-400',
        hover: 'hover:border-violet-200',
        accent: 'accent-violet-600',
    },
    {
        key: 'indigo',
        hex: '#4f46e5',
        rail: 'bg-indigo-500',
        dot: 'bg-indigo-500',
        label: 'text-indigo-600',
        chip: 'bg-indigo-50 text-indigo-700 ring-indigo-200/70',
        bar: 'bg-indigo-500',
        ring: 'ring-indigo-400',
        hover: 'hover:border-indigo-200',
        accent: 'accent-indigo-600',
    },
    {
        key: 'sky',
        hex: '#0284c7',
        rail: 'bg-sky-500',
        dot: 'bg-sky-500',
        label: 'text-sky-600',
        chip: 'bg-sky-50 text-sky-700 ring-sky-200/70',
        bar: 'bg-sky-500',
        ring: 'ring-sky-400',
        hover: 'hover:border-sky-200',
        accent: 'accent-sky-600',
    },
    {
        key: 'teal',
        hex: '#0d9488',
        rail: 'bg-teal-500',
        dot: 'bg-teal-500',
        label: 'text-teal-600',
        chip: 'bg-teal-50 text-teal-700 ring-teal-200/70',
        bar: 'bg-teal-500',
        ring: 'ring-teal-400',
        hover: 'hover:border-teal-200',
        accent: 'accent-teal-600',
    },
    {
        key: 'emerald',
        hex: '#059669',
        rail: 'bg-emerald-500',
        dot: 'bg-emerald-500',
        label: 'text-emerald-600',
        chip: 'bg-emerald-50 text-emerald-700 ring-emerald-200/70',
        bar: 'bg-emerald-500',
        ring: 'ring-emerald-400',
        hover: 'hover:border-emerald-200',
        accent: 'accent-emerald-600',
    },
    {
        key: 'amber',
        hex: '#d97706',
        rail: 'bg-amber-500',
        dot: 'bg-amber-500',
        label: 'text-amber-600',
        chip: 'bg-amber-50 text-amber-700 ring-amber-200/70',
        bar: 'bg-amber-500',
        ring: 'ring-amber-400',
        hover: 'hover:border-amber-200',
        accent: 'accent-amber-600',
    },
    {
        key: 'rose',
        hex: '#e11d48',
        rail: 'bg-rose-500',
        dot: 'bg-rose-500',
        label: 'text-rose-600',
        chip: 'bg-rose-50 text-rose-700 ring-rose-200/70',
        bar: 'bg-rose-500',
        ring: 'ring-rose-400',
        hover: 'hover:border-rose-200',
        accent: 'accent-rose-600',
    },
];

// Stages beyond the ramp wrap around rather than falling back to a neutral -
// a 8+ level roadmap is rare, and a repeated hue reads better than a grey row.
export const stageStyle = (stage = 0) => STAGES[((stage % STAGES.length) + STAGES.length) % STAGES.length];

// Fixed node geometry. The layout in Roadmap.jsx needs these to centre each
// row, and the node component needs the width to match exactly.
export const NODE_WIDTH = 264;
export const NODE_GAP_X = 56;
export const NODE_GAP_Y = 196;
