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
  <div className="flex-1 h-screen flex items-center justify-center">
    <Loader2 className="animate-spin text-purple-600" size={32} />
  </div>
);

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-slate-50 font-sans flex flex-col">
        <Navbar />
        <div className="flex-1 relative">
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
