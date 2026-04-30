<p align="center">
   <img src="logo.png" alt="imp" width="160">
</p>

<h1 align="center">Imp</h1>
<p align="center"><strong>AI for the parts of git you skip.</strong></p>

<p align="center">
   <a href="https://pypi.org/project/imp-git/"><img src="https://img.shields.io/pypi/v/imp-git.svg" alt="PyPI"></a>
   <a href="https://pypi.org/project/imp-git/"><img src="https://img.shields.io/pypi/pyversions/imp-git.svg" alt="Python"></a>
   <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
</p>

<p align="center">
   <a href="https://katforge.github.io/imp/"><strong>Full documentation →</strong></a>
</p>

---

`imp` is a git CLI that uses AI for the parts git leaves to you: commit messages, splitting dirty working trees into logical commits, rewriting past history, generating changelogs, opening pull requests, and resolving merge conflicts. It runs against the Claude CLI or a local Ollama model.

## Install

```bash
pip install imp-git
imp config
imp doctor
```

## In one example

```
$ git status
 M src/auth.py
 M src/api.py
 M tests/test_auth.py
 M README.md
?? src/rate_limit.py

$ imp split
→ feat(auth): add rate limiting to login
→ test(auth): cover rate-limit edge cases
→ docs: document new auth flags
```

One dirty tree, three coherent Conventional Commits.

![imp tidy](demo/tidy.gif)

## More

- [Full command reference](https://katforge.github.io/imp/#commands)
- [How `imp` compares to aicommits, OpenCommit, commitizen](https://katforge.github.io/imp/#compare)
- [Configuration](https://katforge.github.io/imp/#config)
- [Contributing](CONTRIBUTING.md)

## License

[MIT](LICENSE)
