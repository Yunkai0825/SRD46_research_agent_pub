"""Optional output extraction and ZIP-backed response streaming."""
import secrets
import threading

from flask import abort, jsonify, request, send_file

from zip_images.output_zips.output_reader import OutputPath, default_archives


def send_output_file(path, **kwargs):
    """Serve a loose file when present, otherwise stream its archived bytes."""
    if not isinstance(path, OutputPath) or path.local.is_file():
        return send_file(path, **kwargs)
    kwargs.setdefault("download_name", path.name)
    stream = path.open("rb")
    try:
        response = send_file(stream, conditional=False, **kwargs)
        response.content_length = path.stat().st_size
        response.call_on_close(stream.close)
        return response
    except BaseException:
        stream.close()
        raise


def install_archive_routes(app, archives=None):
    """Prompt once per application startup; extract only after the user chooses."""
    archives = archives or default_archives()
    startup = secrets.token_hex(24)
    lock = threading.Lock()
    job = {"state": "idle", "written": 0, "skipped": 0, "run": "", "error": ""}
    health = {"check_state": "checking", "needs_unpack": False,
              "runs": len(archives.runs) + len(archives.web_archives), "missing_runs": 0}

    def check_outputs():
        try:
            result = archives.unpack_status()
            with lock:
                health.update(result, check_state="complete")
        except Exception as exc:
            app.logger.exception("Output unpacking check failed")
            with lock:
                health.update(check_state="failed", check_error=str(exc))

    threading.Thread(target=check_outputs, name="output-check", daemon=True).start()

    @app.get("/output-archives/status")
    def output_archives_status():
        with lock:
            return jsonify(startup=startup, **health, **job)

    @app.post("/output-archives/extract")
    def output_archives_extract():
        if (request.headers.get("X-Archive-Startup") != startup
                or request.headers.get("Sec-Fetch-Site") == "cross-site"):
            abort(403)
        with lock:
            if job["state"] == "running":
                return jsonify(**job), 202
            job.update(state="running", written=0, skipped=0, run="", error="")

        def update(**values):
            with lock:
                job.update(values)

        def unpack():
            try:
                result = archives.extract(progress=update)
                check_outputs()
                update(state="complete", **result)
            except Exception as exc:
                app.logger.exception("Output archive extraction failed")
                update(state="failed", error=str(exc))

        threading.Thread(target=unpack, name="output-unpack", daemon=True).start()
        return jsonify(state="running"), 202
