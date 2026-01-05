# Tutorial Step: View Receipt
# Demonstrates: motus work status
# Generated from tutorial.yaml structure - update YAML, regenerate this

Output packages/website/public/assets/tutorial/04-receipt.gif

Set Shell "bash"
Set FontSize 14
Set Width 800
Set Height 500
Set Theme "Dracula"
Set Padding 20

# Hidden setup - create complete receipt
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
Type "LEASE=$(motus work claim ADHOC-DEMO-001 --intent 'Add greeting function' 2>/dev/null | grep -o 'lease-[a-z0-9-]*')"
Enter
Sleep 500ms
Type "echo 'def greet(name): return f\"Hello, {name}!\"' > greeter.py"
Enter
Type "motus work evidence $LEASE test_result --passed 1 --failed 0 2>/dev/null"
Enter
Type "motus work outcome $LEASE file --path greeter.py 2>/dev/null"
Enter
Type "motus work decision $LEASE 'Used f-string for readability' 2>/dev/null"
Enter
Type "motus work release $LEASE success 2>/dev/null"
Enter
Sleep 500ms
Show

# Title frame
Type "# View the complete receipt"
Sleep 1s
Enter
Sleep 500ms

# Show status
Type "motus work status $LEASE"
Sleep 300ms
Enter
Sleep 3s

# Pause to show full receipt
Sleep 3s
