# CareerPilot Sans

Subset of IBM Plex Sans SC Regular (400) and Medium (500), copyright 2017 IBM Corp., released under the SIL Open Font License 1.1; see `OFL.txt`.

Source: https://github.com/IBM/plex/tree/71f558992315a12ca1f06a2215d57962a1992162/packages/plex-sans-sc

Only the character coverage and font naming records are changed; the glyph outlines are unchanged. The derivative families are renamed **CareerPilot Sans** and **CareerPilot Sans UI** to respect the reserved font name. Coverage includes GB2312, Latin, common punctuation and full-width characters; other characters use system fallback fonts.

The UI pair contains the interface characters and is preloaded. The GB2312 pair is a separate fallback family, with preloading disabled, and is downloaded only when additional characters are rendered. All four WOFF2 files are served through `next/font/local`; no external font request is made at runtime.

## CareerPilot Serif

Subset of Noto Serif CJK SC (Regular 400 / Medium 500), released under the SIL Open Font License 1.1; see `OFL.txt`. Source: https://github.com/notofonts/noto-cjk

Coverage is limited to the Chinese characters and punctuation actually used by the app UI; other glyphs fall back to system serif fonts. Used for page and section headings via `--font-career-serif`; preloading is disabled.
