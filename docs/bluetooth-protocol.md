# iDotMatrix RGB LED Panel — BLE Protocol Master Reference

Consolidated protocol reference for iDotMatrix pixel-display panels (16x16 / 32x32 / 64x64 RGB
matrices), built for the Home Assistant integration at github.com/whybutter/idotmatrix.

**Sources consolidated** (cited inline as `[8none1]`, `[Toon]`, `[derkalle4]`):

- **`[8none1]`** — `8none1/idotmatrix`. Best low-level reverse-engineering notes (`readme.md`,
  `decoding_bytes.md`, `idotmatrix_controller.py`). btsnoop captures + APK (`jadx`) disassembly.
- **`[Toon]`** — `Toon-nooT/idotmatrix-api-client`. Actively maintained fork; cleanest and most
  complete byte-builders (`idotmatrix/const.py`, `idotmatrix/modules/*.py`).
- **`[derkalle4]`** — `derkalle4/python3-idotmatrix-library`. The archived original. Agrees with
  the above on most commands but its **image-upload scheme is known-wrong for real hardware**
  (see Discrepancies).

All multi-byte length / CRC fields are **little-endian** unless noted. Byte values below are shown
in decimal or hex; `0x` prefixes hex.

---

## 1. BLE Identifiers

| Item | Value | Source |
|------|-------|--------|
| Device name prefix (advertised) | **`IDM-`** | `[Toon]` const.py (`BLUETOOTH_DEVICE_NAME = "IDM-"`); `[8none1]` scans for `IDM-` |
| Primary service UUID | `000000fa-0000-1000-8000-00805f9b34fb` | `[8none1]`, `[Toon]` |
| **Write characteristic** (send commands) | **`0000fa02-0000-1000-8000-00805f9b34fb`** | `[8none1]` (`WRITE_CMD_UUID`), `[Toon]` (`UUID_CHARACTERISTIC_WRITE_DATA`) |
| **Notify / read characteristic** | **`0000fa03-0000-1000-8000-00805f9b34fb`** | `[8none1]` (`NOTIFICATION_UUID`), `[Toon]` (`UUID_READ_DATA`) |
| Device-name service / char (GAP) | `00001800-...` / `00002a00-...` (read "Device Name") | `[Toon]` |
| Secondary vendor service (seen on some units) | `0000ae00-...` with `0000ae01` (write-without-response) / `0000ae02` (notify) | `[Toon]` const.py comments |

Write char `fa02` properties: `write-without-response` **and** `write` (write-with-response both
supported). Notify char `fa03`: `notify`. `[Toon]`

> Note: `[Toon]` const.py also defines legacy `UUID_NOTIFY = d44bc439-abfd-45a2-b575-925416129601`
> and `UUID_READ_CHANNEL/WRITE_CHANNEL = d44bc439-...-925416129600`. These are **not** the iDotMatrix
> characteristics used by the modules (they appear to be carried over from another device family);
> the modules all write to `fa02` and read/notify on `fa03`. Prefer the `fa0x` UUIDs.

Reported MTU / max-write-without-response size is commonly **514** bytes on 32x32/64x64 units,
but can report 20 (default) when the phone/host hasn't negotiated a larger MTU. `[Toon]`, `[8none1]`

---

## 2. Generic command framing convention

Almost every "control" (non-bulk) command is a short packet with this shape:

```
[ len_lo, len_hi, CMD, SUBCMD/FLAG, payload... ]
  \-----/          \-/  \---------/
  uint16 LE total   |    second selector byte, very often 0x01, 0x02, 0x80, or 0x00
  length of packet  command id
  (incl. these 2)
```

- **Bytes 0–1**: total packet length as a little-endian `uint16`, *including* the length bytes
  themselves. (For the short control packets this equals the whole array length, e.g. a 5-byte
  packet starts `05 00`.)
- **Byte 2**: the command id (e.g. `7`=power, `4`=brightness, `6`=flip, `1`=time, `3`=freeze/speed,
  `9`=chronograph, `8`=countdown, `10`=scoreboard, `5`=graffiti, `2`=color/eco...).
- **Byte 3**: a selector/flag byte. Recurring values: `0x01`, `0x02`, `0x80` (=128), `0x00`. The
  same command id with a different byte-3 means a different operation, so command id alone does not
  identify the packet.
- **Bytes 4+**: command-specific payload.

Bulk transfers (Image / GIF / Text) do **not** use this short form — they have their own multi-byte
headers with length + CRC32 and are chunked (see those sections).

**Settle delay / flow control (important):** After each command, wait before sending the next.
`[Toon]` defaults to **0.5 s sleep when writing without response**, and **0 s when writing
with-response** (because the response ack already gates the next write). `[8none1]` uses
`time.sleep(1)` between GIF chunks. `[derkalle4]` sleeps `0.01 s` between BLE sub-chunks. See
Discrepancies for the recommended approach.

---

## 3. Power (on/off)

```
On :  05 00 07 01 01
Off:  05 00 07 01 00
```
- `05 00` len, `07` cmd=power, `01` selector, last byte `1`=on / `0`=off.
- Confirmed by all three: `[8none1]` (`switch_on`), `[Toon]` (`turn_on`/`turn_off`/`set_screen_state`),
  `[derkalle4]` (`screenOn`/`screenOff`).

---

## 4. Brightness

```
05 00 04 80 <percent>
```
- `04`=cmd, `80`(=128)=selector, `<percent>` = brightness **5–100** (percent, single byte). Values
  outside 5–100 are rejected by the libraries.
- Confirmed by `[Toon]` (`set_brightness`) and `[derkalle4]` (`setBrightness`). Note command `04`
  with selector `01` is instead the DIY image-mode toggle (Section 9), and `04` with selector `80`
  value `0x50` appears in the reset sequence (Section 8) — the selector byte disambiguates.

---

## 5. Flip / rotate 180°

```
05 00 06 80 <flip>
```
- `06`=cmd, `80`=selector, `<flip>` = `1` rotated 180° / `0` normal.
- Confirmed by `[Toon]` (`set_screen_flipped`) and `[derkalle4]` (`flipScreen`).
- (Command `06` with selector `01` is the Clock command — Section 10.)

---

## 6. Freeze / unfreeze screen

```
04 00 03 00
```
- 4-byte packet: `04 00` len, `03`=cmd, `00`=selector. Toggles freeze state on the device.
- Confirmed by `[Toon]` (`freeze_screen`) and `[derkalle4]` (`freezeScreen`).
- (Command `03` with selector `01` is Speed — Section 7 — and `03 02` is Effects — Section 12.)

---

## 7. Speed

```
05 00 03 01 <speed>
```
- `03`=cmd, `01`=selector, `<speed>` single byte.
- Present in `[Toon]` (`set_speed`) and `[derkalle4]` (`setSpeed`) but both note it is **not
  referenced anywhere in the iDotMatrix Android app** — likely a leftover / unconfirmed on hardware.
  (Text and GIF carry their own per-effect speed fields, which *are* used.)

---

## 8. Set Time / Date

```
0b 00 01 80 <YY> <MM> <DD> <DOW> <hh> <mm> <ss>
```
- `0b 00` len (=11), `01`=cmd=set-time, `80`(=128)=selector.
- **`YY`** = `year % 100` (`[Toon]`, `[derkalle4]`). `[8none1]` observed the app sends
  `year & 0xFF` (e.g. 2023 → 231) and concludes the **year is effectively irrelevant** to the
  device. `year % 100` (0–99) is the safer maintained choice.
- **`MM`** month (1–12), **`DD`** day (1–31).
- **`DOW`** = day of week, **1–7** (Monday=1). Computed as Python `datetime.weekday()+1`
  (`.weekday()` is Mon=0). `[8none1]` uses `tm_wday + 1`.
- **`hh mm ss`** hour (0–23, 24h), minute, second.
- Confirmed by all three. Byte layout diagram in `[8none1]` readme.

Example (`[8none1]`): `0b 00 01 80 e7 0c 12 01 0a 26 10`.

---

## 9. Reset

Two-packet sequence:
```
04 00 03 80          (reset)
05 00 04 80 50       (follow-up)
```
- `[derkalle4]` `reset()` sends **both** packets.
- `[Toon]` `reset()` sends **only the first** packet `04 00 03 80` (comment: the second may be
  unnecessary). `[8none1]` `send_reset_command()` sends both but notes "maybe the first command is
  all that's needed."
- Discovered by `[8none1]` (credited in `[Toon]`/`[derkalle4]` docstrings).
- ⚠️ Note byte-3 collision: `04 00 03 80` (reset) vs `04 00 03 00` (freeze). The selector byte
  (`80` vs `00`) is what distinguishes them.

---

## 10. DIY / Image upload — RAW RGB pixel data

This is the correct scheme for pushing a still image. **The pixel payload is raw RGB bytes
(`R,G,B` per pixel, row-major), NOT an encoded PNG/JPEG file.** `[Toon]`, `[8none1]`

### 10a. Precondition — enable DIY draw mode first

```
05 00 04 01 <mode>
```
- `04`=cmd, **`01`=selector (DIY mode)**, `<mode>`: `0`=disable DIY, **`1`=enable DIY**, `2`/`3`=unknown.
- You must send `mode=1` **before** uploading pixel data. `[Toon]` `ImageModule.set_mode`,
  `[derkalle4]` `Image.setMode`.
- (Contrast with `05 00 04 80 <percent>` = brightness. Selector `01` vs `80` is the difference.)

### 10b. Pixel payload

- Build a flat `bytearray` of `pixel_size*pixel_size` pixels, 3 bytes each (R, G, B), row-major
  (top-left first). For 32x32 that is `32*32*3 = 3072` bytes. `[Toon]` `upload_image_pixeldata` /
  `_load_image_and_adapt_to_canvas` (uses `PIL img.convert("RGB").tobytes()`).

### 10c. Chunking + 9-byte per-chunk header (`sendDIYImageData`)

Split the RGB payload into **4096-byte** chunks. Each chunk is prefixed with a **9-byte header**:

```
offset  field
0..1    uint16 LE  = len(chunk) + 9   (this packet's length incl. header)
2       0x00       (type)
3       0x00       (subtype)
4       0x00 for the first chunk, 0x02 for every continuation chunk
5..8    uint32 LE  = total length of the whole RGB payload (all chunks, data only)
9..     the 4096-byte (or smaller final) RGB chunk
```
Then each `header+chunk` "large packet" is further split into BLE writes of MTU size
(`509` if MTU enabled, else `18`). Sent with write-with-response. `[Toon]`
`_create_diy_image_data_packets`.

> There is **no CRC32** in the DIY image header (unlike GIF/Text). `[Toon]`

---

## 11. GIF upload (animation)

The device accepts a **standard GIF file** (must match panel size, e.g. 32x32), streamed with
framing headers. `[8none1]` proved (by carving the bytes back out to disk) that the payload is
literally the GIF file bytes, starting `GIF89a` (`47 49 46 38 39 61`) and ending with `0x3B`.

### 11a. Chunking + 16-byte header (master + per-chunk)

Split the GIF file into **4096-byte** chunks. Each chunk gets a **16-byte header**:

```
offset  field
0..1    uint16 LE  = len(chunk) + 16     (this packet length incl. 16-byte header)
2       0x01                             (fixed)
3       0x00                             (fixed)
4       0x00 for first chunk, 0x02 for continuation chunks (multi-chunk indicator)
5..8    uint32 LE  = total GIF file length over ALL chunks (data only, headers not counted)
9..12   uint32 LE  = CRC32 of the WHOLE GIF file (data only, not headers)
13..14  time-signature bytes (see below)
15      GIF "type" byte (see below)
```

- **Bytes 13–14 (time sign) & 15 (type):**
  - `[8none1]` observed the trailer `05 00 0d` in real captures (i.e. `13`=0x05, `14`=0x00, `15`=0x0d).
  - `[Toon]` `create_gif_data_packets` generalizes it: if `gif_type == 12`, bytes 13–14 = `00 00`;
    otherwise bytes 13–14 = `ConvertTime(time_sign)` as a **big-endian** uint16 where the time-sign
    key maps `1→10, 2→30, 3→60, 4→300, else→5`. Byte 15 = `gif_type & 0xFF`.
  - `gif_type` values ≤ 19 all display an image; `[Toon]` uses `12` ("no time signature") for a
    single GIF and notes `13` = "DIY animation". `[8none1]`'s captures used `0d` (=13) in byte 15.
  - Its exact meaning is not fully pinned down; both agree it rarely matters for a single upload.

- CRC32 = standard `zlib.crc32(gif_bytes) & 0xFFFFFFFF`, stored little-endian. `[8none1]`, `[Toon]`,
  `[derkalle4]`.

### 11b. BLE sub-chunking

Each 16-byte-header + 4096-byte "large packet" is then split into BLE writes of `509` bytes (MTU
enabled) or `18` bytes (disabled). `[Toon]`.

### 11c. Flow control

- After each 4K block, the device sends a notification `05 00 01 00 01` when ready for the next; on
  completion it sends `05 00 01 00 03`. Simplest robust approach per `[8none1]`: just `sleep(1)`
  between blocks. Max BLE payload chunk 4 kB. `[8none1]` readme.
- **The ack echoes the payload-type byte.** The notification is `05 00 <type> 00 <01|03>`, where
  `<type>` is header byte 2 of the block that was sent — `01` for a GIF/animation asset, `02` for a
  raw-pixel still asset. So a still asset finishes with `05 00 02 00 03`, *not* `05 00 01 00 03`.
  Gate each asset on the marker derived from the block you actually sent; hardcoding the GIF marker
  makes every still upload sit out its full timeout. Measured on hardware (IDM-C8A2BC, fw as of
  2026-08).
- The device tolerates only a limited frame count; `[Toon]` caps GIFs to **64 frames** and
  ~2000 ms total, re-timing / dropping intermediate frames, and forces PIL `optimize=True`
  (disabling optimize breaks the transfer). `[Toon]` gif.py.

### 11d. Master vs. secondary header example (`[8none1]`)

```
1st (master) : 10 10 01 00 00 b9 18 00 00 db 42 cb 14 05 00 0d
2nd (chunk)  : c9 08 01 00 02 b9 18 00 00 db 42 cb 14 05 00 0d
```
`10 10`→0x1010=4112 = 4096 chunk + 16 header. `b9 18 00 00`→0x000018b9 total GIF len.
`db 42 cb 14` = CRC32 (LE). Byte 4 = `00` (first) then `02` (continuation).

---

## 12. Text

The single richest command. Text is sent as **per-character monochrome bitmaps** with two stacked
headers, chunked to 4 kB with a spanning CRC32. Primary decoding by `[8none1]`; implemented cleanly
by `[Toon]` (`TextModule`) and `[derkalle4]`.

### 12a. Per-character bitmap

- Each character is rendered to a **16 wide × 32 tall** monochrome image (for font size "32").
- Row-major, **little-endian bit packing**: within each row, bit `x%8` of the byte = pixel; low bit
  first. `[8none1]` `string_to_bitmaps`, `[Toon]` `_string_to_bitmaps`.
- Each character's bitmap is prefixed with a 4-byte separator **`05 FF FF FF`**:
  - Byte 0 = **font-size code**: `0x05` (=5) → size "32" (16x32 glyph); `0x02` → size "16"
    (8x16 glyph). (`[8none1]`: "5 is 32 bits", a 2/3 is size 16.)
  - Bytes 1–3 = `FF FF FF` (fixed, shown as `-1` in jadx).
- For a 16x32 glyph the bitmap is `32 rows × 2 bytes = 64` bytes, so each char block is
  `4 (separator) + 64 = 68` bytes. Multiple characters are concatenated, one block each.

### 12b. Header 2 — text metadata (14 bytes, precedes the bitmaps)

```
offset  field                       source
0..1    uint16 LE  = number of characters (count of 05FFFFFF separators)
2       0x00                        (fixed)
3       0x01                        (fixed)
4       text mode (0..8)            see 12d
5       speed (0..100, e.g. 95/100) larger = faster scroll
6       text color mode (0..5)      see 12e
7       text color R
8       text color G
9       text color B
10      text background mode (0/1)  see 12f
11      background R
12      background G
13      background B
```
`[8none1]` readme "Header 2"; `[Toon]` `_build_string_packet` (`text_metadata`); `[derkalle4]`.

### 12c. Header 1 — outer transport header (16 bytes, precedes Header 2)

```
offset  field
0..1    uint16 LE  = TOTAL length of everything incl. this header and any continuation packets
2       0x03                        (fixed)
3       0x00                        (fixed)
4       0x00  (continuation marker; app set this if payload > 4096)
5..8    uint32 LE  = length of (Header 2 + all bitmaps)  == total_len - 16
9..12   uint32 LE  = CRC32 spanning Header-2 + all bitmaps
13..14  0x00 0x00  (if "thing"/byte15 == 0x0c, else time-related)
15      0x0c                        ("thing")
```
`[8none1]` readme "Header 1" + `decoding_bytes.md`; `[Toon]` `_build_string_packet` (`header`).

**CRC32 (critical):** compute `zlib.crc32` over the **text-metadata header plus ALL bitmaps**
(everything after the 16-byte Header 1, even bitmaps that spill into a later BLE packet). Store
little-endian in Header-1 bytes 9–12. `[8none1]` example: CRC `0x49317daa` → bytes `aa 7d 31 49`.

### 12d. Text modes (byte 4)

| Val | Mode | Source |
|-----|------|--------|
| 0 | Fixed / replace (static) | `[8none1]`, `[Toon]` `REPLACE` |
| 1 | Marquee — left→right scroll | `[8none1]`, `[Toon]` `MARQUEE` |
| 2 | Reversed marquee (right→left; letters reversed — for RTL) | `[8none1]`, `[Toon]` `REVERSED_MARQUEE` |
| 3 | Vertical rising / up scroll | `[8none1]`, `[Toon]` `VERTICAL_RISING_MARQUEE` |
| 4 | Vertical lowering / down scroll | `[8none1]`, `[Toon]` `VERTICAL_LOWERING_MARQUEE` |
| 5 | Strobe / blinking | `[8none1]`, `[Toon]` `BLINKING` |
| 6 | Fade | `[8none1]`, `[Toon]` `FADING` |
| 7 | Falling blocks / tetris | `[8none1]`, `[Toon]` `TETRIS` |
| 8 | Laser / filling | `[8none1]`, `[Toon]` `FILLING` |

### 12e. Text color modes (byte 6)

| Val | Meaning | Source |
|-----|---------|--------|
| 0 | White (ignore RGB) | `[Toon]` `WHITE` (`[8none1]` "?") |
| 1 | Fixed — use given RGB | `[8none1]`, `[Toon]` `RGB` |
| 2 | Rainbow / blue→red gradient | `[8none1]`, `[Toon]` `RAINBOW_1` |
| 3 | Rainbow / pastels gradient | `[8none1]`, `[Toon]` `RAINBOW_2` |
| 4 | Rainbow / pink→orange gradient | `[8none1]`, `[Toon]` `RAINBOW_3` |
| 5 | Rainbow (4) | `[Toon]` `RAINBOW_4` (`[8none1]` "?") |

### 12f. Text background mode (byte 10)

| Val | Meaning |
|-----|---------|
| 0 | Off (transparent/black) |
| 1 | Solid color (use background RGB in bytes 11–13) |

`[8none1]`, `[Toon]` (`text_bg_mode = 0 if no bg color else 1`).

### 12g. Full example (`[8none1]`)

```
0a03 03 00 00 fa020000 aa7d3149 0000 0c | 0b00 00 01 01 62 02 21ca ff0000 00 000000 | 05ffffff <64B glyph> 05ffffff ...
\-------- Header 1 (16B) -------------/   \------ Header 2 (14B) --------------/   \---- per-char blocks ----/
```
`0a 03`→0x030a=778 total length. `fa 02 00 00`→0x02fa=762 = 778−16 (Header2+bitmaps len).
`aa 7d 31 49` = CRC32 LE. Trailer `00 00 0c`.

---

## 13. Clock

```
08 00 06 01 <styleFlags> <R> <G> <B>
```
- `08 00` len, `06`=cmd, **`01`=selector (clock; vs `80` for flip)**.
- **`styleFlags`** = `style | (0x80 if show_date) | (0x40 if hour24)`, where `style` is 0–7.
- `R G B` clock color.
- `[Toon]` `ClockModule._create_payload`, `[derkalle4]` `Clock` (identical formula).

**Clock styles (0–7)** `[Toon]` `ClockStyle`:
0 RGB-swipe outline, 1 Christmas tree, 2 Checkers, 3 Color, 4 Hourglass, 5 Alarm clock,
6 Outlines, 7 RGB corners.

Optional (present but "does not seem to work"): time indicator `05 00 07 80 <0/1>`. `[Toon]`
`set_time_indicator`.

---

## 14. Chronograph (stopwatch)

```
05 00 09 80 <mode>
```
- `09`=cmd, `80`=selector. `<mode>`: **0**=reset (and show), **1**=(re)start from zero,
  **2**=pause, **3**=resume after pause.
- `[Toon]` `ChronographModule`, `[derkalle4]` `Chronograph` (identical).

---

## 15. Countdown / timer

```
07 00 08 80 <mode> <minutes> <seconds>
```
- `08`=cmd, `80`=selector. `<mode>`: **0**=disable, **1**=start, **2**=pause, **3**=restart.
- `<minutes>` 0–59, `<seconds>` 0–59.
- `[Toon]` `CountdownModule._create_payload`, `[derkalle4]` `Countdown` (identical).

---

## 16. Scoreboard

```
08 00 0a 80 <c1_lo> <c1_hi> <c2_lo> <c2_hi>
```
- `0a`(=10)=cmd, `80`=selector. Two counters, each a `uint16` **little-endian** (built via
  `struct.pack("!H", ...)` big-endian then written low byte first). Each clamped **0–999**
  (higher risks buffer overflow on device).
- `[Toon]` `ScoreboardModule.show`, `[derkalle4]` `Scoreboard.setMode` (identical).

---

## 17. Effects (built-in animated backgrounds)

```
<6+3N> 00 03 02 <style> 90 <N> <R1 G1 B1> <R2 G2 B2> ... <RN GN BN>
```
- Byte 0 = `6 + N` where `N` = number of colors (packet length low byte). `03`=cmd, **`02`=selector**.
- **`<style>`** 0–6 (see below). Byte 5 = `90` (=144, a fixed speed/param). Byte 6 = `N`
  (count of RGB triples). Then `N` RGB triples. `N` must be **2–7**.
- `[Toon]` `EffectModule._compute_payload`, `[derkalle4]` `Effect` (identical).

**Effect styles (0–6)** `[Toon]` `EffectStyle`:
0 horizontal rainbow gradient, 1 random colored pixels on black, 2 random white pixels on
changing background, 3 vertical rainbow, 4 diagonal-right rainbow, 5 diagonal-left rainbow on black,
6 random colored pixels.

---

## 18. Fullscreen color

```
07 00 02 02 <R> <G> <B>
```
- `02`=cmd, **`02`=selector**, then RGB. Fills the whole panel with one color.
- `[Toon]` `FullscreenColorModule._create_payload`, `[derkalle4]` `FullscreenColor` (identical).
- (Command `02` selector `80` is Eco mode; selector `01`/`12`... in System — the selector
  disambiguates.)

---

## 19. Eco mode (auto-dim by time of day)

```
0a 00 02 80 <enabled> <startH> <startM> <endH> <endM> <ecoBrightness>
```
- `0a 00` len (=10), `02`=cmd, `80`=selector. `<enabled>` 0/1. Start/end hour (0–23) and minute
  (0–59). `<ecoBrightness>` 0–255 (brightness while in eco window; 0 effectively disables the dim).
- `[Toon]` `EcoModule._compute_payload`, `[derkalle4]` `Eco` (identical).

---

## 20. Graffiti (set individual pixels)

Draw specific pixels in a chosen color. **The header differs between repos** — see below.

### 20a. Single-pixel form (`[8none1]`, `[derkalle4]`) — 10 bytes

```
0a 00 05 01 00 <R> <G> <B> <X> <Y>
```
- `0a 00` len (=10), `05`=cmd=graffiti, `01`=selector, byte 4 = `00`. Then RGB, then X, Y (0–31).
- `[8none1]` `graffiti_paint` (validated: drew a red spiral on real hardware). `[derkalle4]`
  `Graffiti.setPixel` (identical layout).

### 20b. Multi-pixel form (`[Toon]`) — variable length

```
<len_lo> <len_hi> 05 01 00 <R> <G> <B> <X1> <Y1> <X2> <Y2> ...
```
- Bytes 0–1 = `uint16 LE` length = `8 + 2*num_pixels`. `05`=cmd, byte 3 = `1` (documented as a
  "mirroring mode 1–4", TODO in source), byte 4 = `0`. Then one shared RGB, then N (X,Y) pairs.
- Max ~255 pixels per packet (trial and error). Single-pixel `set_pixel` uses `sleep_after=0.02`;
  multi-pixel `set_pixels` uses write-with-response.
- `[Toon]` `GraffitiModule._create_payload`. This is a superset: with one coordinate it reduces to
  the same 10 bytes as 20a (`0a 00 05 01 00 R G B X Y`).

> Practical note: enable/consistency with DIY mode is not required for graffiti; `[8none1]` sends it
> directly after power-on + time-sync.

---

## 21. Password / System

### 21a. Set password
```
08 00 04 02 01 <pwd_high> <pwd_mid> <pwd_low>
```
- `04`=cmd, `02`=selector, then `01`, then 3 password bytes. 6-digit password 000000–999999 split as:
  `pwd_high = (pw // 10000) % 256`, `pwd_mid = (pw // 100) % 100`, `pwd_low = pw % 100`.
- Clear the password by resetting the device.
- `[Toon]` `set_password`, `[derkalle4]` `setPassword` (identical).

### 21b. Delete device data / factory-ish reset of stored data
```
11 00 02 01 0c 00 01 02 03 04 05 06 07 08 09 0a 0b
```
- `11 00` len (=17), `02`=cmd, `01`=selector, then `0c` and the sequence 0..11.
- `[Toon]` `SystemModule.delete_device_data` only. (Not in the others.)

### 21c. Get device location (untested / incomplete)
- `[Toon]` `SystemModule.get_device_location` builds a 16-byte command
  `06 4c 4f 43 41 54 45 00...` ("...LOCATE...") and is meant to be **AES-encrypted** per the Android
  app before sending. The current implementation uses a Fernet placeholder and is **not working**.
  Flagged unimplemented.

### 21d. "Joint" mode (unknown)
```
05 00 0c 80 <mode>
```
- `0c`(=12)=cmd, `80`=selector. Purpose unknown. `[Toon]` `set_joint`, `[derkalle4]` `setJoint`.

### 21e. Music / mic sync (mostly unused)
`[Toon]` `MusicSyncModule`:
- Set mic type: `06 00 0b 80 <type>` (`0b`=cmd; unused in app).
- Image rhythm on: `06 00 00 02 <value1> 01`; stop: `06 00 00 02 00 00` (shows a dancing stick
  figure that reacts when value changes). Raw rhythm streaming (`send_rhythm`) intentionally not
  implemented (device has its own onboard mic).

---

## 21f. Device-side albums (the stored-asset carousel)

Verified on hardware (IDM-C8A2BC) — the panel stores "material" assets and rotates through them by
itself. There is **no "play album" command**: storing the assets *is* the trigger.

- **Wipe then re-flash.** The store is write-only (no per-slot delete), so replacing an album is
  `delete-all` (§21b) followed by the new assets in order.
- **Byte 15 of each asset header is the 0-based album slot index** (not `0xFF`).
- **One asset at a time**, each gated on the previous asset's finish-ack (§11c). Measured: 8 large
  animations, 304 KB / 80 blocks, all stored in 43 s with zero missed acks.

### Two banks — stills and animations do not mix

The panel keeps raw-pixel still assets (header type `0x02`) and GIF assets (`0x01`) in **separate
banks**, and when both are non-empty the carousel plays **only the GIF bank**. The stills are
accepted and finish-ack normally — they are simply never displayed. Confirmed in both orders
(stills-then-GIFs and GIFs-then-stills); either type *alone* plays correctly.

Practical consequence: send every album asset through the GIF agreement, encoding stills as
single-frame GIFs. That makes playback independent of what an album happens to contain.

### Slide dwell = the GIF's total frame duration

The header's interval time-sign (bytes 13–14) does **not** drive the carousel for GIF assets. The
panel plays exactly **one pass through the frames**, then advances. Measured:

| encoding | dwell |
|---|---|
| 1 frame, 100 ms (PIL default) | **never displayed at all** |
| 1 frame, 10 000 ms | 10 s |
| 20 frames x 500 ms | 10 s |
| 12-frame 3.6 s loop, `loop=0` | 3.5 s |
| same, Netscape `loop=5` | 3.5 s — **loop count is ignored** |
| same, frames repeated x3 (10.8 s) | 11 s |

So a still must be encoded with `duration = interval`, or the carousel skips straight past it. To
make an *animation* fill an interval you must physically repeat its frames (which multiplies the
upload size); there is no cheap loop-count route.

---

## 22. Discrepancies & gotchas

1. **Image upload: raw RGB (correct) vs PNG-file bytes (WRONG).**
   - ✅ `[Toon]` and `[8none1]` send **raw RGB pixel bytes** (`R,G,B` per pixel, row-major,
     `size*size*3` bytes) behind a **9-byte** per-4K-chunk header (Section 10). This is what real
     hardware expects for DIY still images.
   - ❌ `[derkalle4]` `image.py` (`uploadProcessed`/`uploadUnprocessed`) instead saves the image as
     a **PNG file** and streams the encoded PNG bytes. Its `_createPayloads` also builds a
     malformed header: `idk = len(png_data) + len(png_chunks)` (mixing byte-count with chunk-count),
     packs it as a signed 16-bit short, and never sends a CRC. **This scheme is known-wrong for real
     panels** — treat `[derkalle4]`'s image upload as a historical artifact and follow `[Toon]`.
   - Note the header sizes also differ by design: **DIY image = 9-byte header, no CRC**;
     **GIF = 16-byte header, with CRC32** (Section 11). Don't conflate them.

2. **Graffiti header form.** `[8none1]`/`[derkalle4]` document a fixed 10-byte single-pixel packet
   `0a 00 05 01 00 R G B X Y`. `[Toon]` generalizes to a length-prefixed multi-pixel packet with
   byte-3 = mirroring mode (1–4). Both agree on `05`=cmd and the `...00 R G B (X Y)...` tail; the
   single-pixel case is byte-identical. Use `[Toon]`'s form for batching, but note byte 3 is a
   mirror-mode selector there, documented as fixed `01` elsewhere.

3. **Reset second packet.** `[8none1]`/`[derkalle4]` send `04 00 03 80` **then** `05 00 04 80 50`;
   `[Toon]` sends only the first and comments the second is likely superfluous. Sending both is the
   conservative choice; both note the follow-up may be unnecessary.

4. **Set-time year.** `[Toon]`/`[derkalle4]` use `year % 100`; `[8none1]` observed the app uses
   `year & 0xFF` and believes the device ignores the year entirely. Either works; `% 100` keeps the
   byte in 0–99.

5. **CRC scope must be exact.**
   - **Text:** CRC32 over `Header-2 + all bitmaps` (everything after the 16-byte Header 1), stored
     LE. Getting the span wrong (e.g. including Header 1, or missing spilled bitmaps) makes the
     device reject/garble the text. `[8none1]`.
   - **GIF:** CRC32 over the **entire GIF file data only** (never over the 16-byte headers), stored
     LE. `[8none1]`, `[Toon]`, `[derkalle4]` agree.
   - **DIY image:** **no CRC** at all. `[Toon]`.
   - Use standard `zlib.crc32(data) & 0xFFFFFFFF` (matches Java's `CrcUtils.CRC32`). `[Toon]` notes
     the only subtlety is masking to unsigned 32-bit before taking the LE bytes.

6. **Chunking / MTU.** Bulk payloads are first split into **4096-byte** logical chunks (each getting
   its own header), then each header+chunk is split again into BLE writes of **509 bytes** (MTU
   enabled) or **18 bytes** (MTU disabled/default). These MTU constants come straight from the
   Android `GifAgreement.java`. `[Toon]` image.py/gif.py (`MTU_SIZE_IF_ENABLED=509`,
   `MTU_SIZE_IF_DISABLED=18`). Devices commonly report `max_write_without_response_size` of 514.

7. **Inter-command settle delay (0.5 s).** The device needs a moment between commands. `[Toon]`'s
   base `_send_bytes` sleeps **0.5 s after any write-without-response**, and **0 s when writing
   with-response** (the ack gates the next write) — so prefer write-with-response for back-to-back
   control commands, and insert ~0.5 s pauses when firing rapid write-without-response packets.
   `[8none1]` uses a blunt `sleep(1)` between GIF chunks; `[derkalle4]` sleeps only 0.01 s between
   BLE sub-chunks (too short for reliable back-to-back commands on some units).

8. **GIF flow-control acks.** Device notifies `05 00 01 00 01` (ready for next 4K block) and
   `05 00 01 00 03` (upload complete) on char `fa03`. You may wait on these or just `sleep(1)`
   between blocks. `[8none1]`.

9. **Frame limits.** `[Toon]` caps GIF at **64 frames** / ~2000 ms and forces PIL `optimize=True`
   (disabling it breaks transfers); it also notes an unresolved edge case where a second upload
   after a success sometimes leaves the previous GIF "stuck." `[derkalle4]` does no frame limiting.

10. **Speed command (`05 00 03 01 <speed>`) is unconfirmed.** Both maintained libs carry it but flag
    it as never referenced by the Android app; real per-effect speed lives in the Text metadata
    (byte 5) and GIF frame durations, not this command.

11. **UUID confusion in `[Toon]` const.py.** It defines extra `d44bc439-...` UUIDs that are unused
    by the actual modules. The live characteristics are `fa02` (write) and `fa03` (notify). Ignore
    the `d44bc439` set for iDotMatrix.

12. **Byte-3 selector collisions to watch** (same command id, different operation):
    `04 01`=DIY-mode vs `04 80`=brightness vs `04 02 01`=password;
    `06 01`=clock vs `06 80`=flip;
    `03 00`=freeze vs `03 01`=speed vs `03 02`=effects;
    `02 02`=fullscreen color vs `02 80`=eco vs `02 01`=delete-data;
    `07 01`=power vs `07 80`=clock time-indicator;
    `04 80 50` (in reset) vs `04 80 <5..100>` (brightness) — differentiated by value range and
    the preceding `04 00 03 80`.

---

## Appendix — quick command table

| Feature | Bytes (hex/dec) | cmd/sel |
|---------|-----------------|---------|
| Power on/off | `05 00 07 01 01` / `...00` | 7 / 1 |
| Brightness | `05 00 04 80 <5-100>` | 4 / 128 |
| Flip 180 | `05 00 06 80 <0/1>` | 6 / 128 |
| Freeze | `04 00 03 00` | 3 / 0 |
| Speed (unconfirmed) | `05 00 03 01 <speed>` | 3 / 1 |
| Set time | `0b 00 01 80 YY MM DD DOW hh mm ss` | 1 / 128 |
| Reset | `04 00 03 80` [`+ 05 00 04 80 50`] | 3 / 128 |
| DIY mode enable | `05 00 04 01 01` | 4 / 1 |
| DIY image chunk hdr (9B) | `len16 00 00 (00/02) len32` + RGB | — |
| GIF chunk hdr (16B) | `len16 01 00 (00/02) totlen32 crc32 tt tt type` | — |
| Text hdr1 (16B) | `len16 03 00 00 metaLen32 crc32 00 00 0c` | 3 / — |
| Text hdr2 (14B) | `nChars16 00 01 mode spd colMode R G B bgMode bR bG bB` | — |
| Clock | `08 00 06 01 (style|dateFlag|24Flag) R G B` | 6 / 1 |
| Chronograph | `05 00 09 80 <0-3>` | 9 / 128 |
| Countdown | `07 00 08 80 mode min sec` | 8 / 128 |
| Scoreboard | `08 00 0a 80 c1lo c1hi c2lo c2hi` | 10 / 128 |
| Effects | `(6+N) 00 03 02 style 90 N RGB...` | 3 / 2 |
| Fullscreen color | `07 00 02 02 R G B` | 2 / 2 |
| Eco | `0a 00 02 80 en sH sM eH eM ecoBright` | 2 / 128 |
| Graffiti (1px) | `0a 00 05 01 00 R G B X Y` | 5 / 1 |
| Graffiti (Npx) | `len16 05 01 00 R G B (X Y)...` | 5 / 1 |
| Password | `08 00 04 02 01 hi mid lo` | 4 / 2 |
| Delete data | `11 00 02 01 0c 00 01 02..0b` | 2 / 1 |
| Joint (unknown) | `05 00 0c 80 mode` | 12 / 128 |
| Mic type | `06 00 0b 80 type` | 11 / 128 |
| Image rhythm on/off | `06 00 00 02 v 01` / `06 00 00 02 00 00` | 0 / 2 |
```
