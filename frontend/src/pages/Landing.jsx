import React, { useState, useEffect } from 'react';
import { ArrowRight, GitBranch, Library, CircleCheck, CornerDownLeft, BarChart2, Clock } from 'lucide-react';
// Imported capitalised so the flat ESLint config (no eslint-plugin-react) still
// sees `<Motion.div>` member-expression JSX as a use of the binding.
import { motion as Motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

// Builds a URL-safe slug from a topic string, e.g. "Machine Learning!" -> "machine-learning".
const slugify = (str) =>
    str
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');

const POPULAR_TOPICS = ['Machine Learning', 'Web Development', 'Data Science', 'Cybersecurity', 'Photography'];

const LEVELS = [
    { value: 'beginner', label: 'Beginner', hint: 'Foundations first' },
    { value: 'intermediate', label: 'Intermediate', hint: 'Core techniques' },
    { value: 'advanced', label: 'Advanced', hint: 'Depth + capstone' },
];

const LEVEL_COPY = {
    beginner: 'Foundations first, jargon-free, with time estimates for every step.',
    intermediate: 'One refresher, then core techniques and an applied project.',
    advanced: 'No basics — deep topics, tradeoffs, and a production-grade capstone.',
};

// Every claim here describes something the app actually does - the DAG layout,
// the retrieval pipeline, and the localStorage progress tracking. No invented
// counts, logos or testimonials.
const FEATURES = [
    {
        icon: GitBranch,
        title: 'Prerequisite-aware',
        body: 'Topics are laid out as a dependency graph, so you can see what has to come before what.',
    },
    {
        icon: Library,
        title: 'Real, checkable resources',
        body: 'Each topic is matched against a resource index — courses, docs and videos, with links you can open.',
    },
    {
        icon: CircleCheck,
        title: 'Progress that sticks',
        body: 'Mark topics off as you work through them. Your progress is saved in this browser, per roadmap.',
    },
];

const fadeUp = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } },
};

const stagger = {
    hidden: {},
    show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};

const Landing = () => {
    const [input, setInput] = useState('');
    const [level, setLevel] = useState('beginner');
    const navigate = useNavigate();

    useEffect(() => {
        document.title = 'OpenRoadMap — AI-Powered Learning Roadmaps';
    }, []);

    // Navigates immediately - Roadmap.jsx owns the actual streaming
    // generation (and its loading/error states) once there, so the graph
    // starts appearing in ~1-2s instead of this page sitting on a spinner
    // for the whole ~10-15s generation. Level travels as ?level= so the
    // roadmap page (and shared links) stay reproducible.
    const goToRoadmap = (query, nextLevel = level) => {
        if (!query.trim()) return;
        navigate(`/roadmap/${slugify(query)}?level=${nextLevel}`);
    };

    const handleSearch = () => goToRoadmap(input);

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    };

    const handleTagClick = (tag) => {
        setInput(tag);
        goToRoadmap(tag);
    };

    return (
        <div className="relative flex min-h-[calc(100vh-69px)] flex-col bg-paper font-sans text-ink">
            {/* Editorial frame: hairline rules top and bottom + generous
                whitespace carry the hierarchy now that the pastel blobs,
                gradient headline, and search-box glow are gone. */}
            <div aria-hidden className="mx-auto w-full max-w-5xl px-6 pt-10">
                <hr className="hairline-rule border-t" />
            </div>

            <main id="main-content" className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6 py-14 sm:py-20">
                <Motion.div variants={stagger} initial="hidden" animate="show" className="flex w-full flex-col items-center">
                    {/* Badge — solid ink dot, no ping. */}
                    <Motion.span
                        variants={fadeUp}
                        className="mb-7 inline-flex items-center gap-2 rounded-full border border-ink/15 bg-white px-3.5 py-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-soft"
                    >
                        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-signal" />
                        Open source · AI-generated learning roadmaps
                    </Motion.span>

                    {/* Hero title — flat ink, display face. No gradient text. */}
                    <Motion.h1
                        variants={fadeUp}
                        className="text-center font-display text-[2.75rem] font-bold leading-[1.05] tracking-[-0.03em] text-ink sm:text-6xl"
                    >
                        Learn anything,
                        <br />
                        in the right order.
                    </Motion.h1>

                    <Motion.p
                        variants={fadeUp}
                        className="mt-5 max-w-xl text-center text-base leading-relaxed text-slate-600 sm:text-lg"
                    >
                        Name a goal and get a structured roadmap — every topic placed after its prerequisites, each one
                        paired with real learning resources.
                    </Motion.p>

                    {/* Level selector — personalizes depth/scope, travels as ?level=. */}
                    <Motion.div variants={fadeUp} className="mt-8 flex flex-col items-center gap-2.5">
                        <span id="level-label" className="font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-600">
                            Your level
                        </span>
                        <div role="group" aria-labelledby="level-label" className="flex flex-wrap items-center justify-center gap-2">
                            {LEVELS.map((l) => {
                                const active = level === l.value;
                                return (
                                    <button
                                        key={l.value}
                                        type="button"
                                        onClick={() => setLevel(l.value)}
                                        aria-pressed={active}
                                        title={l.hint}
                                        className={[
                                            'rounded-full border px-4 py-1.5 text-sm font-semibold transition-all',
                                            active
                                                ? 'border-ink bg-ink text-white shadow-sm'
                                                : 'border-ink/15 bg-white text-slate-600 hover:border-ink/35 hover:text-ink',
                                        ].join(' ')}
                                    >
                                        {l.label}
                                    </button>
                                );
                            })}
                        </div>
                        <p aria-live="polite" className="text-[13px] text-slate-600">
                            {LEVEL_COPY[level]}
                        </p>
                    </Motion.div>

                    {/* Search box — flat card with hairline border, no glow. */}
                    <Motion.div variants={fadeUp} className="mt-7 w-full max-w-2xl">
                        <div className="flex items-center gap-2 rounded-2xl border border-ink/15 bg-white p-2 shadow-[0_1px_2px_rgba(20,33,61,0.05),0_16px_40px_-24px_rgba(20,33,61,0.25)] transition-shadow focus-within:border-ink/30 focus-within:shadow-[0_1px_2px_rgba(20,33,61,0.05),0_20px_48px_-24px_rgba(20,33,61,0.3)]">
                            <input
                                type="text"
                                placeholder="What do you want to learn?"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                aria-label="Learning goal"
                                className="min-w-0 flex-1 border-none bg-transparent px-4 py-3 text-base text-ink placeholder-slate-500 focus:outline-none focus:ring-0 sm:text-lg"
                            />
                            <kbd className="hidden shrink-0 items-center gap-1 rounded-md border border-ink/10 bg-paper px-1.5 py-1 font-mono text-[10px] font-medium text-slate-500 sm:flex">
                                <CornerDownLeft size={11} aria-hidden />
                                Enter
                            </kbd>
                            <button
                                onClick={handleSearch}
                                aria-label="Generate roadmap"
                                className="flex shrink-0 items-center gap-1.5 rounded-xl bg-ink px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-[#0e1930] active:scale-[0.98]"
                            >
                                Generate
                                <ArrowRight size={16} aria-hidden />
                            </button>
                        </div>
                        {/* Duration/difficulty promise line. */}
                        <p className="mt-3 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-center text-[13px] text-slate-600">
                            <Clock size={13} aria-hidden className="text-signal" />
                            <span>Every roadmap ships with time estimates, prerequisites in order, and resources leveled to you.</span>
                        </p>
                    </Motion.div>

                    {/* Popular topics */}
                    <Motion.div variants={fadeUp} className="mt-6 flex flex-wrap items-center justify-center gap-2">
                        <span className="mr-1 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-500">Try</span>
                        {POPULAR_TOPICS.map((tag) => (
                            <button
                                key={tag}
                                onClick={() => handleTagClick(tag)}
                                className="rounded-full border border-ink/15 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-600 transition-all hover:-translate-y-0.5 hover:border-signal/50 hover:text-signal-dark hover:shadow-sm"
                            >
                                {tag}
                            </button>
                        ))}
                    </Motion.div>

                    {/* Hairline divider before features. */}
                    <Motion.div variants={fadeUp} aria-hidden className="mt-16 w-full max-w-4xl">
                        <hr className="hairline-rule border-t" />
                    </Motion.div>

                    {/* Feature highlights */}
                    <Motion.div
                        variants={fadeUp}
                        className="mt-8 grid w-full max-w-4xl grid-cols-1 gap-3 sm:grid-cols-3"
                    >
                        {FEATURES.map((feature) => (
                            <div
                                key={feature.title}
                                className="rounded-2xl border border-ink/10 bg-white p-5 transition-all hover:-translate-y-0.5 hover:border-ink/20 hover:shadow-lg hover:shadow-slate-900/[0.06]"
                            >
                                <span className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-white">
                                    <feature.icon size={17} aria-hidden />
                                </span>
                                <h3 className="mb-1 font-display text-sm font-semibold tracking-tight text-ink">
                                    {feature.title}
                                </h3>
                                <p className="text-[13px] leading-relaxed text-slate-600">{feature.body}</p>
                            </div>
                        ))}
                    </Motion.div>

                    <Motion.button
                        variants={fadeUp}
                        onClick={() => navigate('/evaluation')}
                        className="mt-8 inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 transition-colors hover:text-ink"
                    >
                        <BarChart2 size={13} aria-hidden />
                        See how retrieval and generation quality are measured
                        <ArrowRight size={12} aria-hidden />
                    </Motion.button>
                </Motion.div>
            </main>

            <div aria-hidden className="mx-auto w-full max-w-5xl px-6 pb-10">
                <hr className="hairline-rule border-t" />
            </div>
        </div>
    );
};

export default Landing;
