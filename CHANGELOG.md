# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

### Added

### Changed

### Fixed

### Removed

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
