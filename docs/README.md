# iDotMatrix — Reverse-Engineering & Reference Docs

These documents capture what we had to reverse-engineer to build this
integration, so the next person on the same journey doesn't have to rediscover it.
Everything here was recovered from the official app's APK and community projects
and **verified against real hardware / the live API**.

## Contents

- **[bluetooth-protocol.md](./bluetooth-protocol.md)** — the complete BLE protocol
  for the panel: service/characteristic UUIDs, command framing, and every feature
  (power, brightness, flip, clock, effects, chronograph, countdown, scoreboard,
  eco, text, and the image/GIF/album upload transport). Ends with a "discrepancies
  & gotchas" section and a quick command table.

- **[cloud-catalog.md](./cloud-catalog.md)** — the app's cloud art catalog: the
  signed + AES-encrypted `getMaterialUnderCategory` endpoint, the category naming
  (`<tab>_IDM` + the crucial `label="ALL"`), and — the part that stumps everyone —
  how a downloaded asset is an **obfuscated text envelope**, not an image, and the
  exact decode to recover the real PNG/GIF.

- **[architecture.md](./architecture.md)** — how this integration is structured
  (Python modules, frontend, and the two BLE behaviors that are easy to get wrong).

## The short version — what was non-obvious

If you only read one paragraph:

- **BLE:** the panel stops advertising while connected (so availability = connected
  OR advertising); uploads must be **write-without-response**, **paced** (~20 ms),
  and **sub-chunked** (~180 B) or the proxy drops them and the screen stays black;
  device-side albums use a **per-asset index byte** and are **ack-gated** one asset
  at a time, with no separate "play" command.
- **Cloud catalog:** the current endpoint requires an **md5 sign + AES-256-CBC**
  (all keys hard-coded in the app, no login); categorised content needs
  **`label="ALL"`** (not `Product_`); and asset downloads return **obfuscated
  text** — strip a 32-char nonce off each end, `+`→space, URL-decode, **reverse the
  string**, then Base64-decode to the real image.

## Credits & prior art

- [derkalle4/python3-idotmatrix-client](https://github.com/derkalle4/python3-idotmatrix-client)
  and [python3-idotmatrix-library](https://github.com/derkalle4/python3-idotmatrix-library) —
  BLE command reference and, via
  [issue #28](https://github.com/derkalle4/python3-idotmatrix-client/issues/28)
  (2024), the now-defunct `api.e-toys.cn` catalog endpoint and the `label="ALL"`
  hint.
- [8none1/idotmatrix](https://github.com/8none1/idotmatrix) and
  [markusressel/idotmatrix-api-client](https://github.com/markusressel/idotmatrix-api-client) —
  additional BLE protocol details.

The **current** cloud interface (signed/AES endpoint + obfuscated asset downloads)
was reverse-engineered for this project; we could not find it documented publicly.
