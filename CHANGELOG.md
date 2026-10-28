# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

### Added

- Conversation requests carry `device_id` and `satellite_id` request metadata
  (resolved from the pipeline's satellite) so the Nexus Server can scope MCP
  tool lists and tool calls to the requesting assist satellite — unlocks the
  Home Assistant timer tools (`HassStartTimer`, …) over MCP on HA ≥ 2026.10
  without changing the transport.

### Changed

- Request `metadata` values (area/floor names are user-editable) are truncated
  to the OpenAI 512-char value limit instead of risking a hard request failure.
- Sync the OpenAI wire protocol with `openai_conversation` 2026.10.0:
  tool call results now carry the `error` flag to the model
  (`{"data": ..., "error": ...}`), code interpreter calls round-trip as
  native `code_interpreter_call` items instead of `function_call_output`,
  and explicit empty assistant messages (silent after a tool call) are
  preserved instead of erroring
- Structured output schemas are hardened against OpenAI's supported JSON
  Schema subset (ported from upstream `schema.py`): `$ref`/`$defs`
  stabilization, `allOf` flattening, nullable via `anyOf` wrapper, and
  `strict: true` set at the `text.format` level; `to_openapi` now emits
  OpenAPI 3.1.0
- Drop the `include: ["reasoning.encrypted_content"]` request field, which
  OpenAI no longer requires (the deprecated `user` request parameter is
  kept for now)

### Fixed

- The flex service-tier fallback now actually resends the request with
  `service_tier: default` — it previously mutated a stale copy of the
  request args, so the retry went out unchanged until the iteration
  limit was hit and returned silently with no content
- Replace deprecated `ToolResultContent.tool_result` accesses with
  `ToolResultContent.result.data` and yield tool result deltas as
  `llm.ToolResult` (`result` key) — the old spellings log a deprecation
  warning since HA 2026.10 and stop working in HA 2027.11
- Raise the minimum Home Assistant version to 2026.10.0, where the
  `ToolResultContent.result` API was introduced
- Point `documentation` and `issue_tracker` in the manifest, and the config
  flow's `instructions_url`, at `FutureProofHomes/nexus-hacs-integration`,
  and move the manifest `codeowners` to `@FutureProofHomes` — the previous
  URLs pointed at a repository that no longer exists, so HA's "create a bug
  report" links were dead
- The setup form no longer fails with a generic "Unknown error" when the
  base URL is missing its `/v1` suffix: the suffix is appended
  automatically (the stored entry keeps the normalized URL), and a
  genuinely invalid URL now shows a field-level error under the Base URL
  field instead of only in the log

### Removed

- The deprecated `nexus_conversation.generate_content` action and its
  `services.yaml`, service icon, `invalid_config_entry` exception string
  and translation entries — announced for removal in 2026.9.0
  and removed by upstream `openai_conversation` in 2026.10.0; use
  `ai_task.generate_data` instead

## [0.2.1] - 2026-10-26

### Added

- Honour the `scheme` TXT record of the `_nexus._tcp` announcement when
  building the base URL (default `http`); the discovered port now comes from
  the advertisement instead of being hardcoded to 5015
- Discovery cards show the per-device mDNS instance name (e.g.
  `Nexus (nexus-f5cfcb57)`) so multiple appliances on one LAN are
  distinguishable

### Changed

- Manual setup default base URL points at the appliance proxy edge
  (`http://<NEXUS_IP>:80/v1`); the TLS-only backend port is no longer a
  usable plain-HTTP target

### Fixed

- Classify every httpx transport failure as a connection problem — a
  TLS-only backend dropping plain-HTTP probes (`RemoteProtocolError`) no
  longer surfaces as an "Unexpected exception" traceback
- Already-configured devices abort discovery quietly (unique-id match plus
  endpoint matching including DNS-resolved addresses), instead of showing
  the card again after every HA restart
- Unreachable devices abort discovery with `cannot_connect` instead of
  creating a config entry that can never load

## [0.2.0] - 2026-10-22

### Changed

- Remove the `/home-assistant` URL prefix from Nexus API endpoints; the base
  URL is now `http://<host>:5015/v1` (config flow default, validation, and
  zeroconf discovery) — manually configured `base_url` values must be updated

## [0.1.5] - 2026-09-07

### Changed

- Migrate schema conversion from voluptuous-openapi to probatio (aligns with
  HA core 2026.9.1); minimum HA version raised to 2026.9.1

### Removed

- Drop the voluptuous-openapi dependency

## [0.1.4] - 2026-09-07

### Added

- Add voluptuous-openapi requirement for OpenAPI schema support

## [0.1.3] - 2026-08-10

### Changed

- Bump openai SDK minimum version to >=2.45.0

## [0.1.2] - 2026-07-09

### Changed

- Clean up lint warnings: move imports to TYPE_CHECKING blocks, extract string literals before raises, fix exception chaining

## [0.1.1] - 2026-07-09

### Fixed

- Improve server error message display (#?)
- Remove trailing space from integration name in manifest

### Changed

- Simplify model defaults and update branding
- Disable scheduled validation workflow runs
- Update GitHub URLs to futureproofhomes organization

### Docs

- Add release process to AGENTS.md
- Update README.md
