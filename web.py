"""
Metadata Forensics — web interface.

A thin Flask front end over the existing metadata_analyzer logic: upload a
file, and the same extractor that powers the CLI renders its findings in the
browser, with any GPS coordinates shown on an embedded map.

Run:
    python3 web.py        then open http://127.0.0.1:5001

Uploads are analyzed and then deleted; nothing is stored.
"""

import os
import tempfile

from flask import Flask, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename

import metadata_analyzer as mda

app = Flask(__name__)
app.secret_key = os.environ.get("MDA_SECRET", "dev-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB upload cap

ALLOWED = mda.IMAGE_EXT | mda.AUDIO_EXT | {"pdf", "docx"}


def gps_from_flags(flags):
    """Pull (lat, lon, maps_url) out of the flags list if a GPS flag exists."""
    for label, value, note in flags:
        if label == "GPS location":
            try:
                lat, lon = (p.strip() for p in value.split(","))
                return lat, lon, note
            except ValueError:
                return None
    return None


# Category of each finding, used only for colour-coding in the UI.
_FLAG_CATEGORIES = [
    ("location", ("GPS", "location")),
    ("identity", ("author", "artist", "last modified", "copyright")),
    ("software", ("software", "encoder", "encoded", "producer", "authoring", "creator")),
    ("device", ("device", "make", "model")),
    ("time", ("timestamp", "date", "created", "modified")),
]


@app.template_filter("flag_cat")
def flag_cat(label):
    low = label.lower()
    for category, needles in _FLAG_CATEGORIES:
        if any(n in low for n in needles):
            return category
    return "other"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    upload = request.files.get("file")
    if not upload or upload.filename == "":
        flash("Please choose a file to analyze.", "error")
        return redirect(url_for("index"))

    name = secure_filename(upload.filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        flash(f"Unsupported file type: .{ext}. "
              f"Supported: images, pdf, docx, audio.", "error")
        return redirect(url_for("index"))

    # Save to a temp file, analyze, then delete — nothing is retained.
    tmp_dir = tempfile.mkdtemp(prefix="mda_")
    tmp_path = os.path.join(tmp_dir, name)
    upload.save(tmp_path)
    try:
        size = mda.human_size(tmp_path)
        kind, result = mda.analyze(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    gps = gps_from_flags(result.get("flags", [])) if not result.get("error") else None
    return render_template("result.html", filename=name, kind=kind,
                           size=size, result=result, gps=gps)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
