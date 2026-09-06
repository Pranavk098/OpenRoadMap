import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const NotFound = () => {
    const navigate = useNavigate();

    useEffect(() => {
        document.title = 'Page Not Found · OpenRoadMap';
    }, []);

    return (
        <div className="flex-1 h-screen flex flex-col items-center justify-center gap-4 text-center px-6 bg-paper">
            <h1 className="font-display text-6xl font-extrabold text-ink/15">404</h1>
            <h2 className="font-display text-2xl font-bold text-ink">Page not found</h2>
            <p className="text-slate-600 max-w-md">
                The page you're looking for doesn't exist or may have moved.
            </p>
            <button
                onClick={() => navigate('/')}
                className="bg-ink hover:bg-[#0e1930] text-white px-4 py-2 rounded-lg font-medium transition-colors"
            >
                Go home
            </button>
        </div>
    );
};

export default NotFound;
