import os
import json
import re
import requests
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class PathwayRunner:
    """Runs persona interactions with Bland AI pathways."""
    
    def __init__(self, bland_api_key: Optional[str] = None):
        """
        Initialize the PathwayRunner.
        
        Args:
            bland_api_key: Bland AI API key (defaults to BLAND_API_KEY env var)
        """
        self.bland_api_key = bland_api_key or os.getenv('BLAND_API_KEY')
        if not self.bland_api_key:
            raise ValueError("BLAND_API_KEY must be provided or set in environment")
        
        self.base_url = "https://api.bland.ai/v1"
        
        self.client = OpenAI(
            base_url=os.getenv('OPENROUTER_BASE_URL'),
            api_key=os.getenv('OPENROUTER_API_KEY')
        )
    
    def get_pathway_info(self, pathway_id: str) -> Dict[str, Any]:
        """
        Get complete pathway information from Bland AI API.
        
        Args:
            pathway_id: The pathway ID to fetch
        
        Returns:
            Dictionary containing pathway name, description, nodes, and edges
        """
        url = f"{self.base_url}/pathway/{pathway_id}"
        
        headers = {"authorization": self.bland_api_key}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if data.get('errors'):
            raise Exception(f"Error fetching pathway: {data['errors']}")
        
        return data
    
    def _create_chat(self, pathway_id: str, request_data: Optional[Dict] = None) -> str:
        """
        Create a pathway chat instance.
        
        Args:
            pathway_id: The pathway ID to interact with
            request_data: Optional initial variables for the pathway
        
        Returns:
            chat_id: The created chat instance ID
        """
        url = "https://us.api.bland.ai/v1/pathway/chat/create"
        
        payload = {"pathway_id": pathway_id}
        if request_data:
            payload["request_data"] = request_data
        
        headers = {
            "authorization": self.bland_api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if data.get('errors'):
            raise Exception(f"Error creating chat: {data['errors']}")
        
        return data['data']['chat_id']
    
    def _send_message(self, chat_id: str, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a message to the pathway chat.
        
        Args:
            chat_id: The chat instance ID
            message: The message to send (optional for first message)
        
        Returns:
            Response data from the pathway
        """
        url = f"https://us.api.bland.ai/v1/pathway/chat/{chat_id}"
        
        payload = {}
        if message:
            payload["message"] = message
        
        headers = {
            "authorization": self.bland_api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if data.get('errors'):
            raise Exception(f"Error sending message: {data['errors']}")
        
        return data['data']
    
    def get_chat_history(self, chat_id: str) -> List[Dict[str, str]]:
        """
        Get the full conversation history for a pathway chat.
        
        Args:
            chat_id: The chat instance ID
        
        Returns:
            List of message objects with role and content
        """
        url = f"https://us.api.bland.ai/v1/pathway/chat/{chat_id}"
        
        headers = {"authorization": self.bland_api_key}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if data.get('errors'):
            raise Exception(f"Error getting chat history: {data['errors']}")
        
        return data.get('data', [])
    
    def _generate_persona_response(self, persona: Dict[str, Any], chat_history: List[Dict]) -> str:
        """
        Generate a response as the persona using AI.
        
        Args:
            persona: The persona dictionary with personality and goals
            chat_history: The conversation history
        
        Returns:
            The generated response message
        """
        personality = persona['personality']
        goal = persona['goal']
        call_context = goal.get('call_context', {})
        
        # Build context-aware introduction
        direction = call_context.get('direction', 'outbound')
        entity_context = call_context.get('entity_context', '')
        
        if direction == 'outbound':
            context_intro = f"""Call Context:
- You are calling/contacting them (you initiated this interaction)
- {entity_context}"""
        else:  # inbound
            context_intro = f"""Call Context:
- You are receiving this call (they contacted you)
- {entity_context}"""
        
        system_prompt = f"""You are roleplaying as a CUSTOMER in a conversation. You are calling or interacting with a business/service.

IMPORTANT: You are the CUSTOMER, not the business representative. Respond as someone who needs service.

{context_intro}

Personality:
- Communication Style: {personality['communication_style']}
- Patience Level: {personality['patience_level']}
- Tech Savviness: {personality['tech_savviness']}
- Attitude: {personality['attitude']}
- Precision Level: {personality['precision_level']}
- Error Prone: {personality['error_prone']}
- Decisiveness: {personality['decisiveness']}
- Detail Orientation: {personality['detail_orientation']}
- Consistency: {personality['consistency']}

Your Goal:
You need to provide the following information during this conversation:
{json.dumps(goal.get('extracted_vars_expected', {}), indent=2)}

Instructions:
- You are the CUSTOMER calling/chatting with a business
- Stay in character based on your personality traits
- Provide the information naturally when asked
- Respond naturally to questions - don't dump all information at once
- Keep responses conversational and realistic (1-2 sentences typically)
- Embody your personality traits in how you communicate
- DO NOT act as if you work for the business - you are seeking their service

Ending the conversation:
- When you successfully complete your goal and are satisfied, say "GOODBYE" to end naturally
- If you get frustrated, confused, or feel the conversation isn't going anywhere, say "END_CALL" to end unsuccessfully
- Use your personality traits to decide when to give up (impatient personas give up faster, patient ones persist longer)"""

        messages = [{"role": "system", "content": system_prompt}]
        
        for msg in chat_history:
            messages.append({
                "role": msg['role'],
                "content": msg['content']
            })
        
        completion = self.client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=messages,
            max_tokens=150,
            temperature=0.8
        )
        
        raw_response = completion.choices[0].message.content or ""
        return self._sanitize_persona_message(raw_response)
    
    def _sanitize_persona_message(self, message: str) -> str:
        """
        Keep only a single customer utterance and strip speaker labels.
        
        This avoids cases where the persona model emits transcript-style lines
        like "User: ..." / "Assistant: ...", which makes logs look like the
        user is talking to themselves.
        """
        cleaned = (message or "").strip()
        if not cleaned:
            return "Sorry, could you repeat that?"
        
        # Keep only the first non-empty line to enforce one-turn response.
        first_line = next((line.strip() for line in cleaned.splitlines() if line.strip()), cleaned)
        
        # Remove common speaker prefixes that the model may hallucinate.
        first_line = re.sub(r"^\s*(user|assistant|\(bland\)\s*assistant)\s*:\s*", "", first_line, flags=re.IGNORECASE)
        
        return first_line.strip() or "Sorry, could you repeat that?"
    
    def _detect_conversation_end(self, last_user_message: str) -> tuple[bool, str | None]:
        """
        Detect if the conversation should end based on special keywords.
        
        Args:
            last_user_message: The most recent user message
        
        Returns:
            (should_end: bool, end_reason: str | None)
        """
        message_upper = last_user_message.upper()
        
        if "END_CALL" in message_upper:
            return True, "user_ended_call_unsuccessfully"
        
        if "GOODBYE" in message_upper:
            return True, "user_ended_call_naturally"
        
        return False, None
    
    def run_conversation(
        self,
        persona: Dict[str, Any],
        pathway_id: str,
        max_turns: int = 50,
        verbose: bool = True,
        auto_detect_end: bool = True,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Run a complete conversation between a persona and a pathway.
        
        Args:
            persona: The persona dictionary from PersonaFactory
            pathway_id: The Bland AI pathway ID
            max_turns: Maximum number of conversation turns
            verbose: Whether to print conversation progress
            auto_detect_end: Whether to auto-detect conversation endings
            debug: Whether to print debug information about response data
        
        Returns:
            Dictionary containing conversation results
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"Starting conversation for persona: {persona['persona_id']}")
            print(f"{'='*60}\n")
        
        chat_id = self._create_chat(pathway_id)
        response_data = self._send_message(chat_id)
        
        if debug:
            print(f"\n[DEBUG] Initial response data keys: {response_data.keys()}")
            print(f"[DEBUG] Variables: {response_data.get('variables', {})}")
            print(f"[DEBUG] Current node: {response_data.get('current_node_name', 'Unknown')}\n")
        
        conversation_log = []
        persona_chat_history: List[Dict[str, str]] = []
        turn_count = 0
        end_reason = None
        printed_final_assistant = False
        consecutive_silent_turns = 0
        
        while not response_data.get('completed', False) and turn_count < max_turns:
            turn_count += 1
            
            assistant_responses = response_data.get('assistant_responses', [])
            chat_history = response_data.get('chat_history', [])
            
            # Print assistant responses
            if verbose:
                for resp in assistant_responses:
                    print(f"(Bland) Assistant: {resp}")
                if not assistant_responses:
                    print("[No assistant response received]\n")
            
            if assistant_responses:
                consecutive_silent_turns = 0
            else:
                consecutive_silent_turns += 1
            
            # Maintain a local, role-safe history for persona generation.
            for resp in assistant_responses:
                persona_chat_history.append({
                    "role": "assistant",
                    "content": resp
                })
            
            # Check if pathway completed
            if response_data.get('completed', False):
                end_reason = "pathway_completed"
                if verbose:
                    print(f"\n[Pathway marked as completed]")
                break
            
            # If the pathway returns no assistant response repeatedly, avoid
            # hallucinating a full two-sided conversation from the persona.
            if consecutive_silent_turns >= 2:
                user_message = "END_CALL"
            elif consecutive_silent_turns == 1 and turn_count > 1:
                user_message = "Hello? Are you still there?"
            else:
                # Generate user response (persona)
                user_message = self._generate_persona_response(persona, persona_chat_history)
            
            # Print user message
            if verbose:
                print(f"User: {user_message}\n")
            
            persona_chat_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Check for conversation end
            if auto_detect_end:
                should_end, detected_reason = self._detect_conversation_end(user_message)
                if should_end:
                    end_reason = detected_reason
                    if verbose:
                        reason_text = "naturally" if "naturally" in detected_reason else "unsuccessfully"
                        print(f"\n[User ended conversation {reason_text}]")
                    
                    # Send the final user message and get the assistant's final response
                    response_data = self._send_message(chat_id, user_message)
                    
                    # Print final assistant responses if any
                    if response_data.get('assistant_responses'):
                        for resp in response_data.get('assistant_responses', []):
                            print(f"(Bland) Assistant: {resp}")
                        printed_final_assistant = True
                    
                    break
            
            # Send user message and get next response
            response_data = self._send_message(chat_id, user_message)
            
            if debug:
                print(f"[DEBUG] Turn {turn_count} response variables: {response_data.get('variables', {})}")
                print(f"[DEBUG] Current node: {response_data.get('current_node_name', 'Unknown')}\n")
            
            conversation_log.append({
                'turn': turn_count,
                'user_message': user_message,
                'assistant_responses': assistant_responses,
                'current_node': response_data.get('current_node_name', 'Unknown')
            })
        
        if response_data.get('assistant_responses') and not printed_final_assistant:
            if verbose:
                for resp in response_data.get('assistant_responses', []):
                    print(f"(Bland) Assistant: {resp}")
        
        if turn_count >= max_turns and not end_reason:
            end_reason = "max_turns_reached"
        
        if debug:
            print(f"\n[DEBUG] Final response data:")
            print(f"[DEBUG] All keys: {response_data.keys()}")
            print(f"[DEBUG] Variables: {response_data.get('variables', {})}")
            print(f"[DEBUG] Completed: {response_data.get('completed', False)}")
            print(f"[DEBUG] Current node: {response_data.get('current_node_name', 'Unknown')}\n")
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"Conversation ended: {end_reason or 'unknown'}")
            print(f"Pathway completed status: {response_data.get('completed', False)}")
            print(f"Total turns: {turn_count}")
            print(f"Final node: {response_data.get('current_node_name', 'Unknown')}")
            if debug:
                print(f"Final variables: {response_data.get('variables', {})}")
            print(f"{'='*60}\n")
        
        return {
            'persona_id': persona['persona_id'],
            'chat_id': chat_id,
            'pathway_id': pathway_id,
            'completed': response_data.get('completed', False),
            'end_reason': end_reason,
            'total_turns': turn_count,
            'final_node': response_data.get('current_node_name'),
            'final_variables': response_data.get('variables', {}),
            'conversation_log': conversation_log,
            'full_chat_history': response_data.get('chat_history', [])
        }
