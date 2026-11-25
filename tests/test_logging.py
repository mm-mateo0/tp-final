"""Pruebas del formato JSON y la rotación gzip."""
import gzip
import json
import pytest
from fenix.utils.logging_json import setup


@pytest.mark.base
def test_all_log_levels_are_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger, listener = setup("levels")
    try:
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.critical("critical")
    finally:
        listener.stop()
    rows = [json.loads(line) for line in (tmp_path / "logs").glob("*.jsonl")
            for line in line.read_text(encoding="utf-8").splitlines()]
    assert {row["level"] for row in rows} == {
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@pytest.mark.base
def test_rotation_creates_readable_gzip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger, listener = setup("rotate", max_bytes=180)
    try:
        for number in range(12):
            logger.info("registro de prueba numero %s", number,
                        extra={"event_id": f"evt-{number:03d}"})
    finally:
        listener.stop()
    archives = list((tmp_path / "logs").glob("*.gz"))
    assert archives, "No se generó el histórico gzip"
    with gzip.open(archives[0], "rt", encoding="utf-8") as stream:
        archived = [json.loads(line) for line in stream]
    assert archived
    assert all(row["timestamp"].endswith("+00:00") for row in archived)
