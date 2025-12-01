import json
import os
import sys
import glob

# Add project root to path
sys.path.append(os.getcwd())

from src.agents.roadmap_agent import RoadmapAgent
from src.agents.eval_agent import EvaluationAgent
from src.models import RoadmapResponse, RoadmapNode

def load_ground_truth(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def run_evaluation():
    print("Starting Evaluation...")
    
    roadmap_agent = RoadmapAgent()
    eval_agent = EvaluationAgent()
    
    manual_data_dir = os.path.join("data", "manual")
    json_files = glob.glob(os.path.join(manual_data_dir, "*.json"))
    
    results = []
    
    for file_path in json_files:
        print(f"\nEvaluating: {os.path.basename(file_path)}")
        ground_truth = load_ground_truth(file_path)
        
        skill = ground_truth.get("skill")
        if not skill:
            print("Skipping: No 'skill' field found.")
            continue
            
        # 1. Generate Roadmap
        print(f"Generating roadmap for '{skill}'...")
        try:
            nodes_data = roadmap_agent.generate_structure(skill)
            # Convert to RoadmapResponse object for evaluation
            roadmap_nodes = [
                RoadmapNode(
                    id=n["id"], 
                    title=n["title"], 
                    description=n["description"], 
                    prerequisites=n.get("prerequisites", []), 
                    resources=[]
                ) for n in nodes_data
            ]
            generated_roadmap = RoadmapResponse(goal=skill, nodes=roadmap_nodes)
        except Exception as e:
            print(f"Generation failed: {e}")
            continue
            
        # 2. Extract Ground Truth Topics
        gt_topics = []
        for stage in ground_truth.get("roadmap", []):
            gt_topics.extend(stage.get("topics", []))
            
        # 3. Evaluate Structure
        print("Calculating metrics...")
        metrics = eval_agent.evaluate_roadmap_structure(generated_roadmap, gt_topics)
        
        print(f"ROUGE-L: {metrics['rouge_l']:.4f}")
        print(f"BERTScore F1: {metrics['bert_score']:.4f}")
        
        results.append({
            "skill": skill,
            "metrics": metrics
        })
        
    # Summary
    print("\n=== Evaluation Summary ===")
    avg_rouge = sum(r["metrics"]["rouge_l"] for r in results) / len(results) if results else 0
    avg_bert = sum(r["metrics"]["bert_score"] for r in results) / len(results) if results else 0
    
    print(f"Total Roadmaps Evaluated: {len(results)}")
    print(f"Average ROUGE-L: {avg_rouge:.4f}")
    print(f"Average BERTScore F1: {avg_bert:.4f}")

if __name__ == "__main__":
    run_evaluation()
