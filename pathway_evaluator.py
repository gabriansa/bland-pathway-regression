from typing import Dict, Any, Tuple, Set, Optional
import os
import requests
from dotenv import load_dotenv

load_dotenv()


class PathwayEvaluator:
    """Evaluates pathway conversation results against expected persona goals."""
    
    # Cache for pathway structures to avoid repeated API calls
    _pathway_cache: Dict[str, Dict[str, Any]] = {}
    
    @staticmethod
    def normalize_value(value: Any) -> Any:
        """Normalize a value for comparison."""
        if isinstance(value, str):
            return value.strip().lower()
        return value
    
    @staticmethod
    def compare_values(expected: Any, actual: Any) -> Tuple[bool, str]:
        """
        Compare expected and actual values with fuzzy matching.
        
        Returns:
            (match: bool, reason: str)
        """
        if expected is None and actual is None:
            return True, "both_none"
        
        if expected is None or actual is None:
            return False, f"one_none: expected={expected}, actual={actual}"
        
        exp_norm = PathwayEvaluator.normalize_value(expected)
        act_norm = PathwayEvaluator.normalize_value(actual)
        
        if exp_norm == act_norm:
            return True, "exact_match"
        
        if isinstance(exp_norm, str) and isinstance(act_norm, str):
            if exp_norm in act_norm or act_norm in exp_norm:
                return True, "partial_match"
        
        try:
            if float(exp_norm) == float(act_norm):
                return True, "numeric_match"
        except (ValueError, TypeError):
            pass
        
        return False, f"mismatch: expected={expected}, actual={actual}"
    
    @staticmethod
    def _fetch_pathway_structure(pathway_id: str) -> Dict[str, Any]:
        """
        Fetch pathway structure from Bland API (with caching).
        
        Args:
            pathway_id: The pathway ID
            
        Returns:
            Pathway structure dictionary
        """
        if pathway_id in PathwayEvaluator._pathway_cache:
            return PathwayEvaluator._pathway_cache[pathway_id]
        
        bland_api_key = os.getenv('BLAND_API_KEY')
        if not bland_api_key:
            return {}
        
        try:
            url = f"https://api.bland.ai/v1/pathway/{pathway_id}"
            headers = {"authorization": bland_api_key}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('errors'):
                PathwayEvaluator._pathway_cache[pathway_id] = data
                return data
        except Exception:
            pass
        
        return {}
    
    @staticmethod
    def _get_variables_for_nodes(pathway_structure: Dict[str, Any], node_names: Set[str]) -> Set[str]:
        """
        Get all variables that should be extracted based on the nodes visited.
        
        Args:
            pathway_structure: The pathway structure from Bland API
            node_names: Set of node names that were visited
            
        Returns:
            Set of variable names that should have been extracted
        """
        expected_vars = set()
        
        for node in pathway_structure.get('nodes', []):
            node_data = node.get('data', {})
            node_name = node_data.get('name', 'Unnamed')
            
            # Check if this node was visited
            if node_name in node_names:
                # Get variables extracted by this node
                extract_vars = node_data.get('extractVars', [])
                for var in extract_vars:
                    if len(var) > 0:
                        var_name = var[0]
                        expected_vars.add(var_name)
        
        return expected_vars
    
    @staticmethod
    def evaluate_result(result: Dict[str, Any], persona: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a conversation result against the persona's expected variables.
        Only checks variables that should have been extracted based on the path taken.
        
        Args:
            result: The conversation result from PathwayRunner
            persona: The persona dictionary with expected goals
        
        Returns:
            Dictionary containing evaluation metrics
        """
        expected_vars = persona.get('goal', {}).get('extracted_vars_expected', {})
        actual_vars = result.get('final_variables', {})
        pathway_id = result.get('pathway_id')
        
        # Get the nodes visited during the conversation
        visited_nodes = set()
        for log_entry in result.get('conversation_log', []):
            node_name = log_entry.get('current_node')
            if node_name:
                visited_nodes.add(node_name)
        
        # Add final node
        if result.get('final_node'):
            visited_nodes.add(result['final_node'])
        
        # Fetch pathway structure and determine which variables should have been extracted
        pathway_structure = PathwayEvaluator._fetch_pathway_structure(pathway_id) if pathway_id else {}
        vars_for_path = PathwayEvaluator._get_variables_for_nodes(pathway_structure, visited_nodes)
        
        # Filter expected variables to only those relevant to the path taken
        # If we couldn't fetch pathway structure, use all expected vars (fallback to old behavior)
        if vars_for_path:
            relevant_expected_vars = {k: v for k, v in expected_vars.items() if k in vars_for_path}
        else:
            relevant_expected_vars = expected_vars
        
        evaluation = {
            'persona_id': result['persona_id'],
            'chat_id': result['chat_id'],
            'pathway_completed': result['completed'],
            'end_reason': result.get('end_reason'),
            'total_turns': result['total_turns'],
            'visited_nodes': list(visited_nodes),
            'expected_variables_for_path': relevant_expected_vars,
            'all_persona_expected_variables': expected_vars,
            'extracted_variables': actual_vars,
            'variable_matches': {},
            'match_summary': {
                'total_expected': len(relevant_expected_vars),
                'total_matched': 0,
                'total_partial': 0,
                'total_missing': 0,
                'total_extra': 0,
                'total_not_on_path': len(expected_vars) - len(relevant_expected_vars)
            }
        }
        
        # Evaluate only the relevant expected variables
        for var_name, expected_value in relevant_expected_vars.items():
            if var_name in actual_vars:
                match, reason = PathwayEvaluator.compare_values(expected_value, actual_vars[var_name])
                evaluation['variable_matches'][var_name] = {
                    'expected': expected_value,
                    'actual': actual_vars[var_name],
                    'matched': match,
                    'match_type': reason
                }
                
                if match:
                    if 'partial' in reason:
                        evaluation['match_summary']['total_partial'] += 1
                    else:
                        evaluation['match_summary']['total_matched'] += 1
                else:
                    evaluation['match_summary']['total_missing'] += 1
            else:
                evaluation['variable_matches'][var_name] = {
                    'expected': expected_value,
                    'actual': None,
                    'matched': False,
                    'match_type': 'not_extracted'
                }
                evaluation['match_summary']['total_missing'] += 1
        
        # Track variables that were not expected on this path
        for var_name, expected_value in expected_vars.items():
            if var_name not in relevant_expected_vars:
                evaluation['variable_matches'][var_name] = {
                    'expected': expected_value,
                    'actual': actual_vars.get(var_name),
                    'matched': None,  # None means "not applicable for this path"
                    'match_type': 'not_on_path'
                }
        
        # Count extra variables extracted
        for var_name in actual_vars:
            # Skip system variables
            if var_name in ['callID', 'channel', 'call_id', 'chat_id', 'BlandStatusCode']:
                continue
            
            if var_name not in relevant_expected_vars:
                evaluation['match_summary']['total_extra'] += 1
        
        # Calculate match percentages based on relevant variables only
        total_expected = evaluation['match_summary']['total_expected']
        if total_expected > 0:
            matched = evaluation['match_summary']['total_matched']
            partial = evaluation['match_summary']['total_partial']
            evaluation['match_summary']['match_percentage'] = (matched / total_expected) * 100
            evaluation['match_summary']['partial_match_percentage'] = ((matched + partial) / total_expected) * 100
        else:
            evaluation['match_summary']['match_percentage'] = 100.0
            evaluation['match_summary']['partial_match_percentage'] = 100.0
        
        return evaluation
