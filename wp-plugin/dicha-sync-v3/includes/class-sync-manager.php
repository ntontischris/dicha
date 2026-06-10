<?php
/**
 * ASA_Sync_Manager
 *
 * Handles the HTTP POST of collected data to the central AI server.
 * Includes retry logic, timeout handling, and response validation.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class ASA_Sync_Manager {

    const TIMEOUT = 300; // seconds (settings-docs pipeline needs time for embeddings)
    const MAX_RETRIES = 2;

    /**
     * Send data to the central server.
     *
     * @param string $endpoint  The API endpoint URL.
     * @param string $token     The authentication token.
     * @param string $json      The JSON-encoded payload.
     * @return array|WP_Error   Response array or WP_Error on failure.
     */
    public function send( $endpoint, $token, $json ) {
        // Validate endpoint
        if ( ! filter_var( $endpoint, FILTER_VALIDATE_URL ) ) {
            return new WP_Error( 'invalid_endpoint', 'Invalid API endpoint URL: ' . $endpoint );
        }

        // Ensure HTTPS (allow HTTP only for localhost/dev)
        $parsed = wp_parse_url( $endpoint );
        $host = isset( $parsed['host'] ) ? $parsed['host'] : '';
        $is_local = in_array( $host, array( 'localhost', '127.0.0.1' ), true ) || strpos( $host, '.local' ) !== false;

        if ( ! $is_local && strpos( $endpoint, 'https://' ) !== 0 ) {
            return new WP_Error( 'insecure_endpoint', 'API endpoint must use HTTPS for production.' );
        }

        // Retry loop
        $last_error = null;
        for ( $attempt = 1; $attempt <= self::MAX_RETRIES; $attempt++ ) {

            $response = wp_remote_post( $endpoint, array(
                'timeout'   => self::TIMEOUT,
                'headers'   => array(
                    'Content-Type'     => 'application/json; charset=utf-8',
                    'Authorization'    => 'Bearer ' . $token,
                    'X-Webhook-Secret' => $token,
                    'X-Plugin-Version' => ASA_VERSION,
                    'X-Attempt'        => $attempt,
                ),
                'body'      => $json,
                'sslverify' => ! $is_local, // Skip SSL verify for localhost
            ) );

            // Network error — retry
            if ( is_wp_error( $response ) ) {
                $last_error = $response;
                if ( $attempt < self::MAX_RETRIES ) {
                    sleep( 2 * $attempt ); // Exponential backoff: 2s, 4s
                    continue;
                }
                return $last_error;
            }

            // HTTP response received
            $code = wp_remote_retrieve_response_code( $response );

            // Success (2xx)
            if ( $code >= 200 && $code < 300 ) {
                return $response;
            }

            // Rate limited (429) or server error (5xx) — retry
            if ( $code === 429 || $code >= 500 ) {
                $last_error = new WP_Error(
                    'server_error',
                    "Server returned HTTP {$code} on attempt {$attempt}. Body: " . wp_remote_retrieve_body( $response )
                );
                if ( $attempt < self::MAX_RETRIES ) {
                    $retry_after = (int) wp_remote_retrieve_header( $response, 'retry-after' );
                    sleep( max( $retry_after, 2 * $attempt ) );
                    continue;
                }
                return $last_error;
            }

            // Client error (4xx) — don't retry, it's our fault
            return new WP_Error(
                'client_error',
                "Server returned HTTP {$code}. Body: " . wp_remote_retrieve_body( $response )
            );
        }

        return isset( $last_error ) ? $last_error : new WP_Error( 'unknown_error', 'Sync failed for unknown reason.' );
    }

    /**
     * Test connection to the endpoint (lightweight health check).
     *
     * @param string $endpoint
     * @param string $token
     * @return array|WP_Error
     */
    public function test_connection( $endpoint, $token ) {
        if ( empty( $endpoint ) ) {
            return new WP_Error( 'empty_endpoint', 'Endpoint is empty.' );
        }

        // Test connection using the /health endpoint
        $health_url = rtrim( $endpoint, '/' );
        $health_url = str_replace( '/webhook', '/health', $health_url );

        $response = wp_remote_get( $health_url, array(
            'timeout' => 15,
            'headers' => array(
                'Authorization'    => 'Bearer ' . $token,
                'X-Webhook-Secret' => $token,
            ),
            'sslverify' => strpos( $endpoint, 'localhost' ) === false,
        ) );

        return $response;
    }
}
