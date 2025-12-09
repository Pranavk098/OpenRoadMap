import json
from pathlib import Path

ROADMAPS = [
    # --- TECH ---
    {
        "skill": "React Development",
        "prerequisites": ["HTML", "CSS", "JavaScript (ES6+)"],
        "roadmap": [
            {"stage": 1, "title": "Fundamentals", "topics": ["JSX", "Components", "Props & State"], "estimated_time": "2 weeks"},
            {"stage": 2, "title": "Hooks & Effects", "topics": ["useState", "useEffect", "Custom Hooks"], "estimated_time": "2 weeks"},
            {"stage": 3, "title": "Routing & State Management", "topics": ["React Router", "Context API", "Redux Toolkit"], "estimated_time": "3 weeks"},
            {"stage": 4, "title": "Advanced Patterns", "topics": ["HOCs", "Render Props", "Performance Optimization"], "estimated_time": "2 weeks"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    {
        "skill": "Docker & Kubernetes",
        "prerequisites": ["Linux Basics", "Networking Fundamentals"],
        "roadmap": [
            {"stage": 1, "title": "Docker Basics", "topics": ["Containers vs VMs", "Dockerfile", "Docker Compose"], "estimated_time": "1 week"},
            {"stage": 2, "title": "Container Orchestration", "topics": ["Kubernetes Architecture", "Pods", "Services"], "estimated_time": "2 weeks"},
            {"stage": 3, "title": "Advanced K8s", "topics": ["Helm Charts", "Ingress Controllers", "Persistent Volumes"], "estimated_time": "3 weeks"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    # --- CREATIVE ---
    {
        "skill": "Digital Illustration",
        "prerequisites": ["Drawing Basics", "Tablet Familiarity"],
        "roadmap": [
            {"stage": 1, "title": "Software Basics", "topics": ["Layers", "Brushes", "Masking"], "estimated_time": "1 week"},
            {"stage": 2, "title": "Sketching & Line Art", "topics": ["Gesture Drawing", "Clean Line Art", "Anatomy"], "estimated_time": "3 weeks"},
            {"stage": 3, "title": "Color & Lighting", "topics": ["Color Theory", "Shading", "Blending Modes"], "estimated_time": "3 weeks"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    {
        "skill": "Screenwriting",
        "prerequisites": ["Creative Writing Interest"],
        "roadmap": [
            {"stage": 1, "title": "Formatting", "topics": ["Sluglines", "Action Lines", "Dialogue"], "estimated_time": "1 week"},
            {"stage": 2, "title": "Structure", "topics": ["Three-Act Structure", "The Hero's Journey", "Plot Points"], "estimated_time": "2 weeks"},
            {"stage": 3, "title": "Character Development", "topics": ["Character Arcs", "Backstory", "Voice"], "estimated_time": "2 weeks"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    # --- BUSINESS ---
    {
        "skill": "Agile Project Management",
        "prerequisites": ["Basic Management Concepts"],
        "roadmap": [
            {"stage": 1, "title": "Agile Manifesto", "topics": ["Values", "Principles", "Waterfall vs Agile"], "estimated_time": "1 week"},
            {"stage": 2, "title": "Scrum Framework", "topics": ["Roles", "Events", "Artifacts"], "estimated_time": "2 weeks"},
            {"stage": 3, "title": "Kanban & Lean", "topics": ["WIP Limits", "Flow", "Kaizen"], "estimated_time": "1 week"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    {
        "skill": "SEO Fundamentals",
        "prerequisites": ["Basic Web Knowledge"],
        "roadmap": [
            {"stage": 1, "title": "Keyword Research", "topics": ["Search Volume", "Intent", "Long-tail Keywords"], "estimated_time": "1 week"},
            {"stage": 2, "title": "On-Page SEO", "topics": ["Title Tags", "Meta Descriptions", "Content Optimization"], "estimated_time": "2 weeks"},
            {"stage": 3, "title": "Off-Page SEO", "topics": ["Backlinks", "Domain Authority", "Local SEO"], "estimated_time": "2 weeks"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    # --- SCIENCE ---
    {
        "skill": "Introduction to Astrophysics",
        "prerequisites": ["Physics I", "Calculus I"],
        "roadmap": [
            {"stage": 1, "title": "Stellar Physics", "topics": ["Star Formation", "Fusion", "Stellar Evolution"], "estimated_time": "3 weeks"},
            {"stage": 2, "title": "Galactic Astronomy", "topics": ["Milky Way Structure", "Dark Matter", "Galaxy Types"], "estimated_time": "3 weeks"},
            {"stage": 3, "title": "Cosmology", "topics": ["Big Bang", "Expansion of Universe", "CMB"], "estimated_time": "3 weeks"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    {
        "skill": "Molecular Biology Basics",
        "prerequisites": ["General Biology", "Chemistry"],
        "roadmap": [
            {"stage": 1, "title": "DNA Structure", "topics": ["Nucleotides", "Double Helix", "Replication"], "estimated_time": "2 weeks"},
            {"stage": 2, "title": "Central Dogma", "topics": ["Transcription", "Translation", "Protein Synthesis"], "estimated_time": "2 weeks"},
            {"stage": 3, "title": "Genetics", "topics": ["Mendelian Genetics", "Mutations", "Gene Regulation"], "estimated_time": "2 weeks"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    # --- OTHER ---
    {
        "skill": "Sourdough Bread Baking",
        "prerequisites": ["Kitchen Basics"],
        "roadmap": [
            {"stage": 1, "title": "The Starter", "topics": ["Creating Starter", "Feeding Schedule", "Discard"], "estimated_time": "2 weeks"},
            {"stage": 2, "title": "Dough Management", "topics": ["Autolyse", "Folding", "Bulk Fermentation"], "estimated_time": "2 weeks"},
            {"stage": 3, "title": "Baking", "topics": ["Shaping", "Scoring", "Oven Spring"], "estimated_time": "Ongoing"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    },
    {
        "skill": "Urban Gardening",
        "prerequisites": ["None"],
        "roadmap": [
            {"stage": 1, "title": "Planning", "topics": ["Space Assessment", "Light Conditions", "Container Selection"], "estimated_time": "1 week"},
            {"stage": 2, "title": "Soil & Planting", "topics": ["Potting Mix", "Seeds vs Starts", "Watering"], "estimated_time": "2 weeks"},
            {"stage": 3, "title": "Maintenance", "topics": ["Pruning", "Pest Control", "Harvesting"], "estimated_time": "Ongoing"}
        ],
        "source": "manual_annotation",
        "annotator": "Pranav Koduru"
    }
]

def main():
    output_dir = Path(__file__).parent.parent.parent / 'data' / 'manual'
    output_dir.mkdir(parents=True, exist_ok=True)

    for roadmap in ROADMAPS:
        filename = roadmap['skill'].lower().replace(' ', '_').replace('&', 'and') + '.json'
        file_path = output_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(roadmap, f, indent=2)
        
        print(f"Created: {filename}")

if __name__ == "__main__":
    main()
