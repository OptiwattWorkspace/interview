"""Command parsing and replies."""

from __future__ import annotations

from datetime import date

import pytest

from taskbot import commands
from taskbot.store import DOING, DONE

TODAY = date(2026, 8, 15)


def reply(text, store, cfg, sender="casey"):
    return commands.handle(text, sender, store, cfg, TODAY)


# -- trigger ------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "tasks",
        "what are the tasks",
        "Tasks",
        "hey can you grab milk",
        "",
        "   ",
    ],
)
def test_ignores_messages_without_trigger(text, store, cfg):
    """Ordinary conversation must never be interpreted as a command."""
    assert reply(text, store, cfg) is None


def test_bare_trigger_is_ignored(store, cfg):
    assert reply("/", store, cfg) is None


def test_custom_trigger(store, cfg):
    cfg.trigger = "@claude "
    assert reply("/tasks", store, cfg) is None
    assert reply("@claude tasks", store, cfg) is not None


# -- listing ------------------------------------------------------------


def test_empty_list(store, cfg):
    assert reply("/tasks", store, cfg) == "No open tasks. Nice."


def test_lists_in_spec_format(store, cfg):
    store.add("Pay water bill", "casey", due=date(2026, 8, 22))
    assert reply("/tasks", store, cfg) == "1. Pay water bill | open | Aug 22 | casey"


def test_lists_both_owners(store, cfg):
    store.add("mine", "casey")
    store.add("hers", "michelle")
    out = reply("/tasks", store, cfg)
    assert "mine" in out and "hers" in out


def test_tasks_mine_filters_to_sender(store, cfg):
    store.add("mine", "casey")
    store.add("hers", "michelle")
    out = reply("/tasks mine", store, cfg, sender="michelle")
    assert "hers" in out and "mine" not in out


def test_tasks_by_owner_name(store, cfg):
    store.add("mine", "casey")
    store.add("hers", "michelle")
    out = reply("/tasks michelle", store, cfg)
    assert "hers" in out and "mine" not in out


def test_tasks_owner_name_is_case_insensitive(store, cfg):
    store.add("hers", "michelle")
    assert "hers" in reply("/tasks MICHELLE", store, cfg)


def test_unknown_owner_is_explained(store, cfg):
    out = reply("/tasks dave", store, cfg)
    assert "Don't know who 'dave' is" in out
    assert "casey" in out and "michelle" in out


def test_done_hidden_by_default_and_shown_with_all(store, cfg):
    task = store.add("finished", "casey")
    store.set_status(task.id, DONE)
    assert "finished" not in reply("/tasks", store, cfg)
    assert "finished" in reply("/tasks all", store, cfg)


def test_list_aliases(store, cfg):
    store.add("a", "casey")
    for alias in ("/tasks", "/task", "/list", "/ls"):
        assert "a" in reply(alias, store, cfg)


# -- adding -------------------------------------------------------------


def test_add_defaults_to_sender_and_open(store, cfg):
    out = reply("/add take out the trash", store, cfg, sender="michelle")
    assert out == "Added — 1. take out the trash | open | — | michelle"


def test_add_with_owner(store, cfg):
    reply("/add buy milk for michelle", store, cfg)
    task = store.get(1)
    assert task.owner == "michelle"
    assert task.title == "buy milk"


def test_add_with_possessive_owner(store, cfg):
    reply("/add dentist for michelle's", store, cfg)
    assert store.get(1).owner == "michelle"


def test_add_with_due_date(store, cfg):
    reply("/add call the vet by friday", store, cfg)
    task = store.get(1)
    assert task.title == "call the vet"
    assert task.due == date(2026, 8, 21)


def test_add_with_owner_and_due(store, cfg):
    reply("/add pick up dry cleaning for michelle by friday", store, cfg)
    task = store.get(1)
    assert task.title == "pick up dry cleaning"
    assert task.owner == "michelle"
    assert task.due == date(2026, 8, 21)


def test_add_with_due_before_owner(store, cfg):
    reply("/add pick up dry cleaning by friday for michelle", store, cfg)
    task = store.get(1)
    assert task.title == "pick up dry cleaning"
    assert task.owner == "michelle"
    assert task.due == date(2026, 8, 21)


def test_add_with_bare_trailing_date(store, cfg):
    reply("/add call the vet tomorrow", store, cfg)
    task = store.get(1)
    assert task.title == "call the vet"
    assert task.due == date(2026, 8, 16)


def test_add_keeps_words_that_only_look_like_dates(store, cfg):
    """'on sale' is not a date, so the words stay in the title."""
    reply("/add buy the couch on sale", store, cfg)
    assert store.get(1).title == "buy the couch on sale"
    assert store.get(1).due is None


def test_add_without_text_prompts(store, cfg):
    out = reply("/add", store, cfg)
    assert "What's the task?" in out


def test_add_that_is_only_a_date_is_rejected(store, cfg):
    out = reply("/add by friday", store, cfg)
    assert "all date and no task" in out
    assert store.list() == []


def test_add_alias(store, cfg):
    reply("/new water the plants", store, cfg)
    assert store.get(1).title == "water the plants"


# -- status -------------------------------------------------------------


def test_done(store, cfg):
    store.add("buy milk", "casey")
    assert reply("/done 1", store, cfg) == "Done — buy milk ✓"
    assert store.get(1).status == DONE


def test_done_accepts_hash_prefix(store, cfg):
    store.add("buy milk", "casey")
    reply("/done #1", store, cfg)
    assert store.get(1).status == DONE


def test_doing(store, cfg):
    store.add("paint the fence", "casey")
    assert "doing" in reply("/doing 1", store, cfg)
    assert store.get(1).status == DOING


def test_reopen(store, cfg):
    task = store.add("a", "casey")
    store.set_status(task.id, DONE)
    reply("/open 1", store, cfg)
    assert store.get(1).status == "open"


def test_status_on_missing_task(store, cfg):
    assert reply("/done 7", store, cfg) == "No task 7."


def test_status_without_id_prompts(store, cfg):
    assert "Which one?" in reply("/done", store, cfg)


# -- deleting -----------------------------------------------------------


def test_drop(store, cfg):
    store.add("mistake", "casey")
    assert reply("/drop 1", store, cfg) == "Deleted — mistake"
    assert store.get(1) is None


def test_drop_missing(store, cfg):
    assert reply("/drop 4", store, cfg) == "No task 4."


# -- misc ---------------------------------------------------------------


def test_help_lists_commands(store, cfg):
    out = reply("/help", store, cfg)
    assert "/tasks" in out and "/add" in out and "/done" in out


def test_unknown_command_points_at_help(store, cfg):
    out = reply("/frobnicate", store, cfg)
    assert "Don't know 'frobnicate'" in out
    assert "/help" in out


def test_full_conversation(store, cfg):
    """The flow from the original spec, end to end."""
    reply("/add Book dentist for michelle by aug 20", store, cfg)
    reply("/add Fix garage door by aug 18", store, cfg)
    reply("/add Pay water bill by aug 22", store, cfg)
    reply("/doing 2", store, cfg)

    assert reply("/tasks", store, cfg) == (
        "2. Fix garage door | doing | Aug 18 | casey\n"
        "1. Book dentist | open | Aug 20 | michelle\n"
        "3. Pay water bill | open | Aug 22 | casey"
    )

    reply("/done 3", store, cfg)
    assert "Pay water bill" not in reply("/tasks", store, cfg)
