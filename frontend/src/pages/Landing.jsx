import React, { useState, useEffect } from 'react';
import { ArrowRight, GitBranch, Library, CircleCheck, CornerDownLeft, BarChart2 } from 'lucide-react';
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
    const navigate = useNavigate();

    useEffect(() => {
        document.title = 'OpenRoadMap — AI-Powered Learning Roadmaps';
    }, []);

    // Navigates immediately - Roadmap.jsx owns the actual streaming
    // generation (and its loading/error states) once there, so the graph
    // starts appearing in ~1-2s instead of this page sitting on a spinner
    // for the whole ~10-15s generation.
    const goToRoadmap = (query) => {
        if (!query.trim()) return;
        navigate(`/roadmap/${slugify(query)}`);
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
        <div className="relative isolate flex min-h-[calc(100vh-69px)] flex-col overflow-hidden bg-white font-sans">
            {/* Ambient background: two soft colour washes over a faint dot grid.
                Purely decorative, and non-interactive. */}
            <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
                <div className="absolute -left-[15%] -top-[20%] h-[55%] w-[55%] rounded-full bg-primary-200/45 blur-[110px]" />
                <div className="absolute -right-[12%] top-[8%] h-[45%] w-[45%] rounded-full bg-sky-200/45 blur-[110px]" />
                <div className="absolute -bottom-[25%] left-[25%] h-[45%] w-[45%] rounded-full bg-teal-100/50 blur-[110px]" />
                <div
                    className="absolute inset-0 opacity-[0.5]"
                    style={{
                        backgroundImage: 'radial-gradient(circle, rgb(203 213 225 / 0.7) 1px, transparent 1px)',
                        backgroundSize: '24px 24px',
                        maskImage: 'radial-gradient(ellipse 80% 60% at 50% 40%, black 30%, transparent 75%)',
                        WebkitMaskImage: 'radial-gradient(ellipse 80% 60% at 50% 40%, black 30%, transparent 75%)',
                    }}
                />
            </div>

            <main className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6 py-16">
                <Motion.div variants={stagger} initial="hidden" animate="show" className="flex w-full flex-col items-center">
                    {/* Badge */}
                    <Motion.span
                        variants={fadeUp}
                        className="mb-7 inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/70 px-3.5 py-1.5 text-xs font-medium text-slate-600 shadow-sm backdrop-blur-sm"
                    >
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary-400 opacity-75" />
                            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary-600" />
                        </span>
                        Open source · AI-generated learning roadmaps
                    </Motion.span>

                    {/* Hero title */}
                    <Motion.h1
                        variants={fadeUp}
                        className="text-center text-[2.75rem] font-bold leading-[1.05] tracking-[-0.03em] text-slate-900 sm:text-6xl"
                    >
                        Learn anything,
                        <br />
                        <span className="bg-gradient-to-r from-primary-600 via-indigo-600 to-sky-600 bg-clip-text text-transparent">
                            in the right order.
                        </span>
                    </Motion.h1>

                    <Motion.p
                        variants={fadeUp}
                        className="mt-5 max-w-xl text-center text-base leading-relaxed text-slate-500 sm:text-lg"
                    >
                        Name a goal and get a structured roadmap — every topic placed after its prerequisites, each one
                        paired with real learning resources.
                    </Motion.p>

                    {/* Search box */}
                    <Motion.div variants={fadeUp} className="relative mt-9 w-full max-w-2xl">
                        <div className="group relative">
                            <div className="absolute -inset-0.5 rounded-2xl bg-gradient-to-r from-primary-500 via-indigo-500 to-sky-500 opacity-20 blur-lg transition duration-500 group-focus-within:opacity-45 group-hover:opacity-35" />
                            <div className="relative flex items-center gap-2 rounded-2xl border border-slate-200/80 bg-white p-2 shadow-xl shadow-slate-900/[0.06] transition-shadow focus-within:shadow-2xl focus-within:shadow-primary-500/10">
                                <input
                                    type="text"
                                    placeholder="What do you want to learn?"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    aria-label="Learning goal"
                                    className="min-w-0 flex-1 border-none bg-transparent px-4 py-3 text-base text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-0 sm:text-lg"
                                />
                                <kbd className="hidden shrink-0 items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-1 text-[10px] font-medium text-slate-400 sm:flex">
                                    <CornerDownLeft size={11} />
                                    Enter
                                </kbd>
                                <button
                                    onClick={handleSearch}
                                    aria-label="Generate roadmap"
                                    className="flex shrink-0 items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-900/15 transition-all hover:bg-slate-800 active:scale-[0.98]"
                                >
                                    Generate
                                    <ArrowRight size={16} />
                                </button>
                            </div>
                        </div>
                    </Motion.div>

                    {/* Popular topics */}
                    <Motion.div variants={fadeUp} className="mt-6 flex flex-wrap items-center justify-center gap-2">
                        <span className="mr-1 text-xs font-medium uppercase tracking-wide text-slate-400">Try</span>
                        {POPULAR_TOPICS.map((tag) => (
                            <button
                                key={tag}
                                onClick={() => handleTagClick(tag)}
                                className="rounded-full border border-slate-200/80 bg-white/70 px-3.5 py-1.5 text-sm font-medium text-slate-600 backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-primary-200 hover:bg-white hover:text-primary-700 hover:shadow-sm"
                            >
                                {tag}
                            </button>
                        ))}
                    </Motion.div>

                    {/* Feature highlights */}
                    <Motion.div
                        variants={fadeUp}
                        className="mt-16 grid w-full max-w-4xl grid-cols-1 gap-3 sm:grid-cols-3"
                    >
                        {FEATURES.map((feature) => (
                            <div
                                key={feature.title}
                                className="rounded-2xl border border-slate-200/70 bg-white/60 p-5 backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-slate-200 hover:bg-white hover:shadow-lg hover:shadow-slate-900/[0.05]"
                            >
                                <span className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-600 ring-1 ring-inset ring-primary-100">
                                    <feature.icon size={17} />
                                </span>
                                <h3 className="mb-1 text-sm font-semibold tracking-tight text-slate-900">
                                    {feature.title}
                                </h3>
                                <p className="text-[13px] leading-relaxed text-slate-500">{feature.body}</p>
                            </div>
                        ))}
                    </Motion.div>

                    <Motion.button
                        variants={fadeUp}
                        onClick={() => navigate('/evaluation')}
                        className="mt-8 inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 transition-colors hover:text-slate-700"
                    >
                        <BarChart2 size={13} />
                        See how retrieval and generation quality are measured
                        <ArrowRight size={12} />
                    </Motion.button>
                </Motion.div>
            </main>
        </div>
    );
};

export default Landing;
