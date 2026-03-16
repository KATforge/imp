from imp import prompts


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


class TestReview:

   def test_contains_diff (self):
      result = prompts.review ("some diff")
      assert "some diff" in result

   def test_contains_checks (self):
      result = prompts.review ("diff")
      assert "Bugs" in result
      assert "Security" in result


class TestBranchName:

   def test_contains_description (self):
      result = prompts.branch_name ("add user auth")
      assert "add user auth" in result

   def test_contains_format (self):
      result = prompts.branch_name ("desc")
      assert "type/short-name" in result


class TestRevert:

   def test_contains_original (self):
      result = prompts.revert ("feat: add login", "some diff")
      assert "feat: add login" in result
      assert "some diff" in result

   def test_contains_revert (self):
      result = prompts.revert ("msg", "diff")
      assert "Revert" in result


class TestFix:

   def test_contains_title (self):
      result = prompts.fix ("Bug in auth", "Details here")
      assert "Bug in auth" in result
      assert "Details here" in result

   def test_fix_format (self):
      result = prompts.fix ("title", "body")
      assert "fix/" in result


class TestPr:

   def test_contains_branch (self):
      result = prompts.pr ("feat/login", "abc123 feat: add login", "diff")
      assert "feat/login" in result
      assert "abc123" in result

   def test_contains_format (self):
      result = prompts.pr ("branch", "log", "diff")
      assert "TITLE:" in result
      assert "DESCRIPTION:" in result


class TestSplit:

   def test_contains_diffs (self):
      result = prompts.split ("--- file.py ---\n+code", "main")
      assert "file.py" in result

   def test_json_format (self):
      result = prompts.split ("diffs", "main")
      assert "JSON array" in result

   def test_ticket_extraction (self):
      result = prompts.split ("diffs", "feat/IMP-123-work")
      assert "IMP-123" in result
