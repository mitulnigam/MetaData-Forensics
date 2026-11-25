#!/usr/bin/env python3
"""
Metadata Forensics
------------------
Extracts hidden metadata from images, PDFs, Word documents, and audio files,
then presents it as a clean report. The same kind of information a forensic
investigator pulls from a file: GPS coordinates, author names, editing history,
software and device fingerprints, and timestamps.

Supported:
    images   .jpg .jpeg .png .tiff .webp   (EXIF via Pillow)
    pdf      .pdf                          (document info via pypdf)
    word     .docx                         (core properties via python-docx)
    audio    .mp3 .flac .m4a .ogg .wav     (tags via mutagen)

Usage:
    python3 metadata_analyzer.py <file_or_folder>
    python3 metadata_analyzer.py --no-color photo.jpg
"""

import os
import sys
import textwrap
import datetime

WIDTH = 74
IMAGE_EXT = {"jpg", "jpeg", "png", "tiff", "tif", "webp"}
AUDIO_EXT = {"mp3", "flac", "m4a", "ogg", "wav", "aac"}


# ---------------------------------------------------------------------------
# Colour handling (same approach as a terminal tool: off when piped)
# ---------------------------------------------------------------------------
class Palette:
    def __init__(self, enabled):
        codes = {"reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
                 "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
                 "cyan": "\033[36m"}
        for k, v in codes.items():
            setattr(self, k, v if enabled else "")

    def paint(self, text, *styles):
        return "".join(styles) + text + self.reset if any(styles) else text


def colour_enabled(argv):
    if "--no-color" in argv or "--no-colour" in argv or os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name == "nt":
        os.system("")
    return True


# ---------------------------------------------------------------------------
# A finding is one piece of extracted metadata. Collectors return:
#   sections: {section_name: {key: value}}   -- everything found
#   flags:    [(label, value, note)]         -- privacy-sensitive highlights
# ---------------------------------------------------------------------------
def _blank():
    return {"sections": {}, "flags": [], "error": None}


# ---------------------------------------------------------------------------
# Images — EXIF (camera, software, timestamps, GPS)
# ---------------------------------------------------------------------------
def analyze_image(path):
    out = _blank()
    try:
        from PIL import Image, ExifTags
    except ImportError:
        out["error"] = "Pillow not installed"
        return out

    try:
        img = Image.open(path)
    except Exception as e:
        out["error"] = f"Could not open image: {e}"
        return out

    out["sections"]["Image"] = {
        "Format": img.format,
        "Mode": img.mode,
        "Dimensions": f"{img.width} x {img.height}",
    }

    exif = img.getexif()
    if not exif:
        out["sections"]["EXIF"] = {"(none)": "No EXIF metadata present"}
        return out

    tag_names = ExifTags.TAGS
    general = {}
    for tag_id, value in exif.items():
        name = tag_names.get(tag_id, str(tag_id))
        if name == "GPSInfo":
            continue  # handled separately below
        general[name] = _clean(value)
    if general:
        out["sections"]["EXIF"] = general

    # Privacy flags from common EXIF fields.
    for field, label, note in [
        ("Make", "Device make", "camera/phone manufacturer"),
        ("Model", "Device model", "specific device fingerprint"),
        ("Software", "Software", "editing or capture software"),
        ("Artist", "Artist / author", "named author"),
        ("Copyright", "Copyright", "named rights holder"),
        ("DateTime", "Timestamp", "when the file was created/edited"),
    ]:
        for tag_id, value in exif.items():
            if tag_names.get(tag_id) == field and str(value).strip():
                out["flags"].append((label, _clean(value), note))

    # GPS — decode the nested IFD into decimal coordinates.
    gps = _extract_gps(exif, ExifTags)
    if gps:
        out["sections"]["GPS"] = gps
        if "Latitude" in gps and "Longitude" in gps:
            lat, lon = gps["Latitude"], gps["Longitude"]
            maps = f"https://maps.google.com/?q={lat},{lon}"
            out["flags"].append(("GPS location", f"{lat}, {lon}", maps))
    return out


def _extract_gps(exif, ExifTags):
    try:
        gps_ifd = exif.get_ifd(0x8825)  # GPSInfo IFD pointer
    except Exception:
        gps_ifd = None
    if not gps_ifd:
        return {}

    names = ExifTags.GPSTAGS
    raw = {names.get(k, str(k)): v for k, v in gps_ifd.items()}
    result = {}

    def to_deg(values, ref):
        d, m, s = (float(x) for x in values)
        dec = d + m / 60 + s / 3600
        if ref in ("S", "W"):
            dec = -dec
        return round(dec, 6)

    try:
        if "GPSLatitude" in raw and "GPSLatitudeRef" in raw:
            result["Latitude"] = to_deg(raw["GPSLatitude"], raw["GPSLatitudeRef"])
        if "GPSLongitude" in raw and "GPSLongitudeRef" in raw:
            result["Longitude"] = to_deg(raw["GPSLongitude"], raw["GPSLongitudeRef"])
        if "GPSAltitude" in raw:
            result["Altitude (m)"] = round(float(raw["GPSAltitude"]), 1)
        if "GPSDateStamp" in raw:
            result["GPS timestamp"] = str(raw["GPSDateStamp"])
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# PDF — document information dictionary
# ---------------------------------------------------------------------------
def analyze_pdf(path):
    out = _blank()
    try:
        from pypdf import PdfReader
    except ImportError:
        out["error"] = "pypdf not installed"
        return out

    try:
        reader = PdfReader(path)
        info = reader.metadata or {}
    except Exception as e:
        out["error"] = f"Could not read PDF: {e}"
        return out

    section = {"Pages": len(reader.pages)}
    mapping = {
        "/Title": "Title", "/Author": "Author", "/Subject": "Subject",
        "/Creator": "Creator (authoring app)", "/Producer": "Producer (PDF engine)",
        "/CreationDate": "Created", "/ModDate": "Modified",
        "/Keywords": "Keywords",
    }
    for key, label in mapping.items():
        value = info.get(key)
        if value:
            section[label] = _clean_pdf_date(str(value))
    out["sections"]["PDF document info"] = section

    for key, label, note in [
        ("/Author", "Author", "named author"),
        ("/Creator", "Authoring software", "application that made the content"),
        ("/Producer", "PDF producer", "library/engine that wrote the PDF"),
        ("/CreationDate", "Created", "original creation time"),
        ("/ModDate", "Modified", "last edit time"),
    ]:
        value = info.get(key)
        if value:
            out["flags"].append((label, _clean_pdf_date(str(value)), note))
    return out


# ---------------------------------------------------------------------------
# DOCX — core properties (reveals author + editing history)
# ---------------------------------------------------------------------------
def analyze_docx(path):
    out = _blank()
    try:
        import docx
    except ImportError:
        out["error"] = "python-docx not installed"
        return out

    try:
        cp = docx.Document(path).core_properties
    except Exception as e:
        out["error"] = f"Could not read DOCX: {e}"
        return out

    section = {
        "Author": cp.author,
        "Last modified by": cp.last_modified_by,
        "Revision": cp.revision,
        "Created": _fmt_dt(cp.created),
        "Modified": _fmt_dt(cp.modified),
        "Last printed": _fmt_dt(cp.last_printed),
        "Title": cp.title,
        "Company/Category": cp.category,
        "Comments": cp.comments,
    }
    section = {k: v for k, v in section.items() if v not in (None, "", 0)}
    out["sections"]["DOCX properties"] = section or {"(none)": "No properties set"}

    if cp.author:
        out["flags"].append(("Author", str(cp.author), "original author"))
    if cp.last_modified_by and cp.last_modified_by != cp.author:
        out["flags"].append(("Last modified by", str(cp.last_modified_by),
                              "a different editor — reveals collaboration"))
    if cp.revision and cp.revision > 1:
        out["flags"].append(("Revision count", str(cp.revision),
                             "number of save/edit cycles"))
    if cp.created:
        out["flags"].append(("Created", _fmt_dt(cp.created), "original creation time"))
    return out


# ---------------------------------------------------------------------------
# Audio — tags + technical info (encoder, device, timestamps)
# ---------------------------------------------------------------------------
def analyze_audio(path):
    out = _blank()
    try:
        import mutagen
    except ImportError:
        out["error"] = "mutagen not installed"
        return out

    try:
        audio = mutagen.File(path)
    except Exception as e:
        out["error"] = f"Could not read audio: {e}"
        return out
    if audio is None:
        out["error"] = "Unrecognized audio format"
        return out

    if audio.info:
        tech = {}
        if hasattr(audio.info, "length"):
            tech["Duration"] = f"{audio.info.length:.1f} s"
        if hasattr(audio.info, "bitrate"):
            tech["Bitrate"] = f"{audio.info.bitrate // 1000} kbps"
        if hasattr(audio.info, "sample_rate"):
            tech["Sample rate"] = f"{audio.info.sample_rate} Hz"
        if tech:
            out["sections"]["Audio (technical)"] = tech

    tags = {}
    if audio.tags:
        for key, value in audio.tags.items():
            tags[str(key)] = _clean(value)
    out["sections"]["Audio tags"] = tags or {"(none)": "No tags present"}

    # Map tag keys to privacy labels. Covers ID3 frame codes (MP3), Vorbis
    # comments (FLAC/OGG, lowercase names), and MP4 atoms (©-prefixed).
    flag_keys = {
        "tpe1": ("Artist", "named performer/author"),
        "artist": ("Artist", "named performer/author"),
        "\xa9art": ("Artist", "named performer/author"),
        "tenc": ("Encoded by", "software/person that encoded the file"),
        "encodedby": ("Encoded by", "software/person that encoded the file"),
        "tsse": ("Encoding software", "software that encoded the file"),
        "encoder": ("Encoding software", "software that encoded the file"),
        "\xa9too": ("Encoding software", "software that encoded the file"),
        "tdrc": ("Date", "recording/encoding date"),
        "date": ("Date", "recording/encoding date"),
        "\xa9day": ("Date", "recording/encoding date"),
    }
    for key, value in tags.items():
        entry = flag_keys.get(key.lower())
        if entry and str(value).strip():
            label, note = entry
            out["flags"].append((label, _clean(value), note))
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean(value):
    text = str(value).strip().replace("\x00", "")
    return text[:120] + "..." if len(text) > 120 else text


def _clean_pdf_date(value):
    # PDF dates look like D:20240115103000+00'00' — make them readable.
    if value.startswith("D:") and len(value) >= 16:
        v = value[2:]
        try:
            return (f"{v[0:4]}-{v[4:6]}-{v[6:8]} {v[8:10]}:{v[10:12]}:{v[12:14]}")
        except Exception:
            return value
    return value


def _fmt_dt(value):
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def file_kind(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext in IMAGE_EXT:
        return "image", ext
    if ext == "pdf":
        return "pdf", ext
    if ext == "docx":
        return "docx", ext
    if ext in AUDIO_EXT:
        return "audio", ext
    return None, ext


def analyze(path):
    kind, _ext = file_kind(path)
    dispatch = {"image": analyze_image, "pdf": analyze_pdf,
                "docx": analyze_docx, "audio": analyze_audio}
    if kind is None:
        result = _blank()
        result["error"] = "Unsupported file type"
        return "unknown", result
    return kind, dispatch[kind](path)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def human_size(path):
    try:
        n = os.path.getsize(path)
    except OSError:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def wrap_kv(key, value, pal, key_width=26):
    indent = " " * (4 + key_width)
    avail = WIDTH - len(indent)
    lines = textwrap.wrap(str(value), width=avail) or [""]
    out = [f"    {pal.paint(key, pal.dim):<{key_width + len(pal.dim) + len(pal.reset) if pal.dim else key_width}}{lines[0]}"]
    out.extend(indent + ln for ln in lines[1:])
    return "\n".join(out)


def print_report(path, kind, result, pal):
    bar = "=" * WIDTH
    print(bar)
    print(pal.paint("  METADATA FORENSICS REPORT", pal.bold, pal.cyan))
    print(f"  File: {os.path.basename(path)}")
    print(f"  Type: {kind} · {human_size(path)}")
    print(bar)

    if result["error"]:
        print(pal.paint(f"\n  Could not analyze: {result['error']}", pal.yellow))
        print(bar)
        return

    flags = result["flags"]
    print("\n" + pal.paint("  PRIVACY HIGHLIGHTS", pal.bold)
          + f"  ({len(flags)} sensitive item{'s' if len(flags) != 1 else ''})")
    print("-" * WIDTH)
    if flags:
        for label, value, note in flags:
            mark = pal.paint("!", pal.bold, pal.red)
            print(f"  {mark} {pal.paint(label + ':', pal.bold)} {value}")
            print(f"      {pal.paint(note, pal.dim)}")
    else:
        print(pal.paint("  None found — file appears clean of identifying metadata.",
                        pal.green))

    for section, fields in result["sections"].items():
        print("\n" + pal.paint(f"  {section.upper()}", pal.bold))
        print("-" * WIDTH)
        for key, value in fields.items():
            print(wrap_kv(key, value, pal))

    print(bar)


def gather(target):
    if os.path.isfile(target):
        yield target
    elif os.path.isdir(target):
        for root, _d, files in os.walk(target):
            for name in sorted(files):
                yield os.path.join(root, name)
    else:
        print(f"[ERROR] '{target}' is not a file or folder.")


def main():
    argv = sys.argv[1:]
    pal = Palette(colour_enabled(argv))
    paths = [a for a in argv if not a.startswith("-")]
    if len(paths) != 1:
        print("Usage: python3 metadata_analyzer.py [--no-color] <file_or_folder>")
        sys.exit(1)

    for path in gather(paths[0]):
        kind, result = analyze(path)
        if kind == "unknown":
            continue  # skip unsupported files silently in folder mode
        print_report(path, kind, result, pal)
        print()


if __name__ == "__main__":
    main()
