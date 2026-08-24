import React from 'react';
import { MessageSquare, BarChart2 } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

const Navbar = () => {
    const navigate = useNavigate();
    const location = useLocation();

    const isActive = (path) => location.pathname === path;

    return (
        <div className="w-full bg-white/85 backdrop-blur-md border-b border-slate-200/80 px-6 py-4 flex justify-between items-center sticky top-0 z-50">
            {/* Logo — same three-node mark as the favicon / OG image */}
            <button
                className="flex items-center gap-2.5 cursor-pointer group"
                onClick={() => navigate('/')}
                aria-label="OpenRoadMap home"
            >
                <BrandMark />
                <span className="text-[15px] font-semibold tracking-tight text-slate-900">
                    OpenRoadMap
                </span>
            </button>

            {/* Navigation Links */}
            <div className="flex items-center gap-2">
                <NavItem
                    icon={<MessageSquare size={18} />}
                    label="Home"
                    active={isActive('/')}
                    onClick={() => navigate('/')}
                />
                <NavItem
                    icon={<BarChart2 size={18} />}
                    label="Evaluation"
                    active={isActive('/evaluation')}
                    onClick={() => navigate('/evaluation')}
                />
            </div>
        </div>
    );
};

// A roadmap in miniature: one root node branching into two, which is exactly
// what the graph page draws. Kept in sync with public/favicon.svg.
const BrandMark = () => (
    <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-gradient-to-br from-primary-500 to-indigo-600 shadow-sm shadow-primary-600/25 transition-transform group-hover:scale-105">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
                d="M12 7.5v3.25a1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 0 6 13.75V16M12 7.5v3.25a1.5 1.5 0 0 0 1.5 1.5h3a1.5 1.5 0 0 1 1.5 1.5V16"
                stroke="white"
                strokeWidth="1.9"
                strokeLinecap="round"
                strokeOpacity="0.85"
            />
            <circle cx="12" cy="5.5" r="2.4" fill="white" />
            <circle cx="6" cy="18.5" r="2.4" fill="white" />
            <circle cx="18" cy="18.5" r="2.4" fill="white" />
        </svg>
    </span>
);

const NavItem = ({ icon, label, active, onClick }) => (
    <button
        onClick={onClick}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all duration-200 ${active
                ? 'bg-primary-50 text-primary-700 font-medium shadow-sm ring-1 ring-primary-100'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
    >
        {icon}
        <span>{label}</span>
    </button>
);

export default Navbar;
