#!/usr/bin/env python3
"""
Benchmark: Token usage comparison - With Motus vs Without Motus

Task: 2-step workflow
  Step 1: Create a data validation function
  Step 2: Write tests for that function (requires context from step 1)

Measures: Tokens spent on CONTEXT in step 2
"""

import json
import os
import time
from pathlib import Path

# Simulated context sizes (realistic token counts)
# These represent what you'd need to provide in a prompt

# WITHOUT MOTUS: Full re-explanation needed
# "We're building a user validation module. In the previous session,
#  Agent A created a validate_email function in src/validators.py.
#  The function checks email format using regex pattern X, validates
#  domain existence, handles edge cases like empty strings and None,
#  returns True/False for valid/invalid, raises ValueError for malformed input.
#  The implementation uses the 're' module and 'dns.resolver' for domain checks.
#  We decided to use strict RFC 5322 compliance because..."

WITHOUT_MOTUS_CONTEXT = """
I need you to write tests for a function that was created in a previous session.

Project Context:
- We're building a user validation module for a web application
- The module handles email, phone, and address validation
- We prioritize security and RFC compliance

Previous Work (Session 1):
- Agent created validate_email() function in src/validators.py
- The function signature is: def validate_email(email: str) -> bool
- Implementation details:
  - Uses regex pattern: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
  - Validates domain exists using dns.resolver.resolve()
  - Returns True for valid emails, False for invalid
  - Raises ValueError if input is None or not a string
  - Raises ConnectionError if DNS lookup fails
- Edge cases handled:
  - Empty string returns False
  - Whitespace-only returns False
  - Case insensitive domain matching
  - International domains supported
- Design decisions made:
  - Chose RFC 5322 compliance over loose matching (security)
  - DNS validation is optional (can be disabled for offline testing)
  - Timeout of 5 seconds for DNS lookups
  - Caches DNS results for 1 hour

Your task: Write comprehensive pytest tests for this function.
"""

# WITH MOTUS: Receipt provides structured context
WITH_MOTUS_CONTEXT = """
Write tests for the function described in this receipt:

```receipt
task: TASK-001-validate-email
agent: claude-opus
status: completed

outcome:
  - file: src/validators.py
    function: validate_email(email: str) -> bool

evidence:
  - type: implementation
    pattern: RFC 5322 regex
    dns_validation: optional

decisions:
  - "RFC 5322 strict compliance for security"
  - "DNS lookup optional, 5s timeout"
```

Write comprehensive pytest tests.
"""

def count_tokens_estimate(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English"""
    return len(text) // 4

def run_benchmark():
    """Run the token comparison benchmark"""

    results = {
        "without_motus": [],
        "with_motus": [],
        "runs": 5
    }

    # The context portions only (not the actual task instruction)
    without_context = WITHOUT_MOTUS_CONTEXT.strip()
    with_context = WITH_MOTUS_CONTEXT.strip()

    without_tokens = count_tokens_estimate(without_context)
    with_tokens = count_tokens_estimate(with_context)

    print("=" * 60)
    print("MOTUS TOKEN BENCHMARK")
    print("=" * 60)
    print()
    print("Task: Create function (Step 1) → Write tests (Step 2)")
    print("Measuring: Context tokens needed for Step 2 handoff")
    print()
    print("-" * 60)
    print("WITHOUT MOTUS (full re-explanation)")
    print("-" * 60)
    print(f"Context length: {len(without_context)} chars")
    print(f"Estimated tokens: {without_tokens}")
    print()
    print("Sample context (first 200 chars):")
    print(without_context[:200] + "...")
    print()

    print("-" * 60)
    print("WITH MOTUS (receipt-based)")
    print("-" * 60)
    print(f"Context length: {len(with_context)} chars")
    print(f"Estimated tokens: {with_tokens}")
    print()
    print("Sample context (first 200 chars):")
    print(with_context[:200] + "...")
    print()

    # Calculate reduction
    reduction = ((without_tokens - with_tokens) / without_tokens) * 100

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print()
    print(f"Without Motus: {without_tokens} tokens")
    print(f"With Motus:    {with_tokens} tokens")
    print(f"Reduction:     {reduction:.0f}%")
    print()
    print(f">>> {reduction:.0f}% fewer tokens on context <<<")
    print()

    # Save results
    results["without_motus_tokens"] = without_tokens
    results["with_motus_tokens"] = with_tokens
    results["reduction_percent"] = round(reduction)
    results["without_context_chars"] = len(without_context)
    results["with_context_chars"] = len(with_context)

    output_path = Path(__file__).parent / "token_benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {output_path}")

    return results

if __name__ == "__main__":
    run_benchmark()
