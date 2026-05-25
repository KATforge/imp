#!/usr/bin/env bash
# Generator for every .tape file in this demo directory.
# Run from demo/. Re-run any time tape bodies change. Idempotent.
set -euo pipefail

cd "$(dirname "$0")"

HEADER='Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 720
Set Theme { "name": "Imp", "background": "#0d120d", "foreground": "#e5e7eb", "cursor": "#4ADE00", "selection": "#1E2D1E", "black": "#0A0A0A", "red": "#ff3131", "green": "#4ADE00", "yellow": "#fcd34d", "blue": "#60a5fa", "magenta": "#a335ee", "cyan": "#22d3ee", "white": "#e5e7eb", "brightBlack": "#4e7a4e", "brightRed": "#ff5757", "brightGreen": "#7FFF20", "brightYellow": "#ffd76e", "brightBlue": "#93c5fd", "brightMagenta": "#c084fc", "brightCyan": "#67e8f9", "brightWhite": "#ffffff" }
Set TypingSpeed 60ms'

tape () {
   local name=$1 ; local setup=$2 ; local height=${3:-720}
   {
      echo "Output ${name}.gif"
      echo
      echo "$HEADER" | sed "s/Set Height 720/Set Height ${height}/"
      echo
      echo "Hide"
      if [ -n "$setup" ]; then
         echo "Type \"${setup} >/dev/null && cd /tmp/demo-repo && clear\" Enter"
         echo "Sleep 600ms"
      else
         echo "Type \"clear\" Enter"
         echo "Sleep 300ms"
      fi
      echo "Show"
      echo
      cat
   } > "${name}.tape"
}

# ─── existing hero tapes (kept verbatim, regenerated for consistency) ──────

tape commit setup-commit <<'EOF'
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

Type "imp log"
Sleep 600ms
Enter
Sleep 4s
EOF

tape pr setup-pr <<'EOF'
Type "imp log"
Sleep 600ms
Enter
Sleep 3s

Type "imp pr"
Sleep 600ms
Enter
Sleep 7s

Enter
Sleep 5s
EOF

tape release setup-release 800 <<'EOF'
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
EOF

tape tidy setup-tidy <<'EOF'
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
EOF

# ─── compose ──────────────────────────────────────────────────────────────

tape amend setup-commit <<'EOF'
Type "imp log"
Sleep 600ms
Enter
Sleep 3s

Type "imp commit -a"
Sleep 600ms
Enter
Sleep 5s

Enter
Sleep 3s

Type "echo '# also tweak docs' >> auth.py"
Sleep 600ms
Enter
Sleep 600ms

Type "imp amend"
Sleep 600ms
Enter
Sleep 6s

Enter
Sleep 4s
EOF

tape split setup-dirty <<'EOF'
Type "imp status"
Sleep 600ms
Enter
Sleep 4s

Type "imp split"
Sleep 600ms
Enter
Sleep 8s

Enter
Sleep 6s

Type "imp log"
Sleep 600ms
Enter
Sleep 5s
EOF

# ─── inspect ──────────────────────────────────────────────────────────────

tape status setup-commit <<'EOF'
Type "imp status"
Sleep 600ms
Enter
Sleep 6s
EOF

tape log setup-history <<'EOF'
Type "imp log"
Sleep 600ms
Enter
Sleep 7s

Type "imp log -n 3"
Sleep 600ms
Enter
Sleep 5s
EOF

tape review setup-dirty <<'EOF'
Type "imp review"
Sleep 600ms
Enter
Sleep 8s
EOF

tape explain setup-history <<'EOF'
Type "imp explain"
Sleep 600ms
Enter
Sleep 8s

Type "imp explain --brief HEAD~2..HEAD"
Sleep 600ms
Enter
Sleep 7s
EOF

tape standup setup-history <<'EOF'
Type "imp standup --since '2024-01-01'"
Sleep 600ms
Enter
Sleep 8s
EOF

# ─── history ──────────────────────────────────────────────────────────────

tape undo setup-history <<'EOF'
Type "imp log -n 3"
Sleep 600ms
Enter
Sleep 4s

Type "imp undo"
Sleep 600ms
Enter
Sleep 4s

Type "imp status"
Sleep 600ms
Enter
Sleep 5s
EOF

tape revert setup-history <<'EOF'
Type "imp log -n 3"
Sleep 600ms
Enter
Sleep 4s

Type "imp revert HEAD~1"
Sleep 600ms
Enter
Sleep 6s

Enter
Sleep 4s

Type "imp log -n 3"
Sleep 600ms
Enter
Sleep 4s
EOF

tape fixup setup-fixup <<'EOF'
Type "git log --oneline"
Sleep 600ms
Enter
Sleep 3s

Type "imp fixup"
Sleep 600ms
Enter
Sleep 7s

Enter
Sleep 5s

Type "git log --oneline"
Sleep 600ms
Enter
Sleep 4s
EOF

tape rescue setup-rescue <<'EOF'
Type "imp log --oneline"
Sleep 600ms
Enter
Sleep 3s

Type "imp rescue 'rate limit'"
Sleep 600ms
Enter
Sleep 7s

Enter
Sleep 5s
EOF

# ─── branch ───────────────────────────────────────────────────────────────

tape branch setup-commit <<'EOF'
Type "imp branch add rate limiting to auth"
Sleep 600ms
Enter
Sleep 6s

Enter
Sleep 4s

Type "git branch --show-current"
Sleep 600ms
Enter
Sleep 3s
EOF

tape fix setup-commit <<'EOF'
Type "imp fix 42"
Sleep 600ms
Enter
Sleep 6s

Enter
Sleep 4s

Type "git branch --show-current"
Sleep 600ms
Enter
Sleep 3s
EOF

tape clean setup-feat <<'EOF'
Type "git branch"
Sleep 600ms
Enter
Sleep 3s

Type "git checkout main"
Sleep 600ms
Enter
Sleep 2s

Type "git merge --no-ff feat/rate-limit -m 'merge feat/rate-limit'"
Sleep 600ms
Enter
Sleep 3s

Type "imp clean"
Sleep 600ms
Enter
Sleep 4s

Type "git branch"
Sleep 600ms
Enter
Sleep 3s
EOF

# ─── sync ─────────────────────────────────────────────────────────────────

tape push setup-feat <<'EOF'
Type "imp push"
Sleep 600ms
Enter
Sleep 5s
EOF

tape sync setup-feat <<'EOF'
Type "imp sync"
Sleep 600ms
Enter
Sleep 6s
EOF

tape merge setup-conflict 800 <<'EOF'
Type "imp merge feat/per-user-limits"
Sleep 600ms
Enter
Sleep 4s

Enter
Sleep 6s

Enter
Sleep 6s

Type "git log --oneline -3"
Sleep 600ms
Enter
Sleep 4s
EOF

tape resolve setup-resolve 800 <<'EOF'
Type "git status -s"
Sleep 600ms
Enter
Sleep 3s

Type "imp resolve"
Sleep 600ms
Enter
Sleep 8s

Enter
Sleep 5s
EOF

tape done setup-feat <<'EOF'
Type "imp done"
Sleep 600ms
Enter
Sleep 4s

Enter
Sleep 4s

Type "git branch"
Sleep 600ms
Enter
Sleep 3s
EOF

# ─── release ──────────────────────────────────────────────────────────────

tape changelog setup-history <<'EOF'
Type "imp changelog"
Sleep 600ms
Enter
Sleep 7s

Enter
Sleep 4s

Type "cat CHANGELOG.md"
Sleep 600ms
Enter
Sleep 4s
EOF

tape tag setup-history <<'EOF'
Type "imp tag --minor"
Sleep 600ms
Enter
Sleep 6s

Enter
Sleep 5s

Type "git tag"
Sleep 600ms
Enter
Sleep 3s
EOF

tape ship setup-dirty 800 <<'EOF'
Type "imp ship --minor"
Sleep 600ms
Enter
Sleep 8s

Enter
Sleep 6s

Enter
Sleep 6s

Type "git log --oneline"
Sleep 600ms
Enter
Sleep 4s
EOF

tape fleet setup-fleet 800 <<'EOF'
Type "imp fleet /tmp/demo-fleet --patch --dry-run"
Sleep 600ms
Enter
Sleep 6s
EOF

# ─── setup ────────────────────────────────────────────────────────────────

tape setup setup-empty <<'EOF'
Type "imp setup git@github.com:demo/auth-service.git"
Sleep 600ms
Enter
Sleep 6s

Type "ls -la"
Sleep 600ms
Enter
Sleep 3s
EOF

tape config "" <<'EOF'
Type "imp config"
Sleep 600ms
Enter
Sleep 6s
EOF

tape doctor "" <<'EOF'
Type "imp doctor"
Sleep 600ms
Enter
Sleep 6s
EOF

tape help "" <<'EOF'
Type "imp help"
Sleep 600ms
Enter
Sleep 8s
EOF

# ─── stash subcommands ────────────────────────────────────────────────────

tape stash setup-stash <<'EOF'
Type "git status -s"
Sleep 600ms
Enter
Sleep 2s

Type "imp stash"
Sleep 600ms
Enter
Sleep 6s

Type "imp stash list"
Sleep 600ms
Enter
Sleep 4s
EOF

tape "stash-list" setup-stash <<'EOF'
Type "imp stash list"
Sleep 600ms
Enter
Sleep 6s
EOF

tape "stash-show" setup-stash <<'EOF'
Type "imp stash show 0"
Sleep 600ms
Enter
Sleep 6s
EOF

tape "stash-pop" setup-stash <<'EOF'
Type "imp stash list"
Sleep 600ms
Enter
Sleep 3s

Type "imp stash pop 0 -y"
Sleep 600ms
Enter
Sleep 5s

Type "git status -s"
Sleep 600ms
Enter
Sleep 3s
EOF

tape "stash-drop" setup-stash <<'EOF'
Type "imp stash list"
Sleep 600ms
Enter
Sleep 3s

Type "imp stash drop 0 -y"
Sleep 600ms
Enter
Sleep 4s

Type "imp stash list"
Sleep 600ms
Enter
Sleep 3s
EOF

# ─── worktree subcommands ─────────────────────────────────────────────────

tape worktree setup-worktree <<'EOF'
Type "imp worktree list"
Sleep 600ms
Enter
Sleep 5s
EOF

tape "worktree-add" setup-worktree <<'EOF'
Type "imp worktree add feat/new-thing"
Sleep 600ms
Enter
Sleep 5s

Type "imp worktree list"
Sleep 600ms
Enter
Sleep 4s
EOF

tape "worktree-list" setup-worktree <<'EOF'
Type "imp worktree list"
Sleep 600ms
Enter
Sleep 6s
EOF

tape "worktree-path" setup-worktree <<'EOF'
Type "imp worktree path feat/rate-limit"
Sleep 600ms
Enter
Sleep 4s
EOF

tape "worktree-remove" setup-worktree <<'EOF'
Type "imp worktree list"
Sleep 600ms
Enter
Sleep 3s

Type "imp worktree remove feat/rate-limit"
Sleep 600ms
Enter
Sleep 5s

Type "imp worktree list"
Sleep 600ms
Enter
Sleep 3s
EOF

tape "worktree-prune" setup-worktree <<'EOF'
Type "imp worktree prune"
Sleep 600ms
Enter
Sleep 5s
EOF

echo "wrote $(ls *.tape | wc -l) tape files"
