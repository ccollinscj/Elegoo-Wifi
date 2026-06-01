# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Python Tkinter GUI tool (`ChituCode.py`) for uploading print files and starting print jobs on Elegoo/Chitu resin 3D printers over WiFi. Two pre-built Windows executables (`chitu8.exe`, `chituv2.exe`) are bundled distributions of earlier versions.

## Running the App

```bash
python ChituCode.py
```

**Dependencies** (install via pip if missing):
```bash
pip install requests websocket-client
```
`tkinter` is part of the Python standard library but may require `python3-tk` on Linux (`apt install python3-tk`).

## Network Protocol

The printer communication uses the **SDCP (Chitu Systems Data Communication Protocol)**. All commands share the same envelope structure with a `Topic` of `sdcp/request/{MainboardID}`.

### Discovery
UDP broadcast on port 3000 with the string `"M99999"`. The printer responds with JSON containing `Data.MainboardIP` and `Data.MainboardID`.

### File Upload
HTTP POST to `http://{MainboardIP}:3030/uploadFile/upload` as multipart form data.
Required custom headers: `S-File-MD5` (hex MD5 of the whole file), `Check` (`"1"`), `Offset` (`"0"`), `Uuid` (UUID4 without dashes), `TotalSize` (file size in bytes).
Success response: `{"code": "000000"}`.

### WebSocket Commands
WebSocket endpoint: `ws://{MainboardIP}:3030/websocket`

| Cmd | Purpose | Key fields in `Data.Data` |
|-----|---------|--------------------------|
| 258 | Get file list | `Url: "/local/"` → response has `FileList[].name` |
| 128 | Start print | `Filename`, `StartLayer: 0` |

**Ack codes** returned in `Data.Data.Ack` for Cmd 128:
- `0` = success, `1` = printer busy, `2` = file not found, `3` = MD5 fail,
- `4` = file read fail, `5` = resolution mismatch, `6` = unknown format, `7` = machine model mismatch

## Application Flow

1. **Discover** — UDP broadcast finds the printer's IP and mainboard ID
2. **Select file** — file picker opens; upload button enables once both file and IP are ready
3. **Upload** — HTTP POST with MD5/UUID headers; on success, a WebSocket call (Cmd 258) refreshes the file list and updates `self.uploaded_filename` to the name as stored on the printer
4. **Print** — WebSocket Cmd 128 with the printer-side filename triggers the job

The `uploaded_filename` is intentionally re-fetched from the printer after upload (step 3) because the printer may rename or store the file differently than the local name.
