# Tutorial Step: The Reveal - Receipt 1
# Demonstrates: motus work status showing complete receipt
# Generated from tutorial.yaml structure - update YAML, regenerate this

Output packages/website/public/assets/tutorial/05-reveal-1.gif

Set Shell "bash"
Set FontSize 14
Set Width 900
Set Height 500
Set Theme "Dracula"
Set Padding 20

# Hidden setup - create completed task with full receipt
Hide
Type "cd /tmp && rm -rf demo-app && mkdir demo-app && cd demo-app"
Enter
Sleep 500ms
Type "motus init --lite --path . 2>/dev/null"
Enter
Sleep 500ms

# Task 1 - complete the full loop
Type "L1=$(motus work claim DEMO-001 --intent 'Add greeting function' 2>/dev/null | grep -o 'lease_[a-z0-9]*')"
Enter
Type "echo 'def greet(name): return f\"Hello, {name}!\"' > greeter.py"
Enter
Type "motus work evidence $L1 test --passed 1 --failed 0 2>/dev/null"
Enter
Type "motus work outcome $L1 file --path greeter.py 2>/dev/null"
Enter
Type "motus work decision $L1 'Used f-string for readability' 2>/dev/null"
Enter
Type "motus work release $L1 success 2>/dev/null"
Enter
Sleep 500ms
Show

# Title frame
Type "# The Reveal: Your first receipt"
Sleep 1s
Enter
Sleep 500ms

# Show the complete receipt
Type "motus work status $L1"
Sleep 300ms
Enter
Sleep 4s

# Pause to show full receipt
Sleep 3s
