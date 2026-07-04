<!-- PROJECT LOGO -->
<div align="center"><pre>
███╗░░██╗███████╗██╗░░██╗██╗░░░██╗░██████╗
████╗░██║██╔════╝╚██╗██╔╝██║░░░██║██╔════╝
██╔██╗██║█████╗░░░╚███╔╝░██║░░░██║╚█████╗░
██║╚████║██╔══╝░░░██╔██╗░██║░░░██║░╚═══██╗
██║░╚███║███████╗██╔╝╚██╗╚██████╔╝██████╔╝
╚═╝░░╚══╝╚══════╝╚═╝░░╚═╝░╚═════╝░╚═════╝░
</pre>
  <h1 align="center">Nexus HACS Integration</h1>
  <p align="center">
    <strong>Nexus</strong> is a powerful, extensible AI voice assistant platform designed for personal and home automation use.
    <br />
    <br />
    📘&nbsp;<a href="https://docs.futureproofhomes.net/ai-base-station-introduction"><strong>Explore the docs</strong></a>
    &nbsp;·&nbsp;
    🍿&nbsp;<a href="https://www.youtube.com/@futureproofhomes">View Demos</a>
    &nbsp;·&nbsp;
    🐛&nbsp;<a href="https://github.com/ms1design/nexus-hacs-integration/issues/new?labels=bug&template=bug.yml">Report Bug</a>
    &nbsp;·&nbsp;
    💡&nbsp;<a href="https://github.com/ms1design/nexus-hacs-integration/issues/new?labels=enhancement&template=feature_request.yml">Request Feature</a>
  </p>
  <p>⭐ <b>Star us on GitHub</b> — it motivates us a lot!</p>
</div>

<br/>

[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/futureproofhomes/nexus-hacs-integration)](https://github.com/ms1design/nexus-hacs-integration/releases)

## Overview

Nexus is a Home Assistant custom integration that connects your home to the **Nexus AI Base Station** — a private, open-source, locally-run AI voice assistant built by [FutureProofHomes](https://futureproofhomes.com).

Where Alexa listens and sells, where Google Home guesses and forgets — Nexus *understands*. Through a native **Model Context Protocol (MCP)** bridge, Nexus pulls live context from every light, climate zone, shutter, and media player into a structured, real-world map of your home. Everything stays local. Your voice, your schedule, your habits — behind your firewall.

This integration replaces the legacy STT/TTS pipeline with a pure text-based conversation engine, enriched with home context (area, floor, user identity, sensors) so the assistant knows *where* and *who* it's talking to.

## Key Differences vs. Native `openai_conversation`

| Feature | Native HA OpenAI | Nexus |
|---------|-----------------|-------|
| **Backend** | Cloud LLM API | Local Nexus AI Base Station |
| **Privacy** | Data leaves your network | Zero cloud — everything stays local |
| **Legacy STT/TTS** | Assumed built-in | Handled via Wyoming protocol separately |
| **Context enrichment** | Basic (area name only) | Area name, floor name, user identity, sensor data |
| **Structured output** | Limited | Full JSON schema generation via AI Tasks |
| **Zero-conf discovery** | None | mDNS/zeroconf auto-discovery of Nexus servers |

### Context Enrichment Detail

When a conversation is initiated through Nexus, the integration resolves:

- **Area name & floor** — from the Home Assistant area/device registry, injected into the system prompt so the assistant knows the physical context.
- **User identity** — resolved from the authenticating user's account, enabling personalized interactions.
- **Sensor data** — ambient sensors tied to the active area (light, humidity, presence) are surfaced to the model as context.

These enrichments happen transparently before the request reaches Nexus — no prompt manipulation required.

## Features

- **Conversation Agent** — Full Responses API support (streaming, tool calls, reasoning)
- **AI Tasks** — Structured data generation with JSON schema output
- **Zero-conf Discovery** — mDNS auto-discovers Nexus servers on the local network
- **Parent/Sub-entry Config** — One API key, multiple conversation agents and AI tasks

## Installation

### HACS (Recommended)

1. Open HACS → Integrations → "+" → **Explore & Download Repositories**
2. Search for **"Nexus"** or add this repository: `https://github.com/ms1design/nexus-hacs-integration`
3. Click **Download** and restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration** → search for **"Nexus"**

### Manual

1. Download the latest release
2. Copy the `nexus_conversation` folder into your `custom_components/` directory
3. Restart Home Assistant

## Configuration

After installing, add the Nexus integration through the HA UI:

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Nexus"**
3. Choose one of:
   - **Manual** — enter your Nexus endpoint URL and API key
   - **Auto-discover** — click a Nexus server found on your network (requires Nexus server broadcasting via mDNS)

### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `base_url` | Nexus API endpoint | `http://<NEXUS_HOST>:5015/home-assistant/v1` |
| `api_key` | Your API key | `sk-1` |

## Setting Up Nexus

For a complete end-to-end setup:

1. **Start Nexus OS** — Flash the **Nexus AI Base Station** ISO to an NVMe drive and run `nexus up`. Nexus broadcasts itself on the network via mDNS and will be auto-discovered by Home Assistant.
2. **Install this HACS Integration** — as described above
3. **Configure the Conversation Agent** — discover Nexus via zeroconf or enter the endpoint manually
4. **Activate the MCP Server** — add the Home Assistant MCP Server integration to expose LLM Tools for Nexus
5. **Connect STT & TTS** — configure Wyoming STT/TTS integrations with your Nexus host
6. **Configure Assist Pipeline** — route your default pipeline through the Nexus Conversation Agent

## Debug Logging

Enable debug output in `configuration.yaml`:

```yaml
logger:
  default: warn
  logs:
    custom_components.nexus_conversation: debug
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Credits

Built by the [FutureProofHomes Team](https://futureproofhomes.com) with inspiration from [Home Assistant](https://www.home-assistant.io/) and the [openai_conversation](https://www.home-assistant.io/integrations/openai_conversation) core integration.
