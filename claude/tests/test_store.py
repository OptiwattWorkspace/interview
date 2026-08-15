"""Task storage."""

from __future__ import annotations

from datetime import date

import pytest

from taskbot.store import DOING, DONE, OPEN, Store


def test_add_returns_task_with_id(store):
    task = store.add("buy milk", "casey")
    assert task.id == 1
    assert task.status == OPEN
    assert task.owner == "casey"
    assert task.due is None


def test_ids_increment(store):
    assert store.add("a", "casey").id == 1
    assert store.add("b", "michelle").id == 2


def test_round_trips_due_date(store):
    task = store.add("dentist", "michelle", due=date(2026, 8, 20))
    assert store.get(task.id).due == date(2026, 8, 20)


def test_get_missing_returns_none(store):
    assert store.get(99) is None


def test_list_excludes_done_by_default(store):
    store.add("a", "casey")
    done = store.add("b", "casey")
    store.set_status(done.id, DONE)

    titles = [t.title for t in store.list()]
    assert titles == ["a"]
    assert len(store.list(include_done=True)) == 2


def test_list_filters_by_owner(store):
    store.add("mine", "casey")
    store.add("hers", "michelle")
    assert [t.title for t in store.list(owner="michelle")] == ["hers"]


def test_list_sorts_by_due_with_undated_last(store):
    store.add("no date", "casey")
    store.add("later", "casey", due=date(2026, 9, 1))
    store.add("sooner", "casey", due=date(2026, 8, 1))

    assert [t.title for t in store.list()] == ["sooner", "later", "no date"]


def test_set_status_missing_returns_none(store):
    assert store.set_status(99, DONE) is None


def test_set_status_rejects_unknown(store):
    task = store.add("a", "casey")
    with pytest.raises(ValueError):
        store.set_status(task.id, "procrastinating")


def test_doing_still_listed(store):
    task = store.add("a", "casey")
    store.set_status(task.id, DOING)
    assert len(store.list()) == 1


def test_delete(store):
    task = store.add("a", "casey")
    assert store.delete(task.id) is True
    assert store.get(task.id) is None
    assert store.delete(task.id) is False


def test_state_round_trip(store):
    assert store.get_state("last_rowid") is None
    assert store.get_state("last_rowid", "0") == "0"
    store.set_state("last_rowid", "42")
    assert store.get_state("last_rowid") == "42"
    store.set_state("last_rowid", "43")
    assert store.get_state("last_rowid") == "43"


def test_persists_across_connections(tmp_path):
    path = tmp_path / "tasks.db"
    with Store(path) as s:
        s.add("survives", "casey")
    with Store(path) as s:
        assert [t.title for t in s.list()] == ["survives"]


def test_format_matches_spec(store):
    task = store.add("Pay water bill", "casey", due=date(2026, 8, 22))
    assert task.format() == "1. Pay water bill | open | Aug 22 | casey"


def test_format_without_due(store):
    task = store.add("Someday", "michelle")
    assert task.format() == "1. Someday | open | — | michelle"
