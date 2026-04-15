Output release.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 800
Set Theme "Catppuccin Mocha"
Set TypingSpeed 60ms

Hide
Type "setup-release >/dev/null && cd /tmp/demo-repo && clear" Enter
Sleep 600ms
Show

Type "imp status"
Sleep 600ms
Enter
Sleep 4s

Type "imp commit -a"
Sleep 600ms
Enter
Sleep 6s

Enter
Sleep 4s

Type "imp release"
Sleep 600ms
Enter
Sleep 5s

Enter
Sleep 6s

Enter
Sleep 4s

Enter
Sleep 5s

Type "cat CHANGELOG.md"
Sleep 600ms
Enter
Sleep 5s
