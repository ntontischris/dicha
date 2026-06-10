<?php
/**
 * ASA_Admin_Settings
 *
 * WordPress admin page for configuring the Agency Sync Agent.
 * Includes: settings form, manual sync, connection test, logs, data preview.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class ASA_Admin_Settings {

    private $collector;
    private $sync_manager;

    public function __construct( ASA_Data_Collector $collector, ASA_Sync_Manager $sync_manager ) {
        $this->collector    = $collector;
        $this->sync_manager = $sync_manager;

        add_action( 'admin_menu', array( $this, 'add_menu' ) );
        add_action( 'admin_init', array( $this, 'register_settings' ) );
        add_action( 'admin_post_asa_manual_sync', array( $this, 'handle_manual_sync' ) );
        add_action( 'admin_post_asa_test_connection', array( $this, 'handle_test_connection' ) );
        add_action( 'admin_post_asa_clear_logs', array( $this, 'handle_clear_logs' ) );
        add_action( 'admin_post_asa_preview_data', array( $this, 'handle_preview_data' ) );
        add_action( 'admin_post_asa_upload_manual', array( $this, 'handle_upload_manual' ) );
        add_action( 'admin_post_asa_save_prefixes', array( $this, 'handle_save_prefixes' ) );
        add_action( 'wp_ajax_asa_find_options', array( $this, 'handle_find_options' ) );
        add_action( 'admin_post_asa_delete_plugin', array( $this, 'handle_delete_plugin' ) );

        // Settings link on plugins page
        add_filter( 'plugin_action_links_' . ASA_PLUGIN_BASENAME, array( $this, 'add_settings_link' ) );
    }

    public function add_settings_link( $links ) {
        $settings_link = '<a href="' . admin_url( 'options-general.php?page=agency-sync-agent' ) . '">Settings</a>';
        array_unshift( $links, $settings_link );
        return $links;
    }

    public function add_menu() {
        add_options_page(
            'Agency Sync Agent',
            'Agency Sync',
            'manage_options',
            'agency-sync-agent',
            array( $this, 'render_page' )
        );
    }

    public function register_settings() {
        register_setting( 'asa_settings', 'asa_api_endpoint', array( 'sanitize_callback' => 'esc_url_raw' ) );
        register_setting( 'asa_settings', 'asa_api_token', array( 'sanitize_callback' => 'sanitize_text_field' ) );
        register_setting( 'asa_settings', 'asa_project_id', array( 'sanitize_callback' => 'sanitize_text_field' ) );
    }

    public function render_page() {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }

        $endpoint   = get_option( 'asa_api_endpoint', '' );
        $token      = get_option( 'asa_api_token', '' );
        $project_id = get_option( 'asa_project_id', '' );
        $logs       = get_option( ASA_LOG_OPTION, array() );
        $last_sync  = get_option( 'asa_last_successful_sync', 'Never' );

        // Check for action messages
        $message = '';
        if ( isset( $_GET['asa_message'] ) ) {
            $msg_type = sanitize_text_field( $_GET['asa_message'] );
            $messages = array(
                'sync_done'       => array( 'success', 'Manual sync completed. Check logs below.' ),
                'test_ok'         => array( 'success', 'Connection successful! Server responded: ' . absint( isset( $_GET['asa_code'] ) ? $_GET['asa_code'] : 0 ) ),
                'test_fail'       => array( 'error', 'Connection failed: ' . sanitize_text_field( urldecode( isset( $_GET['asa_detail'] ) ? $_GET['asa_detail'] : 'Unknown error' ) ) ),
                'logs_cleared'    => array( 'success', 'Logs cleared.' ),
                'manual_ok'       => array( 'success', 'Manual uploaded + sync ran — οι ρυθμίσεις του plugin μπήκαν στη βάση γνώσης.' ),
                'manual_fail'     => array( 'error', 'Manual upload failed: ' . sanitize_text_field( urldecode( isset( $_GET['asa_detail'] ) ? $_GET['asa_detail'] : 'Unknown error' ) ) ),
                'prefixes_saved'  => array( 'success', 'Plugin collection list saved.' ),
                'plugin_deleted'  => array( 'success', 'Plugin removed — its manual was deleted and it will no longer be collected.' ),
            );
            if ( isset( $messages[ $msg_type ] ) ) {
                $message = $messages[ $msg_type ];
            }
        }

        ?>
        <div class="wrap">
            <h1>
                <span class="dashicons dashicons-update" style="font-size:28px;margin-right:8px;"></span>
                Agency Sync Agent
                <span style="font-size:12px;color:#999;margin-left:10px;">v<?php echo esc_html( ASA_VERSION ); ?></span>
            </h1>

            <?php if ( $message ) : ?>
                <div class="notice notice-<?php echo esc_attr( $message[0] ); ?> is-dismissible">
                    <p><?php echo esc_html( $message[1] ); ?></p>
                </div>
            <?php endif; ?>

            <!-- STATUS BAR -->
            <?php $configured = $endpoint && $token && $project_id; ?>
            <div style="background:#fff;border:1px solid #ccd0d4;border-left:4px solid <?php echo $configured ? '#00a32a' : '#d63638'; ?>;padding:12px 20px;margin:20px 0;display:flex;align-items:center;gap:20px;">
                <div>
                    <strong>Status:</strong>
                    <?php if ( $configured ) : ?>
                        <span style="color:#00a32a;">&#9679; Configured (sync manually via "Run Sync Now")</span>
                    <?php else : ?>
                        <span style="color:#d63638;">&#9679; Not configured</span>
                    <?php endif; ?>
                </div>
                <div><strong>Last Sync:</strong> <?php echo esc_html( $last_sync ); ?></div>
                <div><strong>Project:</strong> <?php echo $project_id ? esc_html( $project_id ) : '<em>Not set</em>'; ?></div>
            </div>

            <!-- SETTINGS FORM -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
                <div style="background:#fff;border:1px solid #ccd0d4;padding:20px;">
                    <h2 style="margin-top:0;">Configuration</h2>
                    <form method="post" action="options.php">
                        <?php settings_fields( 'asa_settings' ); ?>
                        <table class="form-table">
                            <tr>
                                <th scope="row">API Endpoint</th>
                                <td>
                                    <input type="url" name="asa_api_endpoint" value="<?php echo esc_attr( $endpoint ); ?>" class="regular-text" placeholder="https://your-server.com/api/ingest">
                                    <p class="description">The URL of your central AI server's ingestion endpoint.</p>
                                </td>
                            </tr>
                            <tr>
                                <th scope="row">API Token</th>
                                <td>
                                    <input type="password" name="asa_api_token" value="<?php echo esc_attr( $token ); ?>" class="regular-text" autocomplete="new-password">
                                    <p class="description">Authentication token for the central server.</p>
                                </td>
                            </tr>
                            <tr>
                                <th scope="row">Project ID</th>
                                <td>
                                    <input type="text" name="asa_project_id" value="<?php echo esc_attr( $project_id ); ?>" class="regular-text" placeholder="e.g., client-acme-shop">
                                    <p class="description">Unique identifier for this project. Used for data isolation.</p>
                                </td>
                            </tr>
                        </table>
                        <?php submit_button( 'Save Settings' ); ?>
                    </form>
                </div>

                <!-- ACTIONS -->
                <div style="background:#fff;border:1px solid #ccd0d4;padding:20px;">
                    <h2 style="margin-top:0;">Actions</h2>

                    <!-- Manual Sync -->
                    <div style="margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid #eee;">
                        <h3>Manual Sync</h3>
                        <p>Run a full data collection and send now. This is the only way data is sent — there is no automatic/scheduled sync.</p>
                        <form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
                            <input type="hidden" name="action" value="asa_manual_sync">
                            <?php wp_nonce_field( 'asa_manual_sync_nonce' ); ?>
                            <button type="submit" class="button button-primary" onclick="this.textContent='Syncing...';this.disabled=true;this.form.submit();">
                                Run Sync Now
                            </button>
                        </form>
                    </div>

                    <!-- Test Connection -->
                    <div style="margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid #eee;">
                        <h3>Test Connection</h3>
                        <p>Send a lightweight health check to verify the server is reachable.</p>
                        <form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
                            <input type="hidden" name="action" value="asa_test_connection">
                            <?php wp_nonce_field( 'asa_test_connection_nonce' ); ?>
                            <button type="submit" class="button">Test Connection</button>
                        </form>
                    </div>

                    <!-- Preview Data -->
                    <div style="margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid #eee;">
                        <h3>Preview Data</h3>
                        <p>See what data would be collected and sent (opens in new tab as JSON).</p>
                        <form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" target="_blank">
                            <input type="hidden" name="action" value="asa_preview_data">
                            <?php wp_nonce_field( 'asa_preview_data_nonce' ); ?>
                            <button type="submit" class="button">Preview JSON</button>
                        </form>
                    </div>

                    <!-- Data Summary -->
                    <div>
                        <h3>Quick Data Summary</h3>
                        <?php
                        $wc_active = class_exists( 'WooCommerce' ) ? 'Yes' : 'No';
                        $plugin_count = count( get_option( 'active_plugins', array() ) );
                        $theme = wp_get_theme();
                        $is_child = is_child_theme() ? 'Yes' : 'No';

                        global $wpdb;
                        $snippets_table = $wpdb->prefix . 'snippets';
                        $has_snippets = $wpdb->get_var( $wpdb->prepare( "SHOW TABLES LIKE %s", $snippets_table ) ) === $snippets_table;
                        $snippet_count = $has_snippets ? (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$snippets_table}" ) : 0;
                        $has_wpcode = post_type_exists( 'wpcode' );
                        ?>
                        <table class="widefat striped" style="max-width:100%;">
                            <tr><td>WooCommerce Active</td><td><strong><?php echo $wc_active; ?></strong></td></tr>
                            <tr><td>Active Plugins</td><td><strong><?php echo $plugin_count; ?></strong></td></tr>
                            <tr><td>Theme</td><td><strong><?php echo esc_html( $theme->get('Name') ); ?></strong></td></tr>
                            <tr><td>Is Child Theme</td><td><strong><?php echo $is_child; ?></strong></td></tr>
                            <tr><td>Code Snippets Plugin</td><td><strong><?php echo $has_snippets ? "Yes ({$snippet_count} snippets)" : 'Not found'; ?></strong></td></tr>
                            <tr><td>WPCode Plugin</td><td><strong><?php echo $has_wpcode ? 'Yes' : 'Not found'; ?></strong></td></tr>
                        </table>
                    </div>
                </div>
            </div>

            <!-- PLUGIN KNOWLEDGE (self-service) -->
            <?php
            $active_plugins  = $this->get_active_plugins();
            $custom_prefixes = get_option( 'asa_plugin_prefixes', array() );
            $prefix_lines    = array();
            if ( is_array( $custom_prefixes ) ) {
                foreach ( $custom_prefixes as $p_slug => $p_prefixes ) {
                    $prefix_lines[] = $p_slug . ' = ' . implode( ', ', (array) $p_prefixes );
                }
            }
            $prefix_text = implode( "\n", $prefix_lines );
            ?>
            <h2 style="margin-top:30px;">Plugin Knowledge
                <span style="font-size:12px;color:#999;font-weight:normal;">— teach the AI about your plugins, no code needed</span>
            </h2>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">

                <!-- Upload a manual -->
                <div style="background:#fff;border:1px solid #ccd0d4;padding:20px;">
                    <h3 style="margin-top:0;">&#128216; Plugin Manual</h3>
                    <p>Pick a plugin and paste its manual / how its settings work. It is stored in the AI's knowledge base so the agent interprets that plugin's settings precisely. <strong>Add a line <code>Collect: option_name</code></strong> and its settings get collected automatically — no extra step. Tip: include a <code>## Quick Summary for AI Interpretation</code> section for best results.</p>
                    <form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
                        <input type="hidden" name="action" value="asa_upload_manual">
                        <?php wp_nonce_field( 'asa_upload_manual_nonce' ); ?>
                        <p>
                            <label for="asa_plugin_slug"><strong>Plugin</strong></label><br>
                            <select name="asa_plugin_slug" id="asa_plugin_slug" class="regular-text" required>
                                <option value="">&mdash; select a plugin &mdash;</option>
                                <?php foreach ( $active_plugins as $ap_slug => $ap_name ) : ?>
                                    <option value="<?php echo esc_attr( $ap_slug ); ?>"><?php echo esc_html( $ap_name . ' (' . $ap_slug . ')' ); ?></option>
                                <?php endforeach; ?>
                            </select>
                        </p>
                        <p>
                            <label for="asa_manual_text"><strong>Manual (Markdown or plain text)</strong></label><br>
                            <textarea name="asa_manual_text" id="asa_manual_text" rows="10" style="width:100%;font-family:monospace;" required placeholder="## Quick Summary for AI Interpretation&#10;This plugin does ...&#10;&#10;Collect: option_name&#10;&#10;## Settings&#10;- option_x: what it controls ..."></textarea>
                        </p>
                        <?php submit_button( 'Upload Manual', 'primary', 'asa_submit_manual', false ); ?>
                    </form>
                </div>

                <!-- Choose plugins to collect -->
                <div style="background:#fff;border:1px solid #ccd0d4;padding:20px;">
                    <h3 style="margin-top:0;">&#9881; Settings to Collect
                        <span style="font-size:12px;color:#999;font-weight:normal;">(advanced)</span>
                    </h3>
                    <p>Which plugins' settings get synced. 5 plugins are built in (always on). Below are the ones you added — upload a manual with a <code>Collect:</code> line and it registers here automatically.</p>

                    <!-- Managed plugins: ALL rows show Edit + Delete (built-in deletes via disable list) -->
                    <?php
                    $builtin       = method_exists( $this->collector, 'get_default_prefixes' ) ? $this->collector->get_default_prefixes() : array();
                    $disabled_list = get_option( 'asa_disabled_plugins', array() );
                    if ( ! is_array( $disabled_list ) ) {
                        $disabled_list = array();
                    }
                    $active_builtin = array();
                    foreach ( $builtin as $b_slug => $b_pref ) {
                        if ( ! in_array( $b_slug, $disabled_list, true ) ) {
                            $active_builtin[ $b_slug ] = $b_pref;
                        }
                    }
                    $custom_only = is_array( $custom_prefixes ) ? array_diff_key( $custom_prefixes, $builtin ) : array();
                    $all_rows    = $active_builtin + $custom_only;
                    ?>
                    <table class="widefat striped" style="margin:8px 0;">
                        <thead><tr><th>Plugin</th><th>Συλλέγει</th><th style="width:170px;">Ενέργειες</th></tr></thead>
                        <tbody>
                            <?php foreach ( $all_rows as $row_slug => $row_pref ) :
                                $is_builtin = isset( $builtin[ $row_slug ] );
                            ?>
                                <tr>
                                    <td>
                                        <code><?php echo esc_html( $row_slug ); ?></code>
                                        <?php if ( $is_builtin ) : ?> <span style="color:#999;font-size:11px;">(built-in)</span><?php endif; ?>
                                    </td>
                                    <td><?php echo esc_html( implode( ', ', (array) $row_pref ) ); ?></td>
                                    <td>
                                        <button type="button" class="button asa-edit-plugin-btn" data-slug="<?php echo esc_attr( $row_slug ); ?>" style="margin-right:4px;">Edit</button>
                                        <form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" onsubmit="return confirm('Διαγραφή «<?php echo esc_js( $row_slug ); ?>»; (manual + σταματά η συλλογή)');" style="display:inline;margin:0;">
                                            <input type="hidden" name="action" value="asa_delete_plugin">
                                            <input type="hidden" name="asa_plugin_slug" value="<?php echo esc_attr( $row_slug ); ?>">
                                            <?php wp_nonce_field( 'asa_delete_plugin_nonce' ); ?>
                                            <button type="submit" class="button button-link-delete">Delete</button>
                                        </form>
                                    </td>
                                </tr>
                            <?php endforeach; ?>
                            <?php if ( empty( $all_rows ) ) : ?>
                                <tr><td colspan="3"><em>Καμία ενεργή ρύθμιση. Ανέβασε ένα manual για να ξεκινήσει η συλλογή.</em></td></tr>
                            <?php endif; ?>
                        </tbody>
                    </table>
                    <p style="color:#999;font-size:12px;">
                        <strong>Edit</strong>: ανοίγει το παραπάνω πεδίο «Plugin Manual» για επανα-ανέβασμα (καθαρή αντικατάσταση).
                        <strong>Delete</strong>: σταματά η συλλογή + σβήνεται το manual.
                        <?php if ( ! empty( $disabled_list ) ) : ?>
                            <br><em>Disabled built-in (κρυμμένα): <?php echo esc_html( implode( ', ', $disabled_list ) ); ?>. Ανέβασε ξανά manual για το slug για επαναφορά.</em>
                        <?php endif; ?>
                    </p>
                    <script>
                    document.addEventListener('DOMContentLoaded', function () {
                        var sel = document.getElementById('asa_plugin_slug');
                        document.querySelectorAll('.asa-edit-plugin-btn').forEach(function (btn) {
                            btn.addEventListener('click', function () {
                                var slug = this.getAttribute('data-slug');
                                if (!sel) { return; }
                                if (!sel.querySelector('option[value="' + slug + '"]')) {
                                    var opt = document.createElement('option');
                                    opt.value = slug;
                                    opt.textContent = slug + ' (managed)';
                                    sel.appendChild(opt);
                                }
                                sel.value = slug;
                                sel.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                sel.focus();
                            });
                        });
                    });
                    </script>

                    <details style="margin:10px 0;">
                        <summary style="cursor:pointer;color:#2271b1;">Χειροκίνητη επεξεργασία (advanced)</summary>

                    <!-- Option-name finder: reads this site's own wp_options (no Supabase, no SQL) -->
                    <div style="margin:10px 0;padding:10px;background:#f6f7f7;border:1px dashed #ccd0d4;border-radius:4px;">
                        <label style="font-weight:600;display:block;margin-bottom:6px;">&#128269; Βρες το option name του plugin</label>
                        <input type="text" id="asa-optfinder-input" class="regular-text" placeholder="π.χ. klarna, wp_rocket, woocommerce_cod">
                        <button type="button" class="button" id="asa-optfinder-btn">Αναζήτηση</button>
                        <p class="description" style="margin:6px 0 0;">Ψάχνει στις ρυθμίσεις αυτού του site. Κάνε κλικ σε αποτέλεσμα για να μπει στο πλαίσιο πιο κάτω.</p>
                        <div id="asa-optfinder-results" style="margin-top:8px;font-family:monospace;font-size:12px;max-height:160px;overflow-y:auto;"></div>
                    </div>

                    <form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
                        <input type="hidden" name="action" value="asa_save_prefixes">
                        <?php wp_nonce_field( 'asa_save_prefixes_nonce' ); ?>
                        <p>
                            <textarea name="asa_prefixes_raw" rows="8" style="width:100%;font-family:monospace;" placeholder="my-plugin-slug = my_option_prefix_&#10;another-plugin = opt_a_, opt_b_"><?php echo esc_textarea( $prefix_text ); ?></textarea>
                        </p>
                        <details style="margin-bottom:10px;">
                            <summary style="cursor:pointer;color:#2271b1;">Active plugin slugs (for reference)</summary>
                            <div style="max-height:120px;overflow-y:auto;font-family:monospace;font-size:12px;background:#f6f7f7;padding:8px;margin-top:6px;">
                                <?php foreach ( $active_plugins as $ap_slug => $ap_name ) : ?>
                                    <div><?php echo esc_html( $ap_slug ); ?></div>
                                <?php endforeach; ?>
                            </div>
                        </details>
                        <?php submit_button( 'Save Collection List', 'secondary', 'asa_submit_prefixes', false ); ?>
                    </form>
                    <script>
                    (function () {
                        var btn = document.getElementById('asa-optfinder-btn');
                        if (!btn) return;
                        var input = document.getElementById('asa-optfinder-input');
                        var results = document.getElementById('asa-optfinder-results');
                        var textarea = document.querySelector('textarea[name="asa_prefixes_raw"]');
                        var ajaxUrl = <?php echo wp_json_encode( admin_url( 'admin-ajax.php' ) ); ?>;
                        var nonce = <?php echo wp_json_encode( wp_create_nonce( 'asa_find_options' ) ); ?>;
                        function esc(s){ var d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
                        function search() {
                            var kw = (input.value || '').trim();
                            if (!kw) return;
                            results.innerHTML = 'Αναζήτηση...';
                            var url = ajaxUrl + '?action=asa_find_options&_ajax_nonce=' + encodeURIComponent(nonce) + '&keyword=' + encodeURIComponent(kw);
                            fetch(url, { credentials: 'same-origin' })
                                .then(function (r) { return r.text(); })
                                .then(function (txt) {
                                    var res;
                                    try { res = JSON.parse(txt); }
                                    catch (e) { results.innerHTML = '<span style="color:#d63638;">Μη έγκυρη απάντηση: ' + esc(txt.slice(0, 200)) + '</span>'; return; }
                                    // WP admin-ajax returns 0 (no handler) or -1 (bad nonce) on failure.
                                    if (res === 0 || res === -1) {
                                        results.innerHTML = '<span style="color:#d63638;">Σφάλμα σύνδεσης (κωδ. ' + res + '). Κάνε refresh τη σελίδα· αν συνεχίζει, πες το μου.</span>';
                                        return;
                                    }
                                    if (!res || !res.success) {
                                        results.innerHTML = '<span style="color:#d63638;">Σφάλμα: ' + esc(JSON.stringify(res && res.data ? res.data : res)) + '</span>';
                                        return;
                                    }
                                    if (!res.data || !res.data.length) {
                                        results.innerHTML = '<em>Καμία ρύθμιση με αυτή τη λέξη. Δοκίμασε π.χ. <code>woocommerce</code>, <code>cod</code>, <code>rocket</code>.</em>';
                                        return;
                                    }
                                    results.innerHTML = '';
                                    res.data.forEach(function (name) {
                                        var a = document.createElement('a');
                                        a.href = '#';
                                        a.innerHTML = esc(name);
                                        a.style.cssText = 'display:block;padding:3px 6px;color:#2271b1;text-decoration:none;border-bottom:1px solid #eee;';
                                        a.addEventListener('click', function (e) {
                                            e.preventDefault();
                                            if (textarea) {
                                                var cur = textarea.value.replace(/\s*$/, '');
                                                textarea.value = (cur ? cur + '\n' : '') + name;
                                                textarea.focus();
                                            }
                                        });
                                        results.appendChild(a);
                                    });
                                })
                                .catch(function (err) {
                                    results.innerHTML = '<span style="color:#d63638;">Σφάλμα δικτύου: ' + esc(err.message) + '</span>';
                                });
                        }
                        btn.addEventListener('click', search);
                        input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); search(); } });
                    })();
                    </script>
                    </details>
                </div>
            </div>

            <!-- LOGS -->
            <div style="background:#fff;border:1px solid #ccd0d4;padding:20px;margin-top:20px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <h2 style="margin:0;">Sync Log</h2>
                    <form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" style="margin:0;">
                        <input type="hidden" name="action" value="asa_clear_logs">
                        <?php wp_nonce_field( 'asa_clear_logs_nonce' ); ?>
                        <button type="submit" class="button button-link-delete">Clear Logs</button>
                    </form>
                </div>

                <?php if ( empty( $logs ) ) : ?>
                    <p style="color:#999;">No log entries yet.</p>
                <?php else : ?>
                    <div style="max-height:300px;overflow-y:auto;margin-top:10px;font-family:monospace;font-size:12px;background:#f0f0f1;padding:10px;border-radius:4px;">
                        <?php foreach ( array_reverse( $logs ) as $log ) : ?>
                            <?php
                            $color = '#333';
                            if ( strpos( $log['message'], 'SUCCESS' ) !== false ) $color = '#00a32a';
                            if ( strpos( $log['message'], 'FAILED' ) !== false || strpos( $log['message'], 'ERROR' ) !== false ) $color = '#d63638';
                            if ( strpos( $log['message'], 'skipped' ) !== false ) $color = '#dba617';
                            ?>
                            <div style="margin-bottom:4px;color:<?php echo $color; ?>;">
                                <span style="color:#666;">[<?php echo esc_html( $log['time'] ); ?>]</span>
                                <?php echo esc_html( $log['message'] ); ?>
                            </div>
                        <?php endforeach; ?>
                    </div>
                <?php endif; ?>
            </div>
        </div>
        <?php
    }

    // ─── Action Handlers ─────────────────────────────────────────────────────

    public function handle_manual_sync() {
        if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 'asa_manual_sync_nonce' ) ) {
            wp_die( 'Unauthorized' );
        }

        asa_run_sync( $this->collector, $this->sync_manager );

        wp_redirect( admin_url( 'options-general.php?page=agency-sync-agent&asa_message=sync_done' ) );
        exit;
    }

    public function handle_test_connection() {
        if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 'asa_test_connection_nonce' ) ) {
            wp_die( 'Unauthorized' );
        }

        $endpoint = get_option( 'asa_api_endpoint', '' );
        $token    = get_option( 'asa_api_token', '' );

        $result = $this->sync_manager->test_connection( $endpoint, $token );

        if ( is_wp_error( $result ) ) {
            wp_redirect( admin_url( 'options-general.php?page=agency-sync-agent&asa_message=test_fail&asa_detail=' . urlencode( $result->get_error_message() ) ) );
        } else {
            $code = wp_remote_retrieve_response_code( $result );
            wp_redirect( admin_url( 'options-general.php?page=agency-sync-agent&asa_message=test_ok&asa_code=' . $code ) );
        }
        exit;
    }

    public function handle_clear_logs() {
        if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 'asa_clear_logs_nonce' ) ) {
            wp_die( 'Unauthorized' );
        }

        update_option( ASA_LOG_OPTION, array() );

        wp_redirect( admin_url( 'options-general.php?page=agency-sync-agent&asa_message=logs_cleared' ) );
        exit;
    }

    public function handle_preview_data() {
        if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 'asa_preview_data_nonce' ) ) {
            wp_die( 'Unauthorized' );
        }

        $data = $this->collector->collect_all();

        header( 'Content-Type: application/json; charset=utf-8' );
        echo wp_json_encode( array(
            'project_id' => get_option( 'asa_project_id', 'preview' ),
            'plugin_version' => ASA_VERSION,
            'site_url' => get_site_url(),
            'timestamp' => current_time( 'c' ),
            'data' => $data,
        ), JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE );
        exit;
    }

    /**
     * Upload a plugin manual to the AI knowledge base (category=plugin_docs, global).
     * The agent matches it to a plugin by title, so the title is the slug in spaced
     * form (dashes -> spaces) to mirror the agent's lookup.
     */
    public function handle_upload_manual() {
        if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 'asa_upload_manual_nonce' ) ) {
            wp_die( 'Unauthorized' );
        }

        $redirect = admin_url( 'options-general.php?page=agency-sync-agent' );
        $slug = isset( $_POST['asa_plugin_slug'] ) ? sanitize_text_field( wp_unslash( $_POST['asa_plugin_slug'] ) ) : '';
        $text = isset( $_POST['asa_manual_text'] ) ? sanitize_textarea_field( wp_unslash( $_POST['asa_manual_text'] ) ) : '';

        if ( $slug === '' || $text === '' ) {
            wp_redirect( $redirect . '&asa_message=manual_fail&asa_detail=' . urlencode( 'Plugin and manual text are both required.' ) );
            exit;
        }

        $endpoint = get_option( 'asa_api_endpoint', '' );
        $token    = get_option( 'asa_api_token', '' );
        if ( empty( $endpoint ) || empty( $token ) ) {
            wp_redirect( $redirect . '&asa_message=manual_fail&asa_detail=' . urlencode( 'Configure API Endpoint and Token first.' ) );
            exit;
        }

        $base     = rtrim( $endpoint, '/' );
        $docs_url = str_replace( '/webhook', '/docs', $base );
        $title    = ucwords( str_replace( '-', ' ', $slug ) );
        $is_local = in_array( wp_parse_url( $endpoint, PHP_URL_HOST ), array( 'localhost', '127.0.0.1' ), true );

        // The manual is the single source of truth: a "Collect: opt_a, opt_b" line
        // auto-registers which options to pull — no manual prefix typing.
        $collected = array();
        foreach ( preg_split( '/\r\n|\r|\n/', $text ) as $line ) {
            if ( preg_match( '/^\s*collect\s*:\s*(.+)$/i', $line, $m ) ) {
                foreach ( explode( ',', $m[1] ) as $opt ) {
                    $opt = sanitize_text_field( trim( str_replace( '`', '', $opt ) ) );
                    if ( $opt !== '' ) {
                        $collected[] = $opt;
                    }
                }
            }
        }
        if ( ! empty( $collected ) ) {
            $map = get_option( 'asa_plugin_prefixes', array() );
            if ( ! is_array( $map ) ) {
                $map = array();
            }
            $map[ $slug ] = array_values( array_unique( $collected ) );
            update_option( 'asa_plugin_prefixes', $map );
        }

        // Re-enable: uploading a manual for this slug clears any "disabled" flag,
        // so Delete + then a re-upload of its manual restores the plugin.
        $disabled = get_option( 'asa_disabled_plugins', array() );
        if ( is_array( $disabled ) && in_array( $slug, $disabled, true ) ) {
            $disabled = array_values( array_diff( $disabled, array( $slug ) ) );
            update_option( 'asa_disabled_plugins', $disabled );
        }

        // Clean-replace: delete any previous manual for this plugin first (no dupes).
        $del_url = str_replace( '/webhook', '/api/plugin-manual', $base ) . '?slug=' . urlencode( $slug );
        wp_remote_request( $del_url, array(
            'method'    => 'DELETE',
            'timeout'   => 60,
            'headers'   => array( 'Authorization' => 'Bearer ' . $token, 'X-Webhook-Secret' => $token ),
            'sslverify' => ! $is_local,
        ) );

        $payload = wp_json_encode( array(
            'project_id' => '_global',
            'type'       => 'company_doc',
            'category'   => 'plugin_docs',
            'title'      => $title,
            'content'    => $text,
        ) );

        $result = $this->sync_manager->send( $docs_url, $token, $payload );

        if ( is_wp_error( $result ) ) {
            wp_redirect( $redirect . '&asa_message=manual_fail&asa_detail=' . urlencode( $result->get_error_message() ) );
        } else {
            // Auto-sync so the plugin's actual settings are pulled from wp_options
            // into the knowledge base immediately — one click, not two.
            asa_run_sync( $this->collector, $this->sync_manager );
            wp_redirect( $redirect . '&asa_message=manual_ok' );
        }
        exit;
    }

    /**
     * Save the admin-managed plugin-collection map (slug => option prefixes) as a
     * WP option. ASA_Data_Collector::get_option_prefixes() merges it in, so new
     * plugins can be tracked without editing code.
     */
    public function handle_save_prefixes() {
        if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 'asa_save_prefixes_nonce' ) ) {
            wp_die( 'Unauthorized' );
        }

        $raw = isset( $_POST['asa_prefixes_raw'] ) ? wp_unslash( $_POST['asa_prefixes_raw'] ) : '';
        $map = array();
        foreach ( preg_split( '/\r\n|\r|\n/', $raw ) as $line ) {
            $line = trim( $line );
            if ( $line === '' || strpos( $line, '=' ) === false ) {
                continue;
            }
            list( $slug_part, $prefix_part ) = explode( '=', $line, 2 );
            $slug_part = sanitize_key( trim( $slug_part ) );
            $prefixes  = array_filter( array_map( 'trim', explode( ',', $prefix_part ) ) );
            $prefixes  = array_values( array_map( 'sanitize_text_field', $prefixes ) );
            if ( $slug_part !== '' && ! empty( $prefixes ) ) {
                $map[ $slug_part ] = $prefixes;
            }
        }

        update_option( 'asa_plugin_prefixes', $map );

        wp_redirect( admin_url( 'options-general.php?page=agency-sync-agent&asa_message=prefixes_saved' ) );
        exit;
    }

    /**
     * Remove a managed plugin: stop collecting it (drop from the WP option) AND
     * delete its manual from the AI knowledge base. One action, fully gone.
     */
    public function handle_delete_plugin() {
        if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 'asa_delete_plugin_nonce' ) ) {
            wp_die( 'Unauthorized' );
        }

        $redirect = admin_url( 'options-general.php?page=agency-sync-agent' );
        $slug = isset( $_POST['asa_plugin_slug'] ) ? sanitize_text_field( wp_unslash( $_POST['asa_plugin_slug'] ) ) : '';
        if ( $slug === '' ) {
            wp_redirect( $redirect );
            exit;
        }

        // 1) Stop collecting it — works for built-in too (disabled list) and custom.
        $builtin = method_exists( $this->collector, 'get_default_prefixes' )
            ? array_keys( $this->collector->get_default_prefixes() )
            : array();
        if ( in_array( $slug, $builtin, true ) ) {
            $disabled = get_option( 'asa_disabled_plugins', array() );
            if ( ! is_array( $disabled ) ) {
                $disabled = array();
            }
            if ( ! in_array( $slug, $disabled, true ) ) {
                $disabled[] = $slug;
                update_option( 'asa_disabled_plugins', $disabled );
            }
        } else {
            $map = get_option( 'asa_plugin_prefixes', array() );
            if ( is_array( $map ) && isset( $map[ $slug ] ) ) {
                unset( $map[ $slug ] );
                update_option( 'asa_plugin_prefixes', $map );
            }
        }

        // 2) Delete its manual from the knowledge base.
        $endpoint = get_option( 'asa_api_endpoint', '' );
        $token    = get_option( 'asa_api_token', '' );
        if ( ! empty( $endpoint ) && ! empty( $token ) ) {
            $del_url  = str_replace( '/webhook', '/api/plugin-manual', rtrim( $endpoint, '/' ) ) . '?slug=' . urlencode( $slug );
            $is_local = in_array( wp_parse_url( $endpoint, PHP_URL_HOST ), array( 'localhost', '127.0.0.1' ), true );
            wp_remote_request( $del_url, array(
                'method'    => 'DELETE',
                'timeout'   => 60,
                'headers'   => array( 'Authorization' => 'Bearer ' . $token, 'X-Webhook-Secret' => $token ),
                'sslverify' => ! $is_local,
            ) );
        }

        wp_redirect( $redirect . '&asa_message=plugin_deleted' );
        exit;
    }

    /**
     * AJAX: search THIS site's wp_options by keyword so the owner can find a
     * plugin's option name(s) without opening Supabase or running SQL.
     */
    public function handle_find_options() {
        check_ajax_referer( 'asa_find_options' );
        if ( ! current_user_can( 'manage_options' ) ) {
            wp_send_json_error( 'Unauthorized', 403 );
        }

        $keyword = isset( $_GET['keyword'] ) ? sanitize_text_field( wp_unslash( $_GET['keyword'] ) ) : '';
        if ( $keyword === '' ) {
            wp_send_json_success( array() );
        }

        global $wpdb;
        $like = '%' . $wpdb->esc_like( $keyword ) . '%';
        $names = $wpdb->get_col(
            $wpdb->prepare(
                "SELECT option_name FROM {$wpdb->options}
                 WHERE option_name LIKE %s
                   AND option_name NOT LIKE %s
                   AND option_name NOT LIKE %s
                 ORDER BY option_name LIMIT 50",
                $like,
                '%' . $wpdb->esc_like( '_transient_' ) . '%',
                '%' . $wpdb->esc_like( '_site_transient_' ) . '%'
            )
        );

        wp_send_json_success( $names );
    }

    /**
     * Active plugins as slug => display name, sorted by name.
     */
    private function get_active_plugins() {
        if ( ! function_exists( 'get_plugins' ) ) {
            require_once ABSPATH . 'wp-admin/includes/plugin.php';
        }
        $all    = get_plugins();
        $active = get_option( 'active_plugins', array() );
        $list   = array();
        foreach ( $active as $plugin_file ) {
            $slug = dirname( $plugin_file );
            if ( $slug === '.' ) {
                continue;
            }
            $list[ $slug ] = isset( $all[ $plugin_file ]['Name'] ) ? $all[ $plugin_file ]['Name'] : $slug;
        }
        asort( $list );
        return $list;
    }
}
