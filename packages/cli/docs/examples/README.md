# Motus Examples

Fun, approachable examples demonstrating agent observability with Motus.

These examples show progressively complex uses of the Tracer SDK, from basic logging to multi-agent coordination. All examples use non-proprietary data and demonstrate real value of agent observability.

## Example Progression

| Example | Complexity | Key Features | Concepts |
|---------|-----------|--------------|----------|
| [1. Dad Joke Generator](#1-dad-joke-generator) | Beginner | Traces, thinking events | Basic SDK usage |
| [2. Recipe Research Agent](#2-recipe-research-agent) | Beginner+ | Tools, decisions, risk levels | Decision tracking |
| [3. Hello World Site Builder](#3-hello-world-site-builder) | Intermediate | File changes, multi-step workflows | File operations |
| [4. Multi-Agent Debate](#4-multi-agent-debate) | Intermediate+ | Multiple tracers, spawns | Parallel agents |
| [5. Pomodoro Study Bot](#5-pomodoro-study-bot) | Advanced | Sessions, teleport, awareness | Long-running agents |

---

## 1. Dad Joke Generator

**Complexity:** Beginner
**What it demonstrates:** Basic trace plane usage, thinking events
**Why it's fun:** Everyone loves dad jokes. This shows how simple it is to add observability to any AI task.

### What You'll Learn

- Basic Tracer SDK setup
- Logging thinking/reasoning events
- Viewing traces in real-time with `motus`

### The Code

```python
from motus import Tracer
import random

# Initialize tracer
tracer = Tracer("dad-joke-bot")

# Log thinking
tracer.thinking("Analyzing dad joke database...")
tracer.thinking("Selecting joke with maximum groan potential...")

# Simulate joke generation
jokes = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "I'm reading a book about anti-gravity. It's impossible to put down!",
    "Why did the scarecrow win an award? He was outstanding in his field!"
]

selected = random.choice(jokes)
tracer.thinking(f"Selected joke: {selected[:20]}...")

# Log the decision
tracer.decision(
    decision="Deliver joke #2",
    reasoning="Maximum groan factor, appropriate for all ages",
    alternatives=["joke #1 (overused)", "joke #3 (too corny)"]
)

print(f"\n{selected}\n")
tracer.end_session()
```

### Try It

```bash
# Run the script
python dad_joke_bot.py

# Watch it in Motus dashboard
motus

# Export the session for review
motus list
motus summary <session-id>
```

### What You'll See in Motus

- Real-time thinking events as the bot "decides"
- Decision tracking with alternatives considered
- Session timeline showing the full joke selection process

### Why This Matters

Even simple AI tasks benefit from observability. When your joke bot stops being funny, you can see exactly what changed in its decision-making process.

---

## 2. Recipe Research Agent

**Complexity:** Beginner+
**What it demonstrates:** Tool usage, decision tracking, risk levels
**Why it's fun:** Cooking is relatable, and watching an AI research recipes shows clear decision-making.

### What You'll Learn

- Logging tool calls with input/output
- Tracking decisions with reasoning
- Using risk levels for different operations
- Context managers for timing

### The Code

```python
from motus import Tracer
import time

tracer = Tracer("recipe-researcher")

def search_recipes(query):
    """Simulate recipe search."""
    time.sleep(0.5)  # Simulate API call
    return [
        {"name": "Classic Margherita Pizza", "time": "25 min", "difficulty": "easy"},
        {"name": "Neapolitan Pizza", "time": "48 hours", "difficulty": "expert"},
        {"name": "Quick Pita Pizza", "time": "10 min", "difficulty": "beginner"}
    ]

def check_pantry(ingredients):
    """Simulate pantry check."""
    time.sleep(0.2)
    pantry = {"flour", "tomato sauce", "cheese", "yeast"}
    return pantry.intersection(set(ingredients))

# Main agent logic
tracer.thinking("User wants pizza recipe. Analyzing preferences...")

# Log tool call with timing
with tracer.tool_span("RecipeSearch", {"query": "pizza", "dietary": "none"}) as span:
    recipes = search_recipes("pizza")
    span.output = recipes

tracer.thinking(f"Found {len(recipes)} recipes. Checking pantry availability...")

# Check ingredients
for recipe in recipes:
    ingredients = ["flour", "tomato sauce", "cheese"]

    tracer.tool(
        name="PantryCheck",
        input={"recipe": recipe["name"], "ingredients": ingredients},
        output=check_pantry(ingredients),
        risk_level="safe"
    )

# Make decision
tracer.decision(
    decision="Recommend Classic Margherita Pizza",
    reasoning="User has all ingredients, 25-min cook time fits schedule, skill level matches",
    alternatives=[
        "Neapolitan (rejected: 48-hour ferment too long)",
        "Pita Pizza (rejected: user wants authentic experience)"
    ]
)

print("\nRecommendation: Classic Margherita Pizza")
print("Reasoning: You have all ingredients and it matches your skill level!")

tracer.end_session()
```

### Try It

```bash
# Run the agent
python recipe_agent.py

# Watch with filtering
motus
# Press 'f' to cycle filters: All -> Thinking -> Tools -> Decisions

# Export the decision trail
motus teleport <session-id>
```

### What You'll See in Motus

- Tool calls with input/output and duration
- Decision tree with alternatives considered
- Risk levels (all safe for this read-only agent)
- Timeline showing parallelizable operations

### Why This Matters

When your recipe agent starts making bad recommendations, Motus shows you:
- Which tool calls returned unexpected data
- What reasoning led to each decision
- Which alternatives were considered and why they were rejected

---

## 3. Hello World Site Builder

**Complexity:** Intermediate
**What it demonstrates:** File operations, risk tracking, multi-step workflows
**Why it's fun:** Watching files get created in real-time shows tangible agent actions.

### What You'll Learn

- Logging file changes with diff stats
- Risk escalation (safe -> medium -> high)
- Multi-step workflow tracking
- Auto-tracking functions with decorators

### The Code

```python
from motus import Tracer
from pathlib import Path

tracer = Tracer("site-builder")

@tracer.track(risk_level="safe")
def analyze_requirements(spec):
    """Parse the site specification."""
    return {
        "pages": spec.get("pages", ["index.html"]),
        "style": spec.get("style", "minimal"),
        "features": spec.get("features", [])
    }

@tracer.track(risk_level="medium")
def generate_html(page_name, style):
    """Generate HTML content."""
    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_name.title()}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Hello, World!</h1>
    <p>Built by an AI agent with Motus observability.</p>
</body>
</html>"""
    return template

@tracer.track(risk_level="medium")
def generate_css(style):
    """Generate CSS based on style preference."""
    styles = {
        "minimal": "body { font-family: sans-serif; max-width: 600px; margin: 50px auto; }",
        "colorful": "body { font-family: sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 50px; }"
    }
    return styles.get(style, styles["minimal"])

def write_file(path, content):
    """Write file and log the change."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    # Check if file exists for diff stats
    existing = Path(path).exists()
    old_lines = len(Path(path).read_text().splitlines()) if existing else 0

    # Write file
    Path(path).write_text(content)
    new_lines = len(content.splitlines())

    # Log file change
    tracer.file_change(
        path=path,
        operation="create" if not existing else "modify",
        lines_added=new_lines if not existing else max(0, new_lines - old_lines),
        lines_removed=0 if not existing else max(0, old_lines - new_lines)
    )

# Main workflow
tracer.thinking("Starting site builder. Analyzing spec...")

spec = {
    "pages": ["index.html"],
    "style": "minimal",
    "features": ["responsive"]
}

config = analyze_requirements(spec)

tracer.decision(
    decision=f"Build {len(config['pages'])} page(s) with {config['style']} style",
    reasoning=f"Spec requests {config['style']} design for {len(config['pages'])} pages",
    alternatives=[]
)

tracer.thinking("Generating HTML content...")
html = generate_html("index", config["style"])

tracer.thinking("Generating CSS styles...")
css = generate_css(config["style"])

tracer.thinking("Writing files to disk...")

# Write files (higher risk - actual file system changes)
output_dir = "output/hello-world-site"
write_file(f"{output_dir}/index.html", html)
write_file(f"{output_dir}/style.css", css)

print(f"\nSite built successfully in {output_dir}/")
print("Open index.html in your browser!")

tracer.end_session()
```

### Try It

```bash
# Run the builder
python site_builder.py

# Watch in Motus - notice risk levels
motus
# Yellow highlights for medium-risk operations
# File changes appear in the feed

# Review what files were touched
motus summary <session-id>
```

### What You'll See in Motus

- Risk escalation: safe (analysis) -> medium (generation) -> medium (file writes)
- File change events with diff stats
- Auto-tracked function calls from `@tracer.track` decorator
- Multi-step workflow with clear phases

### Why This Matters

When a site builder goes wrong:
- Motus shows which file operations succeeded/failed
- Risk highlighting shows which steps need review
- File diff stats reveal unexpected changes
- Decisions show why the agent chose certain approaches

**Teleport use case:** Save this session's context to bootstrap a "Blog Builder" agent that extends this pattern.

---

## 4. Multi-Agent Debate

**Complexity:** Intermediate+
**What it demonstrates:** Multiple tracers, agent spawns, parallel execution
**Why it's fun:** Watching two AIs debate "Cats vs Dogs" is entertaining and shows multi-agent coordination.

### What You'll Learn

- Running multiple tracers simultaneously
- Logging agent spawns with metadata
- Parallel agent execution patterns
- Session comparison in Motus

### The Code

```python
from motus import Tracer
import time
import random

class DebateAgent:
    def __init__(self, name, stance, arguments):
        self.tracer = Tracer(f"debate-{name}")
        self.name = name
        self.stance = stance
        self.arguments = arguments

    def make_opening(self):
        """Opening statement."""
        self.tracer.thinking(f"Preparing opening statement for {self.stance}...")
        time.sleep(0.3)

        arg = random.choice(self.arguments)
        self.tracer.decision(
            decision=f"Lead with '{arg[:30]}...'",
            reasoning="Strong opener that appeals to emotions",
            alternatives=[a[:20] + "..." for a in self.arguments if a != arg]
        )
        return arg

    def counter_argument(self, opponent_arg):
        """Respond to opponent."""
        self.tracer.thinking(f"Analyzing opponent's argument: {opponent_arg[:50]}...")
        time.sleep(0.3)

        response = random.choice(self.arguments)
        self.tracer.tool(
            name="ArgumentAnalysis",
            input={"opponent_claim": opponent_arg},
            output={"weakness": "appeals to emotion", "counter": response[:50]},
            risk_level="safe"
        )
        return response

    def conclude(self):
        """Closing statement."""
        self.tracer.thinking("Crafting conclusion...")
        self.tracer.decision(
            decision="Summarize key points",
            reasoning="Reinforce strongest arguments from debate",
            alternatives=["new argument (rejected: too late)", "appeal to emotion"]
        )
        self.tracer.end_session()

# Main coordinator
coordinator = Tracer("debate-coordinator")

coordinator.thinking("Initializing Great Cats vs Dogs Debate...")

# Spawn agents
coordinator.spawn_agent(
    agent_type="DebateAgent",
    description="Pro-cats debater",
    prompt="Argue why cats make better pets",
    model="gpt-4"
)

coordinator.spawn_agent(
    agent_type="DebateAgent",
    description="Pro-dogs debater",
    prompt="Argue why dogs make better pets",
    model="gpt-4"
)

# Create debaters
cat_agent = DebateAgent(
    "pro-cats",
    "cats",
    [
        "Cats are independent and low-maintenance",
        "Cats are clean and groom themselves",
        "Cats are perfect for small apartments",
        "Cats are quiet and respectful of your schedule"
    ]
)

dog_agent = DebateAgent(
    "pro-dogs",
    "dogs",
    [
        "Dogs are loyal and protective companions",
        "Dogs encourage exercise and outdoor activity",
        "Dogs are social and great for families",
        "Dogs can be trained for useful tasks"
    ]
)

# Run debate
print("\n=== THE GREAT CATS VS DOGS DEBATE ===\n")

print("🐱 PRO-CATS OPENING:")
cat_opening = cat_agent.make_opening()
print(f"   {cat_opening}\n")

print("🐶 PRO-DOGS OPENING:")
dog_opening = dog_agent.make_opening()
print(f"   {dog_opening}\n")

print("🐱 PRO-CATS COUNTER:")
cat_counter = cat_agent.counter_argument(dog_opening)
print(f"   {cat_counter}\n")

print("🐶 PRO-DOGS COUNTER:")
dog_counter = dog_agent.counter_argument(cat_opening)
print(f"   {dog_counter}\n")

# Conclude
cat_agent.conclude()
dog_agent.conclude()

coordinator.decision(
    decision="Debate concluded successfully",
    reasoning="Both agents completed their arguments",
    alternatives=["extend to 3 rounds (rejected: sufficient depth)"]
)

print("\n=== DEBATE COMPLETE ===")
print("\nView the debate in Motus:")
print("  motus list          # See all 3 sessions")
print("  motus               # Watch live in TUI")

coordinator.end_session()
```

### Try It

```bash
# Run the debate
python debate_agents.py

# Watch all sessions in Motus
motus
# You'll see 3 sessions: coordinator + 2 debaters

# Compare the sessions
motus list
motus watch <pro-cats-session-id>
motus watch <pro-dogs-session-id>
```

### What You'll See in Motus

- Three simultaneous sessions in the sidebar
- Agent spawn events in coordinator session
- Parallel decision-making in each debater
- Tool calls for argument analysis
- Session relationships (coordinator -> spawned agents)

### Why This Matters

Multi-agent systems are complex. Motus shows:
- Which agent made which decisions
- How agents responded to each other
- Timeline of parallel execution
- Parent-child relationships through spawn events

**Advanced:** Try teleporting context from one debater to the other to see how access to opponent's reasoning changes strategy.

---

## 5. Pomodoro Study Bot

**Complexity:** Advanced
**What it demonstrates:** Long-running sessions, teleport, awareness signals, session restoration
**Why it's fun:** A productivity bot that tracks study sessions and uses its own history to improve.

### What You'll Learn

- Long-running agent sessions
- Teleport for session persistence
- Cross-session memory and learning
- Awareness signals and health tracking
- Context restoration from previous sessions

### The Code

```python
from motus import Tracer
from datetime import datetime, timedelta
from pathlib import Path
import json
import time

class PomodoroBot:
    def __init__(self, restore_from=None):
        self.tracer = Tracer("pomodoro-study-bot")
        self.session_data = {
            "pomodoros_completed": 0,
            "total_focus_time": 0,
            "breaks_taken": 0,
            "topics_studied": [],
            "productivity_score": 0
        }

        # Restore from previous session if provided
        if restore_from:
            self._restore_context(restore_from)
        else:
            self.tracer.thinking("Starting fresh Pomodoro session...")

    def _restore_context(self, context_file):
        """Restore state from teleported context."""
        self.tracer.thinking(f"Restoring context from {context_file}...")

        try:
            data = json.loads(Path(context_file).read_text())
            self.session_data = data.get("state", self.session_data)

            self.tracer.tool(
                name="ContextRestore",
                input={"source": context_file},
                output={"restored": True, "pomodoros": self.session_data["pomodoros_completed"]},
                risk_level="safe"
            )

            self.tracer.thinking(
                f"Restored session: {self.session_data['pomodoros_completed']} pomodoros completed, "
                f"{len(self.session_data['topics_studied'])} topics studied"
            )
        except Exception as e:
            self.tracer.tool(
                name="ContextRestore",
                input={"source": context_file},
                output={"error": str(e)},
                status="error",
                risk_level="safe"
            )

    def start_pomodoro(self, topic, duration_min=25):
        """Start a focused work session."""
        self.tracer.thinking(f"Starting {duration_min}-minute Pomodoro on: {topic}")

        # Check if topic is new or continuation
        is_continuation = topic in self.session_data["topics_studied"]

        self.tracer.decision(
            decision=f"{'Continue' if is_continuation else 'Start'} studying {topic}",
            reasoning=f"{'Building on previous session' if is_continuation else 'New topic exploration'}",
            alternatives=[
                f"{'Switch topics' if is_continuation else 'Review previous topics'} (rejected: stay focused)"
            ]
        )

        # Simulate work period
        print(f"\n🍅 Pomodoro started: {topic}")
        print(f"   Focus time: {duration_min} minutes")
        print(f"   (Simulating work...)\n")

        # In real implementation, this would be actual timer
        time.sleep(2)  # Simulate work

        # Log completion
        self.session_data["pomodoros_completed"] += 1
        self.session_data["total_focus_time"] += duration_min
        if topic not in self.session_data["topics_studied"]:
            self.session_data["topics_studied"].append(topic)

        self.tracer.tool(
            name="PomodoroComplete",
            input={"topic": topic, "duration": duration_min},
            output={"completed": True, "total_today": self.session_data["pomodoros_completed"]},
            risk_level="safe",
            duration_ms=duration_min * 60 * 1000
        )

        # Calculate productivity
        self._assess_productivity()

    def take_break(self, duration_min=5):
        """Take a break between Pomodoros."""
        self.tracer.thinking("Time for a break. Assessing optimal break activity...")

        # Decide break type based on productivity
        if self.session_data["productivity_score"] < 0.6:
            break_type = "active (walk, stretch)"
            reasoning = "Low productivity suggests need for physical movement"
        else:
            break_type = "passive (rest, hydrate)"
            reasoning = "Good productivity, gentle recovery sufficient"

        self.tracer.decision(
            decision=f"{duration_min}-min {break_type} break",
            reasoning=reasoning,
            alternatives=[
                "skip break (rejected: reduces long-term focus)",
                "extend break (rejected: focus loss)"
            ]
        )

        print(f"\n☕ Break time: {break_type}")
        print(f"   Duration: {duration_min} minutes\n")

        time.sleep(1)
        self.session_data["breaks_taken"] += 1

    def _assess_productivity(self):
        """Assess current productivity and emit awareness signal."""
        # Simple productivity metric
        ideal_ratio = 5  # 1 break per 5 pomodoros
        actual_ratio = (
            self.session_data["pomodoros_completed"] / max(1, self.session_data["breaks_taken"])
        )

        self.session_data["productivity_score"] = min(1.0, actual_ratio / ideal_ratio)

        self.tracer.thinking(
            f"Productivity assessment: {self.session_data['productivity_score']:.1%} "
            f"({self.session_data['pomodoros_completed']} pomodoros, "
            f"{self.session_data['breaks_taken']} breaks)"
        )

        # Emit awareness signal if productivity drops
        if self.session_data["productivity_score"] < 0.5:
            self.tracer.decision(
                decision="ALERT: Productivity below threshold",
                reasoning="Too many breaks or too few Pomodoros - suggest break adjustment",
                alternatives=["continue as-is (rejected: intervention needed)"]
            )

    def end_session(self):
        """End session and save state for teleport."""
        self.tracer.thinking("Ending study session. Preparing summary...")

        summary = {
            "completed": self.session_data["pomodoros_completed"],
            "focus_time": self.session_data["total_focus_time"],
            "topics": self.session_data["topics_studied"],
            "productivity": f"{self.session_data['productivity_score']:.1%}"
        }

        self.tracer.tool(
            name="SessionSummary",
            input={"action": "generate"},
            output=summary,
            risk_level="safe"
        )

        # Save state for next session
        state_file = Path(f"pomodoro_state_{datetime.now().strftime('%Y%m%d')}.json")
        state_file.write_text(json.dumps({"state": self.session_data, "summary": summary}))

        self.tracer.file_change(
            path=str(state_file),
            operation="create",
            lines_added=len(json.dumps(summary, indent=2).splitlines())
        )

        print(f"\n📊 Session Summary:")
        print(f"   Pomodoros: {summary['completed']}")
        print(f"   Focus time: {summary['focus_time']} minutes")
        print(f"   Topics: {', '.join(summary['topics'])}")
        print(f"   Productivity: {summary['productivity']}")
        print(f"\n💾 State saved to: {state_file}")
        print(f"   Restore next time with: PomodoroBot(restore_from='{state_file}')\n")

        self.tracer.end_session()
        return str(state_file)

# Example usage
if __name__ == "__main__":
    # Check for existing state
    import sys
    restore_file = sys.argv[1] if len(sys.argv) > 1 else None

    bot = PomodoroBot(restore_from=restore_file)

    # Study session
    bot.start_pomodoro("Python decorators", duration_min=25)
    bot.take_break(duration_min=5)

    bot.start_pomodoro("Async programming", duration_min=25)
    bot.take_break(duration_min=5)

    bot.start_pomodoro("Python decorators", duration_min=25)  # Continue previous topic
    bot.take_break(duration_min=15)  # Longer break

    # End and save
    state_file = bot.end_session()

    print("\n🔍 View in Motus:")
    print("  motus                    # Watch live session")
    print("  motus teleport <id>      # Export full context")
    print(f"\n📚 Continue studying:")
    print(f"  python pomodoro_bot.py {state_file}")
```

### Try It

```bash
# First session
python pomodoro_bot.py

# Watch in Motus
motus

# Continue from saved state
python pomodoro_bot.py pomodoro_state_20250122.json

# Compare sessions
motus list
# You'll see how the bot learns from previous sessions
```

### What You'll See in Motus

- **Long-running sessions** with multiple phases (work -> break -> work)
- **Context restoration** events showing state recovery
- **Awareness signals** when productivity drops
- **Decision evolution** as the bot learns from history
- **File operations** for state persistence
- **Health metrics** in the session summary

### Advanced Features

1. **Cross-Session Learning:**
   ```bash
   # Export first session
   motus teleport <session-1-id> > day1.json

   # Bot uses day1.json to inform day2 strategy
   python pomodoro_bot.py day1.json
   ```

2. **Multi-Day Analysis:**
   ```bash
   # Compare multiple study sessions
   motus list --max-age 168  # Last 7 days

   # See productivity trends across sessions
   ```

3. **Teleport for Team Learning:**
   ```bash
   # Share your productive Pomodoro strategy
   motus teleport <your-session> > productive_pattern.json

   # Teammate imports your rhythm
   python pomodoro_bot.py productive_pattern.json
   ```

### Why This Matters

Long-running, stateful agents are the future. Motus provides:
- **Session continuity** through teleport
- **Cross-session learning** via context restoration
- **Health monitoring** for long-running tasks
- **Audit trail** of decisions over time
- **Pattern detection** across multiple sessions

When your study bot stops being productive, Motus shows:
- Which topics caused focus loss
- How break patterns affected productivity
- Whether context restoration worked correctly
- Trends across multiple study sessions

---

## Running These Examples

### Prerequisites

```bash
# Install Motus
pip install motusos

# Verify installation
motus --version
```

### Quick Start

```bash
# Clone examples (or copy from this doc)
git clone https://github.com/motus-os/motus.git
cd motus/packages/cli/docs/examples

# Run any example
python dad_joke_bot.py

# Watch in Motus
motus
```

### Tips for Learning

1. **Start with Dad Joke Bot** - Get comfortable with basic tracing
2. **Progress to Recipe Agent** - Learn tool tracking and decisions
3. **Build the Site Builder** - Understand risk levels and file operations
4. **Run the Debate** - See multi-agent coordination
5. **Master Pomodoro Bot** - Explore advanced features like teleport

### Customizing Examples

All examples are designed to be extended:

- **Dad Joke Bot:** Add LLM integration for real joke generation
- **Recipe Agent:** Connect to real recipe APIs, add nutrition tracking
- **Site Builder:** Extend to full static site generator with templates
- **Debate:** Add judge agent, scoring system, or real LLM debaters
- **Pomodoro Bot:** Add calendar integration, team sync, or gamification

---

## Key Concepts Demonstrated

### Trace Plane
All examples log events to `~/.motus/traces/<session-id>.jsonl`:
- Thinking events (reasoning)
- Tool calls (input/output/timing)
- Decisions (with alternatives)
- File changes (diffs)
- Agent spawns (multi-agent)

### Observability Primitives

| Primitive | Examples Using It |
|-----------|------------------|
| `tracer.thinking()` | All examples |
| `tracer.tool()` | Recipe, Site Builder, Pomodoro |
| `tracer.decision()` | All examples |
| `tracer.spawn_agent()` | Debate |
| `tracer.file_change()` | Site Builder, Pomodoro |
| `@tracer.track` decorator | Site Builder |
| `tracer.tool_span()` context manager | Recipe |

### Risk Levels

```python
# Safe - read-only operations
tracer.tool("RecipeSearch", {...}, risk_level="safe")

# Medium - writes, modifications
tracer.tool("FileWrite", {...}, risk_level="medium")

# High - destructive potential
tracer.tool("DeleteFile", {...}, risk_level="high")

# Critical - dangerous operations
tracer.tool("SystemCommand", {...}, risk_level="critical")
```

Motus color-codes these in the TUI:
- 🟢 Green = Safe
- 🟡 Yellow = Medium
- 🔴 Red = High
- ⚠️ Critical = Destructive

### Teleport (Session Memory)

The Pomodoro Bot demonstrates teleport for:
- Saving agent state between runs
- Learning from previous sessions
- Sharing successful patterns
- Debugging failed sessions

```bash
# Export any session
motus teleport <session-id> > context.json

# Use in your agent
tracer = Tracer("my-agent", context=context.json)
```

---

## Next Steps

### Build Your Own

Use these examples as templates:

1. Identify a fun agent task
2. Add Tracer SDK to your code
3. Log key decisions and tool calls
4. Watch it work in `motus`
5. Share your example!

### Learn More

- [Tracer SDK Documentation](../api/index.md)
- [Architecture Overview](/ARCHITECTURE.md)
- [Manifesto](../manifesto.md)

### Contribute

Found a bug or have a better example? [Open an issue](https://github.com/motus-os/motus/issues) or submit a PR!

---

## Philosophy

These examples follow Motus's core principle:

**Observability should be fun, not a chore.**

Each example is:
- **Entertaining** - You'd run it even without Motus
- **Educational** - Teaches a specific Motus concept
- **Practical** - Patterns transfer to real agents
- **Progressive** - Builds on previous examples

The best way to learn agent observability is to observe agents doing interesting things.

That's what these examples provide.

---

*Built with [Motus](https://github.com/motus-os/motus) - The local-first agent kernel.*
