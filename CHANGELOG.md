# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [unreleased]

### Added

### Changed

- Migrate schema conversion from voluptuous-openapi to probatio (aligns with
  HA core 2026.9.1); minimum HA version raised to 2026.9.1

### Fixed

### Removed

- Drop the voluptuous-openapi dependency

## [0.1.4] - 2026-09-07

### Added

- Add voluptuous-openapi requirement for OpenAPI schema support
