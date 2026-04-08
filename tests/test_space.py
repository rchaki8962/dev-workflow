import pytest
from dev_workflow.space import validate_space_name

class TestValidateSpaceName:
    def test_valid_simple(self):
        validate_space_name("personal")  # no error

    def test_valid_with_hyphens(self):
        validate_space_name("harness-eng")

    def test_valid_with_numbers(self):
        validate_space_name("team-42")

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_space_name("Personal")

    def test_rejects_leading_hyphen(self):
        with pytest.raises(ValueError):
            validate_space_name("-bad")

    def test_rejects_trailing_hyphen(self):
        with pytest.raises(ValueError):
            validate_space_name("bad-")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError):
            validate_space_name("my_space")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_space_name("")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="40"):
            validate_space_name("a" * 41)


from dev_workflow.space import SpaceManager
from dev_workflow.exceptions import SpaceNotFoundError

class TestSpaceCreate:
    def test_creates_space(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        space = mgr.create("personal", "Personal projects")
        assert space.name == "personal"
        assert space.description == "Personal projects"
        assert (tmp_path / "personal" / "state").is_dir()
        assert (tmp_path / "personal" / "tasks").is_dir()

    def test_creates_registry_file(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("personal")
        assert (tmp_path / "spaces.json").exists()

    def test_rejects_duplicate(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("personal")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create("personal")

    def test_rejects_invalid_name(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        with pytest.raises(ValueError):
            mgr.create("Invalid")

class TestSpaceListAll:
    def test_empty(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        assert mgr.list_all() == []

    def test_sorted_by_name(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("zebra")
        mgr.create("alpha")
        names = [s.name for s in mgr.list_all()]
        assert names == ["alpha", "zebra"]

class TestSpaceGet:
    def test_get_existing(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("personal", "My stuff")
        space = mgr.get("personal")
        assert space.name == "personal"
        assert space.description == "My stuff"

    def test_get_nonexistent(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        with pytest.raises(SpaceNotFoundError):
            mgr.get("ghost")

class TestSpaceRemove:
    def test_removes_empty_space(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("temp")
        mgr.remove("temp")
        assert not mgr.exists("temp")
        assert not (tmp_path / "temp").exists()

    def test_refuses_nonempty_without_force(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("busy")
        (tmp_path / "busy" / "state").mkdir(parents=True, exist_ok=True)
        (tmp_path / "busy" / "state" / "some-task.json").write_text("{}")
        with pytest.raises(ValueError, match="has tasks"):
            mgr.remove("busy")

    def test_removes_nonempty_with_force(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("busy")
        (tmp_path / "busy" / "state" / "some-task.json").write_text("{}")
        mgr.remove("busy", force=True)
        assert not mgr.exists("busy")

    def test_remove_nonexistent(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        with pytest.raises(SpaceNotFoundError):
            mgr.remove("ghost")

class TestSpaceExists:
    def test_exists_true(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("present")
        assert mgr.exists("present") is True

    def test_exists_false(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        assert mgr.exists("absent") is False

class TestSpaceEnsure:
    def test_creates_if_missing(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        space = mgr.ensure("harness")
        assert space.name == "harness"
        assert mgr.exists("harness")

    def test_returns_existing(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.create("harness", "Original description")
        space = mgr.ensure("harness")
        assert space.description == "Original description"

    def test_auto_creates_spaces_json(self, tmp_path):
        mgr = SpaceManager(tmp_path)
        mgr.ensure("harness")
        assert (tmp_path / "spaces.json").exists()
