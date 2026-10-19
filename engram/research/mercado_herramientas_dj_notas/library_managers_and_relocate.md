# DJ library managers, converters and relocate/repair tools (state as of Oct 2026)

Research date: 2026-10-14. Many press sources are from 2020-2023 and are marked [OLD]. Search budget ran out before every vendor page could be verified; gaps are listed per section.

## 1. Main players and their feature sets

### Takeaway
Lexicon DJ is the commercial leader (freemium since v1.9, Sept 2025: free conversion between all major apps, paid tiers for editing/cloud/cues/duplicates). Behind it: DJCU/DJCU2 (cheap one-time Mac converter), rekord.cloud (subscription "Swiss army knife", older), ATGR's Rekordbox Collection Tool (one-time, macOS, relocate-focused), MIXO (cloud library, older info), Rekord Buddy (turned free/open source in 2020, effectively dormant), and a set of free/open-source tools (Traktor Bridge, pyrekordbox, rbox, rekordbox-library-fixer, rekordbox-repair). AlphaTheta's OneLibrary (Oct 2025, with Algoriddim and NI) is the first official cross-vendor format and partially competes with converters.

### Cited Findings
**Lexicon DJ**
- Plans: Free (full library conversion, all DJ apps, community support, no card, 0 cloud tracks); Essential (adds track/playlist editing, iOS & Android app, 1,000 cloud tracks); Ultimate (adds Generate Cue Points, Find Duplicates, Find Missing Tags & Album Art, Watch Folder, Cloud Database Backup, priority support, 10,000 cloud tracks); Unlimited Cloud Storage add-on billed monthly. The pricing page shows no dollar amounts in the fetched version. It mentions a lifetime option, a 30-day money-back guarantee, a price increase "on September 8", and promo codes LIBRARY2026 / LEXICON2026 — [Lexicon pricing](https://www.lexicondj.com/pricing)
- Supported apps: Rekordbox 5/6/7, Serato 3 & 4, Traktor Pro 3 & 4, VirtualDJ, Engine DJ, djay Pro, iTunes/Apple Music. Platforms: Windows 10/11 64-bit, macOS Catalina+ (Apple Silicon), plus a mobile app on paid tiers — [Lexicon pricing](https://www.lexicondj.com/pricing)
- v1.9 (Sept 2025) added the Free plan and a one-off Lifetime License; djay Pro support and faster cue generation also arrived in 2025 — [MusicTech](https://musictech.com/news/gear/dj-library-management-lexicon/), [Magnetic Mag](https://magneticmag.com/2025/09/new-lexicon-update-adds-faster-cue-generation-and-djay-pro-support/)
- Older monthly prices: Basic $17/mo and Pro $39/mo [OLD, around v1.7] — [Gearnews](https://gearnews.com/?p=192239). A directory lists $15–$35/mo (undated) — [AlternativeTo](https://alternativeto.net/software/lexicon/about)

**DJCU / DJCU2 (DJ Conversion Utility, ATGR Production Team)**
- Mac-only converter between Traktor, Rekordbox, Serato, VirtualDJ, djay, Engine DJ and iTunes/Music. Some conversion pairs are two-way, others one-way. DJCU 4.0 cost €19.50 — [Digital DJ Tips review](https://www.digitaldjtips.com/reviews/dj-conversion-utility-4-0/); US$14.50 in 2020 [OLD] — [Digital DJ Tips](https://www.digitaldjtips.com/convert-your-rekordbox-library-to-traktor-with-dj-conversion-utility/)
- DJCU2: store lists €44.50 and supports Rekordbox 6 & 7 and Traktor Pro 3 & 4. It can carry djay Pro's fluid beatgrids to other apps. Its beta was open to existing licence holders, and the release timing given in coverage is unreliable — [Sellfy store](https://atgr-production-team.sellfy.store/p/dj-conversion-utility-two/), [Digital DJ Tips](https://www.digitaldjtips.com/?p=2798826)
- The djconversionutility.com domain did not resolve when fetched (Oct 2026). The vendor now appears to sell only through Sellfy — fetch attempt, unverified.

**Rekordbox Collection Tool (RCT v2.0, also by ATGR)**
- One-time price from €29.50, macOS 11 through 27 (Apple Silicon and Intel), needs internet at startup, and gives no refunds for use on other operating systems. Features: an Auto Relocate that uses "a different method" from Rekordbox 6 and claims to succeed where Rekordbox fails; relocation of Dropbox/CloudSync tracks; resetting tracks so they can be relocated again; and metadata merging between identical tracks as a last resort. The page says "All ATGR apps work with both Rekordbox 6 and Rekordbox 7", but the RCT text calls it a Rekordbox 6 companion — [Sellfy RCT](https://atgr-production-team.sellfy.store/p/rct/)

**rekord.cloud (Rekordcloud)**
- Converts between Traktor, Serato, VirtualDJ and Rekordbox (including v6). It finds duplicate, unused, broken and "lost" files, sets auto cue points and does vocal removal. Windows/Mac. $15/mo, or $7.50/mo billed annually. It was the only converter that handled Rekordbox 6 export in April 2020, and the developer explained how he got around RB6's locked metadata [OLD, 2020] — [Digital DJ Tips](https://www.digitaldjtips.com/rekordcloud-mixo-apps-offer-new-dj-library-conversion-tools/)
- Its conversion wiki lists Rekordbox, Traktor, VirtualDJ, Serato and Engine Prime, carrying track info, paths, cues, beatgrids and playlists — [Rekord.cloud wiki](https://Rekord.cloud/wiki/convert-library)
- In Oct 2026, rekord.cloud/pricing returned 404. The homepage now promotes other products (OpenKeyScan, which is free and open source, plus TrackHack and SonoVault) — [rekord.cloud](https://rekord.cloud/). This suggests the original library product is de-emphasised or pivoted (inference).

**MIXO**
- A cloud library that syncs via Dropbox on Mac, Windows, Linux, iOS and Android. "MIXO Bridge" converts between Rekordbox (up to v5 at the time), Traktor, VirtualDJ and Serato. $7/mo; beta v0.6 [OLD, 2020] — [Digital DJ Tips](https://www.digitaldjtips.com/rekordcloud-mixo-apps-offer-new-dj-library-conversion-tools/)

**Rekord Buddy (Next Audio Labs, Didier Malenfant)**
- Converted libraries between Serato, Traktor and Rekordbox. A paid 2.0 beta was planned at $59.99. In Oct 2020 it was announced as free and to be open-sourced, with "minimal and sporadic" support. Coverage at the time said it could not convert to or from Rekordbox 6 [OLD] — [Digital DJ Tips](https://www.digitaldjtips.com/rekord-buddy-library-conversion-utility-is-now-free-open-source/), [DJWORX](https://djworx.com/teaser-free-world-exclusive-rekord-buddy-goes-open-source/)

**Traktor Bridge (free, community)**
- Exports Traktor NML collections and playlists to Rekordbox XML, the Rekordbox database, M3U, or directly to a USB stick. Compatible with Traktor Pro 3.5.x and 4.x, with a GUI and a CLI. The developer gives no guarantees and advises testing on a copy — [NI Community thread (search snippet)](https://community.native-instruments.com/discussion/47624/traktor-bridge-free-export-nml-playlist-to-recordbox-database-xml-m3u-or-directly-on-usb-stick). The thread returned HTTP 410 Gone when fetched in Oct 2026 (removed or moved).

**Open-source libraries and tools**
- pyrekordbox (dylanljones): MIT, ~495 stars and 48 forks. Tested on RB 5.8.6, 6.7.7 and 7.0.9. Reads and writes master.db via SQLCipher (sqlcipher3-wheels), and only some tables support add/delete. It warns users to back up and disclaims liability, and says it is not affiliated with Pioneer — [GitHub](https://github.com/dylanljones/pyrekordbox)
- rbox (Rust with Python/JS bindings, also rbox-js on npm): reads master.db and needs the key present locally. It disclaims affiliation and liability for data loss — [PyPI rbox](https://pypi.org/project/rbox/), [rbox-js README](https://cdn.jsdelivr.net/npm/rbox-js@0.1.7/README.md)
- rekordbox-library-fixer (koraysels): Electron/React/TS, ~70 stars, 260 commits, v0.6.7 "alpha". Runs on Win, mac (arm/Intel) and Linux. Uses a custom non-commercial licence. Details in §2 — [GitHub](https://github.com/koraysels/rekordbox-library-fixer)
- rekordbox-repair (edkennard): XML-based repair (details in §2) — [GitHub](https://github.com/edkennard/rekordbox-repair)
- rekordbox-xml-to-file (TurboKach): exports playlists from the XML to folders (same niche as listBuddy). It is not a relocator — [GitHub](https://github.com/TurboKach/rekordbox-xml-to-file)

**OneLibrary (official, AlphaTheta + Algoriddim + Native Instruments, announced around Oct 21, 2025)**
- A shared export format for playlists, BPM, key, cues, beatgrids and waveforms. Hardware: CDJ-3000X, CDJ-3000 (fw 3.30+), XDJ-AZ, OPUS-QUAD, OMNIS-DUO. djay Pro exports it now, and Traktor support was announced as "upcoming". Serato and Engine DJ are not involved. Critics call it an export format, not a universal library — [We Are Crossfader](https://wearecrossfader.co.uk/blog/onelibrary/), [Digital DJ Tips](https://www.digitaldjtips.com/?p=2794073), [DJWORX](https://djworx.com/onelibrary-one-love-for-your-music-library-from-alphatheta/), [Substack critique](https://reallychrism.substack.com/p/why-im-not-cheering-onelibrary)
- Lexicon can sync to Pioneer USB in OneLibrary format — [Lexicon manual](https://www.lexicondj.com/manual/sync-to-pioneer-usb)
- March 2026: AlphaTheta suspended CDJ-3000 fw 3.30 over a compatibility issue between OneLibrary (formerly Device Library Plus) and Device Library exports. The fix was to update to rekordbox 7.2.11+ and re-export — [DJ Mag](https://djmag.com/tech/alphatheta-shares-guide-fix-playlist-issues-firmware-update)

### Inferences
- The market has consolidated around Lexicon. Older competitors (rekord.cloud, MIXO, Rekord Buddy) appear stale or pivoted, and ATGR survives with low one-time Mac-only prices.
- Lexicon's free conversion tier (since 2025) commoditises plain conversion. Paid value moves to cleanup, cues, duplicates, cloud and mobile.
- OneLibrary reduces the need for USB-export converters among Pioneer/djay/Traktor users, but it doesn't cover desktop library migration or repairing missing files.

### Gaps
- Current Lexicon prices in USD (monthly, yearly and lifetime) were not visible on the fetched pricing page.
- Current MIXO status and pricing: no 2024–2026 source found.
- Whether Rekord Buddy's code was actually published and is maintained: not verified.
- Traktor Bridge's author, repository and current version: the thread is gone (410).
- Serato- and Engine-specific converters (for example Engine DJ's own Rekordbox/Serato import) were not researched in depth.

## 2. How each tool fixes missing or broken files, compared with Rekordbox Relocate/Auto Relocate and Traktor Consistency Check

### Takeaway
The built-in tools work by folder or filename. Rekordbox's Relocate works folder by folder (RB5) and Auto Relocate was added in RB6. Traktor's Consistency Check plus a mass relocate to a root folder can find moved and renamed files. Third-party tools add multi-folder search, similarity matching and batch database writes. The main split is XML round-trip (safe, but can't delete entries or carry some data) versus writing master.db directly (complete, but unofficial).

### Cited Findings
- rekordbox-repair: scans tracks marked missing and separates "moved" from "truly gone". Flags paths over 255 characters on macOS. Writes a new XML with repaired tracks, keeping cues, loops and playlist membership; you can export only the fixed tracks or rebuild the whole collection. The author notes RB5's built-in Relocate works folder by folder, so it succeeds only if a top-level folder moved with its contents intact — [GitHub](https://github.com/edkennard/rekordbox-repair)
- rekordbox-library-fixer: user-defined search directories, search depth and a similarity threshold, so it can match renamed files. Falls back to track title when the stored path is damaged. Reads XML or a copy of master.db (including the WAL), so Rekordbox can stay open while reading. Writes relocation, dedupe and broken-entry removal straight to master.db, because XML import can add and update but not delete. Writes require RB closed and a verified backup, re-point playlists first, and bump RB's update counter. Removing missing entries is destructive and opt-in. Ships no key: the user obtains it via pyrekordbox. The mac app is unsigned — [GitHub](https://github.com/koraysels/rekordbox-library-fixer)
- RCT (ATGR): claims its Auto Relocate uses a different method from RB6's and succeeds where RB fails. Handles Dropbox/CloudSync tracks and can reset tracks for re-relocation — [Sellfy RCT](https://atgr-production-team.sellfy.store/p/rct/)
- Rekordcloud: finds "broken" and "lost" files [OLD] — [Digital DJ Tips](https://www.digitaldjtips.com/rekordcloud-mixo-apps-offer-new-dj-library-conversion-tools/). Its relocate workflow: relocate, re-import playlists and tracks into RB, then check File → Display All Missing Files — [Rekord.cloud wiki (search snippet; page now 404)](https://Rekord.cloud/wiki/relocate-files)
- Rekordbox 6.0 introduced "Auto Relocate" to find missing files automatically — [DJ Mag](https://djmag.com/news/pioneer-dj-announce-rekordbox-6-cloud-storage-and-sync), [DJ TechTools](https://djtechtools.com/2020/04/14/rekordbox-6-now-with-cloud-library-syncing)
- Traktor: a consistency check at startup reports missing files. A user describes a mass relocate (point Traktor at a root folder) that finds moved or renamed files and keeps cues and grids, attributing this to Traktor fingerprinting tracks. The same source says RB6 fixed the renamed-file problem, with an XML export caveat — [dj-kb](https://dj-kb.readthedocs.io/traktor/). Consistency checks on big libraries can be very slow — [NI Community](https://community.native-instruments.com/discussion/comment/82006)
- Engine DJ's Auto Relocate skips files with multiple candidates (duplicates), and on Mac it is case-sensitive about filenames. Unresolved files are relinked manually with "Relocate Missing File" — [Engine DJ KB](https://enginedj.com/kb/solutions/69000828907/why-does-auto-relocate-fail-to-find-some-of-my-files)
- XML pitfall: if two tracks end up with the identical path after relocation, the Rekordbox XML import fails — [Engine DJ community](https://community.enginedj.com/t/rekordbox-library-xml-doesnt-even-try-to-update/62380/17)
- Lexicon's XML sync limits: very slow; no MyTags, smartlists or memory cue colours; adds and updates only (removed tracks stay in RB); no active loops. A RB 5/6/7 bug requires right-clicking tracks rather than playlists, or existing tracks won't update. RB 5.6.0 is recommended as the last version without the bug — [Lexicon manual](https://www.lexicondj.com/manual/sync-rekordbox-xml)

### Inferences
- The "XML for reimport" approach (rekordbox-repair, Lexicon XML mode, library-fixer's `_cleaned` XML) is the safe official path. Its structural weaknesses are no deletes, lost MyTags and smartlists, and the track-vs-playlist reimport bug. Tools wanting a clean result write master.db directly.
- Fuzzy or similarity matching across several search roots is the key differentiator over built-in relocate. Duplicates, case-sensitivity and identical-path collisions are common failure modes.

### Gaps
- No official AlphaTheta documentation was found on Auto Relocate's matching criteria (filename only? size? search scope?). The official FAQ page fetched didn't describe it.
- Lexicon's own missing-file/relocate feature details were not fetched (the manual likely has a "find lost files" page).
- Traktor's fingerprint-based relocate is described by a user, not by NI documentation.

## 3. Rekordbox 6/7 master.db access (encrypted DB vs XML) and pushback from AlphaTheta / Native Instruments

### Takeaway
Lexicon (direct sync), rekordbox-library-fixer, Traktor Bridge, pyrekordbox and rbox read or write the SQLCipher-encrypted master.db. DJCU2 and RCT claim RB 6/7 support without saying how. rekordbox-repair, Rekordbox 5 workflows and Lexicon's fallback use the XML. AlphaTheta has not sued anyone or sent a public cease-and-desist that could be found. Its pushback is technical and contractual: it obfuscated key extraction from RB 6.6.5, and its official FAQ warns that unauthorized library tools have corrupted libraries and that it isn't responsible. No NI action against third-party tools was found; NI instead joined OneLibrary.

### Cited Findings
- Lexicon "Direct Sync" writes directly to the Rekordbox database. It is unofficial and recommended for RB 6/7, with XML as the official fallback. It requires RB fully closed (including the `rekordbox` and `rekordboxAgent` processes) and warns that force-quitting busy processes may damage the DB. Duplicates are possible with Cloud Sync enabled. MyTags are limited to 4 categories and 128 tags. Each sync replaces RB cues — [Lexicon manual](https://www.lexicondj.com/manual/sync-rekordbox-xml), [Lexicon manual: import RB6/7](https://www.lexicondj.com/manual/import-rekordbox-6)
- User-reported failures: "database disk image is malformed" on sync, fixed by opening and closing RB and restoring Lexicon's backup — [Lexicon forum](https://discuss.lexicondj.com/t/failed-to-sync-to-rekordbox-sqliteerror-database-disk-image-is-malformed/2474); a RB 7.2.2 sync issue worked around with a dummy playlist — [Lexicon forum](https://discuss.lexicondj.com/t/lexicon-wont-sync-to-rekordbox/3266)
- Official AlphaTheta FAQ: "There have been reports of events such as the corruption of rekordbox libraries" linked to library management tools AlphaTheta hasn't authorized. "We are not responsible for damage to libraries caused by the use of unauthorized tools." "The use of such tools is not advised." — [rekordbox FAQ library 6](https://rekordbox.com/en/support/faq/library-6/)
- From RB 6.6.5, Pioneer obfuscated app.asar, which broke automatic key extraction. pyrekordbox added a `download-key` CLI as a workaround — [pyrekordbox docs](https://pyrekordbox.readthedocs.io/en/latest/quickstart.html)
- Alternative key route: the NowPlaying rekordbox integration reads the password from RB's options.json and decrypts it with Blowfish — [NowPlaying docs](https://help.nowplayingapp.com/reference/integrations/rekordbox/)
- In 2020, RB6 "locked metadata" broke converters. Rekordcloud found a workaround first, MIXO and Rekord Buddy lacked RB6 support at the time [OLD] — [Digital DJ Tips](https://www.digitaldjtips.com/rekordcloud-mixo-apps-offer-new-dj-library-conversion-tools/), [DJ Digital Tips: Rekord Buddy](https://www.digitaldjtips.com/rekord-buddy-library-conversion-utility-is-now-free-open-source/)
- Traktor Bridge writes to the "Rekordbox database" as well as XML — [NI Community (snippet)](https://community.native-instruments.com/discussion/47624/traktor-bridge-free-export-nml-playlist-to-recordbox-database-xml-m3u-or-directly-on-usb-stick)

### Inferences
- The main technical risk for any master.db writer is that the key or schema changes with RB updates, the key must be fetched from a third party (pyrekordbox's download-key), concurrent writes or Cloud Sync cause corruption, and the user is left with no vendor support. XML-only tools avoid this but inherit XML's limits.
- The legal risk looks low so far (no C&D found), but AlphaTheta's FAQ creates reputational and support risk ("unauthorized tool"). Redistributing the decryption key could be a sensitive point (circumvention). The open-source tools don't ship the key. That this is a legal concern is an inference, not documented.
- For a product like listBuddy, the safest positioning is read-only master.db plus writing a Rekordbox XML for reimport, which mirrors Lexicon's "read-only import, write only on Sync with backup" model.

### Gaps
- No public cease-and-desist, DMCA takedown or lawsuit from AlphaTheta or NI against Lexicon, pyrekordbox, rbox or others was found. This absence is not proof that none exist.
- Whether RB 7.x releases after 7.0.9 changed the key or schema in ways that broke tools: not confirmed.
- How DJCU2 and RCT access RB 6/7 (DB or XML) is not stated on their pages.

## 4. Prices, free tiers, trials and user base

### Takeaway
| Tool | Model | Price (best available) | Free tier/trial | Platforms | Status |
|---|---|---|---|---|---|
| Lexicon DJ | Freemium subscription + lifetime | Not shown on page (Oct 2026). Older: $17/$39/mo [OLD]; directory: $15–35/mo | Free plan: full conversion; 30-day money-back | Win/mac + iOS/Android | Active (v1.9+ 2025, promos 2026) |
| DJCU2 | One-time | €44.50 (DJCU 4: €19.50) | Not found | macOS | Active (Sellfy) |
| RCT v2 | One-time | from €29.50 | Not found; no refunds on wrong OS | macOS 11–27 | Active |
| rekord.cloud | Subscription | $15/mo or $7.50/mo yearly [OLD 2020] | Online demo [OLD] | Win/mac | Pricing page 404; pivoted |
| MIXO | Subscription | $7/mo [OLD 2020] | Beta | Mac/Win/Linux/iOS/Android | Unknown |
| Rekord Buddy | Free (was going to be $59.99) | Free since 2020 | — | macOS | Dormant |
| Traktor Bridge | Free | — | — | (GUI+CLI) | Thread gone (410) |
| pyrekordbox / rbox | Free (MIT / OSS) | — | — | Cross-platform | Active |
| rekordbox-library-fixer | Free, non-commercial licence | — | — | Win/mac/Linux | Alpha v0.6.7 |
| rekordbox-repair | Free OSS | — | — | — | Not verified |

### Cited Findings
- See the citations in §1 for every price: [Lexicon pricing](https://www.lexicondj.com/pricing), [Gearnews](https://gearnews.com/?p=192239), [AlternativeTo](https://alternativeto.net/software/lexicon/about), [DJCU2 Sellfy](https://atgr-production-team.sellfy.store/p/dj-conversion-utility-two/), [DJCU4 review](https://www.digitaldjtips.com/reviews/dj-conversion-utility-4-0/), [RCT Sellfy](https://atgr-production-team.sellfy.store/p/rct/), [Rekordcloud/MIXO](https://www.digitaldjtips.com/rekordcloud-mixo-apps-offer-new-dj-library-conversion-tools/), [Rekord Buddy](https://www.digitaldjtips.com/rekord-buddy-library-conversion-utility-is-now-free-open-source/)
- GitHub traction as a usage proxy: pyrekordbox ~495 stars — [GitHub](https://github.com/dylanljones/pyrekordbox); rekordbox-library-fixer ~70 stars — [GitHub](https://github.com/koraysels/rekordbox-library-fixer)
- For context, Rekordbox's own paid plans at the 2020 launch were Core £9.99 and Creative £14.99 per month (€6.99/€9.99) [OLD] — [DJ Mag](https://djmag.com/news/pioneer-dj-announce-rekordbox-6-cloud-storage-and-sync)

### Inferences
- The price ladder is: free OSS/CLI → about €20–45 one-time Mac utilities → about $10–40/mo subscriptions (Lexicon, older Rekordcloud). A one-time-fee, cross-platform, Rekordbox+Traktor export/repair tool sits in an underserved gap between ATGR (Mac-only) and Lexicon (subscription).

### Gaps
- No public user counts for any vendor were found (Lexicon doesn't publish one on its pricing page).
- Lexicon's exact current USD prices, lifetime price and trial terms are unknown. Its pricing page renders the prices client-side or in a way the fetch didn't capture.
