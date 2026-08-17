import pytest

from imp_git import spans, state, workspace

MANIFEST = """
schema: katforge.workspace.v1
name: demo
services:
  api:
    path: api
  web:
    path: web
    needs:
      api: "*"
  infra: {}
"""


@pytest.fixture
def demo (tmp_path, monkeypatch):
   (tmp_path / "workspace.yaml").write_text (MANIFEST)
   for name in [ "api", "web" ]:
      (tmp_path / name).mkdir ()
   monkeypatch.setenv ("XDG_STATE_HOME", str (tmp_path / "state"))
   monkeypatch.chdir (tmp_path)
   workspace.load.cache_clear ()
   yield tmp_path
   workspace.load.cache_clear ()


class TestWorkspace:

   def test_manifest_is_discovered_from_a_nested_directory (self, demo):
      nested = demo / "web"

      assert workspace.find (nested) == demo / "workspace.yaml"
      assert workspace.load (str (nested)) ["name"] == "demo"

   def test_absent_manifest_leaves_imp_a_single_repository_tool (self, tmp_path, monkeypatch):
      monkeypatch.chdir (tmp_path)
      workspace.load.cache_clear ()

      assert workspace.find (tmp_path) is None
      assert workspace.load (str (tmp_path)) is None

   def test_repositories_skip_services_without_a_checkout (self, demo):
      value = workspace.load (str (demo))

      assert sorted (workspace.repositories (value)) == [ "api", "web" ]
      assert workspace.resolve (value, "api") == str (demo / "api")

   def test_members_integrate_dependency_first (self, demo):
      value = workspace.load (str (demo))

      assert workspace.order (value, [ "web", "api" ]) == [ "api", "web" ]

   def test_unknown_repository_names_the_known_ones (self, demo):
      value = workspace.load (str (demo))

      with pytest.raises (state.StateError, match="Unknown workspace repository"):
         workspace.resolve (value, "ghost")

   def test_unsupported_schema_is_refused (self, demo):
      (demo / "workspace.yaml").write_text (
         "schema: katforge.workspace.v9\nname: demo\nservices:\n  api:\n    path: api\n"
      )
      workspace.load.cache_clear ()

      with pytest.raises (state.StateError, match="Unsupported workspace schema"):
         workspace.load (str (demo))

   def test_legacy_manifest_name_and_schema_still_load (self, demo):
      (demo / "workspace.yaml").unlink ()
      (demo / "temper.yaml").write_text (MANIFEST.replace ("katforge.workspace.v1", "temper.workspace.v1"))
      workspace.load.cache_clear ()

      assert workspace.load (str (demo)) ["name"] == "demo"

   def test_cycles_are_reported_with_their_chain (self, demo):
      (demo / "workspace.yaml").write_text (
         "schema: katforge.workspace.v1\nname: demo\nservices:\n"
         "  api:\n    path: api\n    needs:\n      web: \"*\"\n"
         "  web:\n    path: web\n    needs:\n      api: \"*\"\n"
      )
      workspace.load.cache_clear ()
      value = workspace.load (str (demo))

      with pytest.raises (state.StateError, match="dependency cycle"):
         workspace.order (value, [ "api", "web" ])


class TestSpans:

   def test_a_span_records_its_members_and_orders_them (self, demo):
      value = workspace.load (str (demo))

      span = spans.record (
         value, "checkout", { "web": str (demo / "web"), "api": str (demo / "api") }, "actor:human:anders",
      )

      assert span ["feature_id"] == "feature:checkout"
      assert spans.find (value, "checkout") ["members"] ["api"] ["repository"] == str (demo / "api")
      assert [ member ["alias"] for member in spans.members (value, span) ] == [ "api", "web" ]

   def test_forgetting_a_span_leaves_no_record (self, demo):
      value = workspace.load (str (demo))
      span = spans.record (value, "checkout", { "api": str (demo / "api") }, "actor:human:anders")

      spans.forget (value, span)

      assert spans.find (value, "checkout") is None
      assert spans.all (value) == []

   def test_entering_a_member_restores_the_previous_directory (self, demo):
      before = demo.resolve ()

      with spans.inside (str (demo / "api")):
         pass

      assert before == demo.resolve ()
