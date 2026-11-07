"""Tests for `src.utils.paths` data-directory resolution."""

import os
import subprocess
import sys
from pathlib import Path

from src.utils import paths


class TestResolvePath:
    def test_missing_value_uses_default(self):
        default = paths.PROJECT_ROOT / "data"
        assert paths._resolve_path(None, default) == default

    def test_empty_and_whitespace_use_default(self):
        default = paths.PROJECT_ROOT / "data"
        assert paths._resolve_path("", default) == default
        assert paths._resolve_path("   ", default) == default

    def test_absolute_path_is_used_as_is(self, tmp_path):
        resolved = paths._resolve_path(str(tmp_path), paths.PROJECT_ROOT / "data")
        assert resolved == tmp_path

    def test_relative_path_resolves_against_project_root(self):
        resolved = paths._resolve_path("scratch/data", paths.PROJECT_ROOT / "data")
        assert resolved == paths.PROJECT_ROOT / "scratch" / "data"

    def test_tilde_is_expanded(self):
        resolved = paths._resolve_path("~/lumina-data", paths.PROJECT_ROOT / "data")
        assert resolved == Path.home() / "lumina-data"

    def test_surrounding_whitespace_is_stripped(self, tmp_path):
        resolved = paths._resolve_path(f"  {tmp_path}  ", paths.PROJECT_ROOT / "data")
        assert resolved == tmp_path


class TestEnsureDirectories:
    def test_creates_configured_directories(self, monkeypatch, tmp_path):
        monkeypatch.setattr(paths, "BRONZE_DIR", tmp_path / "bronze")
        monkeypatch.setattr(paths, "SILVER_DIR", tmp_path / "silver")
        monkeypatch.setattr(paths, "GOLD_DIR", tmp_path / "gold")
        monkeypatch.setattr(paths, "QUARANTINE_DIR", tmp_path / "quarantine")
        monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state" / "ingestion_state.json")

        paths.ensure_directories()

        for name in ("bronze", "silver", "gold", "quarantine", "state"):
            assert (tmp_path / name).is_dir()


class TestStateFileResolution:
    def test_default_state_file_is_unchanged(self):
        default = paths.PROJECT_ROOT / "configs" / "ingestion_state.json"
        assert paths._resolve_path(None, default) == default
        assert paths._resolve_path("", default) == default
        assert paths._resolve_path("   ", default) == default

    def test_absolute_state_file_is_used_as_is(self, tmp_path):
        default = paths.PROJECT_ROOT / "configs" / "ingestion_state.json"
        target = tmp_path / "ingestion_state.json"
        assert paths._resolve_path(str(target), default) == target

    def test_relative_state_file_resolves_against_project_root(self):
        default = paths.PROJECT_ROOT / "configs" / "ingestion_state.json"
        resolved = paths._resolve_path("scratch/ingestion_state.json", default)
        assert resolved == paths.PROJECT_ROOT / "scratch" / "ingestion_state.json"


class TestEnvVarPropagation:
    def test_consumers_read_lumina_data_dir(self, tmp_path):
        env = os.environ.copy()
        env["LUMINA_DATA_DIR"] = str(tmp_path)
        env["PYTHONPATH"] = str(paths.PROJECT_ROOT)

        code = (
            "from src.utils.api_data_loader import GOLD_DIR\n"
            "from src.transformation.silver import BRONZE_DIR\n"
            "print(GOLD_DIR)\n"
            "print(BRONZE_DIR)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            cwd=paths.PROJECT_ROOT,
        )

        gold_dir, bronze_dir = (Path(line) for line in result.stdout.strip().splitlines())
        assert gold_dir == tmp_path / "gold"
        assert bronze_dir == tmp_path / "bronze"

    def test_state_file_honours_lumina_state_file(self, tmp_path):
        env = os.environ.copy()
        env["LUMINA_DATA_DIR"] = str(tmp_path / "data")
        env["LUMINA_STATE_FILE"] = str(tmp_path / "state" / "ingestion_state.json")
        env["PYTHONPATH"] = str(paths.PROJECT_ROOT)

        code = (
            "from src.utils.paths import GOLD_DIR, STATE_FILE\n"
            "from scripts.run_bronze_ingestion import STATE_FILE as INGEST_STATE_FILE\n"
            "print(GOLD_DIR)\n"
            "print(STATE_FILE)\n"
            "print(INGEST_STATE_FILE)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            cwd=paths.PROJECT_ROOT,
        )

        gold_dir, state_file, ingest_state_file = (
            Path(line) for line in result.stdout.strip().splitlines()
        )
        assert gold_dir == tmp_path / "data" / "gold"
        assert state_file == tmp_path / "state" / "ingestion_state.json"
        assert ingest_state_file == tmp_path / "state" / "ingestion_state.json"

