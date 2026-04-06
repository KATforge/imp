# Changelog

All notable changes to this project will be documented in this file.


## [0.0.35] - 2026-04-06

### Added
- Improve resolve with structured response parsing
- Add diff collection with line limit to changelog

### Changed
- Clean up imports and simplify command registration
- Extract gh module and use it in commands
- Deduplicate branch types constant in prompts
- Export COMMIT_RE and simplify version bump logic
- Consolidate git tests and update error assertions
- Extract review_commit to workflow module

### Fixed
- Add timeouts to ai calls and cache config load

## [0.0.34] - 2026-04-02

### Fixed
- Normalize status code display

## [0.0.33] - 2026-04-02

### Changed
- Ship now uses intelligent commit splitting

## [0.0.32] - 2026-04-02

### Added
- Add git sync status to branch display

## [0.0.31] - 2026-04-02

### Changed
- Add blank line before gitignore prompt

## [0.0.30] - 2026-04-02

### Added
- Add setup command and refactor error handling

## [0.0.29] - 2026-04-01

### Added
- Handle large diffs with file stats in split

## [0.0.28] - 2026-04-01

### Added
- Add --push option to commit

## [0.0.27] - 2026-03-30

### Added
- Add imp changelog command
- Add tag remediation plan builder
- Add changelog generation from version map
- Add AI-based version boundary inference
- Add AI prompt for inferring version boundaries
- Add version map builder from tags and commits
- Add --since value parser for changelog command
- Add tag_commit_map and log_full git helpers

### Changed
- Update installation instructions to use imp-git
- Add changelog command integration test

### Fixed
- Address review issues in changelog implementation

## [0.0.24] - 2026-03-26

### Added
- Add push command

## [0.0.23] - 2026-03-26

### Added
- Set commit dates from file modification times

## [0.0.22] - 2026-03-24

### Changed
- Restructure readme and remove table of contents

## [0.0.21] - 2026-03-24

### Changed
- Implement dynamic vcs-based versioning with hatch-vcs

## [0.0.20] - 2026-03-24

### Added
- Add resolve command for ai-assisted conflict resolution

## [0.0.19] - 2026-03-24

### Changed
- Refactor workflows section

## [0.0.18] - 2026-03-24

### Added
- Add interactive config management

## [0.0.17] - 2026-03-23

### Changed
- Rewrite why section to emphasize opinionated approach

## [0.0.16] - 2026-03-23

### Added
- Warn when releasing from non-base branch

## [0.0.15] - 2026-03-21

### Fixed
- Replace broad exception handling with specific types

## [0.0.14] - 2026-03-20

### Added
- Add ship command for one-shot commit and release

## [0.0.13] - 2026-03-20

### Added
- Add whisper option to AI commands

## [0.0.12] - 2026-03-20

### Added
- Overhaul done to merge locally and delete branch

### Changed
- Expand command docstrings with behavior descriptions
- Replace git edit flag with interactive console.edit

### Fixed
- Include exception details in error messages
- Parse status file paths with lstrip instead of fixed index

## [0.0.11] - 2026-03-15

### Added
- Add __main__ entry point and dynamic version from metadata

### Changed
- Use builtin print instead of console.out.print
- Update install instructions for python package
- Add ai tests, command tests, and update imports
- Move sanitize to ai module and add truncate helper
- Remove deprecated bash scripts and bin wrapper
- Sync (alias).
- Rewrite in python

### Fixed
- Rename range to rev_range, add git timeout, fix split paths

## [0.0.10] - 2026-02-26

- Added: add split, done, clean commands and branch switching
- Changed: normalize output to use item helper
- Changed: remove stash, diff, describe, and init commands
- Fixed: improve reliability and ux across commands

## [0.0.9] - 2026-02-24

- Changed: Pipe AI prompts via stdin instead of passing as shell arguments, removing argument size limits
- Changed: Increase Claude request timeout from 60s to 120s
- Added: `--tools ""` flag to Claude CLI calls to disable tool use
- Changed: Ollama prompt now piped through `jq -Rs` and `curl -d @-` instead of inline JSON argument
- Fixed: Changelog file path now resolved relative to repo root instead of current working directory
- Changed: `prompt_changelog` now receives full diff as primary input alongside commit log
- Changed: Changelog prompt format changed from Keep a Changelog sections to flat prefixed lines (`Added:`, `Changed:`, `Fixed:`, `Removed:`)
- Changed: `prompt_commit` now counts and reports number of changed files in the prompt
- Changed: Commit message rules updated to require prose body (semicolon-separated) instead of bullet points, with example included
- Changed: Release squash now stages all changes with `git add -A` instead of only staging the changelog file
- Added: Integration test verifying release creates a tag and includes changelog in the commit
- Added: Integration test verifying release squashes multiple commits into one since the last tag
- Removed: Directory structure section from README
- Changed: README description, examples, and command reference updated for clarity

## [0.0.8] - 2026-02-21

### Changed
- Consolidated v0.0.5 changes into main development branch

## [0.0.7] - 2026-02-21

### Changed
- Release process no longer pushes unrelated tags

## [0.0.6] - 2026-02-21

### Changed
- Simplified version calculation and fallback logic

## [0.0.5] - 2026-02-21

### Added
- Gum spinners for improved UX during operations

### Changed
- Command names aligned with actual behavior
- Version accuracy and tag conflict prevention

## [0.0.4] - 2026-02-17

### Changed
- Use `--force-with-lease` for squashed commits to preserve history integrity

## [0.0.3] - 2026-02-17

### Added
- Daily workflow commands and analysis tools to the command set

## [0.0.2] - 2026-02-07

### Changed
- Improved user experience with consistent output formatting and clearer hints

## [0.0.1] - 2026-02-07

### Added
- AI-powered git commands functionality

### Changed
- Refactored user input prompts for improved clarity and safety
