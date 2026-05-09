import subprocess
from pathlib import Path

from imp import depgraph


def _git (cwd: Path, *args: str):
   subprocess.run ([ "git", *args ], cwd=cwd, check=True, capture_output=True)


def _make_repo (path: Path, origin_url: str | None = None):
   path.mkdir (parents=True, exist_ok=True)
   _git (path, "init", "-b", "main")
   if origin_url:
      _git (path, "remote", "add", "origin", origin_url)


def _add_workflow (repo: Path, name: str, content: str):
   wf = repo / ".github" / "workflows"
   wf.mkdir (parents=True, exist_ok=True)
   (wf / name).write_text (content)


class TestOriginSlug:

   def test_ssh_url (self, tmp_path):
      _make_repo (tmp_path, "git@github.com:katforge/hearth.git")
      assert depgraph.origin_slug (tmp_path) == ("katforge", "hearth")

   def test_https_url (self, tmp_path):
      _make_repo (tmp_path, "https://github.com/katforge/hearth.git")
      assert depgraph.origin_slug (tmp_path) == ("katforge", "hearth")

   def test_https_without_dot_git (self, tmp_path):
      _make_repo (tmp_path, "https://github.com/katforge/hearth")
      assert depgraph.origin_slug (tmp_path) == ("katforge", "hearth")

   def test_https_with_trailing_slash (self, tmp_path):
      _make_repo (tmp_path, "https://github.com/katforge/hearth/")
      assert depgraph.origin_slug (tmp_path) == ("katforge", "hearth")

   def test_lowercases_slug (self, tmp_path):
      _make_repo (tmp_path, "git@github.com:KATforge/Hearth.git")
      assert depgraph.origin_slug (tmp_path) == ("katforge", "hearth")

   def test_no_origin (self, tmp_path):
      _make_repo (tmp_path, None)
      assert depgraph.origin_slug (tmp_path) is None

   def test_not_a_repo (self, tmp_path):
      assert depgraph.origin_slug (tmp_path) is None


class TestWorkflowUses:

   def test_extracts_action_ref (self, tmp_path):
      _add_workflow (tmp_path, "ci.yml",
         "jobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n")
      assert depgraph.workflow_uses (tmp_path) == { ("actions", "checkout") }

   def test_extracts_reusable_workflow_ref (self, tmp_path):
      _add_workflow (tmp_path, "release.yml",
         "jobs:\n  ship:\n    uses: katforge/hearth/.github/workflows/release-template.yml@master\n")
      assert depgraph.workflow_uses (tmp_path) == { ("katforge", "hearth") }

   def test_combines_across_files (self, tmp_path):
      _add_workflow (tmp_path, "a.yml",
         "    - uses: actions/checkout@v4\n")
      _add_workflow (tmp_path, "b.yaml",
         "    uses: katforge/hearth/.github/workflows/x.yml@main\n")
      assert depgraph.workflow_uses (tmp_path) == {
         ("actions",  "checkout"),
         ("katforge", "hearth"),
      }

   def test_lowercases_owner_and_name (self, tmp_path):
      _add_workflow (tmp_path, "ci.yml",
         "    uses: KATforge/Hearth/.github/workflows/x.yml@master\n")
      assert depgraph.workflow_uses (tmp_path) == { ("katforge", "hearth") }

   def test_no_workflows_dir (self, tmp_path):
      assert depgraph.workflow_uses (tmp_path) == set ()

   def test_empty_workflows_dir (self, tmp_path):
      (tmp_path / ".github" / "workflows").mkdir (parents=True)
      assert depgraph.workflow_uses (tmp_path) == set ()


class TestTopoSort:

   def test_single_repo_returns_input (self, tmp_path):
      a = tmp_path / "a"
      _make_repo (a, "git@github.com:org/a.git")
      assert depgraph.topo_sort ([ a ]) == [ a ]

   def test_no_deps_preserves_order (self, tmp_path):
      a = tmp_path / "a"
      b = tmp_path / "b"
      _make_repo (a, "git@github.com:org/a.git")
      _make_repo (b, "git@github.com:org/b.git")
      assert depgraph.topo_sort ([ a, b ]) == [ a, b ]

   def test_dep_ships_first (self, tmp_path):
      a = tmp_path / "a"
      b = tmp_path / "b"
      _make_repo (a, "git@github.com:org/a.git")
      _make_repo (b, "git@github.com:org/b.git")
      _add_workflow (a, "release.yml",
         "jobs:\n  ship:\n    uses: org/b/.github/workflows/x.yml@main\n")
      assert depgraph.topo_sort ([ a, b ]) == [ b, a ]

   def test_third_party_uses_ignored (self, tmp_path):
      a = tmp_path / "a"
      b = tmp_path / "b"
      _make_repo (a, "git@github.com:org/a.git")
      _make_repo (b, "git@github.com:org/b.git")
      _add_workflow (a, "ci.yml",
         "jobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n")
      assert depgraph.topo_sort ([ a, b ]) == [ a, b ]

   def test_fan_out (self, tmp_path):
      hearth = tmp_path / "hearth"
      api    = tmp_path / "api"
      ui     = tmp_path / "ui"
      _make_repo (hearth, "git@github.com:org/hearth.git")
      _make_repo (api,    "git@github.com:org/api.git")
      _make_repo (ui,     "git@github.com:org/ui.git")
      _add_workflow (api, "release.yml",
         "jobs:\n  ship:\n    uses: org/hearth/.github/workflows/x.yml@master\n")
      _add_workflow (ui, "release.yml",
         "jobs:\n  ship:\n    uses: org/hearth/.github/workflows/x.yml@master\n")
      ordered = depgraph.topo_sort ([ api, ui, hearth ])
      assert ordered [0] == hearth
      assert set (ordered [1:]) == { api, ui }

   def test_repo_referencing_itself_is_ignored (self, tmp_path):
      a = tmp_path / "a"
      _make_repo (a, "git@github.com:org/a.git")
      _add_workflow (a, "ci.yml",
         "    uses: org/a/.github/workflows/x.yml@master\n")
      assert depgraph.topo_sort ([ a ]) == [ a ]

   def test_cycle_falls_back_to_input_order (self, tmp_path):
      a = tmp_path / "a"
      b = tmp_path / "b"
      _make_repo (a, "git@github.com:org/a.git")
      _make_repo (b, "git@github.com:org/b.git")
      _add_workflow (a, "ci.yml",
         "    uses: org/b/.github/workflows/x.yml@master\n")
      _add_workflow (b, "ci.yml",
         "    uses: org/a/.github/workflows/x.yml@master\n")
      assert depgraph.topo_sort ([ a, b ]) == [ a, b ]
