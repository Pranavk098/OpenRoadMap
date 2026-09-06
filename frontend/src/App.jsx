import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import Navbar from './layout/Navbar';
import Landing from './pages/Landing';
import NotFound from './pages/NotFound';
import ErrorBoundary from './components/ErrorBoundary';

// Route-level code splitting: Evaluation (Recharts) and Roadmap (ReactFlow)
// are the only pages that need those heavy libraries, so keep them out of
// the landing page's initial bundle.
const Evaluation = lazy(() => import('./pages/Evaluation'));
const Roadmap = lazy(() => import('./pages/Roadmap'));

const PageLoadingFallback = () => (
    <div className="flex-1 h-screen flex flex-col items-center justify-center gap-4 bg-paper px-6" aria-live="polite" aria-busy="true">
        <Loader2 className="animate-spin text-ink" size={28} aria-hidden />
        <div className="w-full max-w-sm space-y-2" aria-hidden>
            <div className="skeleton-shimmer h-4 w-3/4 rounded" />
            <div className="skeleton-shimmer h-4 w-1/2 rounded" />
        </div>
        <span className="sr-only">Loading page…</span>
    </div>
);

function App() {
    return (
        <Router>
            <div className="min-h-screen bg-paper font-sans text-ink flex flex-col">
                <a href="#main-content" className="skip-link">
                    Skip to content
                </a>
                <Navbar />
                <div className="flex-1 relative flex flex-col">
                    <ErrorBoundary>
                        <Suspense fallback={<PageLoadingFallback />}>
                            <Routes>
                                <Route path="/" element={<Landing />} />
                                <Route path="/evaluation" element={<Evaluation />} />
                                <Route path="/roadmap/:slug" element={<Roadmap />} />
                                {/* Old bare /roadmap route used to silently serve fake demo data - send it home instead */}
                                <Route path="/roadmap" element={<Navigate to="/" replace />} />
                                <Route path="*" element={<NotFound />} />
                            </Routes>
                        </Suspense>
                    </ErrorBoundary>
                </div>
            </div>
        </Router>
    );
}

export default App;
