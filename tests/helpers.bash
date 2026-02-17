#!/bin/bash
#
# Shared test helpers
#

# shellcheck disable=SC2034
IMP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

setup_test_repo() {
   TEST_DIR=$(mktemp -d)
   cd "$TEST_DIR" || exit 1
   git init -b main
   git config user.email "test@test.com"
   git config user.name "Test"
   echo "hello" > file.txt
   git add file.txt
   git commit -m "Initial commit"
}

teardown_test_repo() {
   cd / || true
   rm -rf "$TEST_DIR"
}

# Mock AI to avoid real API calls
mock_ai() {
   local response="$1"

   # Create a fake claude that returns canned response
   mkdir -p "$TEST_DIR/.bin"
   cat > "$TEST_DIR/.bin/claude" << SCRIPT
#!/bin/bash
echo "$response"
SCRIPT
   chmod +x "$TEST_DIR/.bin/claude"
   export PATH="$TEST_DIR/.bin:$PATH"
   export IMP_AI_PROVIDER=claude
}
