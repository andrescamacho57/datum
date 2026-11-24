# Static files of the web app

| File | What it is | Where it came from |
|---|---|---|
| `pico.min.css` | Pico CSS, version **2.1.1**: a small style sheet that makes plain HTML look right on a phone, with no JavaScript | Downloaded on Nov 24, 2026 from `https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css`, which served version 2.1.1. The file is unchanged. Its SHA-256 checksum is `fbc9a63fc9fc9f72d12fd7fc9806e11fa9f77ae4f9cad146b27003a1119ba3db` |
| `PICO_LICENSE.md` | Pico's license, the MIT License, which allows copying and use as long as this notice travels with the file | Downloaded the same day from the same package |
| `datum.css` | Four rules of Datum's own | Written in leg C4 |

Why a copy is kept here (decision d20, and leg C4 of Phase C): a contractor's phone then loads the style sheet from Datum itself and never calls a third party. The app's Content-Security-Policy header forbids loading a style sheet from anywhere else.

`pico.min.css` holds no address of another site: its only `url(...)` values are small pictures written into the file itself (`data:` addresses).

To upgrade Pico, download the new file, replace this one, and update the version and the checksum in this table, in a commit of its own.
