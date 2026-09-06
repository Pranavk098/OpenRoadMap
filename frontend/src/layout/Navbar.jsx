import React from 'react';
import { MessageSquare, BarChart2 } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

const Navbar = () => {
    const navigate = useNavigate();
    const location = useLocation();

    const isActive = (path) => location.pathname === path;

    return (
        <div className="w-full bg-paper/90 backdrop-blur-md border-b border-ink/10 px-4 sm:px-6 py-4 flex justify-between items-center sticky top-0 z-50">
            {/* Logo — same three-node mark as the favicon / OG image */}
            <button
                className="flex items-center gap-2.5 cursor-pointer group"
                onClick={() => navigate('/')}
                aria-label="OpenRoadMap home"
            >
                <BrandMark />
                <span className="font-display text-[15px] font-semibold tracking-tight text-ink">
                    OpenRoadMap
                </span>
            </button>

            {/* Navigation Links */}
            <nav aria-label="Primary" className="flex items-center gap-2">
                <NavItem
                    icon={<MessageSquare size={18} aria-hidden />}
                    label="Home"
                    active={isActive('/')}
                    onClick={() => navigate('/')}
                />
                <NavItem
                    icon={<BarChart2 size={18} aria-hidden />}
                    label="Evaluation"
                    active={isActive('/evaluation')}
                    onClick={() => navigate('/evaluation')}
                />
            </nav>
        </div>
    );
};

// A roadmap in miniature: one root node branching into two, which is exactly
// what the graph page draws. Flat ink tile with a single signal node —
// no gradients anywhere in chrome.
const BrandMark = () => (
    <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-ink shadow-sm transition-transform group-hover:scale-105">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
                d="M12 7.5v3.25a1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 0 6 13.75V16M12 7.5v3.25a1.5 1.5 0 0 0 1.5 1.5h3a1.5 1.5 0 0 1 1.5 1.5V16"
                stroke="white"
                strokeWidth="1.9"
                strokeLinecap="round"
                strokeOpacity="0.85"
            />
            <circle cx="12" cy="5.5" r="2.4" fill="#E85D2A" />
            <circle cx="6" cy="18.5" r="2.4" fill="white" />
            <circle cx="18" cy="18.5" r="2.4" fill="white" />
        </svg>
    </span>
);

const NavItem = ({ icon, label, active, onClick }) => (
    <button
        onClick={onClick}
        aria-current={active ? 'page' : undefined}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all duration-200 ${active
                ? 'bg-ink text-white font-medium shadow-sm'
                : 'text-slate-600 hover:bg-ink/[0.06] hover:text-ink'
            }`}
    >
        {icon}
        <span>{label}</span>
    </button>
);

export default Navbar;
