"""Deploy cs-edge-cache-marker to wyliberty.org via cPanel UAPI + Joomla CLI.

Uses passthru() on the Joomla CLI console (php cli/joomla.php extension:install)
rather than bootstrapping Joomla from an arbitrary PHP entry-point.
"""
import base64
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request

TOKEN     = "ACFQDKF2LHQKJQ66G08KECFF5W0AR38N"
CP_USER   = "wyadmin"
CP_HOST   = "host.server01.breakthroughgraphics.com"
CP_PORT   = 2083
DOC_ROOT  = "/home/wyadmin/public_html"
INSTALLER = "cs_marker_installer_2026_07_02.php"

ZIP_PATH = r"E:\github\cs-edge-cache-marker\dist\plg_system_csedgecachemarker_v1.0.0_20260702_1438.zip"

zip_b64 = base64.b64encode(open(ZIP_PATH, "rb").read()).decode()

installer_php = r"""<?php
// One-shot CLI installer for cs-edge-cache-marker on wyliberty.org.
// Self-deletes after running.

@ini_set('display_errors', '1');
error_reporting(E_ALL);

$self  = __FILE__;
$out   = [];

try {
    $b64 = <<<B64
""" + zip_b64 + r"""
B64;
    $zip_bytes = base64_decode(preg_replace('/\s+/', '', $b64));
    if (!$zip_bytes || strlen($zip_bytes) < 100) {
        throw new RuntimeException('base64 decode failed');
    }
    $tmp_zip = sys_get_temp_dir() . '/cs_edge_cache_marker.zip';
    file_put_contents($tmp_zip, $zip_bytes);
    $out['zip_written']   = $tmp_zip;
    $out['zip_size']      = filesize($tmp_zip);

    // Run the Joomla CLI installer under wyadmin's PHP-FPM pool (same user).
    $cmd = 'cd ' . escapeshellarg(dirname(__FILE__)) . ' && '
         . '/usr/local/bin/php cli/joomla.php extension:install --path=' . escapeshellarg($tmp_zip) . ' 2>&1';
    $out['cmd'] = $cmd;

    ob_start();
    passthru($cmd, $rc);
    $out['cli_output'] = ob_get_clean();
    $out['return_code'] = $rc;

    @unlink($tmp_zip);

    // Ensure enabled
    // Query DB via a mini script using the site's configuration.php.
    $conf_path = dirname(__FILE__) . '/configuration.php';
    if (file_exists($conf_path)) {
        require_once $conf_path;
        $cfg = new JConfig();
        $mysqli = new mysqli($cfg->host, $cfg->user, $cfg->password, $cfg->db);
        if (!$mysqli->connect_error) {
            $mysqli->set_charset('utf8mb4');
            $upd = $mysqli->query("UPDATE `{$cfg->dbprefix}extensions` SET enabled=1 WHERE type='plugin' AND folder='system' AND element='csedgecachemarker'");
            $out['db_enable_ok']       = (bool) $upd;
            $out['db_enable_affected'] = $mysqli->affected_rows;
            $row = $mysqli->query("SELECT extension_id, enabled, manifest_cache FROM `{$cfg->dbprefix}extensions` WHERE type='plugin' AND folder='system' AND element='csedgecachemarker'");
            if ($row) {
                $out['extension_row'] = $row->fetch_assoc();
            }
            $mysqli->close();
        } else {
            $out['db_connect_error'] = $mysqli->connect_error;
        }
    }

    $out['status'] = ($rc === 0 && !empty($out['extension_row'])) ? 'installed' : 'partial';

} catch (\Throwable $e) {
    $out['status']    = 'exception';
    $out['exception'] = $e->getMessage();
    $out['trace']     = $e->getTraceAsString();
}

header('Content-Type: application/json');
echo json_encode($out, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);

// Self-delete on next tick
@unlink($self);
"""

# Save via UAPI
url = f"https://{CP_HOST}:{CP_PORT}/execute/Fileman/save_file_content"
data = urllib.parse.urlencode({
    "dir":     DOC_ROOT,
    "file":    INSTALLER,
    "content": installer_php,
    "from_charset": "utf-8",
    "to_charset":   "utf-8",
}).encode()

ctx = ssl._create_unverified_context()
req = urllib.request.Request(
    url,
    data=data,
    headers={"Authorization": f"cpanel {CP_USER}:{TOKEN}"},
)
resp = urllib.request.urlopen(req, timeout=60, context=ctx)
save_result = json.loads(resp.read().decode())
print("save:", save_result.get("status"), save_result.get("errors"))
if save_result.get("status") != 1:
    sys.exit(1)

# Trigger
trigger_url = f"https://wyliberty.org/{INSTALLER}"
print(f"\nTrigger: {trigger_url}\n")

req2 = urllib.request.Request(trigger_url, headers={
    "User-Agent": "Cybersalt-Installer/1.0",
    "Cache-Control": "no-cache",
})
try:
    resp2 = urllib.request.urlopen(req2, timeout=120)
    print("HTTP:", resp2.status)
    print(resp2.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP error:", e.code)
    body = e.read().decode()
    # Look for JSON inside the response
    if body.startswith('{'):
        print(body)
    else:
        # Truncated dump
        print(body[:1500])
