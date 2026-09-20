import pytest

from backend.ml import lead_scoring as ls


def test_a_healthy_account_has_no_training_problem():
    assert ls.training_problem(rows=500, converted=180, sales_rows=500) is None


def test_sales_without_customers_says_they_are_not_linked():
    msg = ls.training_problem(rows=0, converted=0, sales_rows=900)
    assert "linked to a customer" in msg and "customer_id" in msg


def test_too_few_linked_sales_says_how_many_are_needed():
    msg = ls.training_problem(rows=40, converted=15, sales_rows=900)
    assert "Only 40" in msg and str(ls.MIN_ROWS) in msg


@pytest.mark.parametrize("converted", [0, 3, 9, 491, 500])
def test_a_single_outcome_or_almost_one_is_refused_with_a_specific_reason(converted):
    msg = ls.training_problem(rows=500, converted=converted, sales_rows=500)
    assert "won and lost" in msg and "test-drive converted" in msg


def test_the_smallest_workable_split_is_accepted():
    assert ls.training_problem(rows=100, converted=ls.MIN_CLASS, sales_rows=100) is None


def test_status_defaults_to_not_trained_when_nothing_was_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(ls, "_model_dir", lambda: tmp_path)
    assert ls.get_lead_status() == {"state": "not_trained"}


def test_a_failed_retrain_clears_the_previous_model(tmp_path):
    for name in ls.MODEL_FILES:
        (tmp_path / f"{name}.pkl").write_bytes(b"x")
    (tmp_path / "unrelated.pkl").write_bytes(b"keep")
    ls._clear_model(tmp_path)
    assert not any((tmp_path / f"{n}.pkl").exists() for n in ls.MODEL_FILES)
    assert (tmp_path / "unrelated.pkl").exists()
