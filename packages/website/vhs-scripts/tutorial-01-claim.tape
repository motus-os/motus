# Tutorial Step: Claim Work
# Demonstrates: motus work claim
# Generated from tutorial.yaml structure - update YAML, regenerate this

Output public/assets/tutorial/01-claim.gif

Set Shell "bash"
Set FontSize 14
Set Width 800
Set Height 400
Set Theme "Dracula"
Set Padding 20

# Hidden setup - create clean environment
Hide
Type "cd /tmp && rm -rf demo-app && mkdir demo-app && cd demo-app"
Enter
Sleep 500ms
Type "export MC_DB_PATH=/tmp/demo-app/coordination.db"
Enter
Sleep 200ms
Type "motus init --lite --path . 2>/dev/null"
Enter
Sleep 1s
Show

# Title frame
Type "# Step 1: Claim the work"
Sleep 1s
Enter
Sleep 500ms

# The actual command
Type "motus work claim ADHOC-DEMO-001 --intent 'Add a safe greeting function' 2>/dev/null"
Sleep 500ms
Enter
Sleep 2s

# Pause to show result
Sleep 2s
