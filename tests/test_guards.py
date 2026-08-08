import json
from datetime import datetime, timedelta, timezone

from typer.testing import CliRunner

from imp_git import guards
from imp_git.main import app

runner = CliRunner ()


def test_grant_requires_provider_request (repo, monkeypatch, tmp_path):
   monkeypatch.setenv ("XDG_STATE_HOME", str (tmp_path / "state"))

   result = runner.invoke (
      app,
      [ "--actor-id", "actor:codex:thread-1", "guard", "request", "direct-edit" ],
   )

   assert result.exit_code == 1
   assert "No unique provider-approved guard request is waiting" in result.output


def test_request_creates_scoped_grant_and_revoke_removes_it (repo, monkeypatch, tmp_path):
   monkeypatch.setenv ("XDG_STATE_HOME", str (tmp_path / "state"))
   actor = "actor:codex:thread-1"
   guards.prepare (str (repo), actor, "direct-edit", provider="codex", session_id="thread-1")

   approved = runner.invoke (
      app,
      [ "--actor-id", actor, "--json", "guard", "request", "direct-edit" ],
   )

   assert approved.exit_code == 0
   grant = json.loads (approved.stdout) ["data"] ["grant"]
   assert grant ["actor_id"] == actor
   assert grant ["repository"] == str (repo)
   assert guards.active (str (repo), actor, "direct-edit") == grant

   revoked = runner.invoke (
      app,
      [ "--actor-id", actor, "--json", "guard", "revoke", "direct-edit" ],
   )

   assert revoked.exit_code == 0
   assert json.loads (revoked.stdout) ["data"] ["num_revoked"] == 1
   assert guards.active (str (repo), actor, "direct-edit") is None


def test_request_can_resolve_the_unique_pending_session (repo, monkeypatch, tmp_path):
   monkeypatch.setenv ("XDG_STATE_HOME", str (tmp_path / "state"))
   monkeypatch.delenv ("CODEX_THREAD_ID", raising=False)
   actor = "actor:codex:thread-1"
   guards.prepare (str (repo), actor, "direct-edit", provider="codex", session_id="thread-1")

   result = runner.invoke (app, [ "--json", "guard", "request", "direct-edit" ])

   assert result.exit_code == 0
   assert json.loads (result.stdout) ["data"] ["grant"] ["actor_id"] == actor


def test_expired_grant_is_removed (repo, monkeypatch, tmp_path):
   monkeypatch.setenv ("XDG_STATE_HOME", str (tmp_path / "state"))
   now = datetime (2026, 8, 7, tzinfo=timezone.utc)
   monkeypatch.setattr (guards, "_now", lambda: now)
   actor = "actor:codex:thread-1"
   guards.prepare (str (repo), actor, "direct-edit", provider="codex", session_id="thread-1")
   grant = guards.grant (str (repo), actor, "direct-edit")

   monkeypatch.setattr (guards, "_now", lambda: now + timedelta (minutes=31))

   assert guards.active (str (repo), actor, "direct-edit") is None
   assert not guards._path ("grants", str (repo), actor, "direct-edit").exists ()
   assert grant ["expires_at"] == "2026-08-07T00:30:00Z"
