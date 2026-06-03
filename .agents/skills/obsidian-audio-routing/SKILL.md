---
name: obsidian-audio-routing
description: Use this skill when routing or processing renamed Voice Memos audio into the Obsidian vault for the agentic endpoints `monde` and `réflexion`, or when generating the exact prompt for a headless `codex exec` audio-processing run.
---

# Obsidian Audio Routing

## Overview

This skill defines the routing contract for agentic audio captured in Voice Memos and renamed before it is handed to a headless Codex run.

Use it when you need to:

- choose between the `monde` and `réflexion` endpoints
- resolve the target markdown path pattern deterministically
- generate a prompt for `codex exec` that matches the endpoint contract exactly

## Routing Model

This skill is only for the agentic endpoints:

- `monde`
- `réflexion`

Recordings should be routed by renaming the Voice Memo title to exactly `monde` or `réflexion`.

## Endpoint Source Of Truth

In this repo, read `src/obsidian_audio_routing_endpoints.json` for the exact endpoint contract:

- target directory
- target path template
- target section heading when applicable
- target heading style when the section title is dynamic
- whether the workflow is `agentic`
- speaker handling requirements for agentic endpoints

Do not invent new endpoints or change path templates ad hoc.

## Prompt Generation

In this repo, use `src/render_codex_audio_prompt.py` to build the exact prompt for a headless Codex run.

Example:

```bash
python src/render_codex_audio_prompt.py \
  --endpoint monde \
  --audio /abs/path/to/file.m4a \
  --date 2026-03-29 \
  --vault-root /abs/path/to/obsidian
```

The script prints a prompt that can be fed directly to `codex exec`.

## Output Rules

For `monde` and `réflexion`:

- follow the endpoint contract exactly for whether the output is a people note section or a section inside an existing daily note
- create coherent markdown from the audio, not a raw transcript dump
- preserve a concise structure suitable for long-term reuse

For `monde` specifically:

- assume a multi-speaker conversation or meeting
- infer one primary person and write to `people/{slug}.md`
- create or update a `## YYYY-MM-DD` section in that person note
- preserve distinctions between speakers when synthesizing decisions, viewpoints, and follow-ups

For `réflexion` specifically:

- assume a single-speaker réflexion by default
- do not introduce diarization or speaker labels unless the audio clearly contains another voice
- write the output directly into the dated daily note
- title the section as `## <few-word summary> #reflection`
- keep the réflexion body as plain markdown content rather than cross-note backlinks or references

## Guardrails

- Prefer deterministic path resolution over inferred file locations.
- Do not use this skill for the simple Siri transcription inboxes.
- For agentic endpoints, do not collapse the note into raw bullets unless the audio itself is already structured that way.
- If endpoint metadata is missing, fix `src/obsidian_audio_routing_endpoints.json` rather than encoding one-off rules into the prompt.
