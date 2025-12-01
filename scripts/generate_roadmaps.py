import os
import json
import argparse
from typing import List
from roadmap_schema import Roadmap

# Try to import openai, handle if missing
try:
    from openai import OpenAI
except ImportError:
    print("Error: 'openai' package not found. Please install it using: pip install openai")
    OpenAI = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, we'll just rely on system env vars
    pass

PROMPT_TEMPLATE = """
Generate a learning roadmap for: {skill}

Format as JSON matching this schema:
{{
  "skill": "{skill}",
  "prerequisites": ["List", "of", "prerequisites"],
  "roadmap": [
    {{
      "stage": 1,
      "title": "Stage Title",
      "topics": ["Topic 1", "Topic 2"],
      "estimated_time": "Time estimate"
    }}
  ],
  "source": "synthetic_llm",
  "annotator": "LLM"
}}

Make it realistic with proper prerequisites and progression. Ensure the JSON is valid.
"""

def generate_roadmap(client, skill: str, model: str = "gpt-4o"):
    if not client:
        print("OpenAI client not initialized.")
        return None

    prompt = PROMPT_TEMPLATE.format(skill=skill)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert curriculum designer."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        
        # Validate against schema
        validated = Roadmap(**data)
        return validated.model_dump()
        
    except Exception as e:
        print(f"Error generating roadmap for {skill}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic roadmaps.")
    parser.add_argument("--skills", nargs="+", help="List of skills to generate roadmaps for")
    parser.add_argument("--api-key", help="OpenAI API Key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--base-url", help="Base URL for local LLM (e.g., http://localhost:11434/v1)")
    parser.add_argument("--model", default="gpt-4o", help="Model name to use")
    parser.add_argument("--output-dir", default="../data/synthetic", help="Output directory")
    
    args = parser.parse_args()
    
    if not OpenAI:
        return

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key and not args.base_url:
        print("Warning: No API Key provided. If using a local LLM that doesn't require a key, ignore this.")
        api_key = "dummy" # Some local servers need a non-empty key

    client = OpenAI(api_key=api_key, base_url=args.base_url)
    
    # Resolve output directory relative to this script file to ensure it goes to DataAug/data/synthetic
    # regardless of where the command is run from.
    if args.output_dir == "../data/synthetic":
        # Use robust default
        output_path = Path(__file__).resolve().parent.parent / 'data' / 'synthetic'
    else:
        output_path = Path(args.output_dir)
        
    output_path.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_path}")

    if args.skills:
        skills_to_generate = args.skills
    else:
        # Default list of skills to generate
        skills_to_generate = [
            # Tech
            "Rust Programming", "Go Language", "AWS Solution Architect", "System Design", 
            "GraphQL", "Cybersecurity Basics", "Data Science with Python", "Flutter Development",
            # Creative
            "3D Modeling with Blender", "Digital Photography", "Music Production", "UI/UX Design Principles",
            # Business
            "Product Management", "Digital Marketing Strategy", "Accounting Basics", "Public Speaking",
            # Science
            "Organic Chemistry", "Neuroscience Basics", "Quantum Physics Concepts",
            # Other
            "Chess Strategy", "Yoga for Beginners", "Personal Finance Management"
        ]

    for skill in skills_to_generate:
        print(f"Generating roadmap for: {skill}...")
        roadmap_data = generate_roadmap(client, skill, args.model)
        
        if roadmap_data:
            # Sanitize filename: replace spaces with underscores, remove non-alphanumeric chars except underscores
            safe_name = "".join(c if c.isalnum() or c == ' ' else '_' for c in skill).strip().lower().replace(' ', '_')
            # Remove duplicate underscores
            while '__' in safe_name:
                safe_name = safe_name.replace('__', '_')
                
            filename = f"{safe_name}.json"
            file_path = output_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(roadmap_data, f, indent=2)
            print(f"Saved to {file_path}")

if __name__ == "__main__":
    from pathlib import Path
    main()
