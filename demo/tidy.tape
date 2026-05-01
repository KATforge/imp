Output tidy.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 720
Set Theme { "name": "Imp", "background": "#0d120d", "foreground": "#e5e7eb", "cursor": "#4ADE00", "selection": "#1E2D1E", "black": "#0A0A0A", "red": "#ff3131", "green": "#4ADE00", "yellow": "#fcd34d", "blue": "#60a5fa", "magenta": "#a335ee", "cyan": "#22d3ee", "white": "#e5e7eb", "brightBlack": "#4e7a4e", "brightRed": "#ff5757", "brightGreen": "#7FFF20", "brightYellow": "#ffd76e", "brightBlue": "#93c5fd", "brightMagenta": "#c084fc", "brightCyan": "#67e8f9", "brightWhite": "#ffffff" }
Set TypingSpeed 60ms

Hide
Type "setup-tidy >/dev/null && cd /tmp/demo-repo && clear" Enter
Sleep 600ms
Show

Type "git log --oneline"
Sleep 600ms
Enter
Sleep 3s

Type "imp tidy 3"
Sleep 600ms
Enter
Sleep 6s

Enter
Sleep 6s

Type "git log --oneline"
Sleep 600ms
Enter
Sleep 5s
