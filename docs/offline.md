# Offline downloads

Sign in online before downloading a song or setlist. Opening an online song automatically saves a verified offline copy when none exists. The player reports success or failure. Existing copies are retained, including optional originals; refresh them through **Offline options** in the library. Use **Download for offline** in that menu for an explicit retry, or **Download setlist** in the setlist editor. Originals are excluded unless you select the original PDF option. A setlist retains its order and repeated occurrences. Downloading does not change canonical song text.

The browser stores private snapshots in IndexedDB and verified assets in Cache Storage. Downloads are scoped to the library and its single authenticated owner. The app verifies the stored source hashes, required assets and application shell before reporting a selection as downloaded. If browser storage is cleared, evicted, corrupted or incompatible, the selection can become incomplete; reconnect and download it again. Browser storage persistence is requested where supported but is not guaranteed. The browser's storage estimate is approximate.

Use **Remove download** to remove a song selection. Shared original files are kept while another selection needs them. On browsers without the Web Locks API, unreferenced shared files can remain until you choose to remove private downloads when signing out; this avoids racing another tab's download. Sign-out revokes the server session first, then offers local removal, selected by default. If you keep downloads, a private copy remains on this device. If removal fails, the app reports that failure; use browser site-data controls if necessary.

Downloaded songs and sets can be opened after a cold offline reload. Browser printing uses browser pagination and can differ from the server PDF. Editing, imports and server PDF generation require a connection. An optional downloaded original can be opened from the offline player. Offline first login is not supported. Do not rely on a browser download as the only backup of a library; use the separately documented backup procedure when available.

On reconnection the app checks downloaded revisions without deleting local
copies. An outdated or deleted copy remains available until you remove or
refresh it. Refresh explicitly to replace a downloaded selection, including
new setlist members. A partial set keeps its order and can play intact cached
songs. Preference groups reconcile independently by device timestamp and ID;
incorrect device clocks can affect the winner. See
[offline verification](verification/offline.md) for tested browsers and limits.
