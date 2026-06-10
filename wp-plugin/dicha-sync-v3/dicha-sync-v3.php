<?php
/**
 * Plugin Name: Dicha Sync V3
 * Plugin URI: https://github.com/ntontischris/dicha
 * Description: WooCommerce AI Agent — syncs shop data to central server for intelligent support.
 * Version: 2.5.5
 * Author: Dicha
 * Author URI: https://github.com/ntontischris/dicha
 * License: GPL v2 or later
 * Text Domain: dicha-agent
 * Requires at least: 5.8
 * Requires PHP: 7.4
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

define( 'ASA_VERSION', '2.5.5' );
define( 'ASA_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'ASA_PLUGIN_URL', plugin_dir_url( __FILE__ ) );
define( 'ASA_PLUGIN_BASENAME', plugin_basename( __FILE__ ) );
define( 'ASA_CRON_HOOK', 'asa_daily_sync_event' );
define( 'ASA_LOG_OPTION', 'asa_sync_log' );
define( 'ASA_MAX_FILE_SIZE', 512 * 1024 );
define( 'ASA_MAX_TOTAL_PAYLOAD', 5 * 1024 * 1024 );

// Activation / Deactivation (must work without class loading)
register_activation_hook( __FILE__, 'asa_activate' );
register_deactivation_hook( __FILE__, 'asa_deactivate' );

function asa_activate() {
    // Sync is manual-only — no cron. Clear any schedule left by older versions.
    wp_clear_scheduled_hook( ASA_CRON_HOOK );
    add_option( 'asa_api_endpoint', '' );
    add_option( 'asa_api_token', '' );
    add_option( 'asa_project_id', '' );
    add_option( ASA_LOG_OPTION, array() );
    update_option( ASA_LOG_OPTION, array( array(
        'time'    => current_time( 'Y-m-d H:i:s' ),
        'message' => 'Plugin activated. Version ' . ASA_VERSION,
    ) ), false );
}

function asa_deactivate() {
    wp_clear_scheduled_hook( ASA_CRON_HOOK );
}

// Initialize plugin after all plugins loaded
add_action( 'plugins_loaded', 'asa_init_plugin' );

function asa_init_plugin() {
    // Only load on admin, cron, or CLI
    $is_cron = function_exists( 'wp_doing_cron' ) ? wp_doing_cron() : defined( 'DOING_CRON' );
    if ( ! is_admin() && ! $is_cron && ! defined( 'WP_CLI' ) ) {
        return;
    }

    // Load classes
    require_once ASA_PLUGIN_DIR . 'includes/class-data-sanitizer.php';
    require_once ASA_PLUGIN_DIR . 'includes/class-data-collector.php';
    require_once ASA_PLUGIN_DIR . 'includes/class-sync-manager.php';
    require_once ASA_PLUGIN_DIR . 'admin/class-admin-settings.php';

    $sanitizer    = new ASA_Data_Sanitizer();
    $collector    = new ASA_Data_Collector( $sanitizer );
    $sync_manager = new ASA_Sync_Manager();

    // Admin settings page
    if ( is_admin() ) {
        new ASA_Admin_Settings( $collector, $sync_manager );

        // WooCommerce > AI Agent submenu
        add_action( 'admin_menu', function() {
            add_submenu_page(
                'woocommerce',
                'AI Agent',
                'AI Agent',
                'manage_woocommerce',
                'dicha-agent',
                'asa_render_chat_page'
            );
        } );

        // Chat assets on all admin pages
        add_action( 'admin_enqueue_scripts', 'asa_enqueue_chat_assets' );

        // Floating bubble on all admin pages except dedicated chat page
        add_action( 'admin_footer', 'asa_render_chat_bubble' );
    }

    // Sync is manual-only — remove any daily cron left scheduled by older versions.
    if ( wp_next_scheduled( ASA_CRON_HOOK ) ) {
        wp_clear_scheduled_hook( ASA_CRON_HOOK );
    }

    // WP-CLI
    if ( defined( 'WP_CLI' ) && WP_CLI ) {
        WP_CLI::add_command( 'asa sync', function() use ( $collector, $sync_manager ) {
            asa_run_sync( $collector, $sync_manager );
        } );
    }
}

function asa_render_chat_page() {
    if ( ! current_user_can( 'manage_woocommerce' ) ) {
        return;
    }
    include ASA_PLUGIN_DIR . 'admin/views/chat-page.php';
}

function asa_enqueue_chat_assets() {
    $endpoint   = get_option( 'asa_api_endpoint', '' );
    $project_id = get_option( 'asa_project_id', '' );
    $token      = get_option( 'asa_api_token', '' );

    if ( empty( $endpoint ) || empty( $project_id ) ) {
        return;
    }

    $api_url = preg_replace( '/\/webhook$/', '', rtrim( $endpoint, '/' ) );

    wp_enqueue_style( 'asa-chat-css', ASA_PLUGIN_URL . 'assets/css/chat.css', array(), ASA_VERSION );
    wp_enqueue_script( 'asa-chat-js', ASA_PLUGIN_URL . 'assets/js/chat.js', array(), ASA_VERSION, true );
    wp_localize_script( 'asa-chat-js', 'asaConfig', array(
        'apiUrl'    => $api_url,
        'projectId' => $project_id,
        'token'     => $token,
    ) );
    wp_enqueue_style( 'dashicons' );
}

function asa_render_chat_bubble() {
    if ( ! current_user_can( 'manage_woocommerce' ) ) {
        return;
    }
    $screen = get_current_screen();
    if ( $screen && $screen->id === 'woocommerce_page_dicha-agent' ) {
        return;
    }
    $endpoint   = get_option( 'asa_api_endpoint', '' );
    $project_id = get_option( 'asa_project_id', '' );
    if ( empty( $endpoint ) || empty( $project_id ) ) {
        return;
    }
    include ASA_PLUGIN_DIR . 'admin/views/chat-bubble.php';
}

function asa_run_sync( $collector, $sync_manager ) {
    $endpoint   = get_option( 'asa_api_endpoint', '' );
    $token      = get_option( 'asa_api_token', '' );
    $project_id = get_option( 'asa_project_id', '' );

    if ( empty( $endpoint ) || empty( $token ) || empty( $project_id ) ) {
        asa_log( 'Sync skipped: missing configuration.' );
        return;
    }

    $start_time = microtime( true );

    try {
        asa_log( 'Starting data collection...' );
        $data = $collector->collect_all();

        $payload = array(
            'project_id'        => sanitize_text_field( $project_id ),
            'plugin_version'    => ASA_VERSION,
            'wordpress_version' => get_bloginfo( 'version' ),
            'php_version'       => phpversion(),
            'site_url'          => get_site_url(),
            'timestamp'         => current_time( 'c' ),
            'data'              => $data,
        );

        $json = wp_json_encode( $payload );
        if ( strlen( $json ) > ASA_MAX_TOTAL_PAYLOAD ) {
            asa_log( 'Warning: payload too large. Truncating theme files.' );
            $theme_files = isset( $payload['data']['theme_files'] ) ? $payload['data']['theme_files'] : array();
            $payload['data']['theme_files'] = array_slice( $theme_files, 0, 20 );
            $payload['data']['_truncated'] = true;
            $json = wp_json_encode( $payload );
        }

        asa_log( 'Sending payload (' . round( strlen( $json ) / 1024, 1 ) . 'KB)...' );
        $result = $sync_manager->send( $endpoint, $token, $json );

        $elapsed = round( microtime( true ) - $start_time, 2 );

        if ( is_wp_error( $result ) ) {
            asa_log( 'Sync FAILED (' . $elapsed . 's): ' . $result->get_error_message() );
        } else {
            asa_log( 'Sync SUCCESS (' . $elapsed . 's). Server responded: ' . wp_remote_retrieve_response_code( $result ) );
            update_option( 'asa_last_successful_sync', current_time( 'c' ) );
        }
    } catch ( \Throwable $e ) {
        $elapsed = round( microtime( true ) - $start_time, 2 );
        asa_log( 'Sync ERROR (' . $elapsed . 's): ' . $e->getMessage() );
    }
}

function asa_log( $message ) {
    $logs = get_option( ASA_LOG_OPTION, array() );
    $logs[] = array(
        'time'    => current_time( 'Y-m-d H:i:s' ),
        'message' => $message,
    );
    $logs = array_slice( $logs, -50 );
    update_option( ASA_LOG_OPTION, $logs, false );
    error_log( '[Dicha Sync V3] ' . $message );
}
