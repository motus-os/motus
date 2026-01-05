# Tutorial Step: Record Evidence
# Demonstrates: motus work evidence
# Generated from tutorial.yaml structure - update YAML, regenerate this

Output public/assets/tutorial/02-evidence.gif

Set Shell "bash"
Set FontSize 14
Set Width 800
Set Height 400
Set Theme "Dracula"
Set Padding 20

# Hidden setup - create environment with active lease
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
# Create lease and capture ID
Type "LEASE=$(motus work claim ADHOC-DEMO-001 --intent 'Add a safe greeting function' 2>/dev/null | grep -o 'lease-[a-z0-9-]*')"
Enter
Sleep 1s
# Create the file
Type 'echo "def greet(name): return \"Hello, \" + name + \"!\"" > greeter.py'
Enter
Sleep 500ms
Show

# Title frame
Type "# Step 2: Record evidence"
Sleep 1s
Enter
Sleep 500ms

# Show the test passing
Type 'python3 -c "from greeter import greet; assert greet(\"World\") == \"Hello, World!\"; print(\"Test passed\")"'
Sleep 300ms
Enter
Sleep 1s

# Record evidence
Type "motus work evidence $LEASE test_result --passed 1 --failed 0"
Sleep 300ms
Enter
Sleep 2s

# Pause to show result
Sleep 2s
