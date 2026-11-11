"""
zip_images.environment -- what the unpacker must install and run, read from the commit's own Dockerfile.
======================================================================================================

The packer reads the repository's ``Dockerfile`` AT THE PACKED COMMIT (from git) and records, in the
manifest's "environment" block:

  requirements         the files its ``pip install -r FILE`` lines install, traced back through its COPY
                       lines to repository paths (fallback when there is no such line: ``requirements.txt``
                       at the root, when it exists); "constraints" likewise for ``-c FILE``
  constraints_by_arch  a ``-c FILE`` whose path names BuildKit's automatic ``${TARGETARCH}`` (or
                       ``${TARGETPLATFORM}``): {"amd64": repo path, "arm64": repo path}, only the files that
                       exist in the commit. The unpacker picks the one of the machine it runs on.
  constraints_python   the Python version those per-platform files were made for ("3.12": from a ``py3.12``
                       in their names, else from the source's ``python:<version>`` base image), or null
  pip_options          the package-index options of the pip install lines, in order, e.g.
                       ["--extra-index-url", "https://download.pytorch.org/whl/cpu"] (only --index-url,
                       --extra-index-url, --trusted-host, --pre and --prefer-binary are kept)
  pip_self             {"spec": "pip", "constraints": [repo paths]} when a pip install line installs pip itself
                       with a pin (``pip install -c docker/constraints/pip.txt pip``, or ``pip==X``): the
                       unpacker installs that pip first in its virtual environment, and ``pack --wheels`` packs
                       its wheel. Its -c files are NOT constraints of the packages (absent: no pin)
  requirements_sha256  the sha256 of every file above, so an update re-installs only when they changed
  extra_requirements   opt-in lines added by the maintainer (``pack --extra-requirement`` or the config)
  python_version       the Python the images are meant for (``--python-version``, default 3.12); the
                       generated Dockerfile uses ``python:<version>-slim``, the unpacker warns on an older one
  docker               what the generated Dockerfile mirrors (all taken from the FINAL stage): the ENV pairs,
                       WORKDIR, the apt packages of its RUN lines, EXPOSE, VOLUME ("volumes"), LABEL ("labels"),
                       HEALTHCHECK, USER, CMD / ENTRYPOINT, its ARG defaults ("args"; the global ones before the
                       first FROM: "global_args"), its own base image ("source_base_image") and
                       "revision_arg" / "revision_env": the ARG that its ``org.opencontainers.image.revision``
                       label names, and the ENV names set from that ARG (the packer sets that ARG to the
                       packed commit, so the label and those ENV values name the commit)
  docker.tree_stage    the "tree stage", when the source has one: a stage whose first filesystem step is
                       ``COPY . <dir>`` and whose result the final stage takes with ``COPY --from=<stage>``.
                       {"name", "context_dir" (the <dir>), "args" (name -> default), "run" (its RUN lines
                       after the COPY, verbatim), "copies" ([{"src", "dst"}]: the final stage's COPY --from
                       lines of that stage, as absolute paths), "workdir", "env"}. The generated Dockerfile
                       runs those RUN lines on the unpacked tree and then makes the same copies.
  start                the start command (ENTRYPOINT + CMD in exec form) and its working folder
  docker.replay        the final stage's OTHER steps, in order, for the generated Dockerfile to replay on the
                       unpacked tree: {"copy": repo path, "to": image path, "dir": bool} for a COPY / ADD that
                       puts repository files somewhere else than their own place under WORKDIR, {"run": text}
                       for a RUN that installs no packages (apt / pip lines are handled by the image itself).
                       COPY --from lines of the tree stage are covered by "tree_stage"; other COPY --from
                       lines are noted, not replayed.
  large_files          the big-file tool to run after unpacking ({"tool", "store", "strip"}), or null;
                       "strip" is true when that tool has the ``strip`` command (it deletes the zip parts of
                       big files already restored; used by the generated Dockerfile only)
  wheels               null, or the offline wheels' platform and pip settings (the wheels compartment)

ARG handling: every stage and every ARG is read. ``${NAME}``, ``$NAME``, ``${NAME:-word}`` and
``${NAME:+word}`` of a declared ARG are expanded with its default in the values recorded above (FROM with the
global ARGs, the other instructions with the stage's ARGs and ENV). An ARG without a default -- BuildKit's
automatic ``TARGETARCH`` / ``TARGETPLATFORM`` among them -- stays a placeholder ``${NAME}``. RUN text is
recorded verbatim (the shell expands it at build time); it is expanded only to find the pip files.
"""

from __future__ import annotations

import json
import posixpath
import re
import shlex

DEFAULT_PYTHON = "3.12"
DOCKERFILE = "Dockerfile"
REVISION_LABEL = "org.opencontainers.image.revision"
ARCHES = ("amd64", "arm64")
_PLATFORM_VALUES = {"amd64": {"TARGETARCH": "amd64", "TARGETPLATFORM": "linux/amd64", "TARGETOS": "linux",
                              "TARGETVARIANT": ""},
                    "arm64": {"TARGETARCH": "arm64", "TARGETPLATFORM": "linux/arm64", "TARGETOS": "linux",
                              "TARGETVARIANT": ""}}
_SEPARATORS = {"&&", "||", ";", "|", "&"}
_PIP_VALUE_OPTIONS = ("--index-url", "--extra-index-url", "--trusted-host")
_PIP_FLAG_OPTIONS = ("--pre", "--prefer-binary")
# pip install options that take a value (the word after them is no package name)
_PIP_TAKES_VALUE = frozenset(("-r", "--requirement", "-c", "--constraint", "-i", "--index-url", "--extra-index-url",
                              "--trusted-host", "-t", "--target", "--prefix", "--root", "-f", "--find-links",
                              "--platform", "--python-version", "--implementation", "--abi", "--cache-dir",
                              "--progress-bar", "--src", "--upgrade-strategy", "--no-binary", "--only-binary",
                              "-e", "--editable", "--log", "--timeout", "--retries", "--proxy", "--cert",
                              "--client-cert", "--exists-action", "--global-option", "--config-settings",
                              "--report", "--root-user-action", "--keyring-provider"))
_PIP_SELF = re.compile(r"pip(?:\s*(?:===?|~=|>=|<=|!=|<|>)\s*[0-9][0-9A-Za-z.+!*]*)?")
_REF = re.compile(r"(?<!\\)\$(?:\{(?P<b>[A-Za-z_][A-Za-z0-9_]*)(?:(?P<op>:?[-+])(?P<w>[^}]*))?\}"
                  r"|(?P<n>[A-Za-z_][A-Za-z0-9_]*))")
_STRIP_COMMAND = re.compile(r"""add_parser\(\s*["']strip["']""")


def _logical_lines(text: str) -> list:
    """Dockerfile lines with continuations joined (one space where the break was) and comment lines dropped."""
    out, cur = [], ""
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if cur:
            line = stripped
        if line.endswith("\\"):
            cur += line[:-1].rstrip() + " "
            continue
        cur += line
        if cur.strip():
            out.append(cur.strip())
        cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def _tokens(text: str) -> list:
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def _exec_form(rest: str):
    rest = rest.strip()
    if rest.startswith("["):
        try:
            value = json.loads(rest)
            if isinstance(value, list) and all(isinstance(x, str) for x in value):
                return value
        except ValueError:
            pass
    return ["/bin/sh", "-c", rest] if rest else []


def expand(text: str, values: dict) -> str:
    """Expand ``$NAME`` / ``${NAME}`` / ``${NAME:-word}`` / ``${NAME:+word}`` (and the ``-`` / ``+`` forms)
    for the names in ``values``. A name whose value is None (an ARG without a default, e.g. TARGETARCH)
    stays a placeholder ``${NAME}``; a name that is not in ``values`` stays as written."""
    if not isinstance(text, str) or "$" not in text:
        return text

    def one(m):
        name = m.group("b") or m.group("n")
        if name not in values:
            return m.group(0)
        value, op, word = values[name], m.group("op"), m.group("w")
        if value is None:
            return m.group(0) if op else "${" + name + "}"
        if not op:
            return value
        if op == ":-":
            return value if value else expand(word, values)
        if op == "-":
            return value
        if op == ":+":
            return expand(word, values) if value else ""
        return expand(word, values)                   # "+": the name is set
    return _REF.sub(one, text)


def _refs(text: str) -> set:
    """The names a text refers to with $NAME / ${NAME...}."""
    return {m.group("b") or m.group("n") for m in _REF.finditer(text or "")}


def _commands(run: str) -> list:
    """A RUN line cut at shell separators into token lists."""
    toks = _tokens(run.replace("&&", " && ").replace(";", " ; ").replace("||", " || "))
    cmds, cur = [], []
    for t in toks:
        if t in _SEPARATORS:
            if cur:
                cmds.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _pip_files(cmd: list) -> tuple:
    """(requirement files, constraint files) of one `... pip install ...` command."""
    if "install" not in cmd or not any(re.fullmatch(r"(.*/)?pip[0-9.]*", t) or t == "pip" for t in cmd):
        return [], []
    reqs, cons = [], []
    i = 0
    while i < len(cmd):
        t = cmd[i]
        for flag, bucket in (("-r", reqs), ("--requirement", reqs), ("-c", cons), ("--constraint", cons)):
            if t == flag and i + 1 < len(cmd):
                bucket.append(cmd[i + 1])
                i += 1
                break
            if t.startswith(flag + "=") or (flag in ("-r", "-c") and t.startswith(flag) and len(t) > 2
                                            and not t.startswith(flag + "-")):
                bucket.append(t[len(flag) + 1:] if t.startswith(flag + "=") else t[len(flag):])
                break
        i += 1
    return reqs, cons


def _pip_options(cmd: list, notes: list) -> list:
    """[(option, value or None)] of the package-index options of one `pip install` command."""
    out = []
    if "install" not in cmd:
        return out
    i = cmd.index("install") + 1
    while i < len(cmd):
        t = cmd[i]
        name, eq, value = t.partition("=")
        if name == "-i":
            name = "--index-url"
        if name in _PIP_VALUE_OPTIONS:
            if not eq:
                value = cmd[i + 1] if i + 1 < len(cmd) else ""
                i += 1
            if not value or "$" in value:
                notes.append("pip option {} {!r}: its value is not known when packing -- not recorded".format(
                    name, value))
            else:
                out.append((name, value))
        elif t in _PIP_FLAG_OPTIONS:
            out.append((t, None))
        i += 1
    return out


def _is_pip_install(cmd: list) -> bool:
    return "install" in cmd and any(re.fullmatch(r"(.*/)?pip[0-9.]*", t) for t in cmd)


def _pip_self(cmd: list):
    """The requirement of a `pip install ... pip` command that installs pip itself (its only package), or None."""
    if not _is_pip_install(cmd):
        return None
    i = cmd.index("install") + 1
    names = []
    while i < len(cmd):
        t = cmd[i]
        if t.startswith("-"):
            i += 2 if t in _PIP_TAKES_VALUE else 1
            continue
        names.append(t)
        i += 1
    return names[0] if len(names) == 1 and _PIP_SELF.fullmatch(names[0]) else None


def _is_apt(cmd: list) -> bool:
    return any(t in ("apt-get", "apt", "apk", "yum", "dnf", "microdnf") for t in cmd)


def _from_flag(step: dict):
    """The value of a COPY / ADD step's ``--from=`` flag, or None."""
    for f in step.get("flags") or []:
        if f.startswith("--from="):
            return f[len("--from="):]
    return None


def _folders(tree_paths) -> set:
    folders = set()
    for p in tree_paths:
        parts = p.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            folders.add("/".join(parts[:i]))
    return folders


def _replay(st: dict, tree_paths: dict, notes: list, covered=()) -> list:
    """The final stage's steps the generated Dockerfile must replay on the unpacked tree (see the module doc).
    ``covered`` = the stage names / indexes whose COPY --from lines the tree-stage record already carries."""
    out = []
    workdir = st.get("workdir") or "/"
    folders = _folders(tree_paths)
    for step in st.get("steps", []):
        if step["kind"] == "run":
            cmds = _commands(step["expanded"])
            if any(_is_pip_install(c) or _is_apt(c) for c in cmds):
                continue
            out.append({"run": step["cmd"]})
            continue
        source = _from_flag(step)
        if source is not None:
            if source.lower() not in covered:
                notes.append("{} {} comes from another build stage -- not replayed".format(
                    step["instr"], " ".join(step["srcs"])))
            continue
        dst_abs = posixpath.normpath(posixpath.join(step["workdir"], step["dst"]))
        dst_is_dir = step["dst"].endswith("/") or step["dst"] in (".", "./") or len(step["srcs"]) > 1
        for src in step["srcs"]:
            rp = "." if src in (".", "./") else posixpath.normpath(src.lstrip("/"))
            if rp != "." and rp not in tree_paths and rp not in folders:
                notes.append("{} {}: not a path of the commit -- not replayed".format(step["instr"], src))
                continue
            is_dir = rp == "." or rp in folders
            where = dst_abs if is_dir or not dst_is_dir else posixpath.join(dst_abs, posixpath.basename(rp))
            home = posixpath.normpath(posixpath.join(workdir, rp))
            if where == home:
                continue                      # already in its place: the unpacked tree lies at WORKDIR
            out.append({"copy": rp, "to": where, "dir": is_dir})
    return out


def _apt_packages(cmd: list) -> list:
    for i, t in enumerate(cmd):
        if t in ("apt-get", "apt") and "install" in cmd[i + 1:]:
            j = cmd.index("install", i + 1)
            return [x for x in cmd[j + 1:] if not x.startswith("-")]
    return []


def _arg_decls(rest: str) -> list:
    """[(name, default or None)] of one ARG line (``ARG A``, ``ARG A=1``, ``ARG A=1 B="x y"``)."""
    out = []
    for tok in _tokens(rest):
        name, eq, default = tok.partition("=")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            out.append((name, default if eq else None))
    return out


def _pairs(rest: str, values: dict) -> list:
    """[[key, value]] of an ENV or LABEL line (``K=V ...`` form, or the old ``K V`` form), values expanded."""
    toks = _tokens(rest)
    out = []
    if toks and "=" in toks[0]:
        for t in toks:
            k, _, v = t.partition("=")
            out.append([k, expand(v, values)])
    elif toks:
        k = toks[0]
        v = rest[len(rest.split(None, 1)[0]):].strip()
        out.append([k, expand(v, values)])
    return out


def _set_pair(pairs: list, k: str, v: str) -> list:
    return [p for p in pairs if p[0] != k] + [[k, v]]


_INHERITED = ("workdir", "env", "env_raw", "arg_shadowed", "arg_history", "arg_env_eligible", "labels", "labels_raw", "expose", "volumes", "healthcheck", "cmd",
              "entrypoint", "user", "steps", "copies", "runs")


def parse_stages(text: str, overrides: dict = None) -> dict:
    """Every stage of a Dockerfile, as data: {"global_args": {name: default}, "stages": [stage, ...]}.

    ``overrides`` = build-arg values (name -> value) that replace declared defaults. A stage records its
    ``index``, ``name``, ``from`` (the image, global ARGs expanded), ``args`` (its ARG defaults as declared,
    expanded), ``vars`` (the ARG values in effect), ``workdir``, ``env`` / ``labels`` (expanded pairs),
    ``copies``, ``runs``, ``steps`` (copy / run, in order), ``expose``, ``volumes``, ``healthcheck``, ``cmd``,
    ``entrypoint`` and ``user``. A stage built FROM an earlier stage starts from that stage's settings and
    steps."""
    overrides = overrides or {}
    gdefaults, gvalues = {}, {}
    stages = []
    st = None
    for line in _logical_lines(text):
        instr, _, rest = line.partition(" ")
        instr = instr.upper()
        rest = rest.strip()
        if instr == "ARG":
            for name, default in _arg_decls(rest):
                if st is None:
                    declared = expand(default, gvalues) if default is not None else None
                    gdefaults[name] = declared
                    gvalues[name] = overrides.get(name, declared)
                else:
                    values = dict(st["vars"], **{k: v for k, v in st["env"]})
                    if default is not None:
                        declared = expand(default, values)
                    else:
                        declared = gvalues.get(name)
                    if name in st["arg_history"] and st["arg_history"][name] != declared and name not in st["arg_shadowed"]:
                        st["arg_shadowed"].append(name)
                    st["arg_history"][name] = declared
                    st["args"][name] = declared
                    st["vars"][name] = overrides.get(name, declared)
            continue
        if instr == "FROM":
            toks = [t for t in _tokens(rest) if not t.startswith("--")]
            raw = toks[0] if toks else ""
            name = toks[2] if len(toks) >= 3 and toks[1].upper() == "AS" else None
            image = expand(raw, gvalues)
            st = {"index": len(stages), "name": name, "from": image, "from_raw": raw, "parent": None, "args": {},
                  "vars": {}, "workdir": "/", "env": [], "env_raw": {}, "arg_shadowed": [], "arg_history": {}, "arg_env_eligible": {}, "labels": [], "labels_raw": {}, "copies": [],
                  "runs": [],
                  "steps": [], "expose": [], "volumes": [], "healthcheck": None, "cmd": None,
                  "entrypoint": None, "user": None}
            parent = _stage_ref(stages, image)
            if parent is not None:
                st["parent"] = parent["index"]
                for key in _INHERITED:
                    value = parent[key]
                    st[key] = json.loads(json.dumps(value)) if isinstance(value, (list, dict)) else value
            stages.append(st)
            continue
        if st is None:
            continue
        values = dict(st["vars"], **{k: v for k, v in st["env"]})
        if instr == "WORKDIR":
            st["workdir"] = posixpath.normpath(posixpath.join(st["workdir"], expand(rest.strip('"'), values)))
        elif instr == "ENV":
            raw_pairs = _pairs(rest, {})
            for (k, v), (_, raw_v) in zip(_pairs(rest, values), raw_pairs):
                st["env"] = _set_pair(st["env"], k, v)
                st["env_raw"][k] = raw_v
                st["arg_env_eligible"].pop(k, None)
                direct = re.fullmatch(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))", raw_v)
                if direct:
                    argument = direct.group(1) or direct.group(2)
                    if argument in st["args"]:
                        st["arg_env_eligible"][k] = argument
                if raw_v not in ("$" + k, "$" + "{" + k + "}") and k not in st["arg_shadowed"]:
                    st["arg_shadowed"].append(k)
        elif instr == "LABEL":
            for (k, v), (_, raw_v) in zip(_pairs(rest, values), _pairs(rest, {})):
                st["labels"] = _set_pair(st["labels"], k, v)
                st["labels_raw"][k] = raw_v
        elif instr in ("COPY", "ADD"):
            every = _exec_form(rest) if rest.startswith("[") else _tokens(rest)
            flags = [expand(t, values) for t in every if t.startswith("--")]
            toks = [expand(t, values) for t in every if not t.startswith("--")]
            if rest.startswith("["):
                flags, toks = [], [expand(t, values) for t in every]
            if len(toks) >= 2:
                cp = {"srcs": toks[:-1], "dst": toks[-1], "workdir": st["workdir"], "flags": flags,
                      "instr": instr}
                st["copies"].append(cp)
                st["steps"].append(dict(cp, kind="copy"))
        elif instr == "RUN":
            flags = []
            body = rest
            while body.startswith("--"):
                flag, _, body = body.partition(" ")
                flags.append(flag)
                body = body.lstrip()
            cmd = _exec_form(body)
            text_run = cmd[2] if cmd[:2] == ["/bin/sh", "-c"] else " ".join(shlex.quote(c) for c in cmd)
            run = {"cmd": text_run, "expanded": expand(text_run, values), "workdir": st["workdir"],
                   "flags": flags, "copies_before": len(st["copies"])}
            st["runs"].append(run)
            st["steps"].append(dict(run, kind="run"))
        elif instr == "EXPOSE":
            st["expose"] += [expand(t, values) for t in _tokens(rest)]
        elif instr == "VOLUME":
            vols = _exec_form(rest) if rest.startswith("[") else _tokens(rest)
            if vols[:2] == ["/bin/sh", "-c"]:
                vols = _tokens(rest)
            for v in vols:
                v = expand(v, values)
                if v and v not in st["volumes"]:
                    st["volumes"].append(v)
        elif instr == "HEALTHCHECK":
            st["healthcheck"] = rest
        elif instr == "CMD":
            st["cmd"] = _exec_form(rest)
        elif instr == "ENTRYPOINT":
            st["entrypoint"] = _exec_form(rest)
        elif instr == "USER":
            st["user"] = expand(rest, values)
    return {"global_args": gdefaults, "stages": stages}


def _stage_ref(stages: list, ref: str):
    """The earlier stage that a FROM image / COPY --from value names (by name, case-insensitive, or index)."""
    if not isinstance(ref, str):
        return None
    for s in stages:
        if (s["name"] and s["name"].lower() == ref.lower()) or ref == str(s["index"]):
            return s
    return None


def parse_dockerfile(text: str, overrides: dict = None) -> dict:
    """The final stage of a Dockerfile, as data (see :func:`parse_stages`)."""
    stages = parse_stages(text, overrides)["stages"]
    return stages[-1] if stages else {}


def _tree_stage(stages: list, notes: list):
    """The tree-stage record (see the module doc) and the COPY --from values it covers, or (None, set())."""
    if len(stages) < 2:
        return None, set()
    final = stages[-1]
    found = []
    for s in stages[:-1]:
        fs = [x for x in s["steps"] if x["kind"] in ("copy", "run")]
        if s["parent"] is not None or not fs or fs[0]["kind"] != "copy":
            continue
        first = fs[0]
        if _from_flag(first) is not None or first["srcs"] not in (["."], ["./"]):
            continue
        names = {str(s["index"])} | ({s["name"].lower()} if s["name"] else set())
        refs = [cp for cp in final["copies"] if (_from_flag(cp) or "").lower() in names]
        if not refs:
            continue
        if any(x["kind"] == "copy" for x in fs[1:]):
            notes.append("stage {} starts with COPY . but copies more files later -- not replayed as the tree "
                         "stage".format(s["name"] or s["index"]))
            continue
        found.append((s, first, refs, names))
    if not found:
        return None, set()
    if len(found) > 1:
        notes.append("several stages look like a tree stage; only {} is replayed".format(
            found[0][0]["name"] or found[0][0]["index"]))
    s, first, refs, names = found[0]
    context_dir = posixpath.normpath(posixpath.join(first["workdir"], first["dst"]))
    copies = []
    for cp in refs:
        dst = posixpath.join(cp["workdir"], cp["dst"])
        dst_n = posixpath.normpath(dst) + ("/" if cp["dst"].endswith("/") and dst != "/" else "")
        for src in cp["srcs"]:
            src_n = posixpath.normpath("/" + src.lstrip("/")) + ("/" if src.endswith("/") and src != "/" else "")
            copies.append({"src": src_n, "dst": dst_n})
    record = {"name": s["name"] or str(s["index"]), "context_dir": context_dir, "args": dict(s["args"]),
              "run": [x["cmd"] for x in s["steps"] if x["kind"] == "run"], "copies": copies,
              "workdir": s["workdir"], "env": [p for p in s["env"]]}
    if any(x.get("flags") for x in s["steps"] if x["kind"] == "run"):
        notes.append("RUN options of the tree stage (--mount, ...) are not replayed")
    return record, names


def _to_repo_path(target: str, workdir: str, copies: list, folders=frozenset()):
    """Trace a file path inside the image back to the repository path its COPY lines took it from.
    COPY --from lines are skipped (their files come from another stage); a folder source copies its CONTENTS
    into the destination, as Docker does."""
    abs_t = posixpath.normpath(posixpath.join(workdir, target))
    for cp in reversed(copies):
        if _from_flag(cp) is not None:
            continue
        dst = posixpath.normpath(posixpath.join(cp["workdir"], cp["dst"]))
        dst_is_dir = cp["dst"].endswith("/") or cp["dst"] in (".", "./") or len(cp["srcs"]) > 1
        for src in cp["srcs"]:
            src_n = posixpath.normpath(src.lstrip("/")) if src not in (".", "./") else "."
            if src_n == "." or src_n in folders:
                base = dst.rstrip("/")
                if abs_t.startswith(base + "/"):
                    rest = abs_t[len(base) + 1:]
                    return rest if src_n == "." else src_n + "/" + rest
                continue
            where = posixpath.join(dst, posixpath.basename(src_n)) if dst_is_dir else dst
            if abs_t == where:
                return src_n
            if abs_t.startswith(where + "/"):
                return src_n + abs_t[len(where):]
    return None if target.startswith("/") else posixpath.normpath(target)


def _per_arch(path: str) -> dict:
    """{arch: path} for a path that names the target platform, else {} (the path does not depend on it)."""
    names = _refs(path) & set(_PLATFORM_VALUES["amd64"])
    if not names:
        return {}
    return {arch: expand(path, _PLATFORM_VALUES[arch]) for arch in ARCHES}


def _python_of(text: str):
    m = re.search(r"(?:^|[/:])python:?(\d+\.\d+)", text or "") or re.search(r"py(\d+\.\d+)", text or "")
    return m.group(1) if m else None


def _revision_arg(st: dict):
    """The ARG that the final stage's revision label names (``LABEL org.opencontainers.image.revision=$X``)."""
    for k, v in (st.get("labels_raw") or {}).items():
        if k == REVISION_LABEL:
            m = re.fullmatch(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", (v or "").strip())
            if m and m.group(1) in st.get("vars", {}):
                return m.group(1)
    return None


def _read_final(get_blob, tree_paths: dict, revision, notes: list):
    """(all stages, the final stage, the revision ARG name) -- parsed twice when the revision ARG exists, so
    the recorded values carry the packed commit instead of the ARG's default."""
    text = get_blob(DOCKERFILE).decode("utf-8", "replace")
    parsed = parse_stages(text)
    stages = parsed["stages"]
    if not stages:
        notes.append("the Dockerfile has no FROM line -- nothing read from it")
        return parsed, {}, None
    rev_arg = None
    if isinstance(revision, str) and revision:
        rev_arg = _revision_arg(stages[-1])
        if rev_arg:
            parsed = parse_stages(text, {rev_arg: revision})
    return parsed, parsed["stages"][-1], rev_arg


def _large_files_entry(get_blob, tree_paths: dict, config: dict, notes: list):
    lf = config.get("large_files", "auto")
    if lf == "auto":
        lf = ({"tool": "large_file_packs.py", "store": "_large_files"}
              if "large_file_packs.py" in tree_paths and any(p.startswith("_large_files/") for p in tree_paths)
              else None)
    elif lf is not None and not (isinstance(lf, dict) and lf.get("tool") in tree_paths):
        notes.append("the config's large_files entry names no file of the commit -- ignored")
        lf = None
    if lf is None:
        return None
    lf = dict(lf)
    if not isinstance(lf.get("strip"), bool):
        try:
            source = get_blob(lf["tool"]).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            source = ""
        lf["strip"] = bool(_STRIP_COMMAND.search(source))
    return lf


def build_environment(get_blob, tree_paths: dict, *, python_version: str = DEFAULT_PYTHON,
                      extra_requirements=(), config: dict = None, revision: str = None) -> dict:
    """The manifest's environment block.

    ``get_blob(path) -> bytes`` reads a file of the commit; ``tree_paths`` maps every file path of the commit
    to its sha256 (or None when not known yet); ``revision`` = the packed commit (it replaces the default of
    the ARG that the revision label names)."""
    config = config or {}
    notes = []
    docker = {}
    reqs, cons, by_arch, options = [], [], {}, []
    cons_python = None
    pip_self = None
    if DOCKERFILE in tree_paths:
        parsed, st, rev_arg = _read_final(get_blob, tree_paths, revision, notes)
        stages = parsed["stages"]
        folders = _folders(tree_paths)
        tree, covered = _tree_stage(stages, notes)
        for run in st.get("runs", []):
            if run.get("flags"):
                notes.append("RUN options {} are not replayed".format(" ".join(run["flags"])))
            copies = st["copies"][:run.get("copies_before", len(st["copies"]))]
            for cmd in _commands(run["expanded"]):
                r, c = _pip_files(cmd)
                self_spec = _pip_self(cmd)
                if self_spec is not None:
                    # pip installing itself: its -c files pin pip only (e.g. docker/constraints/pip.txt), so they
                    # are recorded as "pip_self", not as constraints of the packages
                    self_paths = []
                    for f in c:
                        rp = None if "$" in f else _to_repo_path(f, run["workdir"], copies, folders)
                        if rp and rp in tree_paths:
                            self_paths.append(rp)
                        else:
                            notes.append("the pip constraints file {} is not a file of the commit -- not "
                                         "recorded".format(f))
                    if self_paths or re.search(r"[=<>~]", self_spec):
                        pip_self = {"spec": self_spec, "constraints": self_paths}
                    c = []
                for bucket, found in ((reqs, r), (cons, c)):
                    for f in found:
                        arch_paths = _per_arch(f)
                        if arch_paths:
                            if bucket is reqs:
                                notes.append("the requirement file {} depends on the target platform -- not "
                                             "recorded".format(f))
                                continue
                            for arch, fa in arch_paths.items():
                                rp = _to_repo_path(fa, run["workdir"], copies, folders)
                                if rp and rp in tree_paths:
                                    by_arch.setdefault(arch, rp)
                                else:
                                    notes.append("the {} constraints file {} is not a file of the commit".format(
                                        arch, fa))
                            continue
                        if "$" in f:
                            notes.append("the pip file {} is not known when packing -- not recorded".format(f))
                            continue
                        rp = _to_repo_path(f, run["workdir"], copies, folders)
                        if rp and rp in tree_paths:
                            if rp not in bucket:
                                bucket.append(rp)
                        else:
                            notes.append("the Dockerfile installs {} but it is not a file of the commit".format(f))
                if _is_pip_install(cmd):
                    for pair in _pip_options(cmd, notes):
                        if pair not in options:
                            options.append(pair)
                docker.setdefault("apt_packages", [])
                for pkg in _apt_packages(cmd):
                    if pkg not in docker["apt_packages"]:
                        docker["apt_packages"].append(pkg)
        docker["replay"] = _replay(st, tree_paths, notes, covered)
        start_cmd = (st.get("entrypoint") or []) + (st.get("cmd") or [])
        rev_env = [k for k, _ in st.get("env", []) if rev_arg and rev_arg in _refs(st["env_raw"].get(k, ""))]
        # Preserve direct ARG -> ENV relationships for generated build overrides.
        argument_env = {}
        for key, raw in st.get("env_raw", {}).items():
            match = re.fullmatch(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))", raw)
            if match:
                name = match.group(1) or match.group(2)
                final_raw = st.get("env_raw", {}).get(name)
                self_refs = ("$" + name, "$" + "{" + name + "}")
                if name in st.get("args", {}) and name != rev_arg:
                    if (st.get("arg_env_eligible", {}).get(key) == name
                            and name not in st.get("arg_shadowed", [])
                            and (final_raw is None or final_raw in self_refs)):
                        argument_env[key] = name
                    else:
                        notes.append("ARG {} is shadowed by ENV; {} keeps its recorded value "
                                     "in generated builds".format(name, key))
        docker.update({"source": DOCKERFILE, "source_base_image": st.get("from"), "workdir": st.get("workdir"),
                       "env": st.get("env", []), "expose": st.get("expose", []),
                       "healthcheck": st.get("healthcheck"), "user": st.get("user"),
                       "cmd": st.get("cmd"), "entrypoint": st.get("entrypoint"),
                       "args": {k: v for k, v in (st.get("args") or {}).items()},
                       "global_args": dict(parsed["global_args"]), "labels": st.get("labels", []),
                       "volumes": st.get("volumes", []), "revision_arg": rev_arg, "revision_env": rev_env,
                       "tree_stage": tree, "argument_env": argument_env})
        docker.setdefault("apt_packages", [])
        if by_arch:
            pys = {_python_of(posixpath.basename(p)) for p in by_arch.values()}
            cons_python = pys.pop() if len(pys) == 1 and None not in pys else _python_of(st.get("from") or "")
        start = {"command": start_cmd or None, "workdir": st.get("workdir")}
        source = DOCKERFILE if reqs else "default"
    else:
        start = {"command": None, "workdir": None}
        source = "default"
    if not reqs and "requirements.txt" in tree_paths:
        reqs = ["requirements.txt"]
    docker["base_image"] = "python:{}-slim".format(python_version)
    extra = list(extra_requirements or []) + [x for x in config.get("extra_requirements") or []
                                               if isinstance(x, str)]
    lf = _large_files_entry(get_blob, tree_paths, config, notes)
    hashed = []
    for p in reqs + cons + [by_arch[a] for a in ARCHES if a in by_arch] + list((pip_self or {}).get("constraints")
                                                                                or []):
        if p not in hashed:
            hashed.append(p)
    env = {"requirements": reqs, "constraints": cons, "requirements_from": source,
           "requirements_sha256": {p: tree_paths.get(p) for p in hashed},
           "extra_requirements": extra, "python_version": python_version, "docker": docker,
           "start": start, "large_files": lf, "wheels": None, "notes": notes}
    if by_arch:
        env["constraints_by_arch"] = {a: by_arch[a] for a in ARCHES if a in by_arch}
        env["constraints_python"] = cons_python
    if options:
        env["pip_options"] = [x for name, value in options for x in ((name,) if value is None else (name, value))]
    if pip_self:
        env["pip_self"] = pip_self
    return env
