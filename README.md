# CS Edge Cache Marker

**Have your Joomla site fast for the public AND editable from the front-end at the same time.**

A tiny Joomla 5/6 system plugin that sets a marker cookie on editor login so upstream edge caches — **Cloudflare Cache Rules**, **SiteGround Dynamic Cache**, **Fastly**, **Bunny**, **Varnish**, **NGINX proxy_cache**, or any CDN with cookie-inspection support — can **bypass cached HTML for authenticated editor sessions while still serving cached HTML at edge speed to everyone else**.

## The problem this solves

You put a Joomla site behind a full-HTML edge cache and TTFB drops from ~200 ms to ~30 ms for anonymous visitors — a huge win. But the moment a logged-in editor visits a page they built with SP Page Builder, the Edit pencils have vanished. Joomla's core inline edit icons don't appear either. Module edit icons — gone. Template edit icons — gone.

Because the edge is caching the anonymous-user render of the page and serving that copy to *everyone*, including your logged-in editors. Their browser has a valid Joomla session, but they're looking at HTML that was rendered without one. All the editor overlays that Joomla only draws for authenticated users never make it through the cache.

The standard fix is to bypass edge cache when a distinguishing cookie is present. But if you naively bypass on "any Joomla session cookie," you also bypass for every anonymous visitor who submits a contact form or a newsletter signup — because Joomla starts a session for them too. That erodes cache-hit ratio for no benefit.

**This plugin is precise**: it fires the marker cookie **only** on `onUserAfterLogin` for users in a configured editor group list (default: Author / Editor / Publisher / Manager / Administrator / Super Users). Anonymous form submitters don't get the marker. Registered-only members (OSMembership subscribers reading paywalled articles, MembershipPro users, any member-content pattern) don't get the marker. Only real editors trigger bypass, so cache-hit ratio stays maximal.

## What "best of both worlds" looks like in practice

- **Anonymous visitor lands on your homepage**: served from CF edge in ~35 ms. First hit through their POP is a MISS; from then on it's HIT for every visitor from that POP until the TTL rolls.
- **Anonymous visitor submits a contact form**: Joomla starts a session; they get a Joomla session cookie in their browser. Doesn't matter — the plugin only sets `cs_edit_session=1` on `onUserAfterLogin`, not on session start. Their next page load is still a cache HIT.
- **Anonymous visitor buys an OSMembership subscription and logs into a "customer" account** with no editing rights: not in the plugin's configured editor group list, so no `cs_edit_session=1` cookie. Cache stays fully HIT-capable for them.
- **You log into `/administrator`** as a Super User: `onUserAfterLogin` fires, plugin sees you're in group 8 (Super Users), sets `cs_edit_session=1; Path=/`. From that moment, every request your browser makes to any page on the site carries the cookie. Cloudflare's Cache Rule sees the cookie and returns `Cf-Cache-Status: DYNAMIC` — the request goes straight through to Joomla, which renders the page fresh with all your editor overlays. SP Page Builder Edit pencil? Visible. Click it, edit the page, save. Log out → cookie clears → next visit as anonymous is back to cache HIT.

Zero degradation to public-facing speed. Full editor UX preserved. That's the point.

## Features

- Fires on `onUserAfterLogin` — sets the marker cookie
- Fires on `onUserAfterLogout` — clears the cookie
- Group-scoped — only writes the cookie when the logging-in user is in one of the configured groups (default: Author, Editor, Publisher, Manager, Administrator, Super Users)
- Configurable cookie name, value, lifetime, SameSite, HttpOnly
- Session-cookie by default (clears when the browser closes)
- Auto-Secure when the request is HTTPS (respects `X-Forwarded-Proto` for reverse-proxy / Cloudflare)
- Debug logging (optional) to `plg_system_csedgecachemarker` category
- Post-install card in the Joomla admin with copy-paste Cloudflare rule expression

## Requirements

- Joomla 5.0+ (uses namespaced service provider + subscriber pattern; not compatible with legacy plugin loader)
- PHP 8.0+ (uses arrow functions + option-array `setcookie()`)

## Installation

1. Download the latest `plg_system_csedgecachemarker_v*.zip` from the [releases page](https://github.com/cybersalt/cs-edge-cache-marker/releases) or [dist/ folder](./dist).
2. Joomla admin → System → Install → Extensions → Upload Package File → drop the zip.
3. The plugin auto-enables on install (no need to visit the Plugins page first).

## Configuration

**System → Manage → Plugins → search "csedgecachemarker"**

| Field | Default | Notes |
|---|---|---|
| Cookie name | `cs_edit_session` | Reference this exact string in your edge-cache bypass rule |
| Cookie value | `1` | Change only if coordinating with a more complex rule |
| Editor user groups | Author, Editor, Publisher, Manager, Administrator, Super Users | Multi-select. Groups NOT in this list won't trigger the marker |
| Cookie lifetime (seconds) | `0` | `0` = session cookie. Positive value = persistent for N seconds |
| SameSite | `Lax` | `None` requires Secure, auto-downgrades to `Lax` on HTTP |
| HttpOnly | Off | Keep **off** unless you're sure no client JS needs to see the cookie |
| Debug logging | Off | Optional trace to `logs/plg_system_csedgecachemarker.*.php` |

## Edge-cache rule expressions

### Cloudflare Cache Rule

Append to your existing cache-eligibility expression:

```
and not (http.cookie contains "cs_edit_session=1")
```

Full example (cache HTML on `example.com` except admin/API/logged-in editors):

```
(http.host eq "example.com"
 and not starts_with(http.request.uri.path, "/administrator")
 and not starts_with(http.request.uri.path, "/api")
 and not (http.cookie contains "cs_edit_session=1"))
```

### SiteGround Dynamic Cache

Uses cookie exclusion via `.htaccess`:

```apache
SetEnvIf Cookie "cs_edit_session=1" no-cache=1
```

### Varnish (VCL)

```vcl
sub vcl_recv {
    if (req.http.Cookie ~ "cs_edit_session=1") {
        return (pass);
    }
}
```

### NGINX proxy_cache

```nginx
map $http_cookie $skip_cache {
    default 0;
    "~*cs_edit_session=1" 1;
}

# In your location block:
proxy_cache_bypass $skip_cache;
proxy_no_cache $skip_cache;
```

### Fastly

```vcl
if (req.http.Cookie ~ "cs_edit_session=1") {
    return(pass);
}
```

## Compatibility notes

- **Cookie name sanitization**: The cookie name is sanitized to `[A-Za-z0-9_-]` at emit time. If your rule references a name with other characters, adjust the config and match.
- **SameSite=None auto-downgrade**: If you configure `SameSite=None` but the request is HTTP (not HTTPS), the plugin downgrades to `Lax` to avoid the browser silently rejecting a `None`-without-Secure cookie.
- **Reverse proxies**: The plugin respects `X-Forwarded-Proto: https` for detecting HTTPS behind a proxy. If your proxy uses a different header, extend `requestIsSecure()`.

## Build from source

```bash
cd plg_system_csedgecachemarker
7z a -tzip ../dist/plg_system_csedgecachemarker_v$(grep -m1 '<version>' csedgecachemarker.xml | sed 's/.*<version>\(.*\)<\/version>.*/\1/')_$(date +%Y%m%d_%H%M).zip *
```

The Joomla Brain checklist requires 7-Zip, not PowerShell's `Compress-Archive` (which can produce zips Joomla's installer rejects).

## License

GNU General Public License version 2 or later. See [LICENSE](./LICENSE).

## Author

Cybersalt · https://cybersalt.com · support@cybersalt.com
