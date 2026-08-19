from imp_git import state


class TestState:

   def test_temporary_paths_never_collide_with_repositories (self, repo):
      value = state.temporary ("test-")

      assert not value.exists ()
      assert repo not in value.parents

   def test_stamp_is_refname_safe (self):
      value = state.stamp ()

      assert ":" not in value
      assert " " not in value
      assert value.endswith ("Z")
