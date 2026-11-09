"""Build a student-only ZIP from an explicit file list, excluding all user state."""
from pathlib import Path
import argparse, hashlib, json, zipfile
ROOT = Path(__file__).resolve().parents[1]
STAMP = "20261109_1452"
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    files = {"LICENSE": (ROOT / "LICENSE").read_bytes()}
    for name in ["course.mjs", "web.html", "开始使用.command", "开始使用.cmd", "README.md"]:
        files[name] = (ROOT / "student-native" / name).read_bytes()
    paths = ["agents/eg-student-feedback/SOUL.md"]
    for skill in ["eg-authenticity-anchor", "eg-report-feedback"]:
        paths.extend("skills/" + skill + "/" + tail for tail in [
            "SKILL.md", "references/midterm-policy_20261109_1452.md",
            "references/scoring-anchors_20261021_2036.md"
        ] if (ROOT / "skills" / skill / tail).exists())
    paths.extend("schemas/midterm-" + s + ".schema.json" for s in ["submission", "gate", "feedback"])
    for rel in paths:
        files["payload/" + rel] = (ROOT / rel).read_bytes()
    manifest = {"version": STAMP, "agent": "eg-student-feedback",
                "skills": ["eg-authenticity-anchor", "eg-report-feedback"],
                "model": "deepseek-flash", "openclaw": "2026.7.1-2",
                "files": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())}}
    files["MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, content in sorted(files.items()):
            info = zipfile.ZipInfo("eg-student-kit_" + STAMP + "/" + rel, (2026, 11, 9, 14, 52, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if rel.endswith(".command") else 0o100644) << 16
            z.writestr(info, content)
    print(json.dumps({"zip": str(args.output), "files": len(files),
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))
if __name__ == "__main__":
    main()
