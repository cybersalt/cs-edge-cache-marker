"""Deploy cs-edge-cache-marker to wyliberty.org via cPanel UAPI.

Steps:
1. Read the just-built zip, base64-encode it.
2. Compose a single-shot PHP installer that:
   - Decodes the zip to /tmp/csedgecachemarker.zip
   - Bootstraps Joomla and calls Installer->install()
   - Reports success/failure as JSON
   - Deletes itself
3. Save the installer via cPanel UAPI Fileman/save_file_content.
4. Trigger it via HTTPS GET.
5. Report result.
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
DEPLOY_DIR = "/home/wyadmin/public_html"
DEPLOY_FILE = "cs_marker_installer_2026_07_02.php"

ZIP_PATH = r"E:\github\cs-edge-cache-marker\dist\plg_system_csedgecachemarker_v1.0.0_20260702_1438.zip"

zip_b64 = base64.b64encode(open(ZIP_PATH, "rb").read()).decode()

installer_php = r"""<?php
// One-shot installer for cs-edge-cache-marker on wyliberty.org.
// Deletes itself after running.

// Guard: only run once. If __LOCK__ file exists, bail.
$self = __FILE__;
$lock = $self . '.done';
if (file_exists($lock)) {
    header('Content-Type: application/json');
    echo json_encode(['status' => 'already-ran', 'lock' => $lock]);
    exit;
}

$base64_zip = <<<B64
""" + zip_b64 + r"""
B64;

$zip_bytes = base64_decode($base64_zip);
if ($zip_bytes === false || strlen($zip_bytes) < 100) {
    header('Content-Type: application/json');
    echo json_encode(['status' => 'error', 'stage' => 'decode', 'bytes' => strlen($zip_bytes)]);
    exit;
}

$tmp_zip = sys_get_temp_dir() . '/cs_edge_cache_marker_' . uniqid() . '.zip';
file_put_contents($tmp_zip, $zip_bytes);

// Bootstrap Joomla
define('_JEXEC', 1);
define('JPATH_BASE', __DIR__);
require_once JPATH_BASE . '/includes/defines.php';
require_once JPATH_BASE . '/includes/framework.php';

use Joomla\CMS\Factory;
use Joomla\CMS\Installer\Installer;

// Boot the CMS application so Factory can resolve services.
try {
    $app = Factory::getContainer()->get(\Joomla\CMS\Application\SiteApplication::class);
    Factory::$application = $app;
} catch (\Throwable $e) {
    // Some Joomla versions expose the app differently; fall through and hope Installer can run standalone.
}

$installer = new Installer();
$installer->setDatabase(Factory::getContainer()->get(\Joomla\Database\DatabaseInterface::class));
$result = $installer->install($tmp_zip);

// Clean up the extracted temp dir + the zip
@unlink($tmp_zip);

// Try to enable the plugin explicitly (belt-and-braces; script.php also does this).
$db = Factory::getContainer()->get(\Joomla\Database\DatabaseInterface::class);
$q  = $db->getQuery(true)
    ->update($db->quoteName('#__extensions'))
    ->set($db->quoteName('enabled') . ' = 1')
    ->where($db->quoteName('type') . ' = ' . $db->quote('plugin'))
    ->where($db->quoteName('folder') . ' = ' . $db->quote('system'))
    ->where($db->quoteName('element') . ' = ' . $db->quote('csedgecachemarker'));
$db->setQuery($q);
$db->execute();
$affected = $db->getAffectedRows();

// Verify presence
$q2 = $db->getQuery(true)
    ->select($db->quoteName(['extension_id', 'enabled', 'manifest_cache']))
    ->from($db->quoteName('#__extensions'))
    ->where($db->quoteName('type') . ' = ' . $db->quote('plugin'))
    ->where($db->quoteName('folder') . ' = ' . $db->quote('system'))
    ->where($db->quoteName('element') . ' = ' . $db->quote('csedgecachemarker'));
$row = $db->setQuery($q2)->loadAssoc();

header('Content-Type: application/json');
echo json_encode([
    'status'            => $result ? 'installed' : 'install-failed',
    'installer_message' => $installer->message ?? null,
    'extension_row'     => $row,
    'enable_affected'   => $affected,
    'tmp_zip'           => $tmp_zip,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);

// Write lock + schedule self-delete on next request.
file_put_contents($lock, date('c'));
@unlink($self);
@unlink($lock);
"""

# Save via UAPI
url = f"https://{CP_HOST}:{CP_PORT}/execute/Fileman/save_file_content"
data = urllib.parse.urlencode({
    "dir":     DEPLOY_DIR,
    "file":    DEPLOY_FILE,
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
print("UAPI save_file_content:", json.dumps(save_result, indent=2)[:500])
if save_result.get("status") != 1:
    print("SAVE FAILED — aborting.")
    sys.exit(1)

# Trigger it — use direct-to-origin via CF's grey-cloud is complex, so hit through CF.
# CF cache-rule will MISS on unknown path, so no caching concern.
trigger_url = f"https://wyliberty.org/{DEPLOY_FILE}"
print(f"\nTriggering: {trigger_url}")

req2 = urllib.request.Request(trigger_url, headers={
    "User-Agent": "Cybersalt-Installer/1.0",
    "Cache-Control": "no-cache",
})
try:
    resp2 = urllib.request.urlopen(req2, timeout=90)
    body = resp2.read().decode()
    print("HTTP:", resp2.status)
    print("Body:")
    print(body)
except urllib.error.HTTPError as e:
    print("HTTP error:", e.code)
    print(e.read().decode()[:2000])
