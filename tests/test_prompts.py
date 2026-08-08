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

   def test_whisper (self):
      result = prompts.commit ("diff", whisper="use IMP-99999")
      assert "User hint: use IMP-99999" in result

   def test_no_whisper (self):
      result = prompts.commit ("diff")
      assert "User hint" not in result


class TestReview:

   def test_contains_diff (self):
      result = prompts.review ("some diff")
      assert "some diff" in result

   def test_contains_checks (self):
      result = prompts.review ("diff")
      assert "Bugs" in result
      assert "Security" in result

   def test_whisper (self):
      result = prompts.review ("diff", whisper="focus on SQL injection")
      assert "User hint: focus on SQL injection" in result
