# Tutorial Step: Release with Receipt
# Demonstrates: motus work release
# Generated from tutorial.yaml structure - update YAML, regenerate this

Output packages/website/public/assets/tutorial/03-release.gif

Set Shell "bash"
Set FontSize 14
Set Width 800
Set Height 400
Set Theme "Dracula"
Set Padding 20

# Hidden setup - create environment with evidence recorded
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
Sleep 500ms
Show

# Title frame
Type "# Step 3: Release with receipt"
Sleep 1s
Enter
Sleep 500ms

# Release the work
Type "motus work release $LEASE success"
Sleep 300ms
Enter
Sleep 2s

# Pause to show result
Sleep 2s
