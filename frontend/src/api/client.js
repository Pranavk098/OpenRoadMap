const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Generous timeout: roadmap generation runs an LLM pipeline and a cold
// backend can be slow to respond to its first request.
const REQUEST_TIMEOUT_MS = 30000;

// Thrown by generateRoadmap. `kind` lets callers show a specific message:
// 'timeout' (request took too long - likely a cold backend), 'network'
// (fetch couldn't reach the server at all), or 'server' (server responded
// with a non-2xx status).
export class RoadmapApiError extends Error {
    constructor(message, kind) {
        super(message);
        this.name = 'RoadmapApiError';
        this.kind = kind;
    }
}

export const generateRoadmap = async (goal) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
        const response = await fetch(`${API_BASE_URL}/generate-roadmap`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ goal }),
            signal: controller.signal,
        });

        if (!response.ok) {
            throw new RoadmapApiError(`Server responded with ${response.status}`, 'server');
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        if (error instanceof RoadmapApiError) throw error;
        if (error.name === 'AbortError') {
            throw new RoadmapApiError('Request timed out', 'timeout');
        }
        // fetch() rejects with a TypeError when it can't reach the server at all
        // (connection refused, DNS failure, offline, etc.).
        throw new RoadmapApiError('Network error', 'network');
    } finally {
        clearTimeout(timeoutId);
    }
};

// Maps a RoadmapApiError (or any error) to user-facing copy.
export const describeApiError = (error) => {
    switch (error?.kind) {
        case 'timeout':
            return 'Waking up the server, please try again in a moment.';
        case 'network':
            return "Can't reach the server right now.";
        case 'server':
            return 'The server had trouble generating that roadmap. Please try again.';
        default:
            return 'Something went wrong. Please try again.';
    }
};
