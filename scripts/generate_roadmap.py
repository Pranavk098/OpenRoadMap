import json
import os
import sys
import argparse
from dotenv import load_dotenv

# Add PROJECT ROOT to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.roadmap_engine import generate_roadmap

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Generate a learning roadmap for a given skill.")
    parser.add_argument("skill", nargs="?", default="React Development", help="The skill to learn (default: 'React Development')")
    parser.add_argument("--output", default="roadmap_output.json", help="Output JSON file path")
    
    args = parser.parse_args()
    skill = args.skill
    output_file = args.output
    
    print(f"🚀 Generatng Roadmap for: {skill}")
    print("-" * 50)
    
    try:
        # Generate the roadmap using the engine
        roadmap = generate_roadmap(skill)
        
        # Convert Pydantic model to dict
        roadmap_dict = roadmap.model_dump()
        
        print("-" * 50)
        print(f"✅ Success! Generated Roadmap for '{skill}'")
        print("-" * 50)
        
        for node in roadmap.nodes:
            print(f"\n📌 Stage: {node.title}")
            print(f"   Description: {node.description}")
            print(f"   Resources:")
            for res in node.resources:
                print(f"   - [{res.type}] {res.title}")
                print(f"     🔗 {res.url}")
        
        print("-" * 50)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(roadmap_dict, f, indent=2)
            
        print(f"📄 Full JSON saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
