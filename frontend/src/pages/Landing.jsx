import React, { useState } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { generateRoadmap } from '../api/client';

const Landing = () => {
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();

    const handleSearch = async () => {
        if (!input.trim()) return;

        setIsLoading(true);
        try {
            const data = await generateRoadmap(input);
            navigate('/roadmap', { state: { roadmapData: data, topic: input } });
        } catch (error) {
            alert('Failed to generate roadmap. Please ensure the backend is running.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    };

    const handleTagClick = (tag) => {
        setInput(tag);
        setIsLoading(true);
        generateRoadmap(tag)
            .then(data => {
                navigate('/roadmap', { state: { roadmapData: data, topic: tag } });
            })
            .catch(() => {
                alert('Failed to generate roadmap. Please ensure the backend is running.');
            })
            .finally(() => {
                setIsLoading(false);
            });
    };

    return (
        <div className="flex-1 h-screen bg-white flex flex-col relative overflow-hidden font-sans">
            {/* Background Gradients */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] bg-purple-100 rounded-full blur-3xl opacity-60"></div>
                <div className="absolute top-[20%] -right-[10%] w-[30%] h-[30%] bg-blue-100 rounded-full blur-3xl opacity-60"></div>
            </div>



            {/* Main Content */}
            <main className="flex-1 flex flex-col items-center justify-center max-w-4xl mx-auto w-full px-6 -mt-20 relative z-10">

                {/* Badge */}
                <div className="mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
                    <span className="bg-purple-50 text-purple-700 px-4 py-1.5 rounded-full text-sm font-medium border border-purple-100 flex items-center gap-2 shadow-sm">
                        🚀 AI-Powered Learning Platform
                    </span>
                </div>

                {/* Hero Title */}
                <div className="text-center mb-6 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-100">
                    <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 tracking-tight mb-2">
                        Build Your Personalized
                    </h1>
                    <h1 className="text-5xl md:text-6xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-blue-600 tracking-tight">
                        Learning Roadmap
                    </h1>
                </div>

                {/* Subtitle */}


                {/* Search Box */}
                <div className="w-full max-w-2xl relative mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300">
                    <div className="relative group">
                        <div className="absolute -inset-1 bg-gradient-to-r from-purple-600 to-blue-600 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>
                        <div className="relative flex items-center bg-white rounded-2xl shadow-xl border border-slate-100 p-2">
                            <input
                                type="text"
                                placeholder="What do you want to learn? (e.g., Machine Learning, Photography...)"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                disabled={isLoading}
                                className="flex-1 p-4 text-lg text-slate-700 placeholder-slate-400 bg-transparent border-none focus:ring-0 focus:outline-none"
                            />
                            <button
                                onClick={handleSearch}
                                disabled={isLoading}
                                className="bg-purple-600 hover:bg-purple-700 text-white p-3 rounded-xl transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed shadow-lg shadow-purple-200"
                            >
                                {isLoading ? <Loader2 size={24} className="animate-spin" /> : <Send size={24} />}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Popular Tags */}
                <div className="flex flex-wrap items-center justify-center gap-3 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-400">
                    <span className="text-slate-400 font-medium text-sm">Popular:</span>
                    {['Machine Learning', 'Web Development', 'Data Science', 'Cybersecurity', 'Photography'].map((tag) => (
                        <button
                            key={tag}
                            onClick={() => handleTagClick(tag)}
                            disabled={isLoading}
                            className="px-4 py-1.5 rounded-full bg-slate-100 text-slate-600 text-sm font-medium hover:bg-purple-50 hover:text-purple-700 hover:scale-105 transition-all duration-200 border border-transparent hover:border-purple-100"
                        >
                            {tag}
                        </button>
                    ))}
                </div>

            </main>
        </div>
    );
};

export default Landing;
