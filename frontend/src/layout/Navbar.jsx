import React from 'react';
import { MessageSquare, BarChart2, Map } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

const Navbar = () => {
    const navigate = useNavigate();
    const location = useLocation();

    const isActive = (path) => location.pathname === path;

    return (
        <div className="w-full bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center sticky top-0 z-50 shadow-sm">
            {/* Logo */}
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate('/')}>
                <h1 className="text-xl font-bold text-slate-800 tracking-tight">
                    OPENROADMAP
                </h1>
            </div>

            {/* Navigation Links */}
            <div className="flex items-center gap-2">
                <NavItem
                    icon={<MessageSquare size={18} />}
                    label="Home"
                    active={isActive('/')}
                    onClick={() => navigate('/')}
                />
                <NavItem
                    icon={<Map size={18} />}
                    label="Roadmap Demo"
                    active={isActive('/roadmap')}
                    onClick={() => navigate('/roadmap')}
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
