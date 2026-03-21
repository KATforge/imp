# Changelog

All notable changes to this project will be documented in this file.


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
