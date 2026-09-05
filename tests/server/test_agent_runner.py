from __future__ import annotations

from server import agent_runner
from server.run_types import READ_ONLY, execution_spec


def test_every_read_only_run_has_an_explicit_restricted_profile():
    for run_type in READ_ONLY:
        skill, toolsets = execution_spec(run_type)
        assert skill
        assert toolsets is not None
        assert set(toolsets) <= {"web", "read_only_files"}


def test_send_and_agentless_runs_cannot_use_the_headless_runner():
    for run_type in ("analytics_refresh", "email_send", "whatsapp_send"):
        try:
            execution_spec(run_type)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{run_type} unexpectedly received an agent profile")


def test_runner_derives_skill_and_tools_from_run_type(monkeypatch):
    captured = {}

    def fake_run_oneshot(prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(agent_runner, "run_oneshot", fake_run_oneshot)

    assert agent_runner.main([
        "--run-type", "lead_scan",
        "--prompt", "find buyers",
        "--skill", "lead-discovery",
        "--model", "provider/model",
    ]) == 0
    assert captured == {
        "prompt": "find buyers",
        "model": "provider/model",
        "skills": ["lead-discovery"],
        "toolsets": ["web"],
    }


def test_executor_command_uses_the_product_runner():
    assert agent_runner.build_command(
        "lead_research",
        "research Acme",
        skill="lead-research",
        model="provider/model",
    ) == [
        "interfaze-agent-run",
        "--run-type", "lead_research",
        "--prompt", "research Acme",
        "--skill", "lead-research",
        "--model", "provider/model",
    ]


def test_runner_rejects_a_skill_not_allowed_for_the_run_type():
    try:
        execution_spec("lead_scan", "cold-email-outreach")
    except ValueError as exc:
        assert "not allowed" in str(exc)
    else:
        raise AssertionError("runner accepted an unrelated skill")
