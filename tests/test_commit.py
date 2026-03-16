from imp.ai import sanitize


class TestSanitize:

   def test_strips_newlines (self):
      assert sanitize ("hello\nworld\n") == "helloworld"

   def test_strips_whitespace (self):
      assert sanitize ("  hello  ") == "hello"

   def test_mixed (self):
      assert sanitize ("\n  feat/branch  \n") == "feat/branch"
