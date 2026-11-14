# TR-460 WAV sound interpretation and general diagnostic integration

**Status:** Standalone audio analysis was successfully tested with a real 10-second
mission WAV recording: it returned a natural-language description that the
user confirmed matched the recording. The updated general diagnostic router
is committed on GitHub but has NOT yet been installed or tested in Home Assistant.

The existing Audio card, WAV-transfer mechanism, and standalone scripts stay
unchanged. The router adds WAV findings to a concise general diagnostic.

## What it reads

- The mission selected on the Tricorder dashboard via
  input_text.tric_archive_mission_id.
- Mission-tagged audio_recording_begin manifest records from the private
  /config/tricorder/tricorder_uploads.jsonl archive.
- Only WAVs restored under /media/tricorder_audio/, with matching
  /config/tricorder/recordings/audio_XXXXXXXX.json sidecars.
- Mono 16-bit PCM WAVs up to 45 seconds (the normal timed scans).
  Nothing reads the microphone live; Captain's Logs are different.

The OpenAI gpt-audio-1.5 Chat Completions API receives the actual WAV,
not the measured dB levels or a text transcript. It describes the audible
environment in 40 words or fewer per recording, with qualified suggestions
('possibly footsteps', 'may be a dog barking') and uncertainty.

Official API: https://developers.openai.com/api/docs/guides/audio-chat-completions

## One-time installation (do not overwrite other configuration)

1. Back up your Home Assistant configuration.
2. Copy [the audio analyzer](../tricorder/tricorder_audio_ai.py) to
   /config/tricorder/tricorder_audio_ai.py. This is a Python file,
   NOT a Home Assistant Helper.
3. The custom Python process cannot automatically read the API key stored
   in Home Assistant's OpenAI integration. Create a PRIVATE plain-text file
   /config/tricorder/openai_audio_api_key containing JUST your OpenAI API
   key (no quotes or YAML). Another key can be generated at
   https://platform.openai.com/api-keys if the original is unavailable.
   NEVER put the key in GitHub, a dashboard, an automation trace, or chat.
   Protect local file permissions where possible. Alternatively set the
   OPENAI_API_KEY environment variable for the Python process.
   Do NOT put the secret in the shell command.
4. Merge the single entry from
   [the shell command](../setup/tricorder_audio_ai_shell_command.yaml)
   into the EXISTING shell_command: section of configuration.yaml.
   Do not create a duplicate heading. Check configuration and restart HA.
5. Create one new script named Analyze Tricorder Audio Recordings using
   [the standalone script YAML](../setup/tricorder_audio_ai_script.yaml).
   It obtains the selected mission automatically.
6. Select a mission with playable WAVs, then run the script manually and
   inspect the newest trace's audio_result response (status/report/errors).
7. Once this succeeds, replace ONLY the existing TR-460 Tricorder Router
   automation's YAML with
   [the combined router](../setup/tricorder_router_thermal.yaml).
   Do not create a duplicate router. This reuses both standalone analyzers
   and speaks one short report, including sensor, thermal, and recorded WAV
   interpretations. Test a general diagnostic and inspect the router trace.

## Caching, costs and duration

- Cached descriptions are saved to /config/tricorder/audio_ai_cache.json,
  without WAV bytes. The cache key contains the WAV content hash, model,
  and prompt revision. Repeated requests do not rebill unchanged recordings.
- At most TWO previously unanalyzed WAV files per invocation are sent to
  OpenAI. This bounds runtime under the 60-second shell_command limit.
  The response reports how many files remain, if any. Run the script again
  to complete a larger mission; cached descriptions carry forward.
- API errors are reported, not cached. Account billing is through the
  separate OpenAI API (not the ChatGPT subscription).
- Requests use store:false and both text and audio response modalities, as
 described in the documented GPT-audio example. We extract the generated
 audio.transcript as a sound description and discard generated audio bytes;
 the generated audio may add API output charges. The original WAV is still
 uploaded to OpenAI. Keep saved audio private.

## Known limitations

- The analyzer can suggest what a sound resembles but cannot guarantee
  an animal, species, machine, or human identity from short WAV audio.
- It currently does NOT compare audio across missions or process Captain's
  Logs. The separate general router includes audio findings after the updated
  router YAML is installed; this integration is not yet live-tested.
- Each API request has a 22-second timeout; slow calls may fail and can
  motivate asynchronous processing later.
- No dashboard, archived WAV, webhook or device firmware is altered.

## Verification

Offline tests in tests/test_audio_ai.py mock the API, so they incur no
charges; tests/test_router_audio_integration.py checks the router branches.
A real standalone audio request was confirmed successful with the user's
recording. The combined voice diagnostic still needs a manual test.
