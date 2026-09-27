"""Every integrity= hash must match the file it pins.

A mismatch is invisible to every other check in this repository. The template
stays valid, the route still returns 200, the file is still served - and the
browser silently refuses to execute the script. When that happened to
alpine.min.js the entire front end went inert: no dropdowns, no modals, no icons,
and nothing in the server log to suggest anything was wrong.

Two different causes have produced it here, and they need opposite fixes, which
is why this test compares against the committed bytes rather than the working
copy:

  * chart.umd.min.js was replaced without regenerating its hash. The file is
    canonical; the hash was simply stale, and had been wrong since the file
    arrived. Fix: rehash from the file.
  * alpine/purify/lucide were fine, but a Windows checkout rewrote them to CRLF
    under `* text=auto`, changing every byte and so every hash. Fix: pin them
    `-text` in .gitattributes. Rehashing against the CRLF copies would have made
    a Windows checkout work and broken every Linux deploy, production included.

The distinction is: does the file on disk match what git has stored? If yes, the
hash is stale. If no, the checkout mangled the file and the hash is fine.
"""

import base64
import glob
import hashlib
import io
import os
import re
import subprocess

SRI = re.compile(
    r'src="([^"]*?/static/([\w./\-]+))"[^>]{0,300}?integrity="sha384-([A-Za-z0-9+/=]+)"',
    re.S,
)


def _sha384(data):
    return base64.b64encode(hashlib.sha384(data).digest()).decode()


def _pins():
    for path in sorted(glob.glob("app/templates/**/*.html", recursive=True)):
        src = io.open(path, encoding="utf-8", errors="ignore").read()
        for _url, rel, want in SRI.findall(src):
            yield path, rel, want


def test_every_integrity_hash_matches_its_file():
    mismatches = []
    checked = 0
    for template, rel, want in _pins():
        asset = os.path.join("app/static", rel)
        if not os.path.exists(asset):
            continue
        checked += 1
        if _sha384(open(asset, "rb").read()) != want:
            mismatches.append("%s pinned in %s" % (rel, template))

    assert checked, "no integrity-pinned assets found - has the markup changed?"
    assert not mismatches, (
        "%d asset(s) will be REFUSED by the browser:\n  %s\n\n"
        "Check whether the file matches git first: if it does, the hash is stale "
        "and should be regenerated; if it does not, the checkout rewrote the file "
        "and .gitattributes needs to pin it -text." % (len(mismatches), "\n  ".join(mismatches))
    )


def test_pinned_assets_are_not_line_ending_normalised():
    """The committed bytes must equal the bytes on disk.

    If they differ, `* text=auto` has rewritten a hash-pinned file for this
    platform, and every integrity attribute pointing at it is wrong here while
    remaining right everywhere else - a failure only some developers ever see.
    """
    drifted = []
    for _template, rel, _want in _pins():
        asset = os.path.join("app/static", rel)
        if not os.path.exists(asset):
            continue
        blob = subprocess.run(
            ["git", "show", "HEAD:app/static/" + rel], capture_output=True
        ).stdout
        if not blob:
            continue
        if blob != open(asset, "rb").read():
            drifted.append(rel)

    assert not drifted, (
        "%d hash-pinned asset(s) differ from their committed bytes: %s\n"
        "This is line-ending normalisation. Add them to .gitattributes as -text; "
        "do NOT regenerate the hashes, which would break every other platform."
        % (len(drifted), sorted(set(drifted)))
    )
