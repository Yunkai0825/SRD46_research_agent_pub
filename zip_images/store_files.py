"""
zip_images.store_files -- the helper files written next to the zips: the unpacker, the shell setup script,
a Dockerfile that builds from the zips alone, its .dockerignore and a README for whoever receives the folder.
===========================================================================================================

They are regenerated for the manifest that ``latest.json`` points to at every ``pack`` that moves latest.
Shell scripts and the Dockerfile are written with LF line ends (a CR breaks /bin/sh and Docker's parser).
The unpacker is copied from THIS package (the tool), never from the packed repository's working tree.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
from pathlib import Path

from .environment import REVISION_LABEL
from .unpack_images import (KIND_WHEELS, LATEST_NAME, MANIFESTS_DIR, RECORDS_DIR, STATE_DIR, VENV_DIR, ZIPS_DIR, mb,
                            record_name, write_atomic)

HERE = Path(__file__).absolute().parent
UNPACKER = "unpack_images.py"
SETUP_SH = "setup_from_zips.sh"
DEFAULT_DEST = "/app"
IMAGE_NAME = "myapp"                          # the image / container name the README's commands use
GUIDE_FILES = ("MOUNTING.md", "DOCKER.md")    # top-level guides of the packed tree the README points to


def _lf(text: str) -> bytes:
    return text.replace("\r\n", "\n").encode("utf-8")


def _crlf(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def unpacker_bytes() -> bytes:
    return _lf((HERE / UNPACKER).read_bytes().decode("utf-8"))


SETUP_TEXT = r"""#!/bin/sh
# setup_from_zips.sh -- build (or update) the application folder from the zip images next to this script.
#
#   sh setup_from_zips.sh                 unpack into ./app next to this script, install the Python packages
#   sh setup_from_zips.sh /srv/app        ... into /srv/app instead
#   sh setup_from_zips.sh /srv/app --env offline     use the packed wheels (images made with `pack --wheels`)
#   sh setup_from_zips.sh /srv/app --env none        files only, no Python packages
#
# Run it again after newer zips arrive: an existing folder is UPDATED (only changed parts are rewritten).
# Everything after the folder is passed to unpack_images.py (see: python3 unpack_images.py --help).
# Needs Python 3.8 or newer; nothing else (no git, no unzip).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
case "${1:-}" in
  ""|-*) DEST="$HERE/app" ;;
  *) DEST=$1; shift ;;
esac
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' 2>/dev/null; then
    PY=$c
    break
  fi
done
if [ -z "$PY" ]; then
  echo "setup_from_zips.sh: Python 3.8 or newer is needed (Debian/Ubuntu: apt-get install python3 python3-venv)" >&2
  exit 1
fi
if [ -f "$DEST/.zip_images/installed.json" ]; then
  echo "Updating $DEST from $HERE"
  exec "$PY" "$HERE/unpack_images.py" update --images "$HERE" --dest "$DEST" "$@"
fi
echo "Building $DEST from $HERE"
exec "$PY" "$HERE/unpack_images.py" install --images "$HERE" --dest "$DEST" "$@"
"""


def _env_line(pairs: list, extra: list = ()) -> list:
    out = []
    for k, v in list(pairs) + list(extra):
        quote = not v or any(ch in v for ch in " \t\"'$\\")
        out.append("ENV {}={}".format(k, json.dumps(v, ensure_ascii=False) if quote else v))
    return out


def _label_line(pairs: list) -> list:
    """LABEL lines; values are quoted and a ``$`` is escaped (a label value is text, not a variable)."""
    out = []
    for k, v in pairs:
        key = k if all(ch.isalnum() or ch in "._-/" for ch in k) else json.dumps(k, ensure_ascii=False)
        out.append("LABEL {}={}".format(key, json.dumps(str(v), ensure_ascii=False).replace("$", "\\$")))
    return out


def _arg_line(name: str, default) -> str:
    if default is None:
        return "ARG " + name
    quote = not default or any(ch in default for ch in " \t\"'$\\")
    return "ARG {}={}".format(name, json.dumps(default, ensure_ascii=False) if quote else default)


def _translate_path(text: str, old: str, new: str) -> str:
    """``text`` with the folder ``old`` replaced by ``new`` wherever it appears as a whole path prefix."""
    old = old.rstrip("/") or "/"
    new = new.rstrip("/") or "/"
    if old == new or old == "/":
        return text
    return re.sub(r"(?<![\w./-])" + re.escape(old) + r"(?=/|$|[^\w.-])", lambda m: new, text)


def _norm(path: str) -> str:
    return posixpath.normpath(path) if path else path


def _inside(path: str, folder: str) -> bool:
    path, folder = _norm(path), _norm(folder)
    return path == folder or path.startswith(folder.rstrip("/") + "/")


def tree_steps(tree: dict, dest: str) -> tuple:
    """The shell steps that replay a source tree stage on the unpacked folder ``dest``: (steps, outside) where
    ``steps`` = its RUN lines, then its copies, and ``outside`` = the copy destinations that lie outside
    ``dest`` (the final stage copies them from the unpack stage too)."""
    ctx = tree.get("context_dir") or dest
    steps, outside = [], []
    workdir = _translate_path(tree.get("workdir") or "/", ctx, dest)
    exports = ["export {}={}".format(k, shlex.quote(v)) for k, v in tree.get("env") or []
               if isinstance(k, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) and isinstance(v, str)]
    # The replay runs on the fresh verified archive tree, without source-build
    # named-context mounts. This explicit signal lets build helpers select their
    # no-Git image input; it does not become a runtime environment variable.
    exports.append("export ZIP_IMAGES_FRESH_TREE=1")
    for run in tree.get("run") or []:
        body = _translate_path(run, ctx, dest)
        pre = ([] if workdir in ("/", "") else ["cd " + shlex.quote(workdir)]) + exports
        steps.append("( {} )".format(" && ".join(pre + [body])))
    copies = []
    for cp in tree.get("copies") or []:
        src = _translate_path(cp.get("src") or "", ctx, dest)
        dst = _translate_path(cp.get("dst") or "", ctx, dest)
        if not src or not dst or _norm(src) == _norm(dst):
            continue                              # already in its place: the unpacked tree IS the tree stage
        copies.append((src, dst))
    for i, (src, dst) in enumerate(copies):
        s, t = shlex.quote(_norm(src)), shlex.quote(_norm(dst))
        if src.endswith("/"):
            step = "mkdir -p {1} && cp -a {0}/. {1}".format(s, t)
        else:
            parent = shlex.quote(_norm(dst) if dst.endswith("/") else (posixpath.dirname(_norm(dst)) or "/"))
            step = ("{{ if [ -d {0} ]; then mkdir -p {1} && cp -a {0}/. {1}; else mkdir -p {2} && cp -a {0} {1}; "
                    "fi; }}".format(s, t, parent))
        later = any(_inside(src, s2) or _inside(s2, src) for s2, _ in copies[i + 1:])
        if not _inside(src, dest) and not _inside(dest, src) and not later:
            step += " && rm -rf {}".format(s)     # a helper folder of the tree stage: not part of the image
        steps.append(step)
        if not _inside(dst, dest):
            outside.append(_norm(dst))
    return steps, outside


def dockerfile_text(manifest: dict, manifest_rel: str) -> str:
    env = manifest.get("environment") or {}
    d = env.get("docker") or {}
    workdir = d.get("workdir") or "/"
    dest = workdir if workdir not in ("/", "") else DEFAULT_DEST
    commit = manifest.get("commit", "?")
    base = d.get("base_image") or "python:{}-slim".format(env.get("python_version") or "3.12")
    apt = [p for p in d.get("apt_packages") or [] if p and all(ch.isalnum() or ch in "+-.:=_" for ch in p)]
    lf = env.get("large_files") if isinstance(env.get("large_files"), dict) else {}
    tree = d.get("tree_stage") if isinstance(d.get("tree_stage"), dict) else None
    rev_env = {k for k in d.get("revision_env") or [] if isinstance(k, str)}
    pairs = [p for p in d.get("env") or [] if isinstance(p, list) and len(p) == 2]
    argument_env = d.get("argument_env") or {}
    source_args = d.get("args") or {}
    release = any(f.get("path") == "docker/output_seed_manifest.json" for f in manifest.get("files", []))
    lines = [
        "# Generated by zip_images for {} (commit {}, {}).".format(manifest_rel, commit[:12],
                                                                  manifest.get("commit_date", "?")),
        "# Do not edit: `python -m zip_images pack` writes it again. Build it in THIS folder:",
        "#     docker build -t myapp .                          (Python packages from the internet)",
        "#     docker build -t myapp --build-arg ZIP_ENV=offline .   (the packed wheels; images made with --wheels)",
        "# The zips and their compartment records (the file rows) are the only input; they stay in the build stage",
        "# and are not part of the final image.",
        "",
        "FROM {} AS base".format(base),
    ]
    for name in sorted(set(argument_env.values())):
        lines.append(_arg_line(name, source_args.get(name)))
    for key, value in pairs:
        if key in rev_env:
            continue
        if key in argument_env:
            lines.append("ENV {}=${{{}}}".format(key, argument_env[key]))
        else:
            lines += _env_line([[key, value]])
    if apt:
        lines.append("RUN apt-get update \\\n    && apt-get install -y --no-install-recommends {} \\\n"
                     "    && rm -rf /var/lib/apt/lists/*".format(" ".join(apt)))
    install = ("python3 /zip_images/{} install --images /zip_images --manifest {} --dest {} --install venv{} "
               "${{ZIP_ENV:+--env \"$ZIP_ENV\"}}".format(UNPACKER, commit[:12], dest,
                                                       " --strip-large-parts" if lf.get("strip") is True else ""))
    if release:
        install = "CSTEEL_IMAGE_BUILD=1 " + install + " --image-tree"
    steps = [install, "rm -rf {}/{}/wheels".format(dest, STATE_DIR)]
    outside = []
    lines += ["", "FROM base AS unpack", "ARG ZIP_ENV="]
    if tree:
        for name, default in (tree.get("args") or {}).items():
            if isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                lines.append(_arg_line(name, None if name in argument_env.values() else (default if isinstance(default, str) else None)))
        more, outside = tree_steps(tree, dest)
        steps += more
    steps += ["chmod -R g=u {}".format(" ".join(shlex.quote(p) for p in [dest] + outside))]
    lines.append("COPY . /zip_images")
    if tree:
        lines.append("# One RUN (one layer): unpack{}, then the source's tree stage \"{}\" on the unpacked tree, "
                     "its copies, and group = owner permissions.".format(
                         " + strip the big files' zip parts" if lf.get("strip") is True else "", tree.get("name")))
    lines.append("RUN " + " \\\n    && ".join(steps))
    lines += ["", "FROM base", "COPY --from=unpack {} {}".format(dest, dest)]
    for path in outside:
        lines.append("COPY --from=unpack {} {}".format(path, path))
    lines.append("WORKDIR {}".format(dest))
    if pairs:
        lines.append("# The source's ENV lines are set in the base stage above (this stage inherits them).")
    lines += _env_line([], [("VIRTUAL_ENV", dest + "/" + VENV_DIR), ("PATH", dest + "/" + VENV_DIR + "/bin:$PATH")])
    replay = d.get("replay") or []
    if replay:
        lines.append("# The source Dockerfile's own steps, replayed on the unpacked tree:")
    for step in replay:
        if "run" in step:
            lines.append("RUN " + step["run"])
            continue
        src = dest if step["copy"] == "." else dest + "/" + step["copy"]
        to = step["to"]
        if step["dir"]:
            lines.append("RUN mkdir -p {0} && cp -a {1}/. {0}/".format(shlex.quote(to), shlex.quote(src)))
        else:
            lines.append("RUN mkdir -p {} && cp -a {} {}".format(shlex.quote(posixpath.dirname(to) or "/"),
                                                                 shlex.quote(src), shlex.quote(to)))
    lines += _label_line([p for p in d.get("labels") or [] if isinstance(p, list) and len(p) == 2
                          and p[0] != REVISION_LABEL])
    lines += _label_line([(REVISION_LABEL, commit)])
    lines += _env_line([p for p in pairs if p[0] in rev_env])
    volumes = [v for v in d.get("volumes") or [] if isinstance(v, str) and v]
    if volumes:
        lines.append("VOLUME " + json.dumps(volumes))
    for port in d.get("expose") or []:
        lines.append("EXPOSE {}".format(port))
    if d.get("healthcheck"):
        lines.append("HEALTHCHECK " + d["healthcheck"])
    if d.get("user"):
        lines.append("USER " + d["user"])
    if d.get("entrypoint"):
        lines.append("ENTRYPOINT " + json.dumps(d["entrypoint"]))
    if d.get("cmd"):
        lines.append("CMD " + json.dumps(d["cmd"]))
    return "\n".join(lines) + "\n"


def dockerignore_text(manifest: dict, manifest_rel: str) -> str:
    zips = sorted({q["file"] for c in manifest["compartments"] for q in c["parts"]})
    # format 2: the manifest file holds no file rows; the unpacker reads them from the compartment records
    records = sorted({record_name(c["key"]) for c in manifest["compartments"] if c.get("kind") != KIND_WHEELS})
    lines = ["# Generated by zip_images: the build context is the unpacker, the manifest, its compartment records and"
             " ITS zips only.", "*", "!" + UNPACKER, "!" + LATEST_NAME, "!" + manifest_rel]
    lines += ["!{}/{}".format(RECORDS_DIR, r) for r in records]
    lines += ["!{}/{}".format(ZIPS_DIR, z) for z in zips]
    return "\n".join(lines) + "\n"


def _volume_name(image: str, path: str) -> str:
    last = posixpath.basename(posixpath.normpath(path)) or "data"
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", "{}_{}".format(image, last))
    return name if re.match(r"[A-Za-z0-9]", name) else "v" + name


def docker_run_line(manifest: dict, name: str = IMAGE_NAME) -> str:
    """The ``docker run`` command of the generated README: detached, named, the first EXPOSE port on this
    computer only (127.0.0.1), one named volume per VOLUME of the source."""
    d = (manifest.get("environment") or {}).get("docker") or {}
    parts = ["docker", "run", "-d", "--name", name]
    port = str((d.get("expose") or [""])[0] or "").split("/")[0]
    if port.isdigit():
        parts += ["-p", "127.0.0.1:{0}:{0}".format(port)]
    for vol in d.get("volumes") or []:
        if isinstance(vol, str) and vol:
            parts += ["-v", "{}:{}".format(_volume_name(name, vol), vol)]
    return " ".join(parts + [name])


def guide_files(manifest: dict) -> list:
    """The top-level guide files of the packed tree (``MOUNTING.md``, ``DOCKER.md``) that the manifest lists."""
    have = {f.get("path") for f in manifest.get("files") or [] if isinstance(f, dict)}
    return [g for g in GUIDE_FILES if g in have]


def readme_text(manifest: dict, manifest_rel: str) -> str:
    t = manifest.get("totals") or {}
    env = manifest.get("environment") or {}
    d = env.get("docker") or {}
    start = (env.get("start") or {}).get("command")
    wheels = any(c.get("kind") == "wheels" for c in manifest.get("compartments") or [])
    port = str((d.get("expose") or [""])[0] or "").split("/")[0]
    tree = d.get("tree_stage") if isinstance(d.get("tree_stage"), dict) else None
    volumes = [v for v in d.get("volumes") or [] if isinstance(v, str) and v]
    guides = guide_files(manifest)
    fence = "```"

    def block(cmd: str) -> str:
        return "{0}\n{1}\n{0}\n".format(fence, cmd)

    out = ["# Zip images of commit {}".format(manifest.get("commit", "?")[:12]), "",
           "This folder holds a complete copy of a program as ordinary zip files (each under 100 MB), plus the",
           "scripts that turn them back into a working folder with its Python packages. You do not need git.", "",
           "* Commit {} ({}): \"{}\"".format(manifest.get("commit", "?"), manifest.get("commit_date", "?"),
                                            manifest.get("subject", "")),
           "* {:,} files, {} MB unpacked, in {} zips ({} MB)".format(t.get("files", 0), mb(t.get("raw_bytes", 0)),
                                                                   t.get("zips", 0), mb(t.get("zip_bytes", 0))),
           "* Python packages: {}".format(
               "from the internet by default; the wheels are packed too, so `--env offline` works without it"
               if wheels else "installed from the internet (pip) by default; `--env none` skips them"),
           "* Manifest: `{}` (which files, which zip, their sha256)".format(manifest_rel), ""]
    if guides:
        names, many = " and ".join("`{}`".format(g) for g in guides), len(guides) > 1
        out += ["## The program's own guide", "",
                "The program comes with {} in its top folder. {} how to deploy it where it is meant to run (for "
                "example on a server, at the address its users open), which keys it needs and what it writes. {} "
                "inside the zips. To read {} first, unpack only the top folder's files (no packages, no big files) "
                "into `./guide`:".format(names, "They explain" if many else "It explains",
                                         "They are" if many else "It is", "them" if many else "it"),
                "", block('python3 unpack_images.py --dest ./guide --only "(files*)" --env none --no-large-files '
                          '--skip-checks'),
                "Then open {} in `./guide` and deploy the program the way {} describe{}. The commands under "
                "\"Try it\" below are this tool's generic ones: they start the program only on the machine where "
                "they are typed (a local port, a container and volumes of its own), which is not a "
                "deployment.".format(names, "they" if many else "it", "" if many else "s"), ""]
    out += ["## Try it on one machine (pick one)" if guides else "## Use it (pick one)", "",
            "### With Docker (nothing else needed)", "",
            "Build the image, in this folder:", "", block("docker build -t {} .".format(IMAGE_NAME))]
    if wheels:
        out += ["Without internet (the packed wheels):", "",
                block("docker build -t {} --build-arg ZIP_ENV=offline .".format(IMAGE_NAME))]
    build_args = [(k, v) for k, v in ((tree or {}).get("args") or {}).items() if isinstance(k, str)]
    if build_args:
        out += ["Build options of the program itself (`--build-arg NAME=VALUE`): {}.".format(
            ", ".join("`{}` (default `{}`)".format(k, v) if isinstance(v, str) else "`{}`".format(k)
                      for k, v in build_args)), ""]
    out += ["Start it{}:".format(
                " (it answers on this computer only: http://127.0.0.1:{}/)".format(port) if port.isdigit() else ""),
            "", block(docker_run_line(manifest))]
    if volumes:
        out += ["Each `-v` keeps one folder in a named Docker volume, so what the program writes there survives "
                "a new image: {}.".format(", ".join("`{}`".format(v) for v in volumes)), ""]
    lf = env.get("large_files") if isinstance(env.get("large_files"), dict) else None
    holds = "The image holds the files of the commit"
    if lf:
        holds += (", the big files included (their zip parts are removed once the big files are restored)"
                  if lf.get("strip") is True else ", the big files included")
    if tree:
        holds += ("; while it is built, the program's own \"{}\" build step runs on them, as the program's "
                  "Dockerfile does (it may move or remove folders{})".format(
                      tree.get("name"), ": see the guide above" if guides else ""))
    out += [holds + ". It needs no other folder. To give the program keys or settings, add `--env-file <file>` "
            "(one `NAME=value` per line) to `docker run`{}.".format(", or follow the guide above" if guides else ""),
            "",
            "See its messages:", "", block("docker logs {}".format(IMAGE_NAME)),
            "Stop it:", "", block("docker stop {}".format(IMAGE_NAME)), "",
            "### On a Linux or macOS machine with Python 3.8+", "",
            "Build `./app` next to this file, with its Python packages (run it again to update):", "",
            block("sh setup_from_zips.sh"),
            "Only the files, no Python packages (then install and start them the way the program's own guide "
            "describes):", "", block("sh setup_from_zips.sh ./app --env none"),
            "### On any machine with Python 3.8+ (Windows too)", "", block("python3 unpack_images.py --dest ./app"),
            "Only check the zips (writes nothing):", "", block("python3 unpack_images.py --verify-only"),
            "All options:", "", block("python3 unpack_images.py --help"),
            "## After it is built", "",
            "The folder keeps a note of what it was built from (`app/{}/installed.json`). When newer zips arrive".format(
                STATE_DIR),
            "(copy the new folder over this one), run the same command again: only the parts that changed are "
            "rewritten,",
            "and the Python packages are installed again only when their list changed. Files you edited by hand "
            "stop the",
            "update until you keep a copy and add `--force`.", "",
            "Start command: `{}` (run from the built folder; the setup prints the exact line).".format(
                " ".join(start) if start else "(none recorded)"), "",
            "## If something goes wrong", "",
            "The script stops with a message and an exit code: 3 = a zip is missing or damaged (copy it again),",
            "4 = a file did not match its checksum, 6 = installing the Python packages failed (for example no "
            "internet:",
            "use `--env offline` if the images hold wheels), 8 = the target folder is not empty or the disk is full.",
            ""]
    return "\n".join(out)


def write_store_files(root, manifest: dict, only_unpacker: bool = False) -> list:
    """Write the helper files for ``manifest`` into the store ``root``. -> the paths written."""
    root = Path(root)
    manifest_rel = "{}/{}.json".format(MANIFESTS_DIR, manifest["commit"][:12])
    out = []
    unp = root / UNPACKER
    write_atomic(unp, unpacker_bytes())
    out.append(unp)
    if only_unpacker:
        return out
    for name, data in ((SETUP_SH, _lf(SETUP_TEXT)),
                       ("Dockerfile", _lf(dockerfile_text(manifest, manifest_rel))),
                       (".dockerignore", _lf(dockerignore_text(manifest, manifest_rel))),
                       ("README.md", _crlf(readme_text(manifest, manifest_rel)))):
        write_atomic(root / name, data)
        out.append(root / name)
    for p in (unp, root / SETUP_SH):
        try:
            os.chmod(str(p), 0o755)
        except OSError:
            pass
    return out
