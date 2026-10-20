# Cybersalt Edge Cache Marker

**Keep a Joomla site fast for the public and editable from the front end at the same time.**

A small Joomla 5/6 system plugin that sets a marker cookie when an editor logs in, so an edge cache in front of the site (a **Cloudflare** Cache Rule, **Varnish**, **NGINX** `proxy_cache`, **Fastly**, **Bunny** or any CDN that can match on a cookie) can skip its cached HTML for editors while still serving cached pages to everyone else.

- **Documentation:** https://docs.cybersalt.com/extensions/edge-cache-marker
- **Download and product page:** https://www.cybersalt.com/extensions/edge-cache-marker
- **Support:** https://www.cybersalt.com/services/support-request-form or [GitHub issues](https://github.com/cybersalt/cs-edge-cache-marker/issues)

## The problem it solves

Put a full-HTML edge cache in front of a Joomla site and anonymous visitors get pages in a few tens of milliseconds. But the cache serves that same anonymous copy to logged-in editors too, so the front-end edit icons (Joomla's inline edit buttons, module edit icons, SP Page Builder's edit overlay) disappear: the editor is looking at HTML that was rendered for nobody in particular.

The usual fix is to bypass the cache when a cookie is present. Bypassing on Joomla's session cookie doesn't work, because Joomla gives every visitor a session. Bypassing on Joomla's own `joomla_user_state` cookie bypasses for **every** logged-in user, including members who only read content.

This plugin sets its marker **only** for users in the groups you choose (by default Author, Editor, Publisher, Manager, Administrator and Super Users), on both site and administrator logins, and clears it on logout. Your edge rule bypasses on that one cookie; everyone else, members included, keeps getting cached pages.

## How it works

- `onUserAfterLogin`: if the user belongs to one of the configured groups (or to a group nested under one of them), the response sets `cs_edit_session=1; path=/; SameSite=Lax` (`Secure` on HTTPS, including behind a proxy that sends `X-Forwarded-Proto: https`).
- `onUserAfterLogout`: the response expires the cookie.
- Nothing else. The plugin doesn't change page output and doesn't talk to your CDN.

## Requirements

- Joomla 5.0 or newer (5.x and 6.x)
- PHP 8.1 or newer

## Installation

1. Download the zip from the [product page](https://www.cybersalt.com/extensions/edge-cache-marker) or the [GitHub releases](https://github.com/cybersalt/cs-edge-cache-marker/releases).
2. Joomla admin → **System → Install → Extensions** → upload the zip.
3. The plugin enables itself on install. Updates arrive through **System → Update → Extensions** from Cybersalt's update server.

## Configuration

**System → Manage → Plugins → "Cybersalt Edge Cache Marker"**

| Setting | Default | What it does |
|---|---|---|
| Cookie name | `cs_edit_session` | The name your edge rule looks for. Letters, digits, `_` and `-` only. |
| Cookie value | `1` | The value your rule matches. |
| Editor user groups | Author, Editor, Publisher, Manager, Administrator, Super Users | Users in these groups (or groups nested under them) get the cookie. Left empty, the defaults are used. |
| Cookie lifetime (seconds) | `0` | `0` = session cookie, gone when the browser closes. A positive number keeps it for that many seconds. |
| SameSite | `Lax` | `None` is downgraded to `Lax` on plain HTTP. |
| HttpOnly | No | Hides the cookie from JavaScript. Your edge cache sees it either way. |
| Debug logging | No | Writes to `plg_system_csedgecachemarker.php` in Joomla's log folder. |

## Edge-cache rules

**Cloudflare Cache Rule** — add to the rule's expression:

```
and not (http.cookie contains "cs_edit_session=1")
```

**Varnish (VCL):**

```vcl
sub vcl_recv {
    if (req.http.Cookie ~ "cs_edit_session=1") {
        return (pass);
    }
}
```

**NGINX `proxy_cache`:**

```nginx
map $http_cookie $skip_cache {
    default 0;
    "~*cs_edit_session=1" 1;
}
# in the location block:
proxy_cache_bypass $skip_cache;
proxy_no_cache $skip_cache;
```

**Fastly (VCL, in `vcl_recv`):**

```vcl
if (req.http.Cookie ~ "cs_edit_session=1") {
    return(pass);
}
```

More detail, including how to check it's working and what to purge after enabling it, is in the [documentation](https://docs.cybersalt.com/extensions/edge-cache-marker).

## Things to know

- The cookie is a hint, not a credential. Anyone can send it; all it does is skip the cache for their own requests. It grants no access.
- Logging out of either the site or the administrator clears the cookie.
- If a Joomla session expires without a logout, the cookie stays until the browser closes (with the default lifetime). That only means uncached pages for that browser.
- Existing sites updating from 1.0.0/1.0.1 keep their saved group list, which doesn't include Author. Add it in the plugin if your authors edit on the front end.

## Build from source

```bash
python dist/build.py
```

Builds `plg_system_csedgecachemarker_v<version>.zip` in the repo root (forward-slash zip entries, `CHANGELOG.md` and `CHANGELOG.html` included). The script refuses to build if either changelog is missing or the manifest version doesn't match.

## License

GNU General Public License version 2 or later. See [LICENSE](./LICENSE). The logo's cookie shape is based on the MIT-licensed Tabler Icons "cookie" icon.

## Author

[Cybersalt Consulting Ltd.](https://www.cybersalt.com) · support@cybersalt.com
