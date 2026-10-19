# Competitors: exporting Rekordbox/Traktor playlists to plain folders, in order

Research date: 2026-10-14. About 20 searches and fetches. Several primary pages could not be fetched: the Traktor Bridge GitHub page returned 404, the NI forum thread returned 410, and the Lexicon manual subpage returned 404. Anything resting on secondary sources is marked as such.

## Q1: Which tools export a playlist to a folder with ordered or numbered filenames for Rekordbox 6/7 and Traktor Pro 3/4?

### Takeaway
No established DJ-library product I could verify advertises "copy the playlist's audio files to a folder with `001 - Artist - Title` names" as a feature. Rekordbox's built-in export is a device/USB export. Traktor's built-in export copies files but does not number them. Lexicon, rekordcloud and MIXO do library conversion or USB export, not ordered folder copies. The only folder copiers are small scripts (none of them numbers the files) and Apple Music-era Mac apps such as Export for iTunes, which can keep playlist order in filenames but only read Apple Music.

### Cited Findings
**Built-in features of DJ software**
- Rekordbox: the native route is Sync Manager / USB export, which is built for pushing playlists to a USB stick or device, not to a plain local folder — [We Are Crossfader](https://wearecrossfader.co.uk/blog/rekordbox-export-mode/). One user says Rekordbox's USB export files the tracks into folders by artist, which makes them hard to find in other software — [DJTechTools forum](https://forum.djtechtools.com/t/change-the-file-structure-on-my-rekordbox-stick/72172). The current guide says a playlist exported to USB is written to both OneLibrary and Device Library, i.e. a CDJ database, not plain ordered files — [Rekordbox USB export guide (Oct 2025)](https://cdn.rekordbox.com/files/20251021171528/USB_export_guide_en_251007.pdf). Rekordbox can export a playlist as XML (File → Export Playlist in XML Format), which third-party scripts use as their input — [rekordbox-xml-to-file](https://github.com/TurboKach/rekordbox-xml-to-file).
- Traktor Pro: right-clicking a playlist and choosing Export Playlist can copy the music files along with an .nml file. Cues and loops survive only if they are stored in the file, because Traktor-specific data lives in the collection — [DJTechTools forum](https://forum.djtechtools.com/t/exporting-traktor-set-for-another-computer/47631). Users report incomplete copies (only some tracks exported). The suggested fix is "Check Consistency" first — [NI community](https://community.native-instruments.com/discussion/comment/63007). After a "copy tracks to location" export, the .nml still pointed at the original paths — [NI community](https://community.native-instruments.com/discussion/comment/18931). No numbering option was mentioned in any source.
- Engine DJ: no documented export of a playlist to a folder. The community workaround is to drag the tracks from Engine into a folder on the computer, then move it to USB — [Engine DJ community](https://community.enginedj.com/t/how-can-i-export-the-tracks-of-a-playlist-created-in-the-engine-to-the-computer-or-to-a-usb/43617). An Engine thread notes that ordering problems appear on alphabetic sorting — [Engine DJ community](https://community.enginedj.com/t/alphabetical-playlist-issue/46159).
- Serato: no native crate-to-folder export was found. A plain drag-and-drop copy loses the crate order — [Serato forum](https://serato.com/forum/discussion/342220). The legacy third-party ScratchTools (Scratch Live era) had an "Export Crates to Folder" that copies a crate's tracks into a single folder, with no numbering mentioned — [beyondgaming.be archive](https://www.beyondgaming.be/archive/music.54/draaien-met-serato-of-iets-dergelijks.487947?page=5) (old, unverified for current Serato).

**Commercial library managers**
- **Lexicon DJ** (lexicondj.com): imports Rekordbox 5/6/7, Serato 3/4, Traktor Pro 3/4, VirtualDJ, Engine DJ, djay Pro and Apple Music, and syncs to them. It also has "Pioneer USB (OneLibrary)" sync and "DIRECT2CDJ". Its manual lists no section named "Copy files", "Export to folder" or "Device sync". It does have playlist tools named "Prefix" and "Rewrite Order", whose exact behavior I could not verify (the page returned 404) — [Lexicon manual](https://www.lexicondj.com/manual); [Lexicon pricing](https://www.lexicondj.com/pricing). A September 2025 interview says direct-to-USB export was the most requested feature and was in progress — [Magnetic Mag](https://magneticmag.com/2025/09/how-lexicon-saves-djs-time/). Lexicon is metadata-centric: it imports library and playlist metadata but not the files themselves — [We Are Crossfader](https://wearecrossfader.co.uk/blog/lexicon-music-management-for-djs/).
- **rekordcloud** (rekord.cloud): web-based. Exports playlists to M3U, CSV and HTML/PDF and offers playlist sharing. Audio files are never uploaded, and no file-copy feature was found — [rekordcloud features](https://Rekord.cloud/features); [rekordcloud wiki: library import](https://rekord.cloud/wiki/library-import).
- **MIXO** (mixo.dj): cloud-first library manager with sync through Google Drive, Dropbox or OneDrive. As of June 2026 it exports directly to Rekordbox USB and Engine DJ USB, and it imports and exports Rekordbox, Traktor, Serato, VirtualDJ, Engine, djay, Mixxx and Apple Music. Its mobile app can download playlists locally — [Digital DJ Tips, Jun 2026](https://www.digitaldjtips.com/mixo-now-plays-perfectly-with-pioneer-dj-alphatheta-gear/); [ProMobile review](https://promobile.org.uk/issues/reviews/239/REVIEWED-MIXO). No numbered folder export was found.
- **DJCU** (DJ Conversion Utility): converts libraries between DJ apps. An older version (4.75) was Mac-only at a one-off €19.50 — [Digital DJ Tips](https://www.digitaldjtips.com/convert-from-djay-pro-to-serato-traktor-rekordbox-virtual-dj-with-djcu-4-75/). A vendor page reportedly lists v7.5 as released 23 March 2025. That came from a search snippet ([sellfy](https://sellfy.com/p/emUY)) and I could not verify it directly. No folder-copy feature was found.
- **Mixlog**: has a "Playlist Actions" feature that copies playlists or folders into a target folder (search snippet only; the Notion page did not render) — [Mixlog Notion](https://mixlog.notion.site/NEW-Playlist-Actions-Folders-1182238e17c38068938fd92f28f7a1a3). Not verified: which platforms, whether files are copied, whether order is kept.

**Open-source / GitHub**
- **TurboKach/rekordbox-xml-to-file**: Python. Parses a Rekordbox XML export and copies tracks into one folder per playlist, recursively through sub-playlists. MIT license, 1 star, 8 commits, "compatible with macOS". No numbering, and order is not mentioned — [GitHub](https://github.com/TurboKach/rekordbox-xml-to-file).
- **Traktor Bridge** (bsm3d): free and source-available. Reads a Traktor NML and writes a CDJ-readable USB with playlists, folders, hot cues, loops, grids, keys, waveforms and artwork. It also exports Rekordbox XML, a Rekordbox database and M3U, and converts in reverse into NML. Version 3.5 (the first release the author calls stable) adds incremental copy, SHA-256 verification of every copied file and a FAT32 formatter. It was tested only on a CDJ-2000NXS2 — [NI community: Traktor Bridge 3.5](https://community.native-instruments.com/discussion/51976/traktor-bridge-3-5-take-your-traktor-playlists-to-a-cdj-free-source-available); [GitHub repo](https://github.com/bsm3d/Traktor-Bridge) (404 when fetched; the search snippet said it writes "M3U8, one file per playlist, folders kept").
- **juanmartin/universal-dj-usb**: reads a Rekordbox USB database and converts its playlists to NML, M3U or M3U8. Converts playlists, does not copy audio — [GitHub](https://github.com/juanmartin/universal-dj-usb).
- Converters and tracklist tools that do not copy audio: Segolene-Albouy/Traktor-NML-to-Rekordbox-XML, OwlSurojit/traktor-to-rekordbox, sdjamaa/rekordbox2traktor, digital-dj-tools/dj-data-converter, ewenme/tracklister and troysandal/tracklist (plain-text tracklists) — [search results](https://github.com/digital-dj-tools/dj-data-converter); [tracklister](https://github.com/ewenme/tracklister).
- rekordbox-playlist-converter (PyPI) writes a new standalone XML, not audio files. djops exports *to* Rekordbox — [PyPI](https://pypi.org/project/rekordbox-playlist-converter/0.3.0/); [PyPI djops](https://pypi.org/project/djops/).
- rbsort (Japanese blog, "headroom v2"): a tool for sorting playlist order inside Rekordbox, because the save order carries over to CDJs — [Zenn](https://zenn.dev/jphfa/articles/headroom-v2-rbsort-playlist-sort?locale=en).

**Apple Music / iTunes-era copiers (closest to "numbered ordered copy")**
- **Export for iTunes** (Mac App Store, Georgios Trigonakis): works with the Music app on Catalina and later. It can keep the original playlist order or order by year, artist or shuffle, and it has configurable filename formats. The free version is limited to 10 songs per playlist; the full version is a one-time IAP — [App Store](https://apps.apple.com/us/app/id880764359).
- **Playlist Export** (Mac App Store): exports M3U/WPL and copies files to a target location. Listed at $4.99 in 2018. It is iTunes-oriented, so its current status is unverified — [App Store](https://apps.apple.com/app/id434426826); [DJTechTools 2018](https://djtechtools.com/2018/07/26/move-your-itunes-playlists-to-any-usb-drive).
- **Export Files From Playlists** (dougscripts AppleScript): copies the files of selected playlists into a folder. The demo is limited per launch (5 to 20 tracks, depending on the source) and the full version costs $1.99. No numbering — [dougscripts](https://dougscripts.com/itunes/2014/02/new-export-files-from-playlists).
- **dpet23/Export-iTunes-Playlists** (GitHub AppleScript): can name files with a playlist-order number. Tested with iTunes 12 — [GitHub](https://github.com/dpet23/Export-iTunes-Playlists).
- Other ecosystems ask for the same thing: a KDE/Amarok feature request proposes a playlist-position prefix in filenames so files stay in order on any device — [KDE bug 314371](https://bugs.kde.org/show_bug.cgi?id=314371). A JRiver forum thread covers numbered copies — [JRiver Interact](https://yabb.jriver.com/interact/index.php/topic,54006.0.html).

### Inferences
- The specific job (Rekordbox 6/7 or Traktor NML → plain folder, `NNN - Artist - Title`, order preserved) appears not to be served by any maintained, polished product. The closest are a 1-star script (no numbering, Rekordbox XML only) and Apple Music-only Mac apps. This is a real gap.
- Lexicon's "Prefix"/"Rewrite Order" playlist tools may write position numbers into tags or titles. Combined with Lexicon's file move/rename tools, they could approximate the result. This needs verification before Lexicon is treated as a direct competitor.
- Traktor Bridge is the most capable free tool on the Traktor side, but it targets CDJ USB databases, not human-readable numbered folders.

### Gaps
- Exact behavior of Lexicon's Prefix and Rewrite Order tools, and whether Lexicon's "Moving & Renaming Files" can rename by playlist position: the manual subpage returned 404.
- Whether Traktor Bridge's USB/M3U export keeps playlist order in filenames: the GitHub page returned 404.
- Reddit r/DJs and r/Rekordbox threads: none surfaced in my searches.
- Whether Rekordbox 7's newer releases added any plain-folder export: no evidence either way.

## Q2: Do they read Rekordbox via the official XML, the encrypted master.db, or other means? Do they support Traktor NML?

### Takeaway
Most scripts use the Rekordbox XML export. Lexicon, MIXO and DJCU read the Rekordbox library directly. Traktor NML is supported by Lexicon, MIXO, DJCU, Traktor Bridge and the NML↔XML converters. No ordered folder copier found reads master.db directly together with Traktor NML.

### Cited Findings
- rekordbox-xml-to-file needs a manual XML export (File → Export Playlist in XML Format) — [GitHub](https://github.com/TurboKach/rekordbox-xml-to-file).
- Lexicon lists "Rekordbox 6/7" as a separate import source from "Rekordbox 5" (XML era), plus Traktor import and sync — [Lexicon manual](https://www.lexicondj.com/manual). The manual does not say whether it reads master.db.
- Traktor Bridge reads Traktor NML, and in reverse reads Rekordbox XML, VirtualDJ, Serato, Mixxx and M3U — [NI community](https://community.native-instruments.com/discussion/51976/traktor-bridge-3-5-take-your-traktor-playlists-to-a-cdj-free-source-available).
- pyrekordbox, the open-source library behind many Python tools, handles Rekordbox XML as well as the v6 database — [pyrekordbox docs](https://pyrekordbox.readthedocs.io/en/latest/formats/xml.html).
- rekordcloud works from an uploaded library export (metadata only) — [rekordcloud wiki](https://rekord.cloud/wiki/library-import).

### Inferences
- A tool that reads master.db directly (no manual XML export step) and also Traktor NML, in one app, would be a differentiator against the script-level competitors. Lexicon and MIXO probably do both, but for conversion and sync, not for ordered copies.

### Gaps
- Not confirmed from primary sources whether Lexicon, MIXO or DJCU read master.db directly or need an XML export.

## Q3: Price, licensing model, platforms

### Takeaway
The commercial library managers are freemium or subscription products (Lexicon, MIXO), plus DJCU as a one-off purchase. The folder-copy scripts are free. The Mac copiers are cheap one-time purchases.

### Cited Findings
- Lexicon: free tier (library conversion). Paid Essential and Ultimate tiers are billed monthly with a lifetime option; the pricing page shows no dollar amounts. Windows 10/11 and macOS Catalina or later (Apple Silicon), plus iOS and Android apps — [Lexicon pricing](https://www.lexicondj.com/pricing).
- MIXO: free tier plus a paid tier of about $7/month. Desktop with cloud sync — [Digital DJ Tips](https://www.digitaldjtips.com/mixo-now-plays-perfectly-with-pioneer-dj-alphatheta-gear/); [AlternativeTo](https://alternativeto.net/software/mixo--the-dj-library/about) (undated).
- DJCU: one-off €19.50, Mac-only (v4.75 era; current price unverified) — [Digital DJ Tips](https://www.digitaldjtips.com/convert-from-djay-pro-to-serato-traktor-rekordbox-virtual-dj-with-djcu-4-75/).
- Traktor Bridge: free, source-available — [NI community](https://community.native-instruments.com/discussion/51976/traktor-bridge-3-5-take-your-traktor-playlists-to-a-cdj-free-source-available).
- rekordbox-xml-to-file: free, MIT, macOS — [GitHub](https://github.com/TurboKach/rekordbox-xml-to-file).
- Export for iTunes: free (10 songs per playlist) plus a one-time unlock, macOS — [App Store](https://apps.apple.com/us/app/id880764359). dougscripts: $1.99 — [dougscripts](https://dougscripts.com/itunes/2014/02/new-export-files-from-playlists).
- rekordcloud: web-based. Pricing was not retrieved — [rekordcloud features](https://Rekord.cloud/features).

### Gaps
- Exact current USD prices for Lexicon tiers, rekordcloud plans, DJCU 7 and MIXO.

## Q4: Do any include an audio preview player or missing-file detection/repair before export?

### Takeaway
Lexicon has both: a music player, and tools named Find Broken Tracks, Find Lost Tracks / Relocate and Find Unused Files. Traktor relies on "Check Consistency". Traktor Bridge verifies copies after the fact (SHA-256). None of the scripts check for missing files or play audio.

### Cited Findings
- Lexicon manual sections: "Music Player" (cue points, beatgrid, beat jump, queue), "Find Broken Tracks", "Find Lost Tracks / Relocate" and "Find Unused Files" — [Lexicon manual](https://www.lexicondj.com/manual). The pricing page puts "missing tag and album art detection" in Ultimate — [Lexicon pricing](https://www.lexicondj.com/pricing).
- Traktor: before exporting playlists with files, run Check Consistency and remove missing entries — [NI community](https://community.native-instruments.com/discussion/comment/63007).
- Traktor Bridge 3.5: SHA-256 verification of every copied file, plus a copy that skips files already on the stick — [NI community](https://community.native-instruments.com/discussion/51976/traktor-bridge-3-5-take-your-traktor-playlists-to-a-cdj-free-source-available).

### Inferences
- In the "export to folder" niche, a built-in preview player plus a broken-link pre-check and repair would set a product apart. Only the all-in-one Lexicon matches it, and Lexicon does not do numbered folder export.

### Gaps
- Whether MIXO and rekordcloud have preview or missing-file detection: not found.

## Q5: Which are discontinued or abandoned?

### Takeaway
Rekord Buddy is effectively dead: it went free in October 2020 with an announced open-source plan, and no later release was confirmed. The Scratch Live-era ScratchTools and the iTunes-era scripts are legacy. DJCU, Lexicon, MIXO and Traktor Bridge appear active in 2025–2026.

### Cited Findings
- Rekord Buddy became freeware in October 2020, and the developer announced an open-source release by the end of 2020 — [Bonedo](https://www.bonedo.de/artikel/einzelansicht/rekord-buddy-ab-sofort-freeware-und-bald-open-source-verfuegbar.html). Earlier, it was "no longer available pending Rekord Buddy 2.0" — [Digital DJ Tips](https://digitaldjtips.com/your-questions-how-can-i-switch-from-traktor-to-rekordbox) (undated, likely about 2018). Background: [DJCity interview](https://news.djcity.com/interview-with-rekord-buddy-creator-damien-sirkis).
- DJCU: v7.5 reportedly released March 2025 (vendor snippet) — [sellfy](https://sellfy.com/p/emUY).
- MIXO: active, with a v2 and USB export added in June 2026 — [Digital DJ Tips](https://www.digitaldjtips.com/mixo-now-plays-perfectly-with-pioneer-dj-alphatheta-gear/).
- Lexicon: active, with 2026 promo codes on the pricing page — [Lexicon pricing](https://www.lexicondj.com/pricing).
- Traktor Bridge: active (v3.5 thread on the NI forum; exact date not retrieved) — [NI community](https://community.native-instruments.com/discussion/51976/traktor-bridge-3-5-take-your-traktor-playlists-to-a-cdj-free-source-available).
- Export-iTunes-Playlists was tested with iTunes 12 only (legacy) — [GitHub](https://github.com/dpet23/Export-iTunes-Playlists).

### Gaps
- Whether Rekord Buddy's source was ever published, and whether it still works.
- Last-commit dates for TurboKach/rekordbox-xml-to-file and Traktor Bridge: not shown on the fetched pages.
