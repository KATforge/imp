#!/usr/bin/env bats

load helpers

setup() {
   source "$IMP_ROOT/lib/common.sh"
   setup_test_repo
}

teardown() {
   teardown_test_repo
}

# === bump_version ===

@test "bump_version: patch" {
   result=$(bump_version "1.2.3" patch)
   [[ "$result" == "1.2.4" ]]
}

@test "bump_version: minor" {
   result=$(bump_version "1.2.3" minor)
   [[ "$result" == "1.3.0" ]]
}

@test "bump_version: major" {
   result=$(bump_version "1.2.3" major)
   [[ "$result" == "2.0.0" ]]
}

@test "bump_version: custom passthrough" {
   result=$(bump_version "1.2.3" "5.0.0")
   [[ "$result" == "5.0.0" ]]
}

@test "bump_version: invalid input passes bump through" {
   result=$(bump_version "garbage" patch)
   [[ "$result" == "patch" ]]
}

@test "bump_version: zeros" {
   result=$(bump_version "0.0.0" patch)
   [[ "$result" == "0.0.1" ]]
}

# === base_branch ===

@test "base_branch: returns main when main exists" {
   result=$(base_branch)
   [[ "$result" == "main" ]]
}

@test "base_branch: returns master when only master exists" {
   git branch -m main master
   result=$(base_branch)
   [[ "$result" == "master" ]]
}

# === last_tag ===

@test "last_tag: empty when no tags" {
   result=$(last_tag)
   [[ "$result" == "" ]]
}

@test "last_tag: returns latest tag" {
   git tag v1.0.0
   result=$(last_tag)
   [[ "$result" == "v1.0.0" ]]
}

@test "last_tag: returns most recent tag" {
   git tag v1.0.0
   echo "more" >> file.txt
   git add file.txt
   git commit -m "second"
   git tag v1.1.0
   result=$(last_tag)
   [[ "$result" == "v1.1.0" ]]
}

# === commit_count ===

@test "commit_count: one commit" {
   result=$(commit_count)
   [[ "$result" == "1" ]]
}

@test "commit_count: multiple commits" {
   echo "a" >> file.txt && git add file.txt && git commit -m "two"
   echo "b" >> file.txt && git add file.txt && git commit -m "three"
   result=$(commit_count)
   [[ "$result" == "3" ]]
}

# === has_upstream ===

@test "has_upstream: false when no remote" {
   run has_upstream
   [[ "$status" -ne 0 ]]
}

# === get_diff ===

@test "get_diff: returns 1 when no changes" {
   run get_diff
   [[ "$status" -ne 0 ]]
}

@test "get_diff: detects staged changes" {
   echo "change" >> file.txt
   git add file.txt
   get_diff
   [[ "$DIFF_CONTEXT" == "staged changes" ]]
   [[ -n "$DIFF" ]]
}

@test "get_diff: detects unstaged changes" {
   echo "change" >> file.txt
   get_diff
   [[ "$DIFF_CONTEXT" == "unstaged changes" ]]
   [[ -n "$DIFF" ]]
}

@test "get_diff: staged takes priority over unstaged" {
   echo "staged" >> file.txt
   git add file.txt
   echo "unstaged" >> file.txt
   get_diff
   [[ "$DIFF_CONTEXT" == "staged changes" ]]
}

# === validate_branch ===

@test "validate_branch: valid names pass" {
   validate_branch "feat/my-feature"
   validate_branch "fix/bug-123"
   validate_branch "main"
   validate_branch "release/1.0.0"
}

@test "validate_branch: rejects spaces" {
   run validate_branch "feat/my feature"
   [[ "$status" -ne 0 ]]
}

@test "validate_branch: rejects semicolons" {
   run validate_branch "feat;rm -rf"
   [[ "$status" -ne 0 ]]
}

@test "validate_branch: rejects leading dash" {
   run validate_branch "-delete"
   [[ "$status" -ne 0 ]]
}

# === require_git ===

@test "require_git: passes in git repo" {
   require_git
}

@test "require_git: fails outside git repo" {
   cd /tmp
   run require_git
   [[ "$status" -ne 0 ]]
}

# === require_clean ===

@test "require_clean: passes when clean" {
   require_clean
}

@test "require_clean: fails when dirty" {
   echo "dirty" >> file.txt
   run require_clean
   [[ "$status" -ne 0 ]]
}

# === show_items ===

@test "show_items: formats output" {
   result=$(show_items "Title" "line1
line2")
   [[ "$result" == *"Title"* ]]
   [[ "$result" == *"line1"* ]]
   [[ "$result" == *"line2"* ]]
}
