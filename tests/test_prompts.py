from imp_git import prompts


class TestCommit:

   def test_contains_diff (self):
      result = prompts.commit ("some diff content")
      assert "some diff content" in result

   def test_contains_types (self):
      result = prompts.commit ("diff")
      assert "feat" in result
      assert "fix" in result
      assert "refactor" in result

   def test_ticket_extraction (self):
      result = prompts.commit ("diff", "feat/IMP-123-add-login")
      assert "IMP-123" in result

   def test_no_ticket (self):
      result = prompts.commit ("diff", "feat/add-login")
      assert "Include ticket" not in result
