import React from 'react';

// Catches render/lifecycle errors in the routed page tree (e.g. a malformed
// roadmap payload) and shows a friendly fallback instead of a white screen.
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError() {
        return { hasError: true };
    }

    componentDidCatch(error, info) {
        console.error('Unhandled error in app:', error, info);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex-1 h-screen flex flex-col items-center justify-center gap-4 text-center px-6">
                    <h1 className="text-2xl font-bold text-slate-800">Something went wrong</h1>
                    <p className="text-slate-500 max-w-md">
                        We hit an unexpected error rendering this page. Try heading back home.
                    </p>
                    <a
                        href="/"
                        className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                    >
                        Go home
                    </a>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
