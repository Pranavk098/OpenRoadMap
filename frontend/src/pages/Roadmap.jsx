import React, { useState, useEffect, useCallback } from 'react';
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Book, Video, Globe, X, ArrowLeft } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

const mockRoadmapData = {
    nodes: [
        {
            id: '1',
            title: 'Python Basics',
            description: 'Learn the fundamentals of Python programming language.',
            resources: [
                { title: 'Python for Beginners', url: 'https://www.python.org', type: 'Official Doc' },
                { title: 'Automate the Boring Stuff', url: 'https://automatetheboringstuff.com', type: 'Book' }
            ],
            prerequisites: []
        },
        {
            id: '2',
            title: 'Data Structures',
            description: 'Understand lists, dictionaries, sets, and tuples.',
            resources: [],
            prerequisites: ['1']
        },
        {
            id: '3',
            title: 'NumPy & Pandas',
            description: 'Learn data manipulation and analysis libraries.',
            resources: [],
            prerequisites: ['2']
        },
        {
            id: '4',
            title: 'Data Visualization',
            description: 'Master Matplotlib and Seaborn.',
            resources: [],
            prerequisites: ['3']
        },
        {
            id: '5',
            title: 'Machine Learning Concepts',
            description: 'Intro to supervised and unsupervised learning.',
            resources: [],
            prerequisites: ['3']
        }
    ]
};

const Roadmap = () => {
    const location = useLocation();
    const navigate = useNavigate();

    // Use passed state or fallback to mock data for "Demo" mode
    const { roadmapData, topic } = location.state || {
        roadmapData: mockRoadmapData,
        topic: 'Python Data Science (Demo)'
    };

    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState(null);

    useEffect(() => {
        if (!roadmapData) return;

        // Transform API data to React Flow format
        const { nodes: apiNodes } = roadmapData;
        const newNodes = [];
        const newEdges = [];
        const nodeMap = new Map();

        // 1. Create Nodes (Initial Pass)
        apiNodes.forEach((node) => {
            nodeMap.set(node.id, node);
        });

        // 2. Calculate Levels for Layout
        const levels = new Map();
        const getLevel = (nodeId) => {
            if (levels.has(nodeId)) return levels.get(nodeId);

            const node = nodeMap.get(nodeId);
            if (!node || !node.prerequisites || node.prerequisites.length === 0) {
                levels.set(nodeId, 0);
                return 0;
            }

            let maxPrereqLevel = -1;
            node.prerequisites.forEach(prereqId => {
                maxPrereqLevel = Math.max(maxPrereqLevel, getLevel(prereqId));
            });

            const level = maxPrereqLevel + 1;
            levels.set(nodeId, level);
            return level;
        };

        apiNodes.forEach(node => getLevel(node.id));

        // 3. Assign Positions based on Levels
        const levelCounts = new Map();
        apiNodes.forEach(node => {
            const level = levels.get(node.id);
            const count = levelCounts.get(level) || 0;

            newNodes.push({
                id: node.id,
                position: { x: count * 250, y: level * 150 }, // Simple grid layout
                data: { label: node.title, description: node.description, resources: node.resources },
                style: {
                    background: '#fef08a', // Yellow
                    border: '2px solid #000', // Black border
                    borderRadius: '4px',
                    padding: '10px',
                    width: 180,
                    fontWeight: 'bold',
                    color: '#000', // Black text
                    boxShadow: '4px 4px 0px 0px #000' // Retro shadow
                }
            });

            levelCounts.set(level, count + 1);

            // Create Edges
            if (node.prerequisites) {
                node.prerequisites.forEach(prereqId => {
                    newEdges.push({
                        id: `e${prereqId}-${node.id}`,
                        source: prereqId,
                        target: node.id,
                        markerEnd: { type: MarkerType.ArrowClosed, color: '#000' },
                        type: 'smoothstep',
                        animated: false,
                        style: { stroke: '#000', strokeWidth: 2 }
                    });
                });
            }
        });

        setNodes(newNodes);
        setEdges(newEdges);
    }, [roadmapData, setNodes, setEdges]);

    const onNodeClick = useCallback((event, node) => {
        if (node && node.data) {
            setSelectedNode(node);
        }
    }, []);

    // Helper to safely get hostname
    const getHostname = (url) => {
        try {
            return new URL(url).hostname.replace('www.', '');
        } catch (e) {
            return 'Resource';
        }
    };

    return (
        <div className="flex-1 h-screen relative bg-slate-50">
            {/* Header / Back Button */}
            <div className="absolute top-4 left-4 z-10 flex items-center gap-4">
                <button
                    onClick={() => navigate('/')}
                    className="bg-white p-2 rounded-lg shadow-sm border border-slate-200 hover:bg-slate-50 flex items-center gap-2 text-slate-600"
                >
                    <ArrowLeft size={20} />
                    <span className="font-medium">Back</span>
                </button>
                {topic && (
                    <div className="bg-white px-4 py-2 rounded-lg shadow-sm border border-slate-200">
                        <h1 className="font-bold text-slate-800 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-500"></span>
                            {topic}
                        </h1>
                    </div>
                )}
            </div>

            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodesDraggable={false}
                fitView
            >
                <Background color="#aaa" gap={16} />
                <Controls />
            </ReactFlow>

            {/* Resource Sidebar */}
            {selectedNode && (
                <div className="absolute right-0 top-0 h-full w-[450px] bg-white shadow-xl border-l border-slate-200 p-6 overflow-y-auto z-20 animate-in slide-in-from-right duration-300">
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-bold text-slate-800">{selectedNode.data.label}</h2>
                        <button onClick={() => setSelectedNode(null)} className="p-2 hover:bg-slate-100 rounded-full">
                            <X size={20} className="text-slate-500" />
                        </button>
                    </div>

                    <div className="space-y-6">
                        <div className="bg-primary-50 p-4 rounded-lg border border-primary-100">
                            <h3 className="font-semibold text-primary-800 mb-2">Description</h3>
                            <p className="text-sm text-primary-700 leading-relaxed">
                                {selectedNode.data.description}
                            </p>
                        </div>

                        <div>
                            <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
                                <Book size={18} /> Recommended Resources
                            </h3>
                            <div className="space-y-3">
                                {selectedNode.data.resources && selectedNode.data.resources.length > 0 ? (
                                    selectedNode.data.resources.map((res, idx) => (
                                        <ResourceCard
                                            key={idx}
                                            title={res.title}
                                            description={res.description}
                                            type={res.type || "Resource"}
                                            source={getHostname(res.url)}
                                            url={res.url}
                                            icon={<Globe size={16} className="text-blue-500" />}
                                        />
                                    ))
                                ) : (
                                    <p className="text-sm text-slate-400 italic">No resources found for this topic.</p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

const ResourceCard = ({ title, description, type, source, url, icon }) => {
    const isValidUrl = url && (url.startsWith('http') || url.startsWith('https'));

    const Content = () => (
        <>
            <div className="flex items-start justify-between mb-2">
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 group-hover:bg-primary-50 group-hover:text-primary-600 transition-colors capitalize">
                    {type}
                </span>
                <span className="text-xs text-slate-400 truncate max-w-[120px]">{source}</span>
            </div>
            <h4 className="font-medium text-slate-800 mb-2 group-hover:text-primary-700 transition-colors leading-tight">{title}</h4>
            {description && (
                <p className="text-xs text-slate-500 mb-3 line-clamp-2 leading-relaxed">
                    {description}
                </p>
            )}
            <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
                {icon}
                <span>{isValidUrl ? 'View Resource' : 'Link Unavailable'}</span>
            </div>
        </>
    );

    if (isValidUrl) {
        return (
            <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-4 rounded-xl border border-slate-200 hover:border-primary-300 hover:shadow-md transition-all bg-white group"
            >
                <Content />
            </a>
        );
    }

    return (
        <div className="block p-4 rounded-xl border border-slate-200 bg-slate-50 opacity-75 cursor-not-allowed">
            <Content />
        </div>
    );
};

export default Roadmap;
