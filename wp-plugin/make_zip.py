import zipfile
import os

here = os.path.dirname(os.path.abspath(__file__))
base = os.path.join(here, "dicha-sync-v3")
out = os.path.join(here, "dicha-sync-v3.zip")

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(base):
        for f in files:
            if f == "README.md":
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            arcname = "dicha-sync-v3/" + rel
            zf.write(full, arcname)
            print(f"  + {arcname}")

print("\nVerifying ZIP contents:")
with zipfile.ZipFile(out, "r") as zf:
    for name in zf.namelist():
        print(f"  {name}")

print("\nChecking main plugin file for BOM or issues...")
with zipfile.ZipFile(out, "r") as zf:
    content = zf.read("dicha-sync-v3/dicha-sync-v3.php")
    first_bytes = content[:20]
    print(f"  First bytes: {first_bytes}")
    if content[:3] == b"\xef\xbb\xbf":
        print("  WARNING: BOM detected!")
    elif content[:5] == b"<?php":
        print("  OK: starts with <?php (no BOM)")
    else:
        print(f"  WARNING: unexpected start: {content[:10]}")
