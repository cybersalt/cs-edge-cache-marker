"""Deploy cs-edge-cache-marker to wyliberty.org (v3 — pure PHP, no exec).

passthru/exec/shell_exec/proc_open are disabled on wyadmin's PHP-FPM pool
(standard cPanel hardening). This version:

1. Extracts the zip's contents directly to plugins/system/csedgecachemarker/
   via ZipArchive.
2. Parses the XML manifest for the manifest_cache blob.
3. INSERTs the extension row via mysqli using the site's configuration.php.
4. Copies the language files to administrator/language/en-GB/ (Joomla install
   copies plugin language INIs there for admin display).

This mirrors what Joomla's Installer::install() does, minus the postflight
card.
"""
import base64
import json
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
@ini_set('display_errors', '1');
error_reporting(E_ALL);

$self = __FILE__;
$out  = [];

try {
    $b64 = <<<B64
""" + zip_b64 + r"""
B64;
    $bytes = base64_decode(preg_replace('/\s+/', '', $b64));
    if (!$bytes || strlen($bytes) < 100) {
        throw new RuntimeException('base64 decode failed');
    }
    $tmp_zip = sys_get_temp_dir() . '/cs_edge_cache_marker.zip';
    file_put_contents($tmp_zip, $bytes);
    $out['zip_size'] = filesize($tmp_zip);

    // ------- Extract to plugins/system/csedgecachemarker/ -------
    $base    = dirname(__FILE__);                 // /home/wyadmin/public_html
    $plugdir = $base . '/plugins/system/csedgecachemarker';

    if (!is_dir($plugdir)) {
        mkdir($plugdir, 0755, true);
    }

    $zip = new ZipArchive();
    if ($zip->open($tmp_zip) !== true) {
        throw new RuntimeException('ZipArchive open failed');
    }
    $zip->extractTo($plugdir);
    $extracted = [];
    for ($i = 0; $i < $zip->numFiles; $i++) {
        $extracted[] = $zip->getNameIndex($i);
    }
    $zip->close();
    $out['extracted'] = $extracted;

    // ------- Copy language files to Joomla's language dirs -------
    // Frontend copy (site)
    $langSrc  = $plugdir . '/language/en-GB';
    $langDst  = $base . '/administrator/language/en-GB';  // system plugins land in admin
    if (is_dir($langSrc)) {
        foreach (glob($langSrc . '/*.ini') as $iniSrc) {
            $dst = $langDst . '/' . basename($iniSrc);
            @copy($iniSrc, $dst);
            $out['lang_copied'][] = $dst;
        }
    }

    // ------- Parse manifest for manifest_cache -------
    $xmlFile = $plugdir . '/csedgecachemarker.xml';
    $manifest = simplexml_load_file($xmlFile);
    $manifest_cache = [
        'name'          => (string) $manifest->name,
        'type'          => 'plugin',
        'creationDate'  => (string) $manifest->creationDate,
        'author'        => (string) $manifest->author,
        'copyright'     => (string) $manifest->copyright,
        'authorEmail'   => (string) $manifest->authorEmail,
        'authorUrl'     => (string) $manifest->authorUrl,
        'version'       => (string) $manifest->version,
        'description'   => (string) $manifest->description,
        'group'         => 'system',
        'filename'      => 'csedgecachemarker',
    ];

    // ------- INSERT into #__extensions -------
    require_once $base . '/configuration.php';
    $cfg = new JConfig();
    $mysqli = new mysqli($cfg->host, $cfg->user, $cfg->password, $cfg->db);
    if ($mysqli->connect_error) {
        throw new RuntimeException('DB connect: ' . $mysqli->connect_error);
    }
    $mysqli->set_charset('utf8mb4');
    $tbl = $cfg->dbprefix . 'extensions';

    // Check existing
    $chk = $mysqli->query("SELECT extension_id FROM `{$tbl}` WHERE type='plugin' AND folder='system' AND element='csedgecachemarker' LIMIT 1");
    $existing = $chk ? $chk->fetch_assoc() : null;

    if ($existing) {
        // Update existing (mimics upgrade)
        $stmt = $mysqli->prepare("UPDATE `{$tbl}` SET manifest_cache=?, enabled=1 WHERE extension_id=?");
        $mc = json_encode($manifest_cache);
        $eid = (int) $existing['extension_id'];
        $stmt->bind_param('si', $mc, $eid);
        $stmt->execute();
        $out['db_action']       = 'update';
        $out['extension_id']    = $eid;
    } else {
        // Insert new
        $stmt = $mysqli->prepare("INSERT INTO `{$tbl}` (package_id, name, type, element, changelogurl, folder, client_id, enabled, access, protected, locked, manifest_cache, params, custom_data, checked_out, checked_out_time, ordering, state)
                                  VALUES (0, ?, 'plugin', 'csedgecachemarker', '', 'system', 0, 1, 1, 0, 0, ?, '{}', '', NULL, NULL, 0, 0)");
        $nm = 'plg_system_csedgecachemarker';
        $mc = json_encode($manifest_cache);
        $stmt->bind_param('ss', $nm, $mc);
        $stmt->execute();
        $out['db_action']    = 'insert';
        $out['extension_id'] = $mysqli->insert_id;
    }

    // Verify
    $row = $mysqli->query("SELECT extension_id, name, element, enabled, folder, manifest_cache FROM `{$tbl}` WHERE type='plugin' AND folder='system' AND element='csedgecachemarker'")->fetch_assoc();
    $out['final_row'] = $row;

    // ------- Bump #__assets? Not needed for plugins in Joomla 5. -------

    @unlink($tmp_zip);

    $out['status'] = ($out['extension_id'] ?? 0) > 0 ? 'installed' : 'partial';

    $mysqli->close();

} catch (\Throwable $e) {
    $out['status']    = 'exception';
    $out['exception'] = $e->getMessage();
    $out['trace']     = $e->getTraceAsString();
}

header('Content-Type: application/json');
echo json_encode($out, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);

@unlink($self);
"""

# Save + trigger
url = f"https://{CP_HOST}:{CP_PORT}/execute/Fileman/save_file_content"
data = urllib.parse.urlencode({
    "dir":     DOC_ROOT,
    "file":    INSTALLER,
    "content": installer_php,
    "from_charset": "utf-8",
    "to_charset":   "utf-8",
}).encode()

ctx = ssl._create_unverified_context()
req = urllib.request.Request(url, data=data,
    headers={"Authorization": f"cpanel {CP_USER}:{TOKEN}"})
resp = urllib.request.urlopen(req, timeout=60, context=ctx)
sr = json.loads(resp.read().decode())
print("save:", sr.get("status"), sr.get("errors"))
if sr.get("status") != 1:
    sys.exit(1)

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
    print(e.read().decode()[:2500])
