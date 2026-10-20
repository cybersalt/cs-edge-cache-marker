<?php

/**
 * @package     Cybersalt.Plugin
 * @subpackage  System.CsEdgeCacheMarker
 *
 * @copyright   Copyright (C) 2026 Cybersalt. All rights reserved.
 * @license     GNU General Public License version 2 or later
 */

\defined('_JEXEC') or die;

use Joomla\CMS\Factory;
use Joomla\CMS\Installer\InstallerAdapter;
use Joomla\CMS\Installer\InstallerScriptInterface;
use Joomla\CMS\Uri\Uri;
use Joomla\Database\DatabaseAwareTrait;
use Joomla\Database\DatabaseInterface;

return new class () implements InstallerScriptInterface {
    use DatabaseAwareTrait;

    public function __construct()
    {
        $this->setDatabase(Factory::getContainer()->get(DatabaseInterface::class));
    }

    public function install(InstallerAdapter $adapter): bool
    {
        return true;
    }

    public function update(InstallerAdapter $adapter): bool
    {
        return true;
    }

    public function uninstall(InstallerAdapter $adapter): bool
    {
        return true;
    }

    public function preflight(string $type, InstallerAdapter $adapter): bool
    {
        return true;
    }

    public function postflight(string $type, InstallerAdapter $adapter): bool
    {
        // Only render the post-install card on install / update / discover_install.
        // Joomla calls postflight() on uninstall too — without this gate, users
        // get a "click here to open settings" card right after clicking Uninstall.
        if (!\in_array($type, ['install', 'update', 'discover_install'], true)) {
            return true;
        }

        // Auto-enable the plugin on first install so the login hook fires
        // immediately without a manual admin trip.
        if ($type === 'install' || $type === 'discover_install') {
            $this->enablePlugin();
        }

        $this->normaliseGroupsParam();

        $this->renderPostInstallCard($type);

        return true;
    }

    private function enablePlugin(): void
    {
        try {
            $db = $this->getDatabase();
            $query = $db->getQuery(true)
                ->update($db->quoteName('#__extensions'))
                ->set($db->quoteName('enabled') . ' = 1')
                ->where($db->quoteName('type') . ' = ' . $db->quote('plugin'))
                ->where($db->quoteName('folder') . ' = ' . $db->quote('system'))
                ->where($db->quoteName('element') . ' = ' . $db->quote('csedgecachemarker'));
            $db->setQuery($query)->execute();
        } catch (\Throwable $e) {
            // Silent — non-fatal.
        }
    }

    /**
     * Joomla stores the manifest default for the multi-select "groups" field
     * as one comma-separated string ("3,4,5,6,7,8"). The fancy-select can't
     * show that, so the field looked empty and a Save would clear it. Store
     * the value as a list of IDs instead, on install and on every update.
     */
    private function normaliseGroupsParam(): void
    {
        try {
            $db = $this->getDatabase();
            $query = $db->getQuery(true)
                ->select([$db->quoteName('extension_id'), $db->quoteName('params')])
                ->from($db->quoteName('#__extensions'))
                ->where($db->quoteName('type') . ' = ' . $db->quote('plugin'))
                ->where($db->quoteName('folder') . ' = ' . $db->quote('system'))
                ->where($db->quoteName('element') . ' = ' . $db->quote('csedgecachemarker'));
            $row = $db->setQuery($query)->loadObject();

            if (!$row) {
                return;
            }

            $params = json_decode((string) $row->params, true);

            if (!\is_array($params) || !isset($params['groups']) || !\is_string($params['groups'])) {
                return;
            }

            $ids = array_values(array_filter(
                array_map('trim', explode(',', $params['groups'])),
                static fn(string $id): bool => ctype_digit($id) && (int) $id > 0
            ));

            if ($ids === []) {
                return;
            }

            $params['groups'] = $ids;

            $update = $db->getQuery(true)
                ->update($db->quoteName('#__extensions'))
                ->set($db->quoteName('params') . ' = ' . $db->quote(json_encode($params)))
                ->where($db->quoteName('extension_id') . ' = ' . (int) $row->extension_id);
            $db->setQuery($update)->execute();
        } catch (\Throwable $e) {
            // Non-fatal: the plugin itself also accepts the comma-separated form.
        }
    }

    private function getExtensionId(): int
    {
        try {
            $db = $this->getDatabase();
            $query = $db->getQuery(true)
                ->select($db->quoteName('extension_id'))
                ->from($db->quoteName('#__extensions'))
                ->where($db->quoteName('type') . ' = ' . $db->quote('plugin'))
                ->where($db->quoteName('folder') . ' = ' . $db->quote('system'))
                ->where($db->quoteName('element') . ' = ' . $db->quote('csedgecachemarker'));

            return (int) $db->setQuery($query)->loadResult();
        } catch (\Throwable $e) {
            return 0;
        }
    }

    private function renderPostInstallCard(string $type): void
    {
        $verb = $type === 'update' ? 'updated' : 'installed';

        // Build safe (HTML-escaped) label strings — script strings today are
        // static, but future translations could carry markup. Wrap defensively.
        $esc = static fn(string $s): string => htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

        $title    = $esc('Cybersalt Edge Cache Marker ' . $verb . ' successfully');
        $lead     = $esc('This plugin sets a marker cookie when an editor logs in so upstream edge caches (Cloudflare, SiteGround, Fastly, Varnish) can bypass cached HTML for authenticated sessions.');
        $configL  = $esc('Open plugin settings');
        $cookieL  = $esc('Cookie name (default):');
        $cookieV  = $esc('cs_edit_session');
        $ruleH    = $esc('Add to your edge-cache bypass rule');
        $ruleCF   = $esc('Cloudflare rule expression (append to the existing cache-eligibility expression):');

        $extensionId = $this->getExtensionId();
        $settingsUrl = $esc($extensionId > 0
            ? 'index.php?option=com_plugins&task=plugin.edit&extension_id=' . $extensionId
            : 'index.php?option=com_plugins&view=plugins&filter[folder]=system&filter[search]=csedgecachemarker');
        $logoUrl     = $esc(Uri::root(true) . '/media/plg_system_csedgecachemarker/logo.svg');

        echo <<<HTML
<div class="card border-success mt-3">
    <div class="card-header bg-success text-white d-flex align-items-center">
        <img src="{$logoUrl}" alt="" width="40" height="40" class="me-2" style="background:#fff; border-radius:50%; padding:4px;" />
        <h3 class="card-title mb-0">{$title}</h3>
    </div>
    <div class="card-body">
        <p class="lead">{$lead}</p>

        <p><strong>{$cookieL}</strong> <code>{$cookieV}</code></p>

        <h4>{$ruleH}</h4>
        <p>{$ruleCF}</p>
        <pre class="bg-light p-3 border rounded"><code>and not (http.cookie contains "cs_edit_session=1")</code></pre>

        <p class="mt-3">
            <a class="btn btn-primary text-white text-decoration-none" href="{$settingsUrl}">
                <span class="icon-cog" aria-hidden="true"></span> {$configL}
            </a>
        </p>
    </div>
</div>
HTML;
    }
};
