# AI Interpretability System

## Overview

The ZGDK bot includes a comprehensive AI interpretability system that provides transparency into AI decision-making processes. This system allows developers and administrators to understand how the AI modules make decisions, what features influence those decisions, and track performance metrics.

## Architecture

### Core Components

1. **Decision Logger** (`utils/ai/interpretability.py`)
   - Logs all AI decisions with full context
   - Tracks feature usage statistics
   - Stores decisions in daily JSON log files
   - Maintains in-memory session for quick access

2. **Feature Extractor** (`utils/ai/interpretability.py`)
   - Extracts interpretable features from inputs
   - Supports duration, color, and intent feature extraction
   - Provides consistent feature sets for analysis

3. **Model Explainer** (`utils/ai/interpretability.py`)
   - Generates human-readable explanations
   - Uses AI (Gemini) for natural explanations when available
   - Falls back to rule-based explanations
   - Calculates feature importance

### Integrated Modules

All AI modules have been enhanced with interpretability:

1. **Duration Parser** (`core/ai/duration_parser.py`)
   - Logs parsing decisions with confidence scores
   - Tracks features like number presence, unit keywords, Polish numerals
   - Records execution time for performance monitoring

2. **Color Parser** (`core/ai/color_parser.py`)
   - Logs color interpretation decisions
   - Tracks features like hex format, color names, modifiers
   - Records closest named color matches

3. **Intent Classifier** (`core/ai/command_classifier.py`)
   - Logs command classification decisions
   - Tracks features like sentiment, action keywords, mentions
   - Records alternative category suggestions

## Usage

### Developer Commands

The system includes developer commands accessible through the `/ai` command group:

#### `/ai explain [trace_id] [module]`
Explains a recent AI decision in human-readable terms.

```
/ai explain
```
Shows explanation for the most recent AI decision.

```
/ai explain 5 duration_parser
```
Shows explanation for a specific decision by ID and module.

#### `/ai features <module>`
Shows feature importance statistics for a specific module.

```
/ai features duration_parser
```
Displays which features are most influential in duration parsing decisions.

#### `/ai trace [limit] [module]`
Shows recent AI decision traces.

```
/ai trace 10 color_parser
```
Shows the last 10 color parsing decisions.

#### `/ai stats`
Shows overall AI usage statistics including:
- Total decisions processed
- Success rates by module
- Average confidence scores
- Performance metrics

#### `/ai test <module> <input>`
Tests AI modules with sample input and shows interpretation.

```
/ai test duration "dwa tygodnie"
/ai test color "ciemnoniebieski"
/ai test intent "chcę kupić rolę premium"
```

### Debug Command

#### `/ai_debug`
Shows the current state of the AI system including:
- API key configuration status
- Number of logged decisions
- Feature extraction count

## Data Storage

### Decision Logs

AI decisions are stored in:
- **Location**: `logs/ai_decisions/`
- **Format**: JSON Lines (`.jsonl`)
- **Naming**: `decisions_YYYYMMDD.jsonl`
- **Retention**: Configurable (default: 30 days)

### Log Entry Format

```json
{
  "timestamp": "2025-06-28T20:30:45.123Z",
  "module": "duration_parser",
  "input_data": {
    "text": "2 godziny",
    "context": null
  },
  "features_extracted": {
    "length": 9,
    "has_numbers": true,
    "number_count": 1,
    "has_unit_keywords": true,
    "word_count": 2
  },
  "model_output": "7200",
  "final_decision": 7200,
  "confidence": 1.0,
  "reasoning": "Standard format regex match",
  "execution_time_ms": 1.23,
  "user_id": 123456789,
  "guild_id": 987654321,
  "command_context": "mute"
}
```

## Feature Extraction

### Duration Features
- Text length and word count
- Number presence and count
- Unit keyword detection (Polish/English)
- Polish numeral detection
- Relative term detection
- First/last word analysis

### Color Features
- Hex format detection
- RGB pattern detection
- Color name matching (Polish/English)
- Modifier detection (light/dark)
- Character pattern analysis

### Intent Features
- Command name
- Question detection
- Mention types (@user, @role, #channel)
- Emoji presence
- URL detection
- Sentiment keywords (positive/negative/help)
- Action keywords (add/remove/check/modify)

## Performance Monitoring

The system tracks performance metrics for each AI module:

1. **Execution Time**
   - Measured in milliseconds
   - Tracked per decision
   - Aggregated for statistics

2. **Success Rate**
   - Percentage of successful parsing/classification
   - Tracked by module

3. **Confidence Scores**
   - Average confidence per module
   - Distribution analysis available

## Configuration

### Environment Variables

```bash
# Enable AI features
GEMINI_API_KEY=your_gemini_api_key  # Recommended (free tier)
OPENAI_API_KEY=your_openai_api_key  # Alternative

# Enable interpretability logging
AI_INTERPRETABILITY_ENABLED=true
AI_LOG_RETENTION_DAYS=30
```

### Bot Configuration

Add to your bot's config:

```python
# In bot initialization
self.explainer = get_explainer(gemini_api_key)
```

## Best Practices

1. **Regular Monitoring**
   - Check `/ai stats` regularly to monitor performance
   - Review low-confidence decisions with `/ai trace`
   - Use `/ai features` to understand model behavior

2. **Testing**
   - Test edge cases with `/ai test`
   - Verify Polish language handling
   - Check performance with various input lengths

3. **Debugging**
   - Use `/ai explain` to understand unexpected results
   - Check feature extraction with `/ai trace`
   - Monitor execution times for performance issues

4. **Privacy**
   - Decision logs may contain user input
   - Implement appropriate retention policies
   - Consider anonymization for long-term storage

## Integration Example

```python
from utils.ai.interpretability import log_and_explain

# In your AI module
async def parse_something(input_text: str):
    start_time = time.time()
    features = await FeatureExtractor.extract_features(input_text)
    
    # Your AI logic here
    result = await ai_process(input_text)
    
    # Log the decision
    await log_and_explain(
        module="my_module",
        input_data={"text": input_text},
        features=features,
        output=result,
        decision=result,
        confidence=0.95,
        reasoning="AI processed successfully",
        execution_time_ms=(time.time() - start_time) * 1000,
        auto_explain=True  # Generate explanation automatically
    )
    
    return result
```

## Troubleshooting

### Common Issues

1. **No decisions logged**
   - Check if AI modules are being used
   - Verify interpretability is enabled
   - Check log directory permissions

2. **Missing explanations**
   - Verify Gemini API key is configured
   - Check for API rate limits
   - Review error logs

3. **Performance issues**
   - Check execution times with `/ai stats`
   - Consider disabling auto-explanation
   - Review log file sizes

### Support

For issues or questions about the AI interpretability system:
1. Check the logs in `logs/ai_decisions/`
2. Use `/ai_debug` to check system state
3. Review Docker logs for errors
4. Contact the development team