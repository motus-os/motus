# Tutorial Step: The Reveal - All 3 Receipts
# Demonstrates: Three complete receipts from three features
# Generated from tutorial.yaml structure - update YAML, regenerate this

Output public/assets/tutorial/05-reveal-3.gif

Set Shell "bash"
Set FontSize 14
Set Width 900
Set Height 600
Set Theme "Dracula"
Set Padding 20

# Hidden setup - create all 3 completed tasks
Hide
Type "cd /tmp && rm -rf demo-app && mkdir demo-app && cd demo-app"
Enter
Sleep 500ms
Type "export MC_DB_PATH=/tmp/demo-app/coordination.db"
Enter
Sleep 200ms
Type "motus init --lite --path . 2>/dev/null"
Enter
Sleep 500ms

# Task 1
Type "L1=$(motus work claim ADHOC-DEMO-001 --intent 'Add a safe greeting function' 2>/dev/null | grep -o 'lease-[a-z0-9-]*')"
Enter
Type 'echo "def greet(name): return \"Hello, \" + name + \"!\"" > greeter.py'
Enter
Type "motus work evidence $L1 test_result --passed 1 --failed 0 2>/dev/null"
Enter
Type "motus work outcome $L1 file --path greeter.py 2>/dev/null"
Enter
Type "motus work decision $L1 'Used f-string' 2>/dev/null"
Enter
Type "motus work release $L1 success 2>/dev/null"
Enter
Sleep 300ms

# Task 2
Type "L2=$(motus work claim ADHOC-DEMO-002 --intent 'Prove the validation' 2>/dev/null | grep -o 'lease-[a-z0-9-]*')"
Enter
Type "echo 'import pytest' > test_greeter.py"
Enter
Type "motus work evidence $L2 test_result --passed 2 --failed 0 2>/dev/null"
Enter
Type "motus work outcome $L2 file --path test_greeter.py 2>/dev/null"
Enter
Type "motus work decision $L2 'Used pytest' 2>/dev/null"
Enter
Type "motus work release $L2 success 2>/dev/null"
Enter
Sleep 300ms

# Task 3
Type "L3=$(motus work claim ADHOC-DEMO-003 --intent 'Add CLI entry point' 2>/dev/null | grep -o 'lease-[a-z0-9-]*')"
Enter
Type "echo 'import sys' > cli.py"
Enter
Type "motus work evidence $L3 test_result --passed 1 --failed 0 2>/dev/null"
Enter
Type "motus work outcome $L3 file --path cli.py 2>/dev/null"
Enter
Type "motus work decision $L3 'Used argparse-free approach' 2>/dev/null"
Enter
Type "motus work release $L3 success 2>/dev/null"
Enter
Sleep 500ms
Show

# Title frame
Type "# 3 features. 3 receipts. Complete audit trail."
Sleep 1.5s
Enter
Sleep 500ms

# Show all three lease IDs
Type 'echo "Feature 1: $L1"'
Enter
Sleep 300ms
Type 'echo "Feature 2: $L2"'
Enter
Sleep 300ms
Type 'echo "Feature 3: $L3"'
Enter
Sleep 1s

# Show the third receipt as the final example
Enter
Type "motus work status $L3"
Sleep 300ms
Enter
Sleep 4s

# Final pause
Sleep 3s
