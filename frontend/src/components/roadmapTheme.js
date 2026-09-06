// Visual language for the roadmap graph.
//
// Nodes are coloured by curriculum role (node_type), not by depth tier:
// foundation / concept / project / capstone. Depth already has a cue —
// vertical position plus the "Stage N" label — so painting all 7+ tiers as
// a rainbow only added noise. Four muted editorial stops (ink -> steel ->
// clay -> signal) read as one journey from foundations to capstone, and the
// single signal accent (#E85D2A) is reserved for the capstone + interactive
// highlights. Gradients are reserved for data-viz only, never for node
// chrome or text.
//
// Class strings are written out in full (never interpolated) so Tailwind's
// content scanner can see them.
//
// Backend contract (src/models.py): node_type is optional, one of
// foundation/concept/project/capstone. Old cached roadmaps may omit it —
// callers fall back to depth-based stageStyle in that case.
export const NODE_TYPES = {
    foundation: {
        key: 'foundation',
        label: 'Foundation',
        hex: '#14213D',
        rail: 'bg-[#14213D]',
        dot: 'bg-[#14213D]',
        text: 'text-[#14213D]',
        chip: 'bg-[#14213D]/[0.06] text-[#14213D] ring-[#14213D]/20',
        bar: 'bg-[#14213D]',
        ring: 'ring-[#14213D]/40',
        hover: 'hover:border-[#14213D]/40',
        accent: 'accent-[#14213D]',
    },
    concept: {
        key: 'concept',
        label: 'Concept',
        hex: '#3D5A80',
        rail: 'bg-[#3D5A80]',
        dot: 'bg-[#3D5A80]',
        text: 'text-[#3D5A80]',
        chip: 'bg-[#3D5A80]/10 text-[#293E57] ring-[#3D5A80]/25',
        bar: 'bg-[#3D5A80]',
        ring: 'ring-[#3D5A80]/40',
        hover: 'hover:border-[#3D5A80]/40',
        accent: 'accent-[#3D5A80]',
    },
    project: {
        key: 'project',
        label: 'Project',
        hex: '#9C4A1A',
        rail: 'bg-[#9C4A1A]',
        dot: 'bg-[#9C4A1A]',
        text: 'text-[#9C4A1A]',
        chip: 'bg-[#9C4A1A]/10 text-[#7A3A14] ring-[#9C4A1A]/25',
        bar: 'bg-[#9C4A1A]',
        ring: 'ring-[#9C4A1A]/40',
        hover: 'hover:border-[#9C4A1A]/40',
        accent: 'accent-[#9C4A1A]',
    },
    capstone: {
        key: 'capstone',
        label: 'Capstone',
        hex: '#E85D2A',
        rail: 'bg-[#E85D2A]',
        dot: 'bg-[#E85D2A]',
        text: 'text-[#B53E14]',
        chip: 'bg-[#FDEEE6] text-[#B53E14] ring-[#E85D2A]/30',
        bar: 'bg-[#E85D2A]',
        ring: 'ring-[#E85D2A]/50',
        hover: 'hover:border-[#E85D2A]/50',
        accent: 'accent-[#E85D2A]',
    },
};

const TYPE_KEYS = ['foundation', 'concept', 'project', 'capstone'];

// Primary entry point: colour by curriculum role. Unknown / missing types
// fall back to concept (the neutral middle) rather than guessing from depth,
// so a mistyped backend value never paints a foundation as a capstone.
export const nodeTypeStyle = (nodeType) => {
    const key = (nodeType || '').strip().toLowerCase();
    return NODE_TYPES[key] || NODE_TYPES.concept;
};

// Depth-based fallback for roadmaps cached before node_type existed.
// Maps stage index onto the same 4-stop ramp (wraps) so legacy data still
// renders in the editorial palette instead of the old 7-step rainbow.
export const stageStyle = (stage = 0) => {
    const idx = ((stage % TYPE_KEYS.length) + TYPE_KEYS.length) % TYPE_KEYS.length;
    const style = NODE_TYPES[TYPE_KEYS[idx]];
    // Preserve the legacy field names RoadmapNode.jsx / Roadmap.jsx read.
    return { ...style, label: style.text };
};

// Fixed node geometry. The layout in Roadmap.jsx needs these to centre each
// row, and the node component needs the width to match exactly.
export const NODE_WIDTH = 264;
export const NODE_GAP_X = 56;
export const NODE_GAP_Y = 196;
