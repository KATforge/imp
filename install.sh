#!/bin/bash
set -euo pipefail

IMP_ROOT="$(cd "$(dirname "$0")" && pwd)"

chmod +x "$IMP_ROOT/bin/"*
chmod +x "$IMP_ROOT/lib/"*

shell_rc=""
if [[ -f "$HOME/.zshrc" ]]; then
   shell_rc="$HOME/.zshrc"
elif [[ -f "$HOME/.bash_profile" ]]; then
   shell_rc="$HOME/.bash_profile"
elif [[ -f "$HOME/.profile" ]]; then
   shell_rc="$HOME/.profile"
elif [[ -f "$HOME/.bashrc" ]]; then
   shell_rc="$HOME/.bashrc"
fi

path_line="export PATH=\"$IMP_ROOT/bin:\$PATH\""

if [[ -n "$shell_rc" ]]; then
   if ! grep -q "imp/bin" "$shell_rc" 2> /dev/null; then
      echo "" >> "$shell_rc"
      echo "# imp - AI git tools" >> "$shell_rc"
      echo "$path_line" >> "$shell_rc"
      echo "Added to $shell_rc"
      echo "Run: source $shell_rc"
   else
      echo "Already in $shell_rc"
   fi
else
   echo "Add to your shell config:"
   echo "  $path_line"
fi

echo
echo "Installed. Run: imp doctor"
