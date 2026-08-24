import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const NotFound = () => {
    const navigate = useNavigate();

    useEffect(() => {
        document.title = 'Page Not Found · OpenRoadMap';
    }, []);

    return (
        <div className="flex-1 h-screen flex flex-col items-center justify-center gap-4 text-center px-6">
            <h1 className="text-6xl font-extrabold text-slate-200">404</h1>
            <h2 className="text-2xl font-bold text-slate-800">Page not found</h2>
            <p className="text-slate-500 max-w-md">
                The page you're looking for doesn't exist or may have moved.
            </p>
            <button
                onClick={() => navigate('/')}
                className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
            >
                Go home
            </button>
        </div>
    );
};

export default NotFound;
