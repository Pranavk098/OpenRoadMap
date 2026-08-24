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

// Streams a roadmap via the backend's SSE endpoint instead of waiting for
// the full non-streaming response - the DAG structure typically arrives in
// ~1-2s (before any resource retrieval), so callers can render the graph
// immediately and let resources fill in per-node as they resolve, instead
// of a blank/loading state for the whole ~10-15s generation.
//
// Event contract (see DECISIONS.md "SSE event contract"):
//   structure -> { nodes: [{id, title, description, prerequisites}, ...] }
//   resources -> { id, resources: [...] }   (once per node)
//   done      -> { cache_hit }
//   error     -> { error, correlation_id }  (terminal, in place of done)
//
// Returns a handle with `.close()` to stop listening (e.g. on unmount or
// when the user navigates away mid-stream).
export const streamRoadmap = (goal, { onStructure, onResources, onDone, onError }) => {
    const url = `${API_BASE_URL}/v1/roadmap/stream?goal=${encodeURIComponent(goal)}`;
    const source = new EventSource(url);
    let gotAnyMessage = false;
    let closed = false;

    const close = () => {
        if (closed) return;
        closed = true;
        source.close();
    };

    source.addEventListener('structure', (e) => {
        gotAnyMessage = true;
        try {
            onStructure?.(JSON.parse(e.data).nodes || []);
        } catch (err) {
            console.error('Failed to parse structure event:', err);
        }
    });

    source.addEventListener('resources', (e) => {
        gotAnyMessage = true;
        try {
            const { id, resources } = JSON.parse(e.data);
            onResources?.(id, resources || []);
        } catch (err) {
            console.error('Failed to parse resources event:', err);
        }
    });

    source.addEventListener('done', (e) => {
        gotAnyMessage = true;
        close();
        try {
            onDone?.(JSON.parse(e.data));
        } catch {
            onDone?.({});
        }
    });

    source.addEventListener('error', (e) => {
        // A named "error" SSE event from our backend (has e.data) is
        // distinct from EventSource's own connection-level error below.
        if (!e.data) return;
        gotAnyMessage = true;
        close();
        try {
            const { error } = JSON.parse(e.data);
            onError?.(new RoadmapApiError(error || 'Generation failed', 'server'));
        } catch {
            onError?.(new RoadmapApiError('Generation failed', 'server'));
        }
    });

    // EventSource's built-in error handler: fires on connection failure
    // (can't reach the server at all) or if the browser can't parse the
    // stream. We never want its default auto-reconnect behavior here -
    // this is a one-shot request, not a live feed - so always close.
    source.onerror = () => {
        if (closed) return;
        close();
        onError?.(new RoadmapApiError(gotAnyMessage ? 'Connection lost' : "Can't reach the server right now.", gotAnyMessage ? 'server' : 'network'));
    };

    return { close };
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
