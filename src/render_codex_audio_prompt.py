#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the endpoint-specific prompt for a headless Codex audio run."
    )
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--date", required=True, help="ISO date, e.g. 2026-03-29")
    parser.add_argument("--vault-root", required=True)
    return parser.parse_args()


def load_endpoints() -> dict[str, dict[str, object]]:
    config_path = Path(__file__).resolve().with_name("obsidian_audio_routing_endpoints.json")
    return json.loads(config_path.read_text())


def render_target_path(template: str, date: str, slug: str | None) -> str:
    values = {"date": date, "slug": slug or "{slug}"}
    return template.format(**values)


def build_agentic_prompt(
    endpoint: str,
    config: dict[str, object],
    audio: Path,
    target_path: str,
    vault_root: Path,
    date: str,
) -> str:
    routing_mode = str(config.get("routing_mode") or "daily_note")
    speaker_mode = str(config.get("speaker_mode") or "single")
    section_heading_template = config.get("section_heading_template")
    section_heading_style = config.get("section_heading_style")
    lines = [
        "Process this audio capture for the Obsidian vault.",
        f"Endpoint: {endpoint}",
        "Workflow: agentic",
        f"Audio file: {audio}",
        f"Obsidian vault root: {vault_root}",
        f"Recording date: {date}",
    ]
    if routing_mode == "primary_person":
        lines.append(f"Target markdown path pattern: {vault_root / target_path}")
    else:
        lines.append(f"Target markdown path: {vault_root / target_path}")
    if section_heading_template:
        lines.append(f"Target section heading template: {section_heading_template.format(date=date)}")
    if section_heading_style:
        lines.append(f"Target section heading style: {section_heading_style}")
    lines.append("Task:")
    lines.extend(
        [
            "- Edit the Obsidian vault in place.",
            "- Preserve important proper nouns, references, and ideas from the audio.",
            "- Do not include audio-file backlinks or attachment references in the markdown.",
        ]
    )
    if routing_mode == "primary_person":
        lines.extend(
            [
                "- Infer one primary person from the recording.",
                "- Use that person to choose the final note path under the `people/` directory, using a lowercase hyphenated slug for the filename.",
                f"- Copy the source `.m4a` into `{vault_root / 'audio'}` as `<primary-person-slug>-{date}.m4a`.",
                f"- Create or update a `## {date}` section in that person note.",
                "- Preserve the rest of the person note if it already exists.",
            ]
        )
    else:
        lines.extend(
            [
                "- Listen to or transcribe the audio and synthesize it into a coherent markdown section for the daily note.",
                "- Write directly into the target daily note.",
                "- Title the section as an H2 using a few-word summary of the réflexion and append `#reflection` on that same heading line.",
                f"- Copy the source `.m4a` into `{vault_root / 'audio'}` as `<section-summary-slug>-{date}.m4a`.",
            ]
        )
    if speaker_mode == "multi":
        lines.extend(
            [
                "- Treat this as a multi-speaker conversation or meeting.",
                "- Preserve distinctions between speakers when synthesizing decisions, viewpoints, and follow-ups.",
                "- Do not collapse separate commitments or disagreements into a single voice.",
                "- If exact names are unclear, preserve role separation without inventing identities.",
            ]
        )
    else:
        lines.extend(
            [
                "- Preserve the first-person voice and internal structure when useful.",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    endpoints = load_endpoints()
    if args.endpoint not in endpoints:
        valid = ", ".join(sorted(endpoints))
        raise SystemExit(f"Unknown endpoint `{args.endpoint}`. Valid endpoints: {valid}")

    endpoint_config = endpoints[args.endpoint]
    audio_path = Path(args.audio).expanduser().resolve()
    vault_root = Path(args.vault_root).expanduser().resolve()
    target_path = render_target_path(
        str(endpoint_config["target_path_template"]),
        date=args.date,
        slug=None,
    )
    workflow = str(endpoint_config["workflow"])

    if workflow != "agentic":
        raise SystemExit(f"Unsupported workflow `{workflow}` for endpoint `{args.endpoint}`.")
    prompt = build_agentic_prompt(args.endpoint, endpoint_config, audio_path, target_path, vault_root, args.date)

    print(prompt)


if __name__ == "__main__":
    main()
