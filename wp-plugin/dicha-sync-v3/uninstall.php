<?php
/**
 * Uninstall script for Dicha Sync V3.
 * Removes all plugin options and scheduled events.
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
    exit;
}

// Clean up options
delete_option( 'asa_enabled' );
delete_option( 'asa_api_endpoint' );
delete_option( 'asa_api_token' );
delete_option( 'asa_project_id' );
delete_option( 'asa_sync_log' );
delete_option( 'asa_last_successful_sync' );

// Clean up cron
wp_clear_scheduled_hook( 'asa_daily_sync_event' );
