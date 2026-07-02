# CS Edge Cache Marker

A tiny Joomla 5/6 system plugin that sets a marker cookie on editor login so upstream edge caches (Cloudflare, SiteGround, Fastly, Bunny, Varnish, any CDN with rule-expression support) can **bypass cached HTML for authenticated editor sessions** — preserving cache-hit ratio for anonymous visitors while letting logged-in editors see live, uncached page renders.

## The problem this solves

When you put a Joomla site behind a full-HTML edge cache (Cloudflare Cache Rules with `override_origin`, SiteGround's Dynamic Cache, Varnish, etc.), you get big cached-HIT wins for anonymous traffic — but front-end editor overlays disappear. SP Page Builder's Edit pencils, Joomla's core inline edit icons, module edit icons — none of them render because the edge is serving the anonymous cached copy to your logged-in editors too.

The standard fix is to bypass cache when a distinguishing cookie is present. This plugin sets that cookie in a way that fires **only for real editors** (not for anonymous form submitters, not for member-only content readers), so you keep the maximum possible cache-hit ratio.

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
