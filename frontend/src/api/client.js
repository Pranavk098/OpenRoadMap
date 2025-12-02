const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const generateRoadmap = async (goal) => {
    try {
        const response = await fetch(`${API_BASE_URL}/generate-roadmap`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ goal }),
        });

        if (!response.ok) {
            throw new Error('Failed to generate roadmap');
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
};
