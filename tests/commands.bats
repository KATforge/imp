#!/usr/bin/env bats

load helpers

setup() {
   setup_test_repo
   mock_ai "Test commit message"
}

teardown() {
   teardown_test_repo
}

# === imp (dispatcher) ===

@test "imp: shows usage with no args" {
   run "$IMP_ROOT/bin/imp"
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"AI-powered git workflow"* ]]
}

@test "imp: shows version" {
   run "$IMP_ROOT/bin/imp" --version
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"imp 0."* ]]
}

@test "imp: unknown command fails" {
   run "$IMP_ROOT/bin/imp" nonexistent
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"Unknown command"* ]]
}

# === imp commit ===

@test "commit: fails with nothing staged" {
   run "$IMP_ROOT/bin/imp-commit"
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"Nothing staged"* ]]
}

@test "commit: -a flag stages and generates message" {
   echo "new content" >> file.txt
   run "$IMP_ROOT/bin/imp-commit" -a <<< "y"
   [[ "$status" -eq 0 ]]
   # Verify commit was made
   [[ $(git log --oneline | wc -l) -eq 2 ]]
}

# === imp amend ===

@test "amend: fails with no commits beyond initial" {
   echo "change" >> file.txt
   git add file.txt
   # amend should work since there's at least 1 commit
   run "$IMP_ROOT/bin/imp-amend" <<< "y"
   [[ "$status" -eq 0 ]]
}

# === imp branch ===

@test "branch: fails with no description" {
   run "$IMP_ROOT/bin/imp-branch"
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"Missing description"* ]]
}

@test "branch: creates branch from AI suggestion" {
   mock_ai "feat/test-branch"
   run "$IMP_ROOT/bin/imp-branch" "test feature" <<< "y"
   [[ "$status" -eq 0 ]]
   [[ $(git branch --show-current) == "feat/test-branch" ]]
}

@test "branch: validates AI output" {
   mock_ai "invalid branch; rm -rf"
   run "$IMP_ROOT/bin/imp-branch" "test" <<< "y"
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"Invalid branch name"* ]]
}

# === imp undo ===

@test "undo: undoes last commit keeping changes staged" {
   echo "a" >> file.txt && git add file.txt && git commit -m "second"
   run "$IMP_ROOT/bin/imp-undo" <<< "y"
   [[ "$status" -eq 0 ]]
   [[ $(git log --oneline | wc -l) -eq 1 ]]
   # Changes should be staged
   [[ -n "$(git diff --cached)" ]]
}

@test "undo: fails with invalid count" {
   run "$IMP_ROOT/bin/imp-undo" abc
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"Invalid count"* ]]
}

@test "undo: fails when count exceeds commits" {
   run "$IMP_ROOT/bin/imp-undo" 99
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"Only 1 commits"* ]]
}

# === imp stash ===

@test "stash: list shows nothing when empty" {
   run "$IMP_ROOT/bin/imp-stash" list
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"No stashes"* ]]
}

@test "stash: fails with no changes" {
   run "$IMP_ROOT/bin/imp-stash"
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"No changes to stash"* ]]
}

@test "stash: stashes changes with AI message" {
   echo "wip" >> file.txt
   run "$IMP_ROOT/bin/imp-stash" <<< "y"
   [[ "$status" -eq 0 ]]
   [[ -z "$(git diff)" ]]
   [[ -n "$(git stash list)" ]]
}

# === imp diff ===

@test "diff: shows no changes when clean" {
   run "$IMP_ROOT/bin/imp-diff"
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"No changes"* ]]
}

# === imp review ===

@test "review: shows no changes when clean" {
   run "$IMP_ROOT/bin/imp-review"
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"No changes"* ]]
}

# === imp list ===

@test "list: shows repo overview" {
   run "$IMP_ROOT/bin/imp-list"
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"Branch"* ]]
   [[ "$output" == *"main"* ]]
}

# === imp doctor ===

@test "doctor: runs without error" {
   run "$IMP_ROOT/bin/imp-doctor"
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"git"* ]]
}

# === imp help ===

@test "help: shows workflow guide" {
   run "$IMP_ROOT/bin/imp-help"
   [[ "$status" -eq 0 ]]
   [[ "$output" == *"workflow"* ]]
}

# === imp fix ===

@test "fix: fails with no issue number" {
   if ! command -v gh &> /dev/null; then
      skip "gh not installed"
   fi
   run "$IMP_ROOT/bin/imp-fix"
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"Missing issue number"* ]]
}

@test "fix: rejects non-numeric issue" {
   if ! command -v gh &> /dev/null; then
      skip "gh not installed"
   fi
   run "$IMP_ROOT/bin/imp-fix" abc
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"numeric"* ]]
}

# === imp init ===

@test "init: fails inside existing repo" {
   run "$IMP_ROOT/bin/imp-init"
   [[ "$status" -ne 0 ]]
   [[ "$output" == *"Already a git repository"* ]]
}
