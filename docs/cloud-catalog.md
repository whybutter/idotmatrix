# iDotMatrix Cloud Catalog — Reverse-Engineered API

The official iDotMatrix app ("Cloud assets" screen) browses a cloud library of
pixel-art **images** and **animations**, grouped into categories (Daily,
Holiday, Emoji, Creative, Business). This document describes how to reach that
same catalog yourself — the endpoint, its request signing, its AES encryption,
the category naming, and (the part that trips everyone up) how to turn a
downloaded asset into an actual PNG/GIF.

Everything here was recovered from the app's APK and **verified live**. No login,
token, or per-user secret is involved — every secret is hard-coded in the app.
This is interoperability with a device you own.

> **Prior art.** An older, now-defunct endpoint (`api.e-toys.cn`, plain JSON, no
> signing) was documented by the community in
> [derkalle4/python3-idotmatrix-client#28](https://github.com/derkalle4/python3-idotmatrix-client/issues/28)
> (2024). That endpoint now returns `"Failed, please use a new interface"`. The
> **current** endpoint below (signed + AES-encrypted, with obfuscated asset
> downloads) did not appear to be publicly documented; it was cracked for this
> project. The one crucial hint we borrowed from that issue was `label="ALL"`.

---

## 1. The endpoint

There is exactly **one** catalog endpoint (plus an unrelated firmware-info one):

```
POST https://manage.heaton.com.cn/api/rm/getMaterialUnderCategory
     ?sign=<md5>&timestamp=<ms>&random=<8char>
Content-Type: text/plain; charset=utf-8
Body: <AES-CBC-Base64 of the sorted, URL-encoded query string>
```

- `sign`, `timestamp`, `random` are **URL query params**.
- The actual request parameters travel **AES-encrypted in the POST body**, not as
  query params.
- The response body is likewise **AES-encrypted Base64** of a JSON payload.

## 2. Request parameters (the map that gets signed + encrypted)

| Key | Value | Notes |
|-----|-------|-------|
| `appid` | `140` | constant |
| `sort` | `1` | constant |
| `page` | `1`-based page index | paging |
| `count` | e.g. `10` (or larger) | page size; **required** |
| `category_name` | see §5 | the tab |
| `type` | `图片` (images) / `动画` (animations) | Chinese literals, sent verbatim |
| `width` / `height` | panel size, e.g. `32` | **filters asset size** (16/32/64) |
| `label` | `ALL` | see §5 — this is the important one |
| `filter_tags` | `ALL` | |
| `file_lang` | `none,cn` | (`none,en` behaves the same for the catalog) |

## 3. Signing & encryption

All secrets are hard-coded in the app (`CloudEncipher` + `AESUtils`):

- **app_key** = `Jy47rzJAgKMfrcc92PamyyukQqB7wmFu`
- **AES**: `AES/CBC/PKCS7Padding`, **key = the same 32-byte ASCII `Jy47…` string**
  (AES-256), **IV = ASCII `0000000000000000`** (sixteen `0x30` bytes), standard
  Base64.

The signing string and the AES plaintext are both built the same way:

1. Take the params map. Sort entries by key ascending; join as `k=v` pairs with `&`.
2. **URL-encode** the whole joined string using Java's `URLEncoder` semantics
   (keep `[A-Za-z0-9.*-_]`, space → `+`, everything else → `%XX` of the UTF-8
   bytes), then **un-escape** `%26`→`&`, `%3D`→`=`, `%3F`→`?` so the structural
   separators survive.

- **sign** = `md5( urlencode( sorted("k=v&…" including random, timestamp,
  app_key) ) ).toLowerCase()`
- **body** = `base64( AES-encrypt( urlencode( sorted("k=v&…" WITHOUT app_key) ) ) )`

The response is `base64 → AES-decrypt → JSON`.

### Response schema

```jsonc
{ "status": 0, "msg": "请求成功",
  "data": {
    "totalCount": 70, "totalPage": 7, "pageNo": 1, "pageSize": 10,
    "records": [
      { "app_id": 140, "category_id": 8, "category_name": "节日_IDM",
        "file_path": "https://images.heaton.com.cn/download/<id>",
        "format": "png",        // or "gif"
        "width": 32, "height": 32, "label": "Product_…,…", "sort": 100 }
    ]
  }
}
```

> Note: the `CloudMaterialBean` is nested under `data`, and the whole thing is
> wrapped in `{status, msg, data}`. `status:1` with a Chinese `msg` means a
> parameter was rejected (e.g. `category_name不能为空` = "cannot be empty").

## 4. Working example (Python)

Requires `cryptography` (bundled with Home Assistant). See
[`custom_components/idotmatrix/catalog.py`](../custom_components/idotmatrix/catalog.py)
for the production version.

```python
import base64, hashlib, json, random, string, time, urllib.parse, requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

APP_KEY = b"Jy47rzJAgKMfrcc92PamyyukQqB7wmFu"; IV = b"0000000000000000"

def java_url_encode(s):
    out = []
    for b in s.encode():
        c = chr(b)
        if c.isascii() and (c.isalnum() or c in ".*-_"): out.append(c)
        elif c == " ": out.append("+")
        else: out.append("%%%02X" % b)
    return "".join(out).replace("%26","&").replace("%3D","=").replace("%3F","?")

def sorted_q(p): return "&".join(f"{k}={p[k]}" for k in sorted(p))

def aes(): return Cipher(algorithms.AES(APP_KEY), modes.CBC(IV))
def enc(s):
    pad = padding.PKCS7(128).padder(); d = pad.update(s.encode()) + pad.finalize()
    e = aes().encryptor(); return base64.b64encode(e.update(d)+e.finalize()).decode()
def dec(b):
    x = aes().decryptor(); raw = x.update(base64.b64decode(b)) + x.finalize()
    u = padding.PKCS7(128).unpadder(); return (u.update(raw)+u.finalize()).decode()

def list_category(category_name, mtype, page=1, count=10, size=32):
    p = {"appid":"140","sort":"1","page":str(page),"count":str(count),
         "category_name":category_name,"type":mtype,"width":str(size),
         "height":str(size),"label":"ALL","filter_tags":"ALL","file_lang":"none,cn"}
    rnd = "".join(random.choices(string.ascii_letters+string.digits, k=8))
    ts  = str(int(time.time()*1000))
    sign = hashlib.md5(java_url_encode(sorted_q({**p,"random":rnd,"timestamp":ts,
                       "app_key":APP_KEY.decode()})).encode()).hexdigest()
    body = enc(java_url_encode(sorted_q(p)))
    url = ("https://manage.heaton.com.cn/api/rm/getMaterialUnderCategory"
           f"?sign={sign}&timestamp={ts}&random={rnd}")
    r = requests.post(url, data=body,
                      headers={"Content-Type":"text/plain; charset=utf-8"})
    return json.loads(dec(r.text.strip()))["data"]

data = list_category("节日_IDM", "图片")   # Holiday images
print(data["totalCount"], data["records"][0]["file_path"])
```

## 5. Categories — and the `label="ALL"` gotcha

Both images and animations are organised into the **same five tabs**, encoded as
`<chinese-tab>_IDM`:

| Tab | `category_name` |
|-----|-----------------|
| Daily | `日常_IDM` |
| Holiday | `节日_IDM` |
| Emoji | `表情_IDM` |
| Creative | `创意_IDM` |
| Business | `商业_IDM` |

`type` selects still vs. animated: `图片` (image) or `动画` (animation).

**The trap:** with `label="Product_"` / `filter_tags="IDM_"`, `<tab>_IDM` returns
**zero** stills (and the images collapse to a single flat `iPixels` bucket of ~105
items). The categorised content — for *both* stills and animations — is only
returned with **`label="ALL"`**. This single value is the difference between "the
app clearly has categories but the API won't give them to me" and a fully working
catalog. (Verified counts at 32×32: images — Daily 105 / Holiday 70 / Emoji 72 /
Creative 74 / Business 31; animations — Daily 212 / Holiday 130 / Emoji 163 /
Creative 206 / Business 91.)

> `width`/`height` filter the asset size, so query at your panel's resolution
> (16/32/64). `商业_IDM` (Business) has content only under `label="ALL"`.

The device's PID/VID (from the BLE advertisement) select a per-model **flat**
`iPixels` bucket via `label="Product_<PID4><VID2>"`, but that is a red herring for
categorised browsing — you do **not** need the device codes; `label="ALL"` serves
the full categorised library to everyone.

## 6. Downloading an asset — it is NOT an image, it is obfuscated text

`record.file_path` (e.g. `https://images.heaton.com.cn/download/<id>`) is a plain,
auth-free URL — but a `GET` does **not** return PNG/GIF bytes. It returns an
**obfuscated text envelope** that the app (`DecryptHelper.getDecryptedFile`)
transforms client-side into the real image. A browser or naive `fetch` "fails"
only because it treats that text as an image.

The transform (exact order, bytecode-verified):

```python
import base64, urllib.parse, requests
def download_asset(file_path):
    text = requests.get(file_path, headers={
        "User-Agent": "okhttp/5.1.0", "Connection": "close"}).text
    s = text[32:len(text)-32]          # strip a 32-char nonce off each end
    s = s.replace("+", " ")            # '+' -> space
    s = urllib.parse.unquote(s)        # URL-decode (UTF-8)
    s = s[::-1]                        # reverse the whole string
    s = s.strip().replace("\r","").replace("\n","")
    return base64.b64decode(s)         # standard Base64 -> real PNG / GIF bytes
```

No auth, no Referer, no token, no signed URL. The "protection" is purely this
client-side obfuscation (fixed 32-char envelope + URL-encoding + string reversal +
Base64). Stills decode to PNG, animations to GIF.

---

## Quick reference

- **List images:**  `category_name=<tab>_IDM`, `type=图片`, `label=ALL`
- **List animations:** `category_name=<tab>_IDM`, `type=动画`, `label=ALL`
- **Download:** GET `file_path` as **text**, then the 6-step decode above.
- **Everything is keyed on `appid=140`, `label=ALL`, and your panel size.**
