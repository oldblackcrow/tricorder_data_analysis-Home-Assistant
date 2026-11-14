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
    assert base64.b64decode(
        payload["messages"][0]["content"][1]["input_audio"]["data"]) == sound
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
