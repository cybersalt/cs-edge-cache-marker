# Changelog

All notable changes to `cs-edge-cache-marker` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] — 2026-10-20

### 🐛 Fixes

- **Authors never got the marker cookie.** The documented default is "Author, Editor, Publisher, Manager, Administrator, Super Users", but the shipped default was group IDs 4–8, which leaves out Author (ID 3). New installs now default to 3–8. **Existing sites keep their saved list**: open the plugin and add Author if your authors edit on the front end.
- **Debug logging never wrote anything.** The plugin logged to its own category but never registered a logger for it, so Joomla discarded every line. With *Debug logging* on, entries now go to `plg_system_csedgecachemarker.php` in Joomla's log folder.
- **An empty group list set the marker for every login.** If the list is cleared, the plugin now falls back to the six default editing groups instead of marking every logged-in user (including Registered members) as an editor.
- **Joomla 6: the *Editor user groups* field was empty and no groups could be picked.** It used the `usergroup` form field type, which Joomla 6 removed, so the list rendered with no options at all. It now uses `usergrouplist`, which works on Joomla 5 and 6. Installing or updating also stores the default list as separate group IDs instead of one comma-separated value.
- **Post-install card:** the logo now loads on sites installed in a subfolder, and *Open plugin settings* opens the plugin's own edit screen.

### 🔧 Changes

- **Update server moved to cybersalt.com.** Updates are now served by `https://www.cybersalt.com/index.php?option=com_csreleasemanager&task=api.updatexml&format=raw&element=csedgecachemarker`. The old GitHub `updates.xml` also offers this release, so sites on 1.0.0 / 1.0.1 move over with one normal update.
- **Display name** is now *System - Cybersalt Edge Cache Marker*.
- Removed the `<targetplatform>` element from the plugin manifest; it belongs in the update feed only (flagged by JED Checker).
- The release zip now includes `CHANGELOG.md` and `CHANGELOG.html`.

## [1.0.1] — 2026-07-02

### 🐛 Fixes

- **Manifest `<description>` now references a key that actually exists in `.sys.ini`** — the previous `PLG_SYSTEM_CSEDGECACHEMARKER_DESCRIPTION` key only lived in `.ini`, which Joomla doesn't auto-load on the Extension Manager listing. The listing was showing the raw constant name. Manifest now references `PLG_SYSTEM_CSEDGECACHEMARKER_XML_DESCRIPTION`; the .sys.ini's copy is expanded to the full sentence so the extension listing shows meaningful text.
- **`<targetplatform>` regex added** — `5\.[0-9]+|6\.[0-9]+` (was previously missing from `csedgecachemarker.xml` entirely; `updates.xml` had bare `5` which excluded J6). Joomla 6 sites can now accept the auto-update.

### 🔧 Chore

- Added Joomla Brain submodule at `.joomla-brain/`.

## [1.0.0] — 2026-07-02

### 🚀 Initial release

- **Marker cookie on `onUserAfterLogin`** — sets a configurable cookie (default `cs_edit_session=1`) when a user in one of the configured editor groups logs in.
- **Cookie cleared on `onUserAfterLogout`** — sends an expired cookie so the browser clears the marker.
- **Group-scoped** — only fires for users whose group memberships include one of the configured groups (default: Author, Editor, Publisher, Manager, Administrator, Super Users).
- **Configurable name / value / lifetime / SameSite / HttpOnly**.
- **Auto-Secure detection** — respects `X-Forwarded-Proto: https` so the Secure flag is set correctly behind Cloudflare / reverse proxies.
- **Session-cookie default** — cleared when the browser closes; matches Joomla session lifecycle.
- **Post-install card** with copy-paste Cloudflare rule expression + link to plugin settings.
- **Auto-enable on install** — no manual admin trip needed.
- **Debug logging (optional)** — INFO-level entries to `plg_system_csedgecachemarker` log category.

### 📦 Context

Built the afternoon of 2026-07-02 in response to Derrick Cook reporting SP Page Builder front-end editing wasn't working on [wyliberty.org](https://wyliberty.org) after a Cloudflare Cache Rule was added on 2026-06-29 to serve HTML from CF edge (a 5× TTFB win — from ~210 ms cached HIT to ~35 ms). The rule cached anonymous HTML and served it to logged-in editors too, hiding the SPPB Edit-pencil overlays.

This plugin is the correct fix: a marker cookie lets the CF rule bypass cache specifically for editor sessions while keeping the full anonymous-visitor cache-hit win.

Companion Cloudflare rule expression addition:

```
and not (http.cookie contains "cs_edit_session=1")
```
