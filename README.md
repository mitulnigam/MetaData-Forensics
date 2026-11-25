# Metadata Forensics

A command-line tool that extracts **hidden metadata** from images, PDFs, Word
documents, and audio files, then presents it as a clean forensic report. It
surfaces the same information a digital-forensics investigator looks for: GPS
coordinates, author names, editing history, software and device fingerprints,
and timestamps — the data that travels inside a file without anyone noticing.

## Why this matters

Everyday files quietly carry metadata. A photo taken on a phone can embed the
exact **GPS location** it was shot at. A Word document records its **author**
and everyone who edited it. A PDF names the **software** that produced it. People
share these files assuming they reveal only what's on the surface — this tool
shows what's actually inside, which is both a privacy lesson and a core
forensic-investigation skill.

## Supported files

| Type | Extensions | Library | Reveals |
| --- | --- | --- | --- |
| Images | jpg, jpeg, png, tiff, webp | Pillow (EXIF) | GPS, camera make/model, software, author, timestamps |
| PDF | pdf | pypdf | author, authoring app, PDF engine, created/modified dates |
| Word | docx | python-docx | author, last editor, revision count, timestamps |
| Audio | mp3, flac, m4a, ogg, wav | mutagen | artist, encoder, recording date, technical info |

## Two ways to use it

### Command line

```bash
# analyze one file
python3 metadata_analyzer.py vacation_photo.jpg

# analyze a whole folder (recursively; skips unsupported files)
python3 metadata_analyzer.py ./evidence/

# generate the sample files, then scan them
python3 make_samples.py
python3 metadata_analyzer.py samples/
```

Output is colour-coded in a terminal (sensitive items flagged in red) and falls
back to clean plain text when piped to a file, or with `--no-color`.

### Web interface

A Flask front end (`web.py`) over the same extraction logic: drag a file in and
see the report in the browser, with any GPS coordinates plotted on an embedded
map.

```bash
python3 web.py        # then open http://127.0.0.1:5001
```

Uploads are analyzed and then deleted immediately — nothing is stored.

![web interface](docs/web-screenshot.png)

## Example output

Scanning the sample photo. The headline is the **Privacy Highlights** block,
which pulls the sensitive items out of the full dump so they don't get lost:

```
==========================================================================
  METADATA FORENSICS REPORT
  File: vacation_photo.jpg
  Type: image · 5.6 KB
==========================================================================

  PRIVACY HIGHLIGHTS  (7 sensitive items)
--------------------------------------------------------------------------
  ! Device make: Apple
      camera/phone manufacturer
  ! Device model: iPhone 13 Pro
      specific device fingerprint
  ! Software: Adobe Photoshop 25.0 (Windows)
      editing or capture software
  ! Artist / author: Jane Photographer
      named author
  ! GPS location: 37.8199, -122.4786
      https://maps.google.com/?q=37.8199,-122.4786

  GPS
--------------------------------------------------------------------------
    Latitude                  37.8199
    Longitude                 -122.4786
    Altitude (m)              67.0
==========================================================================
```

That GPS line is the demo that lands: a photo's coordinates turned into a
clickable map link. The DOCX sample is just as telling — it flags that the
document was **last modified by a different person than the author**, exposing
a collaboration the sharer may not have meant to reveal.

## How it works

1. **Identify the file** by extension and route it to the right handler.
2. **Extract** with the appropriate library — EXIF tags, the PDF info
   dictionary, DOCX core properties, or audio tags.
3. **Flag** the privacy-sensitive fields (identity, location, device, software,
   time) into a highlights block, with GPS converted from EXIF's
   degrees/minutes/seconds rationals into decimal coordinates plus a map link.
4. **Report** the highlights first, then the full metadata by section.

Each handler fails soft: an unreadable or metadata-free file is reported as
such rather than crashing the run, so folder scans complete cleanly.

## The sample files

`make_samples.py` generates four files carrying fabricated-but-realistic
metadata (the GPS point is a public landmark, the names are invented):

| File | Notable metadata |
| --- | --- |
| `vacation_photo.jpg` | GPS coordinates, iPhone model, Photoshop, author |
| `financial_report.pdf` | author, MS Word + Adobe producer, created/modified dates |
| `internal_memo.docx` | author + a different last-editor, revision count |
| `voice_note.mp3` | artist, encoder (LAME), recording date |

## Notes & limitations

- **Pillow vs ExifTool.** This tool uses Pillow for EXIF so it installs with a
  single `pip` command and needs no external binary. The industry reference,
  [ExifTool](https://exiftool.org/), reads more exotic tags (maker notes, XMP,
  IPTC); a natural extension is to call it when it's installed and fall back to
  Pillow otherwise.
- **Metadata can be absent or forged.** Many platforms strip metadata on upload,
  and any field can be edited, so treat findings as leads, not proof.
- **Scope.** This reads metadata only; it does not alter files or attempt
  steganography detection.

## Requirements

- Python 3.8+ and the packages in `requirements.txt` (Pillow, pypdf,
  python-docx, mutagen). `make_samples.py` additionally uses `piexif` and
  `ffmpeg` to build the demo files; the analyzer itself does not need them.

## Author

Built by Mitul Nigam as a hands-on digital-forensics project demonstrating
metadata extraction across file formats and privacy-aware reporting.
