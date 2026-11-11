"""The Launcher's MVP 2005 dynasty conversion (dynasty05) checked against outputs that loaded in the game.

Put the reference saves in a folder under the names in test_vectors.json (only the mvp05/ ones are used), then:
    python tools/saves/mvp05/tests/run_tests.py <that folder>
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import dynasty05 as D  # noqa: E402

V = json.load(open(os.path.join(HERE, "test_vectors.json")))
sha1 = lambda b: hashlib.sha1(b).hexdigest()  # noqa: E731


def main(ref):
    read = lambda rel: open(os.path.join(ref, rel), "rb").read()  # noqa: E731
    ok, outs = True, {}
    for rel, info in V["inputs"].items():
        if rel.startswith("mvp05/") and sha1(read(rel)) != info["sha1"]:
            sys.exit(f"{rel} isn't the reference save")
    for c in V["cases"]:
        if c["game"] != "mvp05":
            continue
        a = c["args"]
        src = outs["t1"] if a[0] == "<t1 output data.dat>" else read(a[0])
        name = a[a.index("--name") + 1] if "--name" in a else None
        if c["direction"] == "gc-to-xbox":
            out = D.gc_to_xbox(src, read(a[1]), name=name)
        else:
            out = D.xbox_to_gc(src, read(a[1]), name=name)[1]
        outs[c["id"]] = out
        good = sha1(out) == c["file_sha1"]
        ok &= good
        print(f"{c['id']} {c['direction']:<11} {'OK' if good else 'DIFFERENT'}")
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) if len(sys.argv) > 1 else __doc__)
