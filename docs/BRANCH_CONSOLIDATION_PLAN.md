# Branch Consolidation Plan

There are currently 49 branches in the repository. This plan categorizes them and outlines a strategy to reduce them to a single `main` branch (plus active feature branches).

## Phase 1: Cleanup Merged Branches
The following branches have been fully merged into `main` and can be safely deleted immediately.

- `cursor/codebase-review-and-documentation-1016`
- `cursor/codebase-review-and-improvement-22c2`
- `cursor/codebase-review-and-improvement-a849`
- `cursor/codebase-review-and-improvement-cff5`
- `cursor/codebase-review-and-improvement-f526`
- `cursor/collector-network-call-improvements-eb63`
- `cursor/early-digital-art-research-fca9`
- `cursor/file-issue-reporting-745b`
- `cursor/file-issue-reporting-9c32`
- `cursor/file-issue-reporting-c2cf`
- `cursor/fix-pickle-security`
- `cursor/github-code-review-and-fix-5021`
- `cursor/hass-ai-orchestrator-integration-95a7`
- `cursor/home-assistant-github-sync-00ff`
- `cursor/home-assistant-integration-research-947f`
- `cursor/issue-resolution-and-fixes-9c13`
- `cursor/issue-resolution-and-fixes-d4c3`
- `cursor/issue-resolution-and-fixes-efb5`
- `cursor/ml-workflow-review-4fc4`
- `cursor/research-and-build-project-gpt-5.1-codex-a510`
- `fix/add-httpx-dependency`
- `fix/reduce-history-io`
- `fix/reduce-io-led-encoder`
- `fix/safer-service-dispatch`
- `fix/sync-led-codes`
- `fix/use-python-dotenv-parsing`

## Phase 2: Prune Redundant & Obsolete Branches
The following branches are either:
1.  Effective duplicates of merged code (same logic, different commit hash).
2.  Older/messier versions of feature branches listed in Phase 3.
3.  Contain very minor fixes already addressed in `main`.

**Recommend Deletion:**
- `cursor/fix-issue-20` (Logic exists in `main`)
- `cursor/fix-issue-23` (Logic exists in `main`)
- `cursor/fix-issue-24` (Logic exists in `main`)
- `cursor/fix-issue-25` (Logic exists in `main`)
- `cursor/fix-issue-27` (Superseded by `feat/firmware-notifications`)
- `cursor/fix-issue-28` (Superseded by `feat/issue-28-state-manager-config`)
- `cursor/fix-issue-29` (Superseded by `docs/issue-29-roadmap`)
- `cursor/fix-ping-parsing` (Duplicate of merged fix)
- `fix/ping-rtt-parsing` (Duplicate)
- `fix-ping-timeout-truncation` (Duplicate)
- `fix/issue-26-httpx-dependency` (Duplicate of `fix/add-httpx-dependency`)
- `fix-test-deps-httpx` (Duplicate)
- `feat/issue-27-firmware-notification` (Messy mix, use `feat/firmware-notifications`)
- `feat/supervisor-yaml-config` (Duplicate of `feat/issue-28...`)
- `fix/host-config-parsing` (Duplicate of `feat/issue-28...`)
- `fix/api-timestamp-robustness` (Likely covered by recent reviews)
- `fix/cognition-json-extraction` (Likely covered by recent reviews)
- `fix/ml-service-and-io` (Likely covered by `fix/reduce-history-io`)
- `fix/service-runner-improvements` (Likely covered by `fix/safer-service-dispatch`)
- `fix/usb-backend-errors` (Likely covered by recent reviews)
- `fix-service-runner-env` (Likely covered by `fix/use-python-dotenv-parsing`)

## Phase 3: Merge Active Feature Branches
These branches contain distinct, valuable work that should be merged into `main` sequentially.

1.  **Firmware Notifications**
    - **Branch:** `feat/firmware-notifications`
    - **Feature:** Adds notification queue to `StateMachine` and LED effects.
    
2.  **State Manager Config**
    - **Branch:** `feat/issue-28-state-manager-config`
    - **Feature:** Adds `from_config` YAML parsing to `StateManager`.

3.  **Project Roadmap**
    - **Branch:** `docs/issue-29-roadmap`
    - **Feature:** Adds `ROADMAP.md`.

4.  **Generative Art & Channels**
    - **Branch:** `feat/issue-38-channel-daemon` (Base)
    - **Branch:** `feat/issue-39-generative-scene-channels` (Dependent)
    - **Feature:** Implements Channel Daemon and updates Generative Scene to use it.

5.  **SPI Partial Updates**
    - **Branch:** `feat/spi-partial-updates`
    - **Feature:** Optimizes e-paper updates.

## Execution Steps

1.  **Approve Phase 1 & 2:** Confirm deletion of these branches to clear noise.
2.  **Review & Merge Phase 3:** I will create Pull Requests (or merge directly if preferred) for each feature group in order.
