# Pathway Regression Testing

Test Bland AI pathways with AI-generated personas.

> **⚠️ Disclaimer**: This entire codebase was AI-generated (white-coded) using Claude via Cursor AI. The code is provided as-is for testing and development purposes.

## Setup

1. **Clone the repository**

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure environment variables**

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
```

Then edit `.env` with your actual keys:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
BLAND_API_KEY=your_bland_api_key_here
```

**Getting API Keys:**
- **OpenRouter**: Sign up at [openrouter.ai](https://openrouter.ai)
- **Bland AI**: Sign up at [bland.ai](https://bland.ai)

## Quick Start

### Option 1: Simple CLI (Fastest)

Just run this and get results in your terminal:

```bash
python src/run_test.py <pathway_id> [num_personas]
```

Example:
```bash
python src/run_test.py fecb7311-770d-4ffc-8347-0ebc9f323674 3
```

Output includes:
- Live conversation display
- Real-time progress for each persona
- Summary statistics and verdict
- Saves JSON files automatically

### Option 2: Web Dashboard (Best for Demos)

Launch the interactive web UI:

```bash
./run.sh
```

Or manually:
```bash
streamlit run src/app.py
```

Then open http://localhost:8501 in your browser.

### Dashboard Features

- **Interactive Testing** - Configure and run tests from the UI
- **Live Chat View** - Watch conversations happen in real-time (toggle on/off)
- **Real-time Progress** - See test progress as it runs
- **Metrics Dashboard** - Success rates, match percentages, conversation stats
- **Visualizations** - Charts showing distribution of results
- **Detailed Results** - View every conversation and variable extraction
- **Export Data** - Download results, evaluations, and personas as JSON

## How It Works

### Call Context Intelligence

The system automatically analyzes each pathway to determine:
- **Call Direction**: Whether the persona is calling (outbound) or receiving a call (inbound)
- **Entity Type**: What kind of place/service is involved (restaurant, hospital, bank, etc.)
- **Context**: Brief description to help the persona understand the situation

This ensures personas have appropriate context and behave naturally in conversations.

### Persona Generation

Each persona includes:
- **Personality traits**: Communication style, patience level, attitude, etc.
- **Behavioral traits**: Precision, error-proneness, decisiveness, etc.
- **Call context**: Understanding of who they're calling or who's calling them
- **Goal variables**: Expected values to provide during the conversation

## Programmatic Usage

### Generate Personas
```python
from src.persona_factory import PersonaFactory

factory = PersonaFactory("pathway-id")
personas = factory.generate_personas(n=10)
factory.save_personas(personas, "personas.json")

# Each persona includes call context
print(personas[0]['goal']['call_context'])
# {
#   "direction": "outbound",
#   "entity_type": "restaurant", 
#   "entity_context": "You are calling to make a reservation..."
# }
```

### Run Tests
```python
from src.pathway_runner import PathwayRunner

runner = PathwayRunner()
result = runner.run_conversation(
    persona=personas[0],
    pathway_id="pathway-id",
    max_turns=50,
    verbose=True
)
```

### Evaluate Results
```python
from src.pathway_evaluator import PathwayEvaluator

evaluation = PathwayEvaluator.evaluate_result(result, personas[0])
print(f"Match: {evaluation['match_summary']['match_percentage']:.1f}%")
```

## Conversation Endings

Personas can end conversations in two ways:

- **`GOODBYE`** - Natural ending when satisfied with the outcome
- **`END_CALL`** - Unsuccessful ending when frustrated or confused

The persona's personality traits (patience, attitude) influence when they give up.

## Command Line Tests

```bash
python test_persona_factory.py
python test_pathway_runner.py
```

## Structure

```
bland-pathway-regression/
├── src/
│   ├── app.py                    # Streamlit web dashboard
│   ├── persona_factory.py        # Generate test personas
│   ├── pathway_runner.py         # Run conversations
│   ├── pathway_evaluator.py      # Compare results with expectations
│   ├── run_test.py               # CLI test runner
│   └── evaluate_results.py       # Batch evaluation
├── requirements.txt              # Python dependencies
├── run.sh                        # Quick launcher script
├── .env                          # Environment variables (create from .env.example)
└── README.md                     # This file
```
