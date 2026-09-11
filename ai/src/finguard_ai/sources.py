"""Download allowlisted original pages locally; never execute page content."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from finguard_ai.corpus import load_manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    args = p.parse_args()
    manifest = Path(args.manifest)
    dest = manifest.parent / "raw"
    dest.mkdir(exist_ok=True)
    snapshots = []
    for url in dict.fromkeys(m.source_url for _, m, _, _ in load_manifest(manifest)):
        # System curl uses the host trust store (some managed hosts use an enterprise CA).
        with tempfile.TemporaryDirectory() as temp:
            download = Path(temp) / "source.html"
            subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--location",
                    "--proto",
                    "=https",
                    "--proto-redir",
                    "=https",
                    "--max-time",
                    "30",
                    "--max-filesize",
                    "4000000",
                    "--output",
                    str(download),
                    url,
                ],
                check=True,
            )
            data = download.read_bytes()
        if b"<html" not in data.lower():
            raise ValueError("Expected original HTML page")
        digest = hashlib.sha256(data).hexdigest()
        (dest / (digest + ".html")).write_bytes(data)
        snapshots.append(
            {
                "url": url,
                "sha256": digest,
                "bytes": len(data),
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    (manifest.parent / "source-snapshots.json").write_text(json.dumps(snapshots, indent=2) + "\n")
    print(f"Downloaded {len(snapshots)} source pages")


if __name__ == "__main__":
    main()
