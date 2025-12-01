import React from 'react';
import { Plus, MessageSquare, BookOpen, Settings, User, BarChart2, Map } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

const Sidebar = () => {
    const navigate = useNavigate();
    const location = useLocation();

    const isActive = (path) => location.pathname === path;

    return (
        <div className="w-64 h-screen bg-white border-r border-slate-200 flex flex-col p-4">
            {/* New Chat Button */}
            <button
                onClick={() => navigate('/')}
                className="flex items-center gap-2 bg-primary-600 text-white px-4 py-3 rounded-lg hover:bg-primary-700 transition-colors shadow-sm mb-8"
            >
                <Plus size={20} />
                <span className="font-medium">New chat</span>
            </button>

            {/* Navigation Links */}
            <div className="flex-1 overflow-y-auto">
                <div className="text-xs font-semibold text-slate-400 mb-3 px-2">Menu</div>
                <div className="space-y-1">
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

                <div className="text-xs font-semibold text-slate-400 mt-6 mb-3 px-2">Recent</div>
                <div className="space-y-1">
                    <button className="w-full text-left px-2 py-2 text-slate-600 hover:bg-slate-50 rounded-md text-sm truncate">
                        Previous conversation
                    </button>
                </div>
            </div>
        </div>
    );
};

const NavItem = ({ icon, label, active, onClick }) => (
    <button
        onClick={onClick}
        className={`flex items-center gap-3 w-full px-2 py-2 rounded-md text-sm transition-colors ${active ? 'bg-primary-50 text-primary-700 font-medium' : 'text-slate-600 hover:bg-slate-50'
            }`}
    >
        {icon}
        <span>{label}</span>
    </button>
);

export default Sidebar;
