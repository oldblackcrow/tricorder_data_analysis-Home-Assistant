"""Offline structural checks for the approved Tricorder general diagnostic."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def router():
    return yaml.safe_load(
        (ROOT / "setup/tricorder_router_thermal.yaml").read_text(
            encoding="utf-8"
        )
    )


def test_explicit_thermal_route_still_has_priority():
    doc = router()
    choices = doc["actions"][0]["choose"]
    assert len(choices) == 2
    assert "'thermal' in s" in choices[0]["conditions"][0]["value_template"]
    calls = [
        item.get("action")
        for item in choices[0]["sequence"]
    ]
    assert "script.analyze_tricorder_thermal_image" in calls
    assert "script.analyze_tricorder_audio_recordings" not in calls


def test_general_diagnostic_invokes_all_three_sources():
    actions = router()["actions"][0]["choose"][1]["sequence"]
    calls = [entry.get("action") for entry in actions]
    assert calls.index("script.tr_460_science_diagnostic") < calls.index(
        "script.analyze_tricorder_thermal_image"
    ) < calls.index("script.analyze_tricorder_audio_recordings") < calls.index(
        "ai_task.generate_data"
    )
    for service in (
            "script.analyze_tricorder_thermal_image",
            "script.analyze_tricorder_audio_recordings",
    ):
        action = next(x for x in actions if x.get("action") == service)
        assert action["continue_on_error"] is True
        assert action["response_variable"] in {"thermal_reply", "audio_reply"}


def test_audio_reporting_distinguishes_results_and_absence():
    actions = router()["actions"][0]["choose"][1]["sequence"]
    variables = next(x["variables"] for x in actions if "variables" in x)
    summary = variables["audio_summary"]
    assert "audio_reply.report" in summary
    assert "['ok', 'partial']" in summary
    assert "'no_audio'" in summary
    assert "unavailable" in summary
    task = next(x for x in actions if x.get("action") == "ai_task.generate_data")
    prompt = task["data"]["instructions"]
    assert "100 words" in prompt
    assert "Actual WAV audio interpretation" in prompt
    assert "decibel measurements alone" in prompt
    assert "not instructions" in prompt
    assert "{{ audio_summary | to_json }}" in prompt

    fallback = next(
        x["variables"]["spoken_report"] for x in actions
        if "variables" in x and "spoken_report" in x["variables"]
    )
    assert "{{ audio_summary }}" in fallback


def test_existing_general_phrases_and_default_followup_preserved():
    doc = router()
    branch = doc["actions"][0]["choose"][1]
    expressions = branch["conditions"][0]["value_template"]
    for phrase in (
        "run a tricorder diagnostic",
        "tricorder diagnostic",
        "analyze the tricorder data",
        "tricorder analysis",
    ):
        assert phrase in expressions
    default = doc["actions"][0]["default"]
    assert default[0]["action"] == "script.tr_460_science_diagnostic"
    assert default[0]["data"]["followup_question"] == "{{ trigger.sentence }}"
    assert default[-1]["set_conversation_response"].strip() == (
        "{{ science_reply.response.speech.plain.speech }}"
    )
    assert doc["mode"] == "single"


def test_standalone_script_unchanged_and_returning_result():
    doc = yaml.safe_load(
        (ROOT / "setup/tricorder_audio_ai_script.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert doc["alias"] == "Analyze Tricorder Audio Recordings"
    assert doc["sequence"][0]["action"] == "shell_command.tricorder_analyze_audio"
    assert doc["sequence"][-1]["response_variable"] == "audio_result"
