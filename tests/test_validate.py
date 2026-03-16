from imp import validate


class TestCommit:

   def test_valid_feat (self):
      assert validate.commit ("feat: add login page")

   def test_valid_fix (self):
      assert validate.commit ("fix: resolve null pointer")

   def test_valid_scoped (self):
      assert validate.commit ("refactor(auth): simplify token flow")

   def test_valid_ticket (self):
      assert validate.commit ("build: IMP-123 update deploy script")

   def test_valid_breaking (self):
      assert validate.commit ("chore!: drop node 14 support")

   def test_reject_plain (self):
      assert not validate.commit ("Add login page")

   def test_reject_uppercase_type (self):
      assert not validate.commit ("FEAT: uppercase type")

   def test_reject_empty_desc (self):
      assert not validate.commit ("feat:")

   def test_reject_no_space (self):
      assert not validate.commit ("feat:missing space")

   def test_reject_uppercase_desc (self):
      assert not validate.commit ("feat: Uppercase description")


class TestBranch:

   def test_valid_simple (self):
      assert validate.branch ("main")

   def test_valid_feature (self):
      assert validate.branch ("feat/my-feature")

   def test_valid_fix (self):
      assert validate.branch ("fix/bug-123")

   def test_valid_release (self):
      assert validate.branch ("release/1.0.0")

   def test_reject_spaces (self):
      assert not validate.branch ("feat/my feature")

   def test_reject_semicolons (self):
      assert not validate.branch ("feat;rm -rf")

   def test_reject_leading_dash (self):
      assert not validate.branch ("-delete")
