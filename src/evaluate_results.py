import json
from pathway_evaluator import PathwayEvaluator


def main():
    with open('pathway_results.json', 'r') as f:
        results = json.load(f)
    
    print("Note: To evaluate results, you need the original personas.")
    print("Make sure to save personas when generating them.\n")
    
    try:
        with open('test_personas.json', 'r') as f:
            persona_data = json.load(f)
            personas = persona_data.get('personas', [])
        
        evaluations = []
        
        for result in results:
            persona = next((p for p in personas if p['persona_id'] == result['persona_id']), None)
            
            if persona:
                evaluation = PathwayEvaluator.evaluate_result(result, persona)
                evaluations.append(evaluation)
                
                summary = evaluation['match_summary']
                print(f"\nPersona: {evaluation['persona_id'][:8]}...")
                print(f"  Match Percentage: {summary['match_percentage']:.1f}%")
                print(f"  Matched: {summary['total_matched']}/{summary['total_expected']}")
                
                if summary['total_missing'] > 0:
                    print(f"  Missing Variables:")
                    for var_name, match_info in evaluation['variable_matches'].items():
                        if not match_info['matched']:
                            print(f"    - {var_name}: expected '{match_info['expected']}', got '{match_info.get('actual', 'NOT EXTRACTED')}'")
        
        with open('pathway_evaluations.json', 'w') as f:
            json.dump(evaluations, f, indent=2)
        
        print(f"\n\nEvaluations saved to pathway_evaluations.json")
        
    except FileNotFoundError:
        print("Could not find test_personas.json")
        print("When generating personas, save them using:")
        print("  factory.save_personas(personas, 'test_personas.json')")


if __name__ == "__main__":
    main()
