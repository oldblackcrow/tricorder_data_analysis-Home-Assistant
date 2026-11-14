"""Offline, no-network tests for the mission WAV sound analyzer."""
import io
import importlib.util
import json
import wave
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tricorder_audio_ai", ROOT / "tricorder" / "tricorder_audio_ai.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def wav_bytes(seconds=2):
    target = io.BytesIO()
    with wave.open(target, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * (8000 * seconds))
    return target.getvalue()


@pytest.fixture()
def archive(tmp_path, monkeypatch):
    media = tmp_path / "media"
    meta = tmp_path / "recordings"
    media.mkdir()
    meta.mkdir()
    source = tmp_path / "archive.jsonl"
    records = []
    for i in range(1, 4):
        name = f"audio_{i:08d}.wav"
        (media / name).write_bytes(wav_bytes(i + 1))
        (meta / name.replace(".wav", ".json")).write_text(
            json.dumps({"record_type": "audio_recording", "file": name}))
        records.append({"record_type": "audio_recording_begin",
                        "mission_file": "mission-A", "mission_code": "A",
                        "time": f"2026-11-14T00:00:0{i}", "file": name})
    records += [
        {"record_type": "audio_recording_begin",
         "mission_file": "mission-B", "file": "audio_00000001.wav"},
        {"record_type": "audio_recording_begin",
         "mission_file": "mission-A", "file": "../../other.wav"},
        {"record_type": "audio_recording_chunk",
         "mission_file": "mission-A", "file": "audio_00000002.wav"},
    ]
    source.write_text("\n".join(json.dumps(rec) for rec in records))
    monkeypatch.setattr(module, "ARCHIVE", source)
    monkeypatch.setattr(module, "MEDIA_DIR", media)
    monkeypatch.setattr(module, "META_DIR", meta)
    monkeypatch.setattr(module, "CACHE", tmp_path / "cache.json")
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    return source


def test_file_selection_and_cache_no_duplicate_api_billing(archive, monkeypatch):
    calls = []
    def fake_interpret(data, api_key):
        calls.append((len(data), api_key))
        return "A low mechanical humming sound, possibly ventilation."
    monkeypatch.setattr(module, "interpret", fake_interpret)
    initial = module.analyze("mission-A")
    assert initial["status"] == "partial"
    assert initial["total"] == 3 and initial["analyzed"] == 2
    assert initial["remaining"] == 1 and initial["newly_analyzed"] == 2
    assert len(calls) == 2
    assert module.CACHE.exists()

    again = module.analyze("mission-A")
    assert again["status"] == "ok"
    assert again["total"] == 3 and again["analyzed"] == 3
    assert again["remaining"] == 0 and again["newly_analyzed"] == 1
    assert len(calls) == 3

    cached = module.analyze("mission-A")
    assert cached["status"] == "ok"
    assert cached["newly_analyzed"] == 0
    assert all(x["cached"] for x in cached["recordings"])
    assert len(calls) == 3

    assert module.analyze("mission-C")["status"] == "no_audio"


def test_request_is_real_wav_audio_text_only(archive, monkeypatch):
    request_seen = {}
    class FakeResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps({"choices": [
                {"message": {"content": "Several sharp taps, possibly footsteps."}}
            ]}).encode("utf-8"))
        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=0):
        request_seen["payload"] = json.loads(request.data)
        request_seen["timeout"] = timeout
        assert request.get_header("Authorization") == "Bearer not-a-real-key"
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    sound, _ = module.read_wav(module.MEDIA_DIR / "audio_00000001.wav")
    description = module.interpret(sound, "not-a-real-key")
    assert "sharp taps" in description
    payload = request_seen["payload"]
    assert payload["model"] == "gpt-audio-1.5"
    assert payload["modalities"] == ["text"]
    assert payload["store"] is False
    import base64
    assert payload["messages"][0]["role"] == "system"
    assert "Do not output JSON" in payload["messages"][0]["content"]
    assert payload["messages"][1]["role"] == "user"
    assert base64.b64decode(
        payload["messages"][1]["content"][1]["input_audio"]["data"]) == sound
    assert request_seen["timeout"] == module.API_TIMEOUT_S


def test_missing_key_fails_closed_and_invalid_file_ignored(archive, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setattr(module, "KEY_FILE", module.CACHE.parent / "no-key-file")
    failed = module.analyze("mission-A")
    assert failed["status"] == "error"
    assert "key file is missing" in failed["report"]
    assert not module.CACHE.exists()

    (module.MEDIA_DIR / "audio_00000001.wav").write_bytes(b"not-a-wav")
    files = module.mission_files("mission-A")
    assert len(files) == 3
    with pytest.raises((ValueError, wave.Error, EOFError)):
        module.read_wav(files[0]["path"])


def test_installer_yaml_is_parseable():
    for name in ("setup/tricorder_audio_ai_script.yaml",
                 "setup/tricorder_audio_ai_shell_command.yaml"):
        assert isinstance(yaml.safe_load((ROOT / name).read_text()), dict)


def test_status_only_api_response_rejected_and_not_cached(archive, monkeypatch):
    """Regression: {"analyzable_audio": true} must never count as analyzed."""
    requests = []
    def fake_interpret(data, api_key):
        requests.append(True)
        if len(requests) == 1:
            return '{"analyzable_audio": true}'
        return "A repeated mechanical tapping sound, possibly a loose fan."

    monkeypatch.setattr(module, "interpret", fake_interpret)
    rejected = module.analyze("mission-A")
    assert rejected["status"] == "error"
    assert rejected["analyzed"] == 0
    assert rejected["newly_analyzed"] == 0
    assert "status" in rejected["report"] or "structured" in rejected["report"]
    assert not module.CACHE.exists()

    retry = module.analyze("mission-A")
    assert retry["status"] == "partial"
    assert retry["analyzed"] == 2
    assert retry["newly_analyzed"] == 2
    assert len(requests) == 3
    assert "mechanical tapping" in retry["report"]


def test_invalid_legacy_cached_status_auto_evicted_only(archive, monkeypatch):
    """Drop one legacy false-positive entry without deleting other cached results."""
    data, _ = module.read_wav(module.MEDIA_DIR / "audio_00000001.wav")
    legacy_key = module.cache_key(data, module.LEGACY_PROMPT_VERSION)
    sentinel = "unrelated-valid-entry"
    module.save_cache({
        legacy_key: '{"analyzable_audio": true}',
        sentinel: "A quiet background hum, possibly ventilation.",
    })
    calls = []
    def fake_interpret(data, api_key):
        calls.append(True)
        return "A series of faint knocks with a steady background hiss."
    monkeypatch.setattr(module, "interpret", fake_interpret)
    output = module.analyze("mission-A")
    assert output["status"] == "partial"
    assert output["newly_analyzed"] == 2
    assert len(calls) == 2
    cache = module.load_cache()
    assert legacy_key not in cache
    assert cache[sentinel].startswith("A quiet background hum")
    assert module.cache_key(data) in cache
    assert "status" not in output["report"].lower()


def test_valid_legacy_cached_description_migrates_without_api_call(
        archive, monkeypatch):
    data, _ = module.read_wav(module.MEDIA_DIR / "audio_00000001.wav")
    legacy_key = module.cache_key(data, module.LEGACY_PROMPT_VERSION)
    description = "Faint rustling with short periodic chirps, possibly a bird."
    module.save_cache({legacy_key: description})
    requests = []
    def fake_interpret(data, api_key):
        requests.append(True)
        return "A low background rumble."
    monkeypatch.setattr(module, "interpret", fake_interpret)
    out = module.analyze("mission-A")
    assert out["recordings"][0]["cached"] is True
    assert out["recordings"][0]["description"] == description
    assert out["newly_analyzed"] == 2
    assert len(requests) == 2
    assert module.load_cache()[module.cache_key(data)] == description


def test_status_only_response_received_over_api_is_rejected(archive, monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps({"choices": [{
                "finish_reason": "stop",
                "message": {"content": '{"analyzable_audio": true}'}
            }]}).encode())
        def __exit__(self, exc_type, exc, tb):
            return False
    monkeypatch.setattr(module.urllib.request, "urlopen",
                        lambda request, timeout=0: FakeResponse())
    sound, _ = module.read_wav(module.MEDIA_DIR / "audio_00000001.wav")
    with pytest.raises(ValueError, match="status data"):
        module.interpret(sound, "not-a-real-key")
    for bad in ('{"analyzable_audio": true}', "true", '{"other": 1}',
                '["no", "description"]', "Audio is analyzable"):
        with pytest.raises(ValueError):
            module.validate_description(bad)
    assert module.validate_description("Only faint background hiss.") == (
        "Only faint background hiss.")
