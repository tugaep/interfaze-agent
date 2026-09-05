from __future__ import annotations

import pytest

from hermes_cli import oneshot


def test_run_oneshot_forwards_preloaded_skills(monkeypatch, capsys):
    captured = {}

    def fake_run_agent(prompt, **kwargs):
        captured.update(kwargs)
        return '{"ok": true}', {"failed": False}

    monkeypatch.setattr(oneshot, "_run_agent", fake_run_agent)

    assert oneshot.run_oneshot("research Acme", skills=["lead-research"]) == 0
    assert captured["skills"] == ["lead-research"]
    assert capsys.readouterr().out == '{"ok": true}\n'


def test_preloaded_skill_prompt_rejects_an_entirely_missing_set(monkeypatch):
    monkeypatch.setattr(
        "agent.skill_commands.build_preloaded_skills_prompt",
        lambda identifiers: ("", [], list(identifiers)),
    )

    with pytest.raises(ValueError, match="Unknown skill.*missing-skill"):
        oneshot._build_preloaded_skills_prompt(["missing-skill"])


def test_preloaded_skill_prompt_keeps_valid_skills_when_one_is_missing(monkeypatch):
    monkeypatch.setattr(
        "agent.skill_commands.build_preloaded_skills_prompt",
        lambda identifiers: ("ACTIVE SKILL", ["lead-research"], ["missing-skill"]),
    )

    assert oneshot._build_preloaded_skills_prompt(
        ["lead-research", "missing-skill"]
    ) == "ACTIVE SKILL"


def test_explicit_empty_toolset_list_does_not_fall_back_to_config():
    assert oneshot._normalize_toolsets([]) == []


def test_run_agent_injects_skill_prompt_and_preserves_no_tools(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_conversation(self, prompt):
            captured["prompt"] = prompt
            return {"final_response": "done"}

    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {"model": {}})
    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda **kwargs: {
            "api_key": None,
            "base_url": None,
            "provider": "test",
            "api_mode": "chat_completions",
            "credential_pool": None,
        },
    )
    monkeypatch.setattr("run_agent.AIAgent", FakeAgent)
    monkeypatch.setattr(oneshot, "_create_session_db_for_oneshot", lambda: None)
    monkeypatch.setattr(oneshot, "get_fallback_chain", lambda config: [])
    monkeypatch.setattr(
        oneshot,
        "_build_preloaded_skills_prompt",
        lambda skills: "ACTIVE LEAD RESEARCH SKILL",
    )

    response, _ = oneshot._run_agent(
        "research Acme",
        toolsets=[],
        use_config_toolsets=False,
        skills=["lead-research"],
    )

    assert response == "done"
    assert captured["enabled_toolsets"] == []
    assert captured["ephemeral_system_prompt"] == "ACTIVE LEAD RESEARCH SKILL"
    assert captured["prompt"] == "research Acme"
