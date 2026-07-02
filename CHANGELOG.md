# Changelog

All notable changes to `cs-edge-cache-marker` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
