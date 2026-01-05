Output "docs/assets/demo.gif"
Set Shell "bash"
Set Theme "Catppuccin Mocha"
Set FontSize 16
Set Width 960
Set Height 540
Set Padding 20
Set TypingSpeed 55ms
Set CursorBlink true

Type "cd $MOTUS_DEMO_DIR"
Enter
Sleep 500ms

Type "python3 -m motus.cli init --lite --path ."
Enter
Sleep 600ms

Type "LEASE=$(python3 -m motus.cli work claim TASK-001 --intent 'Run first loop' --json | jq -r .lease_id)"
Enter
Sleep 300ms

Type "python3 -m motus.cli work evidence $LEASE test_result --passed 1"
Enter
Sleep 300ms

Type "python3 -m motus.cli work decision $LEASE 'Ready to ship' --rationale 'Checks passed'"
Enter
Sleep 300ms

Type "python3 -m motus.cli work release $LEASE success"
Enter
Sleep 300ms

Type "python3 -m motus.cli work status $LEASE"
Enter
