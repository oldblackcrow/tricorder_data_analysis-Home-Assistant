# TR-460 WAV sound interpretation (separate initial test)

**Status:** Committed implementation only. NOT installed or tested against
your live Home Assistant instance or a live OpenAI API call.

The existing Audio card and WAV-transfer mechanism stay unchanged.
This is a new, separate script. It is not yet included in general
diagnostic voice reports; that integration comes after an end-to-end test.

## What it reads

- The mission selected on the Tricorder dashboard via
  input_text.tric_archive_mission_id.
- Mission-tagged audio_recording_begin manifest records from the private
  /config/tricorder/tricorder_uploads.jsonl archive.
- Only WAVs restored under /media/tricorder_audio/, with matching
  /config/tricorder/recordings/audio_XXXXXXXX.json sidecars.
- 8 kHz mono 16-bit PCM WAVs up to 45 seconds (the normal timed scans).
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
   Do NOT expose or integrate it into the general diagnostic yet.

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
- Requests use store:false and TEXT-only output; the WAV is still uploaded
  to OpenAI. Keep saved audio private.

## Known limitations

- The analyzer can suggest what a sound resembles but cannot guarantee
  an animal, species, machine, or human identity from short WAV audio.
- It currently does NOT compare missions, process Captain's Logs, or add
  its findings to the general Tricorder diagnostic. Those come after
  the standalone test succeeds.
- Each API request has a 22-second timeout; slow calls may fail and can
  motivate asynchronous processing later.
- No dashboard, archived WAV, webhook or device firmware is altered.

## Verification

Offline tests in tests/test_audio_ai.py mock the API, so they incur no
charges. Tests alone cannot establish the live model permissions, API-key
access, or Home Assistant behavior. A live manual test remains required.
