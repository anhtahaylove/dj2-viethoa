"""Translate a .lang source into an exact key->Vietnamese JSON map."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

PROMPT = r'''Translate these Minecraft 1.12.2 localization values from English to natural, concise Vietnamese.
Return ONLY one valid JSON object mapping every exact input key to its translation. No markdown.
Rules:
- Preserve every input key exactly and include each once.
- Preserve the exact ordered sequence/count of all placeholders (%n, %%, %s, %d, positional variants), section-sign formatting codes, and URLs.
- Preserve official item/block/mod/mob/dimension/multiblock/enchantment/proper names in English for JEI and Wiki lookup.
- Translate explanatory prose, instructions, statuses and descriptions only.
- No raw line breaks inside values. Do not invent mechanics.

INPUT JSON:
'''

# Minecraft placeholders. Require a real conversion type immediately after
# optional flags/width; do not misclassify prose such as "100% and" or "50% slower".
FORMAT = re.compile(r"%(?:n|%|(?:\d+\$)?[-#+0,(<]*\d*(?:\.\d+)?[bBhHsScCdoxXeEfgGaAtT])")
COLOR = re.compile(r"§.")
URL = re.compile(r"https?://.*?(?=%n|\s|§|$)")


def parse_lang(path: Path) -> dict[str, str]:
    result = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if raw and not raw.startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            result[key] = value
    return result


def tokens(value: str):
    return FORMAT.findall(value), COLOR.findall(value), URL.findall(value)


def decode_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--chunk", type=int, default=14)
    args = parser.parse_args()
    source = parse_lang(Path(args.source))
    output_path = Path(args.output)
    result = {}
    if output_path.exists():
        result = json.loads(output_path.read_text(encoding="utf-8"))
        result = {key: value for key, value in result.items() if key in source and tokens(source[key]) == tokens(value)}
    pending = [key for key in source if key not in result]
    for pos in range(0, len(pending), args.chunk):
        keys = pending[pos : pos + args.chunk]
        batch = {key: source[key] for key in keys}
        cp = subprocess.run(
            ["hermes", "-z", PROMPT + json.dumps(batch, ensure_ascii=False), "--cli", "--ignore-user-config", "--ignore-rules", "--safe-mode", "-t", ""],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=900,
        )
        if cp.returncode:
            raise RuntimeError(cp.stderr + cp.stdout)
        translated = decode_json(cp.stdout.strip())
        if set(translated) != set(batch):
            raise RuntimeError(f"key mismatch at chunk {pos}: missing={set(batch)-set(translated)}, extra={set(translated)-set(batch)}")
        unsafe = [
            key for key, value in translated.items()
            if not isinstance(value, str) or tokens(source[key]) != tokens(value)
        ]
        if unsafe:
            # Model retries can repair a whole batch, but should not discard the
            # already validated checkpoints from previous batches.
            for key in unsafe:
                translated.pop(key, None)
            result.update(translated)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            raise RuntimeError(f"unsafe token sequence; retry resumably: {unsafe}")
        result.update(translated)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(result)}/{len(source)}", flush=True)
    if set(result) != set(source):
        raise RuntimeError("final key mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
