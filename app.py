import streamlit as st
import json
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from persona_factory import PersonaFactory
from pathway_runner import PathwayRunner
from pathway_evaluator import PathwayEvaluator


st.set_page_config(
    page_title="Pathway Regression Testing",
    page_icon="🤖",
    layout="wide"
)

def init_session_state():
    if 'test_results' not in st.session_state:
        st.session_state.test_results = None
    if 'personas' not in st.session_state:
        st.session_state.personas = None
    if 'running' not in st.session_state:
        st.session_state.running = False


def create_metrics_dashboard(evaluations):
    st.subheader("📊 Overall Metrics")
    
    total = len(evaluations)
    completed = sum(1 for e in evaluations if e['pathway_completed'])
    natural_endings = sum(1 for e in evaluations if e['end_reason'] == 'user_ended_call_naturally')
    unsuccessful_endings = sum(1 for e in evaluations if e['end_reason'] == 'user_ended_call_unsuccessfully')
    
    avg_match = sum(e['match_summary']['match_percentage'] for e in evaluations) / total if total > 0 else 0
    avg_turns = sum(e['total_turns'] for e in evaluations) / total if total > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Tests", total)
        st.metric("Completed", f"{completed}/{total}")
    
    with col2:
        st.metric("Avg Match Rate", f"{avg_match:.1f}%")
        st.metric("Natural Endings", natural_endings)
    
    with col3:
        st.metric("Avg Turns", f"{avg_turns:.1f}")
        st.metric("Failed Endings", unsuccessful_endings)
    
    with col4:
        success_rate = (completed / total * 100) if total > 0 else 0
        st.metric("Success Rate", f"{success_rate:.1f}%")
        st.metric("Total Variables", evaluations[0]['match_summary']['total_expected'] if evaluations else 0)


def create_visualizations(evaluations):
    st.subheader("📈 Visualizations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Match percentage distribution
        match_percentages = [e['match_summary']['match_percentage'] for e in evaluations]
        fig = go.Figure(data=[go.Histogram(x=match_percentages, nbinsx=10)])
        fig.update_layout(
            title="Variable Match Rate Distribution",
            xaxis_title="Match Percentage",
            yaxis_title="Count",
            height=300
        )
        st.plotly_chart(fig, width='stretch')
    
    with col2:
        # End reasons pie chart
        end_reasons = [e['end_reason'] for e in evaluations]
        reason_counts = {}
        for reason in end_reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        fig = go.Figure(data=[go.Pie(
            labels=list(reason_counts.keys()),
            values=list(reason_counts.values())
        )])
        fig.update_layout(
            title="Conversation End Reasons",
            height=300
        )
        st.plotly_chart(fig, width='stretch')
    
    # Variable extraction success
    st.subheader("🎯 Variable Extraction Success")
    
    if evaluations:
        var_names = list(evaluations[0]['variable_matches'].keys())
        var_success = {var: 0 for var in var_names}
        
        for eval in evaluations:
            for var_name, match_info in eval['variable_matches'].items():
                if match_info['matched']:
                    var_success[var_name] += 1
        
        var_success_pct = {var: (count / len(evaluations) * 100) for var, count in var_success.items()}
        
        fig = go.Figure(data=[go.Bar(
            x=list(var_success_pct.keys()),
            y=list(var_success_pct.values()),
            text=[f"{v:.1f}%" for v in var_success_pct.values()],
            textposition='auto'
        )])
        fig.update_layout(
            title="Variable Extraction Success Rate by Variable",
            xaxis_title="Variable",
            yaxis_title="Success Rate (%)",
            height=300
        )
        st.plotly_chart(fig, width='stretch')


def run_conversation_with_live_updates(runner, persona, pathway_id, max_turns, chat_area, status_area):
    """Run conversation and update UI in real-time"""
    import time
    
    # Start conversation
    chat_id = runner._create_chat(pathway_id)
    response_data = runner._send_message(chat_id)
    
    conversation_log = []
    chat_messages = []
    turn_count = 0
    end_reason = None
    
    while not response_data.get('completed', False) and turn_count < max_turns:
        turn_count += 1
        
        # Display assistant responses
        assistant_responses = response_data.get('assistant_responses', [])
        chat_history = response_data.get('chat_history', [])
        
        for resp in assistant_responses:
            chat_messages.append(("assistant", resp))
            # Update chat display
            chat_html = "<div style='max-height: 400px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: white;'>"
            for role, msg in chat_messages[-10:]:  # Show last 10 messages
                if role == "assistant":
                    chat_html += f"<div style='background: #1976d2; color: white; padding: 10px; margin: 5px 0; border-radius: 5px;'>🤖 <strong>Assistant:</strong> {msg}</div>"
                else:
                    chat_html += f"<div style='background: #424242; color: white; padding: 10px; margin: 5px 0; border-radius: 5px;'>👤 <strong>User:</strong> {msg}</div>"
            chat_html += "</div>"
            chat_area.markdown(chat_html, unsafe_allow_html=True)
            time.sleep(0.3)  # Small delay for readability
        
        status_area.info(f"💬 Turn {turn_count} - Thinking...")
        
        if response_data.get('completed', False):
            end_reason = "pathway_completed"
            break
        
        # Generate persona response
        user_message = runner._generate_persona_response(persona, chat_history)
        chat_messages.append(("user", user_message))
        
        # Update chat display with user message
        chat_html = "<div style='max-height: 400px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: white;'>"
        for role, msg in chat_messages[-10:]:
            if role == "assistant":
                chat_html += f"<div style='background: #1976d2; color: white; padding: 10px; margin: 5px 0; border-radius: 5px;'>🤖 <strong>Assistant:</strong> {msg}</div>"
            else:
                chat_html += f"<div style='background: #424242; color: white; padding: 10px; margin: 5px 0; border-radius: 5px;'>👤 <strong>User:</strong> {msg}</div>"
        chat_html += "</div>"
        chat_area.markdown(chat_html, unsafe_allow_html=True)
        
        # Check for ending keywords
        should_end, detected_reason = runner._detect_conversation_end(user_message)
        if should_end:
            end_reason = detected_reason
            status_area.warning(f"🛑 Conversation ended: {end_reason}")
            break
        
        status_area.info(f"💬 Turn {turn_count} - Waiting for response...")
        
        # Send message
        response_data = runner._send_message(chat_id, user_message)
        
        conversation_log.append({
            'turn': turn_count,
            'user_message': user_message,
            'assistant_responses': assistant_responses,
            'current_node': response_data.get('current_node_name', 'Unknown')
        })
    
    # Final assistant response
    if response_data.get('assistant_responses'):
        for resp in response_data.get('assistant_responses', []):
            chat_messages.append(("assistant", resp))
            chat_html = "<div style='max-height: 400px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: white;'>"
            for role, msg in chat_messages[-10:]:
                if role == "assistant":
                    chat_html += f"<div style='background: #1976d2; color: white; padding: 10px; margin: 5px 0; border-radius: 5px;'>🤖 <strong>Assistant:</strong> {msg}</div>"
                else:
                    chat_html += f"<div style='background: #424242; color: white; padding: 10px; margin: 5px 0; border-radius: 5px;'>👤 <strong>User:</strong> {msg}</div>"
            chat_html += "</div>"
            chat_area.markdown(chat_html, unsafe_allow_html=True)
    
    if turn_count >= max_turns and not end_reason:
        end_reason = "max_turns_reached"
    
    status_area.success(f"✅ Conversation complete - {turn_count} turns")
    
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


def show_detailed_results(evaluations, results):
    st.subheader("🔍 Detailed Results")
    
    for i, (evaluation, result) in enumerate(zip(evaluations, results), 1):
        with st.expander(f"Persona {i} - {evaluation['persona_id'][:8]}... ({evaluation['end_reason']})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Conversation Info**")
                st.write(f"- Completed: {'✅' if evaluation['pathway_completed'] else '❌'}")
                st.write(f"- End Reason: {evaluation['end_reason']}")
                st.write(f"- Total Turns: {evaluation['total_turns']}")
                st.write(f"- Final Node: {result.get('final_node', 'Unknown')}")
                
                st.write("**Match Summary**")
                summary = evaluation['match_summary']
                st.write(f"- Match Rate: {summary['match_percentage']:.1f}%")
                st.write(f"- Matched: {summary['total_matched']}/{summary['total_expected']}")
                st.write(f"- Partial: {summary['total_partial']}")
                st.write(f"- Missing: {summary['total_missing']}")
            
            with col2:
                st.write("**Variable Extraction**")
                for var_name, match_info in evaluation['variable_matches'].items():
                    status = "✅" if match_info['matched'] else "❌"
                    st.write(f"{status} **{var_name}**")
                    st.write(f"  Expected: `{match_info['expected']}`")
                    st.write(f"  Actual: `{match_info.get('actual', 'NOT EXTRACTED')}`")
            
            # Show conversation
            if st.checkbox(f"Show Conversation", key=f"conv_{i}"):
                st.write("**Conversation Log**")
                for turn in result['conversation_log']:
                    st.write(f"**Turn {turn['turn']}:**")
                    for resp in turn['assistant_responses']:
                        st.write(f"🤖 Assistant: {resp}")
                    st.write(f"👤 User: {turn['user_message']}")
                    st.write("---")


def main():
    init_session_state()
    
    st.title("🤖 Pathway Regression Testing Dashboard")
    st.markdown("Test your Bland AI pathways with AI-generated personas")
    
    # Sidebar - Configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        pathway_id = st.text_input(
            "Pathway ID",
            value="",
            help="Enter your Bland AI pathway ID"
        )
        
        num_personas = st.slider(
            "Number of Personas",
            min_value=1,
            max_value=20,
            value=3,
            help="How many test personas to generate"
        )
        
        options_per_var = st.slider(
            "Options per Variable",
            min_value=5,
            max_value=20,
            value=10,
            help="Number of diverse options to generate for each variable"
        )
        
        max_turns = st.slider(
            "Max Conversation Turns",
            min_value=10,
            max_value=100,
            value=50,
            help="Maximum number of turns per conversation"
        )
        
        show_live_chat = st.checkbox(
            "Show Live Conversations",
            value=True,
            help="Display conversations in real-time (slower but more engaging)"
        )
        
        st.markdown("---")
        
        run_button = st.button("🚀 Run Tests", type="primary", disabled=st.session_state.running)
        
        if run_button:
            st.session_state.running = True
            st.rerun()
    
    # Main content
    if st.session_state.running:
        st.info("🔄 Running tests... This may take a few minutes.")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Generate personas
            status_text.text("Generating personas...")
            progress_bar.progress(10)
            
            factory = PersonaFactory(pathway_id, options_per_variable=options_per_var)
            personas = factory.generate_personas(n=num_personas)
            st.session_state.personas = personas
            
            status_text.text(f"Generated {len(personas)} personas. Running conversations...")
            progress_bar.progress(30)
            
            # Run tests
            runner = PathwayRunner()
            results = []
            evaluations = []
            
            # Create live conversation container if enabled
            if show_live_chat:
                live_chat_container = st.container()
            
            for i, persona in enumerate(personas):
                if show_live_chat:
                    with live_chat_container:
                        st.markdown(f"### 💬 Persona {i+1}/{len(personas)} - Live Conversation")
                        
                        # Show personality traits
                        with st.expander("👤 Persona Details", expanded=False):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Communication:** {persona['personality']['communication_style']}")
                                st.write(f"**Patience:** {persona['personality']['patience_level']}")
                                st.write(f"**Attitude:** {persona['personality']['attitude']}")
                            with col2:
                                st.write(f"**Tech Savvy:** {persona['personality']['tech_savviness']}")
                                st.write(f"**Decisiveness:** {persona['personality']['decisiveness']}")
                        
                        # Live chat area
                        chat_area = st.empty()
                        status_area = st.empty()
                
                status_text.text(f"Running persona {i+1}/{len(personas)}...")
                progress = 30 + (50 * (i / len(personas)))
                progress_bar.progress(int(progress))
                
                # Run conversation with or without live updates
                if show_live_chat:
                    result = run_conversation_with_live_updates(
                        runner,
                        persona,
                        pathway_id,
                        max_turns,
                        chat_area,
                        status_area
                    )
                else:
                    result = runner.run_conversation(
                        persona=persona,
                        pathway_id=pathway_id,
                        max_turns=max_turns,
                        verbose=False,
                        debug=False
                    )
                
                results.append(result)
                
                evaluation = PathwayEvaluator.evaluate_result(result, persona)
                evaluations.append(evaluation)
                
                # Show final status
                if show_live_chat:
                    with live_chat_container:
                        if evaluation['pathway_completed']:
                            st.success(f"✅ Completed - {evaluation['end_reason']} - {evaluation['match_summary']['match_percentage']:.1f}% match")
                        else:
                            st.warning(f"⚠️ Not completed - {evaluation['end_reason']} - {evaluation['match_summary']['match_percentage']:.1f}% match")
                        st.markdown("---")
            
            status_text.text("Processing results...")
            progress_bar.progress(90)
            
            st.session_state.test_results = {
                'results': results,
                'evaluations': evaluations,
                'timestamp': datetime.now().isoformat(),
                'pathway_id': pathway_id,
                'num_personas': num_personas
            }
            
            progress_bar.progress(100)
            status_text.text("✅ Tests completed!")
            
            st.session_state.running = False
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error running tests: {str(e)}")
            st.session_state.running = False
    
    # Display results
    if st.session_state.test_results:
        results = st.session_state.test_results['results']
        evaluations = st.session_state.test_results['evaluations']
        
        st.success("✅ Tests completed successfully!")
        
        # Metrics Dashboard
        create_metrics_dashboard(evaluations)
        
        st.markdown("---")
        
        # Visualizations
        create_visualizations(evaluations)
        
        st.markdown("---")
        
        # Detailed Results
        show_detailed_results(evaluations, results)
        
        st.markdown("---")
        
        # Export options
        st.subheader("💾 Export Results")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            results_json = json.dumps(results, indent=2)
            st.download_button(
                "📥 Download Results JSON",
                results_json,
                file_name=f"pathway_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        with col2:
            evaluations_json = json.dumps(evaluations, indent=2)
            st.download_button(
                "📥 Download Evaluations JSON",
                evaluations_json,
                file_name=f"pathway_evaluations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        with col3:
            personas_json = json.dumps(st.session_state.personas, indent=2)
            st.download_button(
                "📥 Download Personas JSON",
                personas_json,
                file_name=f"personas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    else:
        st.info("👈 Configure your test settings in the sidebar and click 'Run Tests' to get started!")
        
        # Show example
        st.markdown("### 📖 How it works")
        st.markdown("""
        1. **Enter your Pathway ID** - Get this from your Bland AI dashboard
        2. **Configure test parameters** - Number of personas, conversation turns, etc.
        3. **Run tests** - The system will:
           - Generate diverse AI personas with different personalities
           - Run each persona through your pathway
           - Track conversations and variable extraction
           - Evaluate success rates
        4. **View results** - See metrics, visualizations, and detailed conversation logs
        5. **Export data** - Download results for further analysis
        
        **Conversation Endings:**
        - `GOODBYE` - Persona is satisfied (natural ending)
        - `END_CALL` - Persona is frustrated (unsuccessful ending)
        """)


if __name__ == "__main__":
    main()
