# Preparing a local publication

The Git files contain original data bytes, either directly or in lossless
ZIPs. Git LFS, download placeholders, symlinks, and submodule pointers are
not used. Keep archives below 95 MiB to leave room under GitHub's 100 MiB
per-file limit. Restored databases are local installations; their ZIPs are
the publishable payloads.

Run these checks from the repository root:

```sh
python scripts/check_publication.py --worktree
python workspace_setup.py --verify
python launch_srd46_browser.py --check
```

Review `git status` and `git diff` before staging the intended changes.
Then verify the actual staged bytes:

```sh
python scripts/check_publication.py --index
```

Install the local publication hook after cloning:

```sh
git config --local core.hooksPath .githooks
```

The pre-push hook checks each outgoing tip and newly introduced Git objects
for LFS pointers, symlinks/submodules, and oversized files. It does not upload
anything itself. If the remote base commit is unavailable locally, fetch it
before retrying; the checker will not silently omit the history check.
Historical pointers already on the remote are not introduced again by a
normal update, but a new remote or branch can expose them. A failed check
must be resolved without substituting pointers or silently rewriting history.

`__tmp__/` holds local backups and verification reports and is ignored.
Generated diagnostic logs/caches are excluded; maintained tests, source
prompts, reference answers, and published scientific outputs are retained.
Only an explicit user request authorizes a push.
