#!/usr/bin/env python3
"""
Simple CLI tool to test pathways with AI personas
Usage: python run_test.py <pathway_id> [num_personas]
"""
import sys
import json
from persona_factory import PersonaFactory
from pathway_runner import PathwayRunner
from pathway_evaluator import PathwayEvaluator


def print_banner(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)


def main():
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python run_test.py <pathway_id> [num_personas]")
        print("\nExample:")
        print("  python run_test.py fecb7311-770d-4ffc-8347-0ebc9f323674 3")
        sys.exit(1)
    
    pathway_id = sys.argv[1]
    num_personas = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    print_banner(f"🤖 Pathway Regression Test")
    print(f"Pathway ID: {pathway_id}")
    print(f"Personas: {num_personas}")
    
    # Generate personas
    print("\n⚙️  Generating personas...")
    factory = PersonaFactory(pathway_id, options_per_variable=10)
    print(f"   Pathway: {factory.pathway_data.get('name', 'Unknown')}")
    
    personas = factory.generate_personas(n=num_personas)
    print(f"   ✅ Generated {len(personas)} personas")
    
    # Run tests
    runner = PathwayRunner()
    results = []
    evaluations = []
    
    for i, persona in enumerate(personas, 1):
        print_banner(f"👤 Persona {i}/{len(personas)}")
        
        # Show personality
        p = persona['personality']
        print(f"Personality: {p['communication_style']}, {p['patience_level']}, {p['attitude']}")
        print(f"Goal: {list(persona['goal']['extracted_vars_expected'].keys())}\n")
        
        try:
            result = runner.run_conversation(
                persona=persona,
                pathway_id=pathway_id,
                max_turns=50,
                verbose=True,
                debug=False
            )
            results.append(result)
            
            evaluation = PathwayEvaluator.evaluate_result(result, persona)
            evaluations.append(evaluation)
            
            # Quick status
            match_pct = evaluation['match_summary']['match_percentage']
            if match_pct >= 80:
                print(f"\n✅ Success: {match_pct:.1f}% match - {evaluation['end_reason']}")
            elif match_pct >= 50:
                print(f"\n⚠️  Partial: {match_pct:.1f}% match - {evaluation['end_reason']}")
            else:
                print(f"\n❌ Failed: {match_pct:.1f}% match - {evaluation['end_reason']}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    # Save results
    print("\n💾 Saving results...")
    with open("pathway_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    print("   ✅ pathway_results.json")
    
    with open("pathway_evaluations.json", 'w') as f:
        json.dump(evaluations, f, indent=2)
    print("   ✅ pathway_evaluations.json")
    
    # Summary
    print_banner("📊 SUMMARY")
    
    total = len(evaluations)
    completed = sum(1 for e in evaluations if e['pathway_completed'])
    natural = sum(1 for e in evaluations if e['end_reason'] == 'user_ended_call_naturally')
    failed = sum(1 for e in evaluations if e['end_reason'] == 'user_ended_call_unsuccessfully')
    avg_match = sum(e['match_summary']['match_percentage'] for e in evaluations) / total
    avg_turns = sum(e['total_turns'] for e in evaluations) / total
    
    print(f"\n📈 Overall Stats:")
    print(f"   Total Tests: {total}")
    print(f"   Completed: {completed}/{total} ({completed/total*100:.1f}%)")
    print(f"   Natural Endings: {natural}")
    print(f"   Failed Endings: {failed}")
    print(f"   Avg Match Rate: {avg_match:.1f}%")
    print(f"   Avg Turns: {avg_turns:.1f}")
    
    print(f"\n🎯 Individual Results:")
    for i, evaluation in enumerate(evaluations, 1):
        summary = evaluation['match_summary']
        status = "✅" if summary['match_percentage'] >= 80 else "⚠️" if summary['match_percentage'] >= 50 else "❌"
        
        print(f"\n   {status} Persona {i}:")
        print(f"      Match: {summary['match_percentage']:.1f}% ({summary['total_matched']}/{summary['total_expected']})")
        print(f"      End: {evaluation['end_reason']}")
        print(f"      Turns: {evaluation['total_turns']}")
        
        # Show path information
        if evaluation.get('visited_nodes'):
            print(f"      Path: {' → '.join(evaluation['visited_nodes'][:3])}{'...' if len(evaluation['visited_nodes']) > 3 else ''}")
        
        # Show variables not on path (if any)
        not_on_path = summary.get('total_not_on_path', 0)
        if not_on_path > 0:
            print(f"      ℹ️  {not_on_path} variable(s) not required for path taken")
        
        if summary['total_missing'] > 0:
            print(f"      Missing variables (expected for this path):")
            for var_name, match_info in evaluation['variable_matches'].items():
                if match_info.get('matched') is False and match_info.get('match_type') != 'not_on_path':
                    expected = match_info['expected']
                    actual = match_info.get('actual', 'NOT EXTRACTED')
                    print(f"         • {var_name}: expected '{expected}', got '{actual}'")
    
    # Final verdict
    print_banner("🏁 FINAL VERDICT")
    if avg_match >= 80 and completed/total >= 0.8:
        print("✅ PASS - Pathway performing well!")
    elif avg_match >= 50:
        print("⚠️  NEEDS IMPROVEMENT - Some issues detected")
    else:
        print("❌ FAIL - Significant issues found")
    
    print(f"\nOverall Match Rate: {avg_match:.1f}%")
    print(f"Success Rate: {completed/total*100:.1f}%\n")


if __name__ == "__main__":
    main()
