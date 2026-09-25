# Pipecat Screening Orchestration Migration Plan

## Purpose

Replace the hand-built real-time screening orchestration with Pipecat while preserving the current bot behavior, Core API contracts, interview scoring, external model services and artifacts, Attendee WebSocket contract, and scheduling behavior.

This document is an implementation plan. It does not itself change the runtime. The implementation must be performed on a separate branch, tested end to end, and merged only after the compatibility gates pass.

## Decision

Use Pipecat as the real-time pipeline/runtime for one interview session. Keep EZScreen domain policy in application-owned Python code:

- Core API continues to own scheduling, calendar events, invitations, session status, and durable persistence.
- EZScreen continues to own question routing, intent classification, answer evaluation, scoring, transcript shape, termination reasons, and bot leave behavior.
- Pipecat owns audio transport, audio frames, VAD/turn detection, STT/TTS pipeline execution, interruption, and lifecycle of the real-time pipeline.
- WhisperFast/Whisper remains the STT model/service.
- Kokoro remains the TTS model/service and continues to emit 24 kHz mono PCM for Attendee.
- Model artifacts are deployment inputs only. They are not source code, are not committed to Git, and are not copied into the application image.

Do not move calendar scheduling, Core API persistence, scoring formulas, or question-routing rules into Pipecat. Pipecat is not the source of truth for those concerns.

## Current System Contract

These behaviors must remain unchanged after migration.

### Scheduling and lifecycle

1. HR schedules an interview through Core API.
2. Core API validates application state, job-fit readiness, duplicate active sessions, and future time.
3. Core API generates questions, creates or accepts a Meet link, sends invitations, and dispatches Attendee.
4. Attendee joins at the scheduled time and opens the existing WebSocket path:

   `/attendee-websocket/{interview_session_id}`

5. The WebSocket currently creates the interview runtime and starts the greeting. The migration must preserve that behavior. Do not depend on the currently incomplete webhook TODOs to start the greeting unless a later, separately tested lifecycle change is approved.
6. Attendee lifecycle webhooks update Core API status.
7. The runtime requests Attendee to leave after the closing interaction is persisted.

### Conversation behavior

The following exact behavior is a compatibility requirement:

- Speak `GREETING_TEXT` once after the session starts.
- Begin listening only after greeting audio has finished streaming.
- Accept candidate audio from `realtime_audio.user`.
- Use `realtime_audio.mixed` only as a fallback while listening or accepting a closing reply.
- Do not feed bot audio back into STT.
- Use the current STT language, endpoint, model, audio format, minimum clip behavior, and hallucination filter unless a test-approved configuration change is required for WhisperFast. The STT service/model is configured externally and is not bundled in this repository.
- Route each transcript through the existing `AnswerEvaluator`.
- Preserve `CLARIFICATION`, `SMALL_TALK`, `SKIP`, and answer handling semantics.
- Preserve `REPEAT_QUESTION` behavior, including repeating the same follow-up without creating another follow-up.
- Preserve `MAX_FOLLOW_UPS_PER_QUESTION`.
- Preserve dynamic category routing in `routing_engine.py`.
- Preserve the exact silence prompt text, 30-second interval, three-prompt limit, grace period, candidate-activity cancellation, and `candidate_silence` termination reason.
- Preserve the closing text, closing reply handling, 30-second silent closing timeout, and closing-reply persistence.
- Finalize exactly once, including when the WebSocket disconnects early.
- Request Attendee leave only after final persistence is attempted.

### Data contracts

Pipecat must not alter these payloads or endpoints:

- Core API `POST /api/v1/interview-sessions/{id}/qa-transcript`
- Core API `POST /api/v1/interview-sessions/{id}/evaluation`
- Core API `POST /api/v1/interview-sessions/{id}/evaluation/summary`
- Core API `POST /api/v1/interview-sessions/{id}/transcript`
- Attendee `realtime_audio.bot_output` JSON message shape
- Attendee WebSocket URL and session ID path
- Evaluation decisions: `ASK_FOLLOW_UP`, `NEXT_QUESTION`, `REPEAT_QUESTION`
- Transcript interaction fields: `interaction_type`, `bot_speech`, `candidate_answer`, `question_id`, and `follow_ups`

## Repository File Impact

### Files expected to change

#### `services/ai-core-services/pyproject.toml`

Add the pinned Pipecat dependency and only the extras needed for the selected transport/STT/TTS adapters. Keep existing `kokoro-onnx`, `numpy`, `webrtcvad`, and `httpx` dependencies until the migration is proven. Dependencies are runtime libraries; model weights do not belong in Git.

Do not remove the old dependencies during the migration branch. Removal is a separate cleanup after the fallback path has been retired.

#### `services/ai-core-services/uv.lock`

Regenerate using the repository's dependency workflow after changing `pyproject.toml`. Review the lock diff for unrelated upgrades.

#### `services/ai-core-services/src/core/config.py`

Add only model and transport configuration required by the Pipecat runtime:

- Pipecat transport frame settings if they cannot be derived from existing settings
- Explicit STT endpoint, model name, language, and sample-rate settings if WhisperFast differs from the current hard-coded value
- Explicit external Kokoro model directory, voices file, voice, language, and speed settings
- A required model-artifact root such as `AI_MODELS_DIR`, or separate `KOKORO_MODEL_PATH` and `KOKORO_VOICES_PATH`
- Optional model checksum/version settings for startup validation

Use the existing environment naming style. Do not make Pipecat the default until compatibility testing is complete.

#### `services/ai-core-services/.env.example`

Document the new feature flag and any required Pipecat/STT settings without adding secrets. Document the external model mount/path contract, required Kokoro files, permissions, and provisioning procedure. Do not add model files, binary blobs, or credentials to the repository.

#### `services/ai-core-services/src/screening_pipeline/audio_websocket.py`

Keep the public route and Attendee message contract. The handler is a small
transport adapter that always starts the Pipecat session runtime.

The route should remain responsible for accepting the WebSocket, validating/normalizing Attendee messages, selecting user versus mixed audio, and running cleanup. It should not contain interview policy.

Preserve `_should_forward_candidate_audio` behavior and its tests. Avoid a second independent message parser in the Pipecat path.

#### `services/ai-core-services/src/screening_pipeline/pipecat_policy.py`

Keep interview business behavior in the Pipecat policy/session object.

The safe migration is:

1. Extract session loading, transcript event construction, question selection, evaluator calls, persistence, finalization, and leave behavior into an application-owned session policy.
2. Keep the existing class as a compatibility wrapper around that policy.
3. Add a Pipecat adapter that invokes the same policy from Pipecat events.
4. Remove only transport-specific code from the legacy wrapper after the Pipecat path passes all gates.

Do not change prompts, evaluator inputs, routing decisions, persistence ordering, or termination reasons while extracting.

#### New `services/ai-core-services/src/screening_pipeline/pipecat_runtime.py`

Create one focused entry point that:

- Builds one Pipecat pipeline per WebSocket session.
- Loads the session using the existing repository/session API path.
- Instantiates the existing evaluator, LLM client, session API client, and Kokoro/Whisper adapters.
- Registers pipeline event handlers.
- Runs the pipeline until disconnect, normal close, fatal error, or cleanup.
- Calls finalization exactly once.

This file should coordinate components only. It should not duplicate the interview decision tree.

#### New `services/ai-core-services/src/screening_pipeline/pipecat_transport.py`

Implement the Attendee transport boundary:

- Decode inbound JSON/base64 audio messages.
- Accept binary messages using the current 24 kHz assumption.
- Preserve the user-audio preference and mixed-audio fallback.
- Convert inbound PCM to Pipecat audio frames with the correct sample rate and channel count.
- Encode outbound frames as 50 ms, 24 kHz, mono PCM chunks in the existing `realtime_audio.bot_output` JSON format.
- Serialize WebSocket writes so concurrent pipeline events cannot interleave output frames.

This adapter is where any Pipecat transport mismatch must be contained.

#### New `services/ai-core-services/src/screening_pipeline/pipecat_stt.py`

Create a thin Pipecat STT service/processor for the same WhisperFast/Whisper backend. It must preserve the current external behavior:

- Same endpoint and credentials.
- Same model name, or an explicit configured WhisperFast model name.
- Same language.
- Same PCM/WAV format expected by the endpoint.
- Same transcript callback/event semantics.
- Same probable-hallucination filtering, unless that filtering is moved unchanged into the policy layer.

Do not silently switch to a hosted STT provider or Pipecat's default provider.

If WhisperFast is a local streaming server rather than the current HTTP transcription endpoint, implement that protocol here and document the exact conversion. The rest of EZScreen must receive the same final transcript events.

#### New `services/ai-core-services/src/screening_pipeline/pipecat_tts.py`

Wrap the existing `LocalKokoroTTSClient` as a Pipecat TTS service/processor. Preserve:

- External Kokoro model and voices paths supplied by configuration.
- Model files mounted from deployment-managed storage, not copied from the repository or downloaded into a Git-tracked directory.
- `af_bella` voice, `1.0` speed, and `en-us` language unless explicitly configured.
- 24 kHz output.
- 16-bit mono PCM conversion.
- Output pacing or an equivalent mechanism that prevents listening from starting before prompt audio is delivered.
- Existing fallback behavior on synthesis failure, unless a tested equivalent is required by Pipecat.

Do not create a second Kokoro model loader.

#### New `services/ai-core-services/src/screening_pipeline/pipecat_policy.py`

Prefer a small policy class or service over embedding business logic in Pipecat processors. It should expose narrow operations such as:

- `start_session()`
- `on_candidate_transcript(transcript)`
- `on_candidate_activity()`
- `on_silence_timeout()`
- `on_audio_output_started/finished()` if required
- `cleanup(reason)`

The policy should own the current interaction state, transcript log, evaluation list, question queues, finalization guard, and termination reason. It should reuse existing helper modules rather than duplicate them.

Pipecat should call this policy; Pipecat should not decide whether an answer is a skip, follow-up, repeat, or next question.

#### `services/ai-core-services/src/screening_pipeline/webhook_handler.py`

Do not change lifecycle behavior as part of the first migration. Preserve status updates and immediate webhook acknowledgement.

Only add a small, idempotent runtime notification if testing proves that Pipecat requires it. The current WebSocket connection remains the authoritative runtime start trigger for this migration. Do not implement the existing TODOs opportunistically.

#### `services/ai-core-services/Dockerfile`

Change only if the selected Pipecat extras require system libraries. Keep Python 3.11 and the CPU-only dependency strategy. Do not copy model artifacts into the image, run model downloads during image build, or add GPU dependencies without a measured requirement. The image should contain code and Python dependencies only.

#### `docker-compose.yml`

Update this file to remove any repository-relative model fallback such as `./data/ai-models`. A model host path must be supplied explicitly by deployment configuration, or the service must fail fast with a clear missing-artifact error. Mount external model storage read-only where practical.

Preserve:

- the configured external Kokoro mount/path
- public WebSocket URL configuration
- Core API service URL
- existing port `8002`

Do not commit model files or add a volume whose default points into the repository. The current worktree already has an unrelated modification in this file; preserve and review it before applying any migration change.

#### Deployment-managed model provisioning

This is an operational requirement rather than a source-code directory:

- Provision WhisperFast/Whisper outside this repository, or configure the external STT endpoint.
- Provision Kokoro's ONNX model and voices file outside this repository.
- Mount the artifacts into the container or provide stable host paths through environment variables.
- Keep the mount read-only for the application process.
- Pin and record artifact versions/checksums in deployment configuration or a release manifest, not in Git as binary files.
- Ensure the runtime user can read the files.
- Fail startup or health checks clearly when required artifacts are missing or unreadable.
- Never download model files from the application request path.
- Never use a local repository directory as a production fallback.

### Files that should not change in the first migration

These are compatibility boundaries and should remain unchanged unless a failing contract test proves otherwise:

- `apps/core-api/src/services/interview_session_service.py`
- `apps/core-api/src/services/bot_dispatch_service.py`
- `apps/core-api/src/api/routes/interview_sessions.py`
- `apps/core-api/src/schemas/interview_session.py`
- `apps/core-api/src/schemas/interview_analysis.py`
- `apps/core-api/src/services/interview_analysis_service.py`
- `services/ai-core-services/src/meeting_bot/client.py`
- `services/ai-core-services/src/meeting_bot/attendee.py`
- `services/ai-core-services/src/meeting_bot/schemas.py`
- `services/ai-core-services/src/screening_pipeline/evaluator.py`
- `services/ai-core-services/src/screening_pipeline/routing_engine.py`
- `services/ai-core-services/src/screening_pipeline/persistence.py`
- `services/ai-core-services/src/screening_pipeline/session_api.py`
- `services/ai-core-services/src/screening_pipeline/evaluation_builders.py`
- `services/ai-core-services/src/screening_pipeline/prompt_builder.py`
- `services/ai-core-services/src/screening_pipeline/prompts.py`
- `services/ai-core-services/src/screening_pipeline/speech_filter.py`
- `services/ai-core-services/src/main.py`

The current worktree already has an unrelated modification in `prompts.py`; do not overwrite it.

## Proposed Runtime Structure

```text
screening_pipeline/
├── audio_websocket.py              # Public Attendee WebSocket; Pipecat entry point
├── pipecat_policy.py               # Pipecat interview business policy
├── pipecat_runtime.py              # Pipecat pipeline lifecycle
├── pipecat_transport.py            # Attendee <-> Pipecat audio/message bridge
├── pipecat_stt.py                  # WhisperFast/Whisper adapter
├── pipecat_tts.py                  # Existing Kokoro adapter
├── evaluator.py                    # Existing scoring and intent policy
├── routing_engine.py               # Existing question routing policy
├── persistence.py                  # Existing persistence and final summary
├── session_api.py                  # Existing Core API client
├── prompts.py                      # Existing user-visible text and limits
└── speech_filter.py                # Existing transcript filter
```

Keep the structure small. Do not introduce a general event bus, database-backed workflow engine, or new persistence model for this migration.

## Migration Sequence

## Execution Status

The migration is being implemented on the separate branch `feat/pipecat`.

Confirmed decisions:

- WhisperFast uses a streaming WebSocket STT interface.
- Kokoro artifacts use explicit environment paths: `KOKORO_MODEL_PATH` and `KOKORO_VOICES_PATH`.
- Pipecat `1.10.0` is verified as the stable release compatible with Python 3.11 and is pinned without provider extras.
- Phase 1 is limited to baseline and contract tests. Runtime refactoring starts only after those tests are in place.
- The existing Attendee WebSocket remains the transport boundary. WebRTC is out of scope for this migration.

Recorded gates:

- Baseline before migration: 137 tests passed.
- Phase 1 contract suite: 5 tests passed.
- Full suite after Phase 1: 140 tests passed.
- Full suite after the policy interface and speech-output seam: 142 tests passed.
- Full suite after Pipecat adapters and the disabled WebSocket branch: 149 tests passed.
- Full suite after deterministic Pipecat WebSocket integration coverage: 150 tests passed.
- Full suite after Pipecat external Kokoro readiness validation: 151 tests passed.
- Full suite after native/Docker external model-path alignment: 152 tests passed.
- Full suite after live Pipecat startup fixes: 152 tests passed.
- `uv` was installed in the user environment because it was not initially available; no repository dependency files were changed.

Current implementation checkpoint:

- Phase 2 is in progress.
- `InterviewPolicy` defines the runtime-facing lifecycle boundary.
- Pipecat is the only screening runtime.
- Pipecat owns VAD, segmented HTTP Whisper transcription, Kokoro speech, and the
  Attendee audio bridge behind the existing public WebSocket route.
- The live Pipecat path has not yet passed a real Attendee session with externally mounted Kokoro artifacts.
- Deterministic Pipecat WebSocket coverage now verifies mixed/user/binary audio routing and cleanup.
- The Pipecat runtime now validates and loads external Kokoro artifacts before starting its pipeline.
- Pipecat sessions fail before pipeline execution when required external Kokoro artifacts are unavailable.
- Native validation succeeded using `/home/ue/ezscreen-models/kokoro`; Docker is configured to use its `/app/.models` mount.
- Real Kokoro synthesis succeeded with 24 kHz PCM output and 2,400-byte frames.
- Live startup fixes: shared the process-level Kokoro client, imported runtime logging correctly, and wait for Pipecat pipeline readiness before starting the interview greeting.

Phase gates:

- [x] Phase 0: branch, baseline, and environment verification
- [x] Phase 1: freeze behavior contracts with deterministic tests
- [ ] Phase 2: extract shared interview policy while legacy runtime remains active
- [ ] Phase 3: enforce external model runtime contract
- [x] Phase 4: implement current Whisper HTTP and Kokoro Pipecat adapters
- [x] Phase 5: implement Attendee Pipecat transport
- [x] Phase 6: implement Pipecat runtime and policy bridge
- [ ] Phase 7: run feature-flagged integration and canary tests
- [ ] Phase 8: cut over and retain rollback path

### Phase 0: Branch and baseline

1. Do not branch from a dirty worktree without recording the baseline.
2. Preserve the existing changes currently present in:
   - `docker-compose.yml`
   - `services/ai-core-services/src/screening_pipeline/prompts.py`
   - `services/attendee/attendee/settings/development.py`
   - untracked local files/data; do not add model artifacts to the branch
3. Create a migration branch from the agreed base commit, for example:

   ```bash
   git switch -c feat/pipecat-screening-runtime
   ```

4. Record the baseline test command and results:

   ```bash
   cd services/ai-core-services
   uv run pytest
   ```

   If `uv` is unavailable, install it outside the repository or use the project's existing virtual environment. Do not change dependency declarations merely to work around a missing local tool.

5. Capture one legacy test interview or deterministic fixture containing greeting, normal answer, clarification, small talk, skip, repeat, follow-up, silence, closing reply, disconnect, and final persistence.

Phase 0 completion criteria:

- Branch is `feat/pipecat`.
- Worktree changes unrelated to this migration are recorded and preserved.
- The baseline test command has a recorded result.
- External model paths and WhisperFast WebSocket protocol are documented.
- No model artifacts are added to the branch.

### Phase 1: Freeze contracts with tests

Before changing runtime code, add or strengthen tests for:

- exact prompt texts and ordering
- audio output message shape and 24 kHz sample rate
- user versus mixed-audio selection
- transcript normalization
- evaluator invocation inputs
- follow-up and repeat behavior
- routing decisions
- three silence prompts and cancellation
- closing timeout and leave request
- finalization exactly once
- persistence ordering and payloads
- unknown session and WebSocket disconnect cleanup

Use fakes for STT, TTS, evaluator, Core API, Attendee, and WebSocket. These tests must be deterministic and must not call real model APIs.

Phase 1 implementation order:

1. Add tests for the existing Attendee audio input/output contract.
2. Add tests for the existing transcript normalization and Core API payloads.
3. Add tests for the existing interview scenario traces.
4. Add tests for cleanup, duplicate finalization, and failure paths.
5. Run the full suite and mark Phase 1 complete only when the legacy runtime still passes.

Do not add Pipecat imports, change runtime selection, or modify production behavior in Phase 1.

### Phase 2: Extract shared policy without Pipecat

Refactor the existing `InterviewOrchestrator` into the proposed shared policy while keeping the legacy runtime active.

Rules:

- Make one small refactor at a time.
- Run the current screening test suite after each refactor.
- Preserve public test seams where practical.
- Do not change prompts, timing constants, score calculations, or persistence payloads.
- Add an explicit finalization lock/guard if required to make concurrent close paths deterministic.

The legacy path must pass all tests before Pipecat is introduced.

### Phase 3: Define external model runtime contract

Before implementing Pipecat adapters, make model location explicit.

1. Choose one deployment contract:
   - an external WhisperFast/Whisper endpoint plus API settings; and
   - `KOKORO_MODEL_PATH` plus `KOKORO_VOICES_PATH`, or an external `AI_MODELS_DIR` containing both files.
2. Remove repository-relative production defaults such as `./data/ai-models` and `.models` where they can cause accidental local downloads.
3. Add startup validation for file existence, readability, and expected format.
4. Add a deployment-only provisioning step that downloads or installs artifacts into external storage.
5. Verify that the Docker image contains no model artifacts and that `git status` remains clean of model binaries.
6. Test the container with the external mount absent and confirm the error is actionable.

The migration branch must not contain Kokoro weights, voices binaries, Whisper weights, Hugging Face caches, or generated model directories.

### Phase 4: Add model adapters

Implement `pipecat_stt.py` and `pipecat_tts.py` around the existing models.

Test each adapter independently:

- STT receives known PCM and emits the same transcript fixture as the legacy client.
- STT does not emit duplicate transcripts for one utterance.
- TTS emits valid mono 16-bit PCM at 24 kHz.
- TTS chunk boundaries are valid and stable.
- TTS failure produces the existing safe behavior.
- Kokoro loading is shared or cached per process and does not download once per utterance.
- Pipecat does not download or mutate model artifacts during a live interview.
- Missing or unreadable external artifacts produce a clear startup failure.

Do not tune turn detection and model behavior simultaneously. First prove audio format and adapter contracts.

### Phase 5: Add Attendee Pipecat transport

Implement the transport adapter and wire it behind the existing WebSocket route without changing the route path or Attendee dispatch payload.

Required transport tests:

- base64 JSON audio is decoded correctly
- binary audio is accepted as before
- sample rate is preserved from the inbound message
- mixed audio is ignored while the bot is speaking
- user audio remains preferred after it is observed
- outbound audio has the exact existing JSON schema
- concurrent output frames are ordered and not interleaved
- disconnect closes the pipeline and invokes policy cleanup

### Phase 6: Implement Pipecat runtime and policy bridge

Build the pipeline in this order:

1. Attendee input transport
2. audio conversion/frame normalization
3. VAD/turn detection configured to match current end-of-utterance behavior
4. WhisperFast/Whisper STT adapter
5. transcript filter and policy callback
6. existing evaluator/policy
7. Kokoro TTS adapter
8. Attendee output transport

The policy callback must serialize candidate turns. A second transcript must not start a second evaluation while the previous evaluation is still deciding the next action.

The policy must control when the bot is listening. Pipecat's automatic conversational behavior must not bypass the interview state machine.

### Phase 7: Feature-flagged shadow and canary testing

Pipecat is the production runtime; no runtime-selection feature flag exists.

Test in this order:

1. Unit tests with the flag off.
2. Unit tests with the flag on.
3. Local fake Attendee WebSocket integration test.
4. One real Attendee meeting using a dedicated test session.
5. Repeated real meetings covering all behavior cases.
6. Small canary percentage or explicitly selected test sessions.

Do not run both runtimes against the same live session. Shadow mode may compare deterministic decisions from recorded transcripts, but only one runtime may send audio or persist results.

### Phase 8: Cutover and cleanup

After compatibility and operational gates pass:

1. Deploy the Pipecat runtime.
2. Monitor the canary.
3. Preserve transcript data when a live session fails; do not start a second
   runtime for that session.
5. Remove unused dependencies only after verifying no other module uses them.

## Behavior Compatibility Matrix

| Area | Legacy source of truth | Pipecat responsibility | Must remain identical |
|---|---|---|---|
| Scheduling | Core API interview session service | None | Session validation, Meet link, invite, reschedule |
| Bot dispatch | `meeting_bot/client.py` and Attendee API | None | Join time, WebSocket URL, sample rate |
| Session start | WebSocket route and Pipecat policy | Runtime startup | Greeting once after connection |
| Input audio | `audio_websocket.py` | Transport adapter | User/mixed selection and sample rate |
| Turn end | Pipecat VAD/silence | Pipecat turn detection | One transcript per utterance |
| STT | Whisper client | Pipecat adapter | Same model/service and transcript semantics |
| Intent | `evaluator.py` | Policy callback | Same prompt and intent handling |
| Scoring | `evaluator.py` | None | Same formula and decisions |
| Question routing | `routing_engine.py` | Policy callback | Same queue/chunk/downgrade behavior |
| TTS | Pipecat Kokoro adapter | Pipecat adapter | Same voice, language, speed, 24 kHz PCM |
| Silence | Pipecat policy constants/logic | Policy/timer integration | Three prompts, timing, cancellation |
| Persistence | `persistence.py` and Core API | Policy invokes it | Same order and payloads |
| Close | Orchestrator and Attendee client | Runtime lifecycle hook | Save once, then leave |
| Webhook status | `webhook_handler.py` | None initially | Existing status updates |

## Testing Plan

### Static and unit validation

Run from `services/ai-core-services`:

```bash
uv run pytest
```

Add focused tests for:

- `tests/screening_pipeline/test_pipecat_transport.py`
- `tests/screening_pipeline/test_pipecat_stt.py`
- `tests/screening_pipeline/test_pipecat_tts.py`
- `tests/screening_pipeline/test_pipecat_policy.py`
- `tests/screening_pipeline/test_pipecat_runtime.py`
- `tests/screening_pipeline/test_compatibility_scenarios.py`

Keep and run the existing tests:

- `test_orchestrator.py`
- `test_audio_websocket.py`
- `test_webhook_handler.py`
- `test_evaluator_scoring.py`
- `test_evaluator_helpers.py`
- `test_routing_engine.py`
- `test_persistence.py`
- `test_session_api.py`
- `test_summary_calculator.py`

### Deterministic scenario tests

Create a fake-session scenario runner that records:

- outbound spoken text
- candidate transcript events
- state transitions
- evaluator calls and arguments
- saved transcript payloads
- saved evaluation payloads
- final summary payload
- leave request
- termination reason

Run every scenario through both legacy and Pipecat runtimes and compare normalized event traces. Ignore implementation-specific event names; compare user-visible text, decisions, payloads, order, and terminal state.

Required scenarios:

1. Normal completion.
2. Clarification then answer.
3. Small talk then answer.
4. Skip.
5. Repeat main question.
6. Repeat follow-up.
7. One follow-up then completion.
8. Three silence prompts then close.
9. Candidate activity cancels a silence prompt.
10. Closing reply received.
11. Closing reply timeout.
12. WebSocket disconnect during listening.
13. WebSocket disconnect during speech output.
14. Missing session.
15. STT failure.
16. TTS failure.
17. Core API evaluation rejection.
18. Duplicate close/finalize events.

### Audio validation

For generated TTS and outbound frames verify:

- mono channel
- signed 16-bit PCM
- 24,000 Hz
- expected frame size of 2,400 bytes for 50 ms frames, except the final partial frame
- no base64 corruption
- no output-frame reordering

For inbound audio verify 24 kHz and any supported 16 kHz path explicitly. Do not assume the Attendee sample rate; use the message value where available and test the configured dispatch value.

### End-to-end validation

Use a dedicated test Meet link and the externally provisioned WhisperFast/Whisper and Kokoro artifacts. Capture:

- connection and join latency
- first greeting output latency
- transcript latency
- response latency
- interruptions/barge-in behavior
- missed or duplicate turns
- WebSocket disconnect behavior
- final persistence completion
- Attendee leave completion
- CPU and memory usage
- model load time

Also verify:

- the image contains no model files
- the runtime can read the external mount
- a missing mount fails before accepting live sessions
- model artifacts are not written, downloaded, or modified during a session

The real-model test is a release gate, not a substitute for deterministic tests.

## Rollback Plan

Rollback must require only configuration:

If Pipecat fails during a live session, do not start a second runtime for that
same session. Mark the session according to the existing failure policy and
preserve available transcript data.

## Operational Requirements

- Use one runtime owner per session.
- Avoid process-local session assumptions if deploying multiple Uvicorn workers. During the first migration, keep the current single-session ownership behavior or add an explicit routing requirement; do not silently claim multi-worker safety.
- Make cleanup idempotent.
- Make final persistence idempotent at the runtime level and preserve Core API upsert behavior.
- Bound all external calls with timeouts.
- Log session ID, runtime mode, state, turn ID, and termination reason without logging secrets or raw audio.
- Do not log full candidate audio or API keys.
- Add metrics for session starts, turn counts, STT failures, TTS failures, disconnects, finalization success, and leave success.

## Documentation Updates After Implementation

Update only after the runtime is working:

- `services/ai-core-services/README.md`: runtime mode, dependencies, test command, and model adapters.
- `docs/integrations/ATTENDEE_INTEGRATION.md`: Pipecat transport flow and unchanged Attendee message contract.
- `docs/architecture/AI_PROCESSING.md`: shared policy versus Pipecat runtime boundary.
- `docs/architecture/SYSTEM_DESIGN.md`: only if the production architecture changes materially.
- `docs/SETUP.md`: new environment variables and local testing steps.

Do not update the Core API scheduling documentation to imply that Pipecat schedules interviews.

## Definition of Done

The migration is ready to merge only when:

- `uv run pytest` passes with Pipecat.
- Compatibility scenario traces match for all required scenarios.
- Core API scheduling and rescheduling tests pass without changes to their behavior.
- Attendee dispatch payload is unchanged except for an explicitly documented runtime flag.
- Real externally provisioned Kokoro and WhisperFast/Whisper tests pass.
- A real Attendee meeting completes successfully.
- A real Attendee meeting covers silence termination and closing timeout.
- No duplicate transcript, evaluation, summary, or leave request is observed.
- A WebSocket disconnect still finalizes the session as before.
- No secrets, model files, model caches, or unrelated worktree changes are committed.

## Explicit Non-Goals

This migration does not:

- replace Core API scheduling
- replace Google Calendar or Meet integration
- replace Attendee.dev
- change LLM prompts or scoring
- change question generation
- change transcript schemas
- add a durable workflow engine
- add a new database schema
- change Kokoro voice or Whisper model intentionally
- fix unrelated webhook TODOs or unrelated dirty-worktree changes
