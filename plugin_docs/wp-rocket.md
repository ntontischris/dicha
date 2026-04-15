All WP Rocket settings are stored in a single WordPress option:

```php
$settings = get_option('wp_rocket_settings');
```

The option key constant is `WP_ROCKET_SLUG = 'wp_rocket_settings'`.

---

### How to Read the Settings

```php
$rocket = get_option('wp_rocket_settings', []);
// Example: is minify CSS enabled?
$minify_css = ! empty($rocket['minify_css']); // 1 = enabled, 0 = disabled
```

Most boolean options are stored as `1` (enabled) or `0` (disabled). Arrays are stored as PHP arrays (serialized by WordPress).

---

### Section 1: File Optimization — CSS

| Key | Type | Default | Description |
|---|---|---|---|
| `minify_css` | `0`/`1` | `0` | Minify CSS files — removes whitespace and comments to reduce file size. |
| `exclude_css` | array of strings | `[]` | URLs of CSS files to exclude from minification (supports `(.*)` wildcards). |
| `optimize_css_delivery` | `0`/`1` | `0` | Master toggle for CSS delivery optimization (eliminates render-blocking CSS). |
| `optimize_css_delivery_method` | `remove_unused_css` / `async_css` | `remove_unused_css` | Which CSS delivery method to use: **Remove Unused CSS** (per-page unused CSS removal) or **Load CSS asynchronously** (generates critical path CSS). |
| `remove_unused_css` | `0`/`1` | `0` | Hidden field — actual toggle for Remove Unused CSS being active (set automatically based on `optimize_css_delivery_method`). |
| `remove_unused_css_safelist` | array of strings | `[]` | CSS filenames, IDs, or classes that should NOT be removed by RUCSS (one per line). |
| `async_css` | `0`/`1` | `0` | Hidden field — actual toggle for Load CSS Asynchronously being active. |
| `critical_css` | string | `''` | Fallback critical path CSS used when async CSS is enabled and auto-generation is incomplete. |
| `minify_concatenate_css` | `0`/`1` | `0` | Hidden field — combine CSS files (deprecated/hidden in newer versions). |
| `minify_google_fonts` | `0`/`1` | `0` | Hidden field — combine Google Fonts requests into a single request. |

---

### Section 2: File Optimization — JavaScript

| Key | Type | Default | Description |
|---|---|---|---|
| `minify_js` | `0`/`1` | `0` | Minify JavaScript files — removes whitespace and comments. |
| `exclude_js` | array of strings | `[]` | URLs of JS files to exclude from minification and concatenation (supports wildcards). |
| `minify_concatenate_js` | `0`/`1` | `0` | Combine JavaScript files — merges internal, 3rd party and inline JS to reduce HTTP requests. Not recommended with HTTP/2. Disabled automatically when Delay JS is active. |
| `exclude_inline_js` | array of strings | `[]` | Patterns of inline JavaScript to exclude from concatenation (e.g. `recaptcha`). |
| `defer_all_js` | `0`/`1` | `0` | Load JavaScript deferred — eliminates render-blocking JS. |
| `exclude_defer_js` | array of strings | `[]` | URLs or keywords of JS files to exclude from defer. |
| `delay_js` | `0`/`1` | `0` | Delay JavaScript execution — delays loading of JS files until user interaction (scroll, click). Automatically disables Combine JS. |
| `delay_js_exclusions` | array of strings | `[]` | URLs or keywords of JS files/inline scripts to exclude from delay execution. |
| `delay_js_exclusions_selected` | array of strings | `[]` | One-click exclusions for known plugins/themes/services from the delay JS feature (selected from a categorized list). |
| `delay_js_execution_safe_mode` | `0`/`1` | `0` | Safe Mode for Delay JS — prevents ALL internal scripts from being delayed. Reduces performance gains but avoids compatibility issues. |
| `emoji` | `0`/`1` | `0` | Hidden field — disable WordPress emoji scripts. |

---

### Section 3: Media

| Key | Type | Default | Description |
|---|---|---|---|
| `lazyload` | `0`/`1` | `0` | Enable LazyLoad for images — images load only when entering the viewport. |
| `lazyload_css_bg_img` | `0`/`1` | `0` | Enable LazyLoad for CSS background images. |
| `lazyload_iframes` | `0`/`1` | `0` | Enable LazyLoad for iframes and videos. |
| `lazyload_youtube` | `0`/`1` | `0` | Replace YouTube iframes with a preview image — loads the actual iframe only on click. Requires `lazyload_iframes = 1`. |
| `exclude_lazyload` | array of strings | `[]` | Keywords (filename, CSS class, domain) from image/iframe code to exclude from LazyLoad. |
| `image_dimensions` | `0`/`1` | `0` | Add missing width/height attributes to images — helps prevent layout shifts (CLS). |
| `auto_preload_fonts` | `0`/`1` | `0` | Preload above-the-fold fonts to improve LCP and layout stability. |
| `host_fonts_locally` | `0`/`1` | `0` | Self-host Google Fonts — downloads and serves fonts from your own server to reduce external connections. |

---

### Section 4: Preload

| Key | Type | Default | Description |
|---|---|---|---|
| `manual_preload` | `0`/`1` | `1` | Activate cache preloading — WP Rocket detects sitemaps and keeps cache always preloaded. Default is ON. |
| `preload_excluded_uri` | array of strings | `[]` | URLs to exclude from the preload feature (supports `(.*)` wildcards). |
| `preload_links` | `0`/`1` | `0` | Enable link preloading — prefetches pages when a user hovers over a link to improve perceived load time. |

---

### Section 5: Advanced Rules

| Key | Type | Default | Description |
|---|---|---|---|
| `purge_cron_interval` | integer | `10` | Cache lifespan — cache files older than this value are deleted. `0` = unlimited (never auto-purge). |
| `purge_cron_unit` | `HOUR_IN_SECONDS` / `DAY_IN_SECONDS` | `HOUR_IN_SECONDS` | Unit for `purge_cron_interval` — Hours or Days. |
| `cache_reject_uri` | array of strings | `[]` | URLs that should never be cached (one per line, supports wildcards). Domain part is stripped automatically. |
| `cache_reject_cookies` | array of strings | `[]` | Cookie IDs (full or partial) that prevent a page from being cached when set in the visitor's browser. |
| `cache_reject_ua` | array of strings | `[]` | User agent strings that should never receive cached pages (supports `(.*)` wildcards). |
| `cache_purge_pages` | array of strings | `[]` | URLs that are always purged from cache whenever any post or page is updated. |
| `cache_query_strings` | array of strings | `[]` | GET query string parameters for which separate cache files should be created (forces caching per query string). |

---

### Section 6: Database Optimization

These are **cleanup action toggles** — when enabled, the corresponding items are included in manual or scheduled cleanups. They do **not** run automatically unless `schedule_automatic_cleanup` is also enabled.

| Key | Type | Default | Description |
|---|---|---|---|
| `database_revisions` | `0`/`1` | `0` | Include post revisions in cleanup. Permanently deletes them. |
| `database_auto_drafts` | `0`/`1` | `0` | Include auto-draft posts in cleanup. Permanently deletes them. |
| `database_trashed_posts` | `0`/`1` | `0` | Include trashed posts in cleanup. Permanently deletes them. |
| `database_spam_comments` | `0`/`1` | `0` | Include spam comments in cleanup. Permanently deletes them. |
| `database_trashed_comments` | `0`/`1` | `0` | Include trashed comments in cleanup. Permanently deletes them. |
| `database_all_transients` | `0`/`1` | `0` | Include all transients in cleanup. Safe to remove — they regenerate automatically. |
| `database_optimize_tables` | `0`/`1` | `0` | Run `OPTIMIZE TABLE` on database tables to reduce overhead. |
| `schedule_automatic_cleanup` | `0`/`1` | `0` | Enable scheduled automatic database cleanup using the frequency below. |
| `automatic_cleanup_frequency` | `daily` / `weekly` / `monthly` | `daily` | How often the automatic database cleanup runs (only active when `schedule_automatic_cleanup = 1`). |

---

### Section 7: CDN

| Key | Type | Default | Description |
|---|---|---|---|
| `cdn` | `0`/`1` | `0` | Enable CDN — rewrites URLs of static files (CSS, JS, images) to use the configured CNAME(s). Not needed for Cloudflare or Sucuri (use their add-ons instead). |
| `cdn_cnames` | array of strings | `[]` | CDN CNAME hostname(s) (e.g. `cdn.example.com`). Multiple CNAMEs are supported. |
| `cdn_zone` | array of strings | `[]` | Zone assignment per CNAME — maps each CNAME index to a file type zone. Values: `all`, `images`, `css_and_js`, `css`, `js`. |
| `cdn_reject_files` | array of strings | `[]` | URLs of files that should NOT be served via CDN (supports wildcards). |

---

### Section 8: Heartbeat

| Key | Type | Default | Description |
|---|---|---|---|
| `control_heartbeat` | `0`/`1` | `0` | Master toggle — enable Heartbeat API control. Must be `1` for the behavior settings below to take effect. |
| `heartbeat_admin_behavior` | `''` / `reduce_periodicity` / `disable` | `reduce_periodicity` | Heartbeat behavior in the WordPress backend. `''` = do not limit, `reduce_periodicity` = reduce from 1/min to 1/2min, `disable` = turn off entirely. |
| `heartbeat_editor_behavior` | `''` / `reduce_periodicity` / `disable` | `reduce_periodicity` | Heartbeat behavior in the post/page editor. |
| `heartbeat_site_behavior` | `''` / `reduce_periodicity` / `disable` | `reduce_periodicity` | Heartbeat behavior on the frontend (visitor-facing pages). |

---

### Section 9: Add-ons

#### One-Click Add-ons (no extra config needed)

| Key | Type | Default | Description |
|---|---|---|---|
| `cache_logged_user` | `0`/`1` | `0` | User Cache — creates a dedicated set of cache files per logged-in WordPress user. Needed for user-specific or restricted content. |
| `varnish_auto_purge` | `0`/`1` | `0` | Varnish — purges Varnish cache each time WP Rocket clears its cache. Enable if Varnish runs on your server. |
| `cache_webp` | `0`/`1` | `0` | WebP Compatibility — serves WebP images to compatible browsers (WP Rocket does not generate WebP; use Imagify or similar). |

#### Cloudflare Add-on

| Key | Type | Default | Description |
|---|---|---|---|
| `do_cloudflare` | `0`/`1` | `0` | Enable Cloudflare integration add-on. |
| `cloudflare_email` | string | `''` | Cloudflare account email address. |
| `cloudflare_api_key` | string | `''` | Cloudflare Global API key (hidden field — stored separately from the masked display field). |
| `cloudflare_zone_id` | string | `''` | Cloudflare Zone ID for the site (hidden field). |
| `cloudflare_devmode` | `0`/`1` | `0` | Enable Cloudflare Development Mode — bypasses Cloudflare cache for 3 hours. |
| `cloudflare_auto_settings` | `0`/`1` | `0` | Apply optimal Cloudflare settings automatically for speed and performance. |
| `cloudflare_protocol_rewrite` | `0`/`1` | `0` | Rewrite static file URLs to use `//` (relative protocol) — only for Cloudflare Flexible SSL. |

#### Sucuri Add-on

| Key | Type | Default | Description |
|---|---|---|---|
| `sucury_waf_cache_sync` | `0`/`1` | `0` | Sucuri WAF cache sync — clears Sucuri cache when WP Rocket cache is cleared. Note: key has a typo (`sucury` not `sucuri`) — this is intentional in the codebase. |
| `sucury_waf_api_key` | string | `''` | Sucuri Firewall API key in format `{32chars}/{32chars}`. |

---

### Section 10: Hidden / Internal Fields

These fields are not shown directly in the UI but are stored in the same option and affect behavior:

| Key | Type | Description |
|---|---|---|
| `cache_ssl` | `0`/`1` | Enable caching for SSL (HTTPS) pages. Auto-set based on site URL scheme. |
| `cache_mobile` | `0`/`1` | Enable caching for mobile devices. Can be enabled via a prompt in the UI. |
| `do_caching_mobile_files` | `0`/`1` | Create separate cache files for mobile (vs. serving desktop cache to mobile). Enabled together with `cache_mobile`. |
| `dns_prefetch` | array of strings | List of external domains to prefetch DNS for (e.g. `//fonts.googleapis.com`). Configured via the Tools tab. |
| `consumer_key` | string | WP Rocket license key (API key). |
| `consumer_email` | string | Email associated with the WP Rocket license. |
| `secret_key` | string | WP Rocket secret key for license validation. |
| `secret_cache_key` | string | Internal key used for cache file naming. |
| `minify_css_key` | string | Internal cache-busting key for minified CSS. |
| `minify_js_key` | string | Internal cache-busting key for minified JS. |
| `version` | string | Current plugin version stored in options. |
| `previous_version` | string | Previous plugin version (used for upgrade routines). |

---

### Section 11: Rocket Insights (Performance Monitoring)

| Key | Type | Default | Description |
|---|---|---|---|
| `performance_monitoring` | `0`/`1` | `0` | Enable automatic performance testing for pages (requires eligible license plan). |
| `performance_monitoring_schedule_frequency` | integer (seconds) | `WEEK_IN_SECONDS` | How often automatic performance tests run. Values: `DAY_IN_SECONDS` (daily), `WEEK_IN_SECONDS` (weekly), `MONTH_IN_SECONDS` (monthly). |

---

### Quick Summary for AI Interpretation

When analyzing a site's WP Rocket configuration, look for:

- **Is caching active?** → Plugin being active = caching is on. Check `cache_ssl`, `cache_mobile`, `do_caching_mobile_files` for scope.
- **How long does cache last?** → `purge_cron_interval` + `purge_cron_unit` (default: 10 hours). `0` = never auto-purge.
- **Is CSS optimized?** → `minify_css`, `optimize_css_delivery` + `optimize_css_delivery_method` (`remove_unused_css` or `async_css`).
- **Is JS optimized?** → `minify_js`, `minify_concatenate_js`, `defer_all_js`, `delay_js`.
- **Is delay JS in safe mode?** → `delay_js_execution_safe_mode = 1` (reduces performance gains).
- **Are images lazy loaded?** → `lazyload`, `lazyload_iframes`, `lazyload_youtube`, `lazyload_css_bg_img`.
- **Is cache preloading active?** → `manual_preload = 1` (default ON).
- **Are there pages excluded from cache?** → `cache_reject_uri`, `cache_reject_cookies`, `cache_reject_ua`.
- **Is CDN configured?** → `cdn = 1` + `cdn_cnames` array.
- **Is Cloudflare integrated?** → `do_cloudflare = 1` + credentials fields.
- **Is Varnish used?** → `varnish_auto_purge = 1`.
- **Is user-specific caching enabled?** → `cache_logged_user = 1`.
- **Is Heartbeat controlled?** → `control_heartbeat = 1` + behavior fields.
- **Is database cleanup scheduled?** → `schedule_automatic_cleanup = 1` + `automatic_cleanup_frequency`.
- **Are Google Fonts self-hosted?** → `host_fonts_locally = 1`.
- **Are fonts preloaded?** → `auto_preload_fonts = 1`.
- **Is DNS prefetching configured?** → `dns_prefetch` array (e.g. `["//fonts.googleapis.com"]`).
