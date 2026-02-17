import json
import random
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()


class PersonaFactory:
    """
    Factory class for generating diverse personas based on pathway JSON files.
    Each persona has a unique personality and pathway-specific goals with expected variable values.
    """
    
    # Personality dimension options
    COMMUNICATION_STYLES = ["Direct", "Verbose", "Hesitant", "Friendly", "Formal"]
    PATIENCE_LEVELS = ["Very Patient", "Patient", "Neutral", "Impatient", "Very Impatient"]
    TECH_SAVVINESS = ["Low", "Medium", "High"]
    ATTITUDES = ["Cooperative", "Skeptical", "Enthusiastic", "Indifferent", "Difficult"]
    
    # Behavioral dimensions
    PRECISION_LEVELS = ["Very Precise", "Precise", "Average", "Imprecise", "Careless"]
    ERROR_PRONE = ["Rarely Makes Mistakes", "Occasionally Makes Mistakes", "Often Makes Mistakes", "Frequently Needs Corrections"]
    DECISIVENESS = ["Very Decisive", "Decisive", "Neutral", "Indecisive", "Frequently Changes Mind"]
    DETAIL_ORIENTATION = ["Highly Detail-Oriented", "Detail-Oriented", "Moderate", "Big Picture Only", "Overlooks Details"]
    CONSISTENCY = ["Very Consistent", "Consistent", "Somewhat Consistent", "Inconsistent", "Contradicts Themselves"]
    
    def __init__(self, pathway_id: str, bland_api_key: Optional[str] = None, options_per_variable: int = 10):
        """
        Initialize the PersonaFactory with a pathway ID.
        
        Args:
            pathway_id: The Bland AI pathway ID
            bland_api_key: Bland AI API key (defaults to BLAND_API_KEY env var)
            options_per_variable: Number of options to generate per variable (default: 10)
        """
        self.pathway_id = pathway_id
        self.options_per_variable = options_per_variable
        self.bland_api_key = bland_api_key or os.getenv('BLAND_API_KEY')
        
        if not self.bland_api_key:
            raise ValueError("BLAND_API_KEY must be provided or set in environment")
        
        # Initialize OpenAI client with OpenRouter
        self.client = OpenAI(
            base_url=os.getenv('OPENROUTER_BASE_URL'),
            api_key=os.getenv('OPENROUTER_API_KEY')
        )
        
        # Fetch pathway data from Bland AI API
        self.pathway_data = self._fetch_pathway_data()
        
        # Parse pathway to extract key information
        self.pathway_info = self._parse_pathway()
        
        # Warn about potential semantic duplicates
        self._check_for_semantic_duplicates()
    
    def _fetch_pathway_data(self) -> Dict[str, Any]:
        """
        Fetch pathway data from Bland AI API.
        
        Returns:
            Dictionary containing pathway structure
        """
        import requests
        
        url = f"https://api.bland.ai/v1/pathway/{self.pathway_id}"
        
        headers = {
            "authorization": self.bland_api_key
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if data.get('errors'):
            raise Exception(f"Error fetching pathway: {data['errors']}")
        
        # The API returns the pathway data directly at the top level
        return data
    
    def _parse_pathway(self) -> Dict[str, Any]:
        """
        Parse the pathway JSON to extract key information.
        
        Returns:
            Dictionary containing extracted variables, end nodes, and call context
        """
        extract_vars = []
        end_nodes = []
        seen_vars = {}  # Track variables we've already seen (case-insensitive)
        
        nodes = self.pathway_data.get('nodes', [])
        
        # Iterate through all nodes
        for node in nodes:
            node_data = node.get('data', {})
            node_type = node.get('type', 'Default')
            node_id = node.get('id', '')
            node_name = node_data.get('name', '')
            
            # Collect extractVars (deduplicate by name, case-insensitive)
            if 'extractVars' in node_data:
                for var in node_data['extractVars']:
                    # extractVars format: [name, type, description, optional?]
                    var_name = var[0]
                    var_name_lower = var_name.lower()
                    
                    # Only add if we haven't seen this variable name before (case-insensitive)
                    if var_name_lower not in seen_vars:
                        var_info = {
                            'name': var_name,
                            'type': var[1],
                            'description': var[2],
                            'optional': var[3] if len(var) > 3 else False,
                            'node_id': node_id,
                            'node_name': node_name
                        }
                        extract_vars.append(var_info)
                        seen_vars[var_name_lower] = var_name  # Store canonical name
            
            # Collect end nodes
            if node_type == 'End Call':
                end_nodes.append({
                    'id': node_id,
                    'name': node_name,
                    'prompt': node_data.get('prompt', '')
                })
        
        # Determine call context (who is calling whom)
        call_context = self._determine_call_context()
        
        return {
            'extract_vars': extract_vars,
            'end_nodes': end_nodes,
            'call_context': call_context
        }
    
    def _check_for_semantic_duplicates(self) -> None:
        """
        Check for semantically similar variable names and warn the user.
        """
        var_names = [v['name'].lower() for v in self.pathway_info['extract_vars']]
        
        # Check for common semantic duplicates
        conflicts = []
        if 'fullname' in var_names and 'name' in var_names:
            conflicts.append(('FullName', 'name'))
        if 'firstname' in var_names and 'name' in var_names:
            conflicts.append(('FirstName', 'name'))
        if 'phonenumber' in var_names and 'phone' in var_names:
            conflicts.append(('PhoneNumber', 'phone'))
        if 'emailaddress' in var_names and 'email' in var_names:
            conflicts.append(('EmailAddress', 'email'))
        
        if conflicts:
            print(f"\n⚠️  WARNING: Potential semantic duplicate variables detected:")
            for var1, var2 in conflicts:
                print(f"   - '{var1}' and '{var2}' may represent the same information")
            print(f"   This may cause personas to have conflicting values.")
            print(f"   Consider consolidating these variables in your pathway.\n")
    
    def _determine_call_context(self) -> Dict[str, Any]:
        """
        Use LLM to determine the call context from the pathway structure.
        
        Returns:
            Dictionary with 'direction' (inbound/outbound), 'entity_type', and 'entity_context'
        """
        # Extract relevant information from pathway
        pathway_name = self.pathway_data.get('name', '')
        pathway_description = self.pathway_data.get('description', '')
        
        # Get first few nodes' prompts for context
        nodes = self.pathway_data.get('nodes', [])
        node_prompts = []
        for node in nodes[:5]:  # Look at first 5 nodes
            node_data = node.get('data', {})
            if 'prompt' in node_data and node_data['prompt']:
                node_prompts.append(node_data['prompt'])
        
        # Build prompt for LLM
        prompt = f"""Analyze who INITIATED this phone call.

Pathway Name: {pathway_name}
AI Assistant Prompts:
{json.dumps(node_prompts[:3], indent=2)}

WHO STARTED THE CALL?

If you see these phrases, the PERSONA called the business:
✓ "thank you for calling"
✓ "thanks for calling"  
✓ "they have called"
✓ "how can I help you today"
→ Answer: "outbound" (persona called them)

If you see these phrases, the BUSINESS called the persona:
✓ "I'm calling about"
✓ "is this [name]?"
✓ "calling to inform"
→ Answer: "inbound" (they called persona)

Return JSON:
{{
  "direction": "outbound" or "inbound",
  "entity_type": "business type (e.g., reception, restaurant, bank)",
  "entity_context": "what this call is about (1 sentence)"
}}"""

        try:
            completion = self.client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            response_text = completion.choices[0].message.content
            call_context = json.loads(response_text)
            
            return call_context
        
        except Exception as e:
            print(f"Warning: Could not determine call context: {e}")
            # Return a safe default
            return {
                "direction": "outbound",
                "entity_type": "business",
                "entity_context": "You are contacting a business or service."
            }
    
    def _generate_personality(self) -> Dict[str, Any]:
        """
        Generate a random personality based on defined dimensions.
        
        Returns:
            Dictionary containing personality attributes
        """
        return {
            'communication_style': random.choice(self.COMMUNICATION_STYLES),
            'patience_level': random.choice(self.PATIENCE_LEVELS),
            'tech_savviness': random.choice(self.TECH_SAVVINESS),
            'attitude': random.choice(self.ATTITUDES),
            # Behavioral traits
            'precision_level': random.choice(self.PRECISION_LEVELS),
            'error_prone': random.choice(self.ERROR_PRONE),
            'decisiveness': random.choice(self.DECISIVENESS),
            'detail_orientation': random.choice(self.DETAIL_ORIENTATION),
            'consistency': random.choice(self.CONSISTENCY)
        }
    
    def _generate_variable_options(self) -> Dict[str, List[Any]]:
        """
        Use LLM to generate realistic options for all variables in the pathway.
        
        Returns:
            Dictionary mapping variable names to lists of possible values
        """
        if not self.pathway_info['extract_vars']:
            return {}
        
        # Build the prompt with all variables
        variables_info = []
        for var_info in self.pathway_info['extract_vars']:
            variables_info.append({
                'name': var_info['name'],
                'type': var_info['type'],
                'description': var_info['description']
            })
        
        # Create prompt for the LLM
        prompt = f"""You are generating realistic test data for variables in a conversation pathway.

For each variable below, generate {self.options_per_variable} diverse, realistic options that someone might use in a real conversation.

Variables:
{json.dumps(variables_info, indent=2)}

Return a JSON object where each key is the variable name and each value is an array of {self.options_per_variable} realistic options.

IMPORTANT:
- Use reasonable values based on context
- Be creative and diverse with the options

Return ONLY valid JSON, no additional text."""

        try:
            completion = self.client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            response_text = completion.choices[0].message.content
            options_dict = json.loads(response_text)
            
            return options_dict
        
        except Exception as e:
            print(f"Error generating variable options with LLM: {e}")
            raise Exception("Failed to generate variable options. Please check your OpenRouter API configuration.")
    
    def _generate_goal(self, variable_options: Dict[str, List[Any]]) -> Dict[str, Any]:
        """
        Generate a pathway-specific goal with expected variable values.
        
        Args:
            variable_options: LLM-generated options for variables
        
        Returns:
            Dictionary containing goal information
        """
        # Pick a random end node (keep it simple - don't try to categorize)
        target_end_node = random.choice(self.pathway_info['end_nodes']) if self.pathway_info['end_nodes'] else None
        
        # Generate values for all extract variables
        extracted_vars = {}
        for var_info in self.pathway_info['extract_vars']:
            # Use LLM-generated options
            if var_info['name'] in variable_options and variable_options[var_info['name']]:
                value = random.choice(variable_options[var_info['name']])
                extracted_vars[var_info['name']] = value
        
        goal = {
            'extracted_vars_expected': extracted_vars,
            'call_context': self.pathway_info['call_context']
        }
        
        # Only add target end node if pathway has end nodes
        if target_end_node:
            goal['target_end_node'] = target_end_node['name']
            goal['target_end_node_id'] = target_end_node['id']
        
        return goal
    
    def generate_personas(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Generate N personas with diverse personalities and pathway-specific goals.
        
        Args:
            n: Number of personas to generate (default: 10)
        
        Returns:
            List of persona dictionaries
        """
        # Generate variable options once using LLM
        print(f"Generating variable options using LLM...")
        variable_options = self._generate_variable_options()
        print(f"Successfully generated options for {len(variable_options)} variables")
        
        personas = []
        
        for i in range(n):
            persona = {
                'persona_id': str(uuid.uuid4()),
                'personality': self._generate_personality(),
                'goal': self._generate_goal(variable_options)
            }
            personas.append(persona)
        
        return personas
    
    def save_personas(self, personas: List[Dict[str, Any]], output_path: str) -> None:
        """
        Save personas to a JSON file.
        
        Args:
            personas: List of persona dictionaries
            output_path: Path where the JSON file should be saved
        """
        output_data = {
            'pathway_id': self.pathway_id,
            'pathway_name': self.pathway_data.get('name', 'Unknown'),
            'generated_at': datetime.now().isoformat(),
            'total_personas': len(personas),
            'personas': personas
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
    
    def generate_and_save(self, n: int = 10, output_path: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
        """
        Convenience method to generate personas and save them to a file.
        
        Args:
            n: Number of personas to generate
            output_path: Path for output file (auto-generated if None)
        
        Returns:
            Tuple of (personas list, output file path)
        """
        personas = self.generate_personas(n=n)
        
        if output_path is None:
            # Auto-generate output filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"personas_{timestamp}.json"
        
        self.save_personas(personas, output_path)
        
        return personas, output_path
