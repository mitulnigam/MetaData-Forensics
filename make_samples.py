"""
Generate sample files that contain realistic (fabricated) metadata, so the
analyzer has something to extract. None of this describes a real person,
place, or device — the GPS point is a well-known public landmark.

    python3 make_samples.py
"""

import os
import subprocess
import datetime

OUT = os.path.join(os.path.dirname(__file__), "samples")
os.makedirs(OUT, exist_ok=True)


def make_image():
    import piexif
    from PIL import Image

    # GPS: Golden Gate Bridge (a public landmark), stored as EXIF rationals.
    def deg_to_rational(dec):
        d = int(dec)
        m = int((dec - d) * 60)
        s = round((dec - d - m / 60) * 3600, 4)
        return [(d, 1), (m, 1), (int(s * 100), 100)]

    lat, lon = 37.8199, -122.4786
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: "N",
        piexif.GPSIFD.GPSLatitude: deg_to_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: "W",
        piexif.GPSIFD.GPSLongitude: deg_to_rational(abs(lon)),
        piexif.GPSIFD.GPSAltitudeRef: 0,
        piexif.GPSIFD.GPSAltitude: (67, 1),
    }
    zeroth = {
        piexif.ImageIFD.Make: "Apple",
        piexif.ImageIFD.Model: "iPhone 13 Pro",
        piexif.ImageIFD.Software: "Adobe Photoshop 25.0 (Windows)",
        piexif.ImageIFD.Artist: "Jane Photographer",
        piexif.ImageIFD.Copyright: "(c) 2024 Jane Photographer",
        piexif.ImageIFD.DateTime: "2024:06:15 14:32:10",
    }
    exif_bytes = piexif.dump({"0th": zeroth, "GPS": gps_ifd, "Exif": {}, "1st": {}, "thumbnail": None})

    img = Image.new("RGB", (640, 480), (70, 110, 160))
    path = os.path.join(OUT, "vacation_photo.jpg")
    img.save(path, "jpeg", exif=exif_bytes)
    return path


def make_pdf():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_metadata({
        "/Title": "Q4 Financial Summary",
        "/Author": "Michael Chen",
        "/Creator": "Microsoft Word for Microsoft 365",
        "/Producer": "Adobe PDF Library 23.1",
        "/CreationDate": "D:20240115103000+00'00'",
        "/ModDate": "D:20240220161500+00'00'",
        "/Keywords": "confidential, internal",
    })
    path = os.path.join(OUT, "financial_report.pdf")
    with open(path, "wb") as f:
        writer.write(f)
    return path


def make_docx():
    import docx

    doc = docx.Document()
    doc.add_heading("Internal Memo", level=1)
    doc.add_paragraph("Draft for review.")
    cp = doc.core_properties
    cp.author = "Sarah Williams"
    cp.last_modified_by = "David Kumar"
    cp.revision = 7
    cp.title = "Restructuring Plan (DRAFT)"
    cp.category = "Acme Corporation"
    cp.created = datetime.datetime(2024, 3, 1, 9, 15, 0)
    cp.modified = datetime.datetime(2024, 3, 12, 17, 42, 0)
    path = os.path.join(OUT, "internal_memo.docx")
    doc.save(path)
    return path


def make_audio():
    # Use ffmpeg to make a 1-second silent MP3, then tag it with mutagen.
    path = os.path.join(OUT, "voice_note.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", "1", "-q:a", "9", path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    from mutagen.easyid3 import EasyID3
    from mutagen.mp3 import MP3
    try:
        audio = MP3(path, ID3=EasyID3)
    except Exception:
        audio = MP3(path)
        audio.add_tags()
    audio["title"] = "Interview recording"
    audio["artist"] = "Field Recorder 01"
    audio["date"] = "2024-07-20"
    audio["encodedby"] = "LAME 3.100"
    audio.save()
    return path


def main():
    made = [make_image(), make_pdf(), make_docx(), make_audio()]
    print("Created sample files:")
    for p in made:
        print("  " + os.path.relpath(p, os.path.dirname(__file__)))


if __name__ == "__main__":
    main()
