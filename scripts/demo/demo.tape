Output "docs/assets/demo.gif"
Set Shell "bash"
Set Theme "Catppuccin Mocha"
Set FontSize 16
Set Width 800
Set Height 450
Set Padding 20
Set TypingSpeed 60ms
Set Framerate 12
Set CursorBlink true

Type "cd $MOTUS_DEMO_DIR"
Enter
Sleep 300ms

Type "LEASE=$(motus work claim TASK-001 --intent 'Demo task' --json | jq -r .lease_id)"
Enter
Sleep 400ms

Type "motus work evidence $LEASE test_result --passed 3 --failed 0"
Enter
Sleep 300ms

Type "motus work release $LEASE success"
Enter
Sleep 300ms

Type "motus work status $LEASE"
Enter
Sleep 600ms
