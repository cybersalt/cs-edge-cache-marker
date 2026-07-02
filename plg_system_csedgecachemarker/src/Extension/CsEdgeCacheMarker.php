<?php

/**
 * @package     Cybersalt.Plugin
 * @subpackage  System.CsEdgeCacheMarker
 *
 * @copyright   Copyright (C) 2026 Cybersalt. All rights reserved.
 * @license     GNU General Public License version 2 or later
 */

namespace Cybersalt\Plugin\System\CsEdgeCacheMarker\Extension;

\defined('_JEXEC') or die;

use Joomla\CMS\Factory;
use Joomla\CMS\Log\Log;
use Joomla\CMS\Plugin\CMSPlugin;
use Joomla\CMS\User\UserFactoryInterface;
use Joomla\Event\SubscriberInterface;

/**
 * CS Edge Cache Marker
 *
 * Sets a marker cookie on user login so upstream edge caches (Cloudflare,
 * SiteGround NGINX cache, Fastly, Bunny, Varnish, any CDN with a Cache Rule
 * expression language) can bypass cached HTML for authenticated editor
 * sessions — preserving cache-hit ratio for anonymous visitors while allowing
 * logged-in editors to see live, uncached page renders (SP Page Builder
 * front-end edit overlays, Joomla core inline edit pencils, module edit
 * icons, template edit icons, etc.).
 *
 * The cookie is set only for users whose primary or secondary groups match
 * the configured group list (default: Author, Editor, Publisher, Manager,
 * Administrator, Super Users). Site-visitor / registered-user-only accounts
 * do NOT trigger the marker — preserving cache for member-only content
 * scenarios.
 *
 * Companion edge-cache rule expression (Cloudflare example):
 *   ... and not (http.cookie contains "cs_edit_session=1")
 */
class CsEdgeCacheMarker extends CMSPlugin implements SubscriberInterface
{
    /** Auto-load language files */
    protected $autoloadLanguage = true;

    public static function getSubscribedEvents(): array
    {
        return [
            'onUserAfterLogin'  => 'onUserAfterLogin',
            'onUserAfterLogout' => 'onUserAfterLogout',
        ];
    }

    /**
     * Set the marker cookie after a successful login (if user is in a
     * configured editor group).
     */
    public function onUserAfterLogin($event): void
    {
        // Joomla 4/5 event shape: array-based event OR EventInterface.
        // Support both by pulling options + subject compatibly.
        $options = $this->extractLoginOptions($event);

        if (!\is_array($options) || empty($options['user'])) {
            return;
        }

        $user = $options['user'];

        // Handle both Joomla\CMS\User\User and stdClass/array
        $userId = 0;
        if (\is_object($user)) {
            $userId = (int) ($user->id ?? 0);
        } elseif (\is_array($user)) {
            $userId = (int) ($user['id'] ?? 0);
        }

        if ($userId <= 0) {
            $this->debug('Login event fired with no user id; skipping cookie set.');
            return;
        }

        if (!$this->userIsInConfiguredGroups($userId)) {
            $this->debug(sprintf('User %d logged in but not in a configured editor group; skipping cookie.', $userId));
            return;
        }

        $this->setMarkerCookie();
        $this->debug(sprintf('Set marker cookie for user %d.', $userId));
    }

    /**
     * Clear the marker cookie on logout.
     */
    public function onUserAfterLogout($event): void
    {
        $this->clearMarkerCookie();
        $this->debug('Cleared marker cookie on logout.');
    }

    // -----------------------------------------------------------------
    // Cookie helpers
    // -----------------------------------------------------------------

    private function setMarkerCookie(): void
    {
        $name     = $this->getCookieName();
        $value    = (string) $this->params->get('cookie_value', '1');
        $lifetime = (int) $this->params->get('cookie_lifetime', 0);
        $samesite = (string) $this->params->get('cookie_samesite', 'Lax');
        $httpOnly = (bool) (int) $this->params->get('cookie_httponly', 0);

        // lifetime=0 → session cookie (clears when browser closes)
        $expires = $lifetime > 0 ? (time() + $lifetime) : 0;

        $this->emitCookie($name, $value, $expires, $samesite, $httpOnly);
    }

    private function clearMarkerCookie(): void
    {
        $name     = $this->getCookieName();
        $samesite = (string) $this->params->get('cookie_samesite', 'Lax');
        $httpOnly = (bool) (int) $this->params->get('cookie_httponly', 0);

        // Send an expired cookie (Max-Age=0 + expires in the past) so the
        // browser clears it. Value doesn't matter since we're deleting.
        $this->emitCookie($name, '', time() - 3600, $samesite, $httpOnly);
    }

    /**
     * Actually emit the Set-Cookie header. Uses setcookie() with the
     * options-array shape (PHP 7.3+) so SameSite is respected.
     */
    private function emitCookie(string $name, string $value, int $expires, string $samesite, bool $httpOnly): void
    {
        // Guard: don't emit if headers already sent (very unusual on login,
        // but a safety net for oddly-configured sites).
        if (headers_sent()) {
            $this->debug('Headers already sent; cannot emit cookie.');
            return;
        }

        $secure = $this->requestIsSecure();

        // SameSite=None requires Secure. If cookie flag says None but request
        // isn't HTTPS, fall back to Lax to avoid the browser silently rejecting.
        if ($samesite === 'None' && !$secure) {
            $samesite = 'Lax';
        }

        \setcookie($name, $value, [
            'expires'  => $expires,
            'path'     => '/',
            'domain'   => '',
            'secure'   => $secure,
            'httponly' => $httpOnly,
            'samesite' => $samesite,
        ]);
    }

    private function getCookieName(): string
    {
        $raw = (string) $this->params->get('cookie_name', 'cs_edit_session');

        // Cookie names must be a valid token per RFC 6265: no controls,
        // no separators. Belt-and-braces sanitize.
        $clean = preg_replace('/[^A-Za-z0-9_\-]/', '', $raw);

        return $clean !== '' ? $clean : 'cs_edit_session';
    }

    private function requestIsSecure(): bool
    {
        if (!empty($_SERVER['HTTPS']) && strtolower($_SERVER['HTTPS']) !== 'off') {
            return true;
        }

        // Behind a reverse proxy / Cloudflare — trust the standard header.
        if (!empty($_SERVER['HTTP_X_FORWARDED_PROTO'])
            && strtolower($_SERVER['HTTP_X_FORWARDED_PROTO']) === 'https') {
            return true;
        }

        return false;
    }

    // -----------------------------------------------------------------
    // Group-membership helpers
    // -----------------------------------------------------------------

    private function userIsInConfiguredGroups(int $userId): bool
    {
        $configured = $this->getConfiguredGroupIds();

        if ($configured === []) {
            // No groups configured — cookie is set for every login.
            return true;
        }

        try {
            $user = Factory::getContainer()
                ->get(UserFactoryInterface::class)
                ->loadUserById($userId);

            $userGroups = array_map('intval', (array) $user->getAuthorisedGroups());
        } catch (\Throwable $e) {
            $this->debug('Failed to resolve user groups: ' . $e->getMessage());
            return false;
        }

        return (bool) array_intersect($configured, $userGroups);
    }

    /**
     * @return int[]
     */
    private function getConfiguredGroupIds(): array
    {
        $raw = $this->params->get('groups', []);

        if (\is_string($raw)) {
            // Comma-separated string fallback.
            $raw = array_map('trim', explode(',', $raw));
        }

        if (!\is_array($raw)) {
            return [];
        }

        $ids = array_filter(array_map('intval', $raw), static fn(int $id): bool => $id > 0);

        return array_values(array_unique($ids));
    }

    // -----------------------------------------------------------------
    // Compatibility helpers
    // -----------------------------------------------------------------

    /**
     * Pull the login-options array from either a Joomla 4/5 event object
     * or a legacy array-shaped event payload.
     *
     * onUserAfterLogin's canonical shape is `[$options]` where `$options`
     * is an associative array containing at least 'user' (the User object
     * being logged in) and 'action' (e.g. 'core.login.site').
     */
    private function extractLoginOptions($event): ?array
    {
        if (\is_object($event) && method_exists($event, 'getArgument')) {
            $options = $event->getArgument('options', null)
                ?? $event->getArgument(0, null)
                ?? $event->getArgument('0', null);

            if (\is_array($options)) {
                return $options;
            }
        }

        // Fallback: legacy array-shaped event
        if (\is_array($event) && isset($event[0]) && \is_array($event[0])) {
            return $event[0];
        }

        return null;
    }

    // -----------------------------------------------------------------
    // Debug logging
    // -----------------------------------------------------------------

    private function debug(string $message): void
    {
        if (!(int) $this->params->get('debug_mode', 0)) {
            return;
        }

        try {
            Log::add($message, Log::INFO, 'plg_system_csedgecachemarker');
        } catch (\Throwable $e) {
            // Silent — never let a logging failure break login.
        }
    }
}
