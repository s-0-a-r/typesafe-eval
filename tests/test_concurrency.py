import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator


def test_cli_concurrency_ordering(tmp_path: Path):
    """Verifies that concurrent evaluation preserves document order."""
    doc_paths = []
    for i in range(8):
        doc = tmp_path / f"doc_{i:02d}.md"
        doc.write_text(f"# Document {i}\nContent for document {i}.", encoding="utf-8")
        doc_paths.append(str(doc))

    runner = CliRunner()

    # Sequential execution (-j 1)
    res_seq = runner.invoke(main, [*doc_paths, "-j", "1", "--dry-run", "-f", "json"])
    assert res_seq.exit_code == 0
    data_seq = json.loads(res_seq.output)

    # Concurrent execution (-j 4)
    res_conc = runner.invoke(main, [*doc_paths, "-j", "4", "--dry-run", "-f", "json"])
    assert res_conc.exit_code == 0
    data_conc = json.loads(res_conc.output)

    assert len(data_seq) == 8
    assert len(data_conc) == 8

    # Compare filenames in exact order
    seq_names = [d["filename"] for d in data_seq]
    conc_names = [d["filename"] for d in data_conc]
    assert seq_names == conc_names
    assert seq_names == [f"doc_{i:02d}.md" for i in range(8)]


def test_evaluator_client_thread_safety(monkeypatch):
    """Verifies that _get_client is thread-safe and creates only one client instance."""
    evaluator = TypeSafeEvaluator(api_key="test-api-key")

    mock_client_cls = MagicMock()
    mock_instance = MagicMock()
    mock_client_cls.return_value = mock_instance
    monkeypatch.setattr("typesafe_eval.client.TypeSafeClient", mock_client_cls)

    def worker(_):
        return evaluator._get_client()

    with ThreadPoolExecutor(max_workers=8) as pool:
        clients = list(pool.map(worker, range(20)))

    # All returned clients must be the exact same instance
    assert all(c is mock_instance for c in clients)
    # Constructor should only be called once
    assert mock_client_cls.call_count == 1


def test_cli_concurrency_partial_error(tmp_path: Path, monkeypatch):
    """Verifies that an error in one file does not halt evaluation of remaining files."""
    doc_paths = []
    for i in range(4):
        doc = tmp_path / f"doc_{i}.md"
        doc.write_text(f"# Doc {i}", encoding="utf-8")
        doc_paths.append(str(doc))

    orig_eval = TypeSafeEvaluator.evaluate_document

    def mock_eval(self, filepath, *args, **kwargs):
        if "doc_2.md" in filepath:
            raise RuntimeError("Simulated transient network failure on doc 2")
        return orig_eval(self, filepath, *args, **kwargs)

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)

    runner = CliRunner()
    result = runner.invoke(main, [*doc_paths, "-j", "2", "--dry-run", "-f", "json"])

    # File error without violations returns exit code 3
    assert result.exit_code == 3
    assert "Simulated transient network failure on doc 2" in result.stderr
    data = json.loads(result.stdout)
    # The 3 successful documents should be in results
    assert len(data) == 3
    filenames = {d["filename"] for d in data}
    assert filenames == {"doc_0.md", "doc_1.md", "doc_3.md"}
