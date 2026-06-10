<?php
/**
 * ASA_Data_Sanitizer
 *
 * Removes sensitive data (API keys, passwords, secrets, PII) from collected data
 * BEFORE it leaves the client's server. This is the first layer of defense.
 * The central server applies a second layer before storing.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class ASA_Data_Sanitizer {

    /**
     * Patterns that match sensitive data.
     * Each pattern has: regex, replacement label, and description.
     */
    private $patterns = array();

    /**
     * Keys in settings arrays that should always be redacted.
     */
    private $sensitive_keys = array();

    public function __construct() {
        $this->init_patterns();
        $this->init_sensitive_keys();
    }

    private function init_patterns() {
        $this->patterns = array(
            // ─── Stripe ───
            array(
                'pattern' => '/\b(sk_live_[a-zA-Z0-9]{20,})\b/',
                'label'   => '[REDACTED:stripe_secret_key]',
            ),
            array(
                'pattern' => '/\b(sk_test_[a-zA-Z0-9]{20,})\b/',
                'label'   => '[REDACTED:stripe_test_key]',
            ),
            array(
                'pattern' => '/\b(pk_live_[a-zA-Z0-9]{20,})\b/',
                'label'   => '[REDACTED:stripe_publishable_key]',
            ),
            array(
                'pattern' => '/\b(pk_test_[a-zA-Z0-9]{20,})\b/',
                'label'   => '[REDACTED:stripe_test_publishable]',
            ),
            array(
                'pattern' => '/\b(rk_live_[a-zA-Z0-9]{20,})\b/',
                'label'   => '[REDACTED:stripe_restricted_key]',
            ),
            array(
                'pattern' => '/\b(whsec_[a-zA-Z0-9]{20,})\b/',
                'label'   => '[REDACTED:stripe_webhook_secret]',
            ),

            // ─── PayPal ───
            array(
                'pattern' => '/\b(A[a-zA-Z0-9_-]{60,80})\b/', // PayPal client ID pattern
                'label'   => '[REDACTED:possible_paypal_key]',
                'context' => 'paypal', // only apply in PayPal context
            ),

            // ─── Generic API Keys ───
            array(
                'pattern' => '/(?i)(api[_-]?key|apikey|api[_-]?secret|secret[_-]?key|access[_-]?key|private[_-]?key|auth[_-]?token|bearer[_-]?token)[\s]*[=:]+[\s]*["\']?([a-zA-Z0-9_\-\.\/\+]{16,})["\']?/',
                'label'   => '$1=[REDACTED]',
            ),

            // ─── Passwords in code/config ───
            array(
                'pattern' => '/(?i)(password|passwd|pwd|pass|db_password|mysql_password|db_pass)[\s]*[=:]+[\s]*["\']?([^\s"\';\n]{4,})["\']?/',
                'label'   => '$1=[REDACTED]',
            ),

            // ─── Consumer Secrets (WooCommerce) ───
            array(
                'pattern' => '/\b(cs_[a-f0-9]{32,})\b/',
                'label'   => '[REDACTED:wc_consumer_secret]',
            ),
            array(
                'pattern' => '/\b(ck_[a-f0-9]{32,})\b/',
                'label'   => '[REDACTED:wc_consumer_key]',
            ),

            // ─── AWS ───
            array(
                'pattern' => '/\b(AKIA[0-9A-Z]{16})\b/',
                'label'   => '[REDACTED:aws_access_key]',
            ),

            // ─── Database connection strings ───
            array(
                'pattern' => '/(?i)(mysql|mysqli|pdo)[^;]*(?:password|pwd)\s*[=:]\s*["\']?[^\s"\';\n]+/',
                'label'   => '[REDACTED:db_connection]',
            ),

            // ─── Email addresses (PII) ───
            array(
                'pattern' => '/\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b/',
                'label'   => '[REDACTED:email]',
                'context' => 'pii', // only in PII-sensitive contexts
            ),

            // ─── Phone numbers (Greek + international) ───
            array(
                'pattern' => '/(?:\+30|0030)?\s?(?:69\d{8}|2\d{9})/',
                'label'   => '[REDACTED:phone_gr]',
                'context' => 'pii',
            ),

            // ─── IP addresses in code ───
            array(
                'pattern' => '/\b(?:\d{1,3}\.){3}\d{1,3}\b/',
                'label'   => '[REDACTED:ip]',
                'context' => 'code',
            ),

            // ─── SSH keys ───
            array(
                'pattern' => '/-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----/',
                'label'   => '[REDACTED:private_key]',
            ),

            // ─── JWT tokens ───
            array(
                'pattern' => '/\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b/',
                'label'   => '[REDACTED:jwt_token]',
            ),
        );
    }

    private function init_sensitive_keys() {
        $this->sensitive_keys = array(
            // WooCommerce payment gateway settings
            'secret_key',
            'test_secret_key',
            'publishable_key',
            'test_publishable_key',
            'api_key',
            'api_secret',
            'private_key',
            'public_key',
            'merchant_key',
            'merchant_secret',
            'client_id',
            'client_secret',
            'access_token',
            'refresh_token',
            'webhook_secret',
            'signing_secret',
            'password',
            'api_password',
            'api_signature',
            'shared_secret',
            'encryption_key',
            'hash_key',
            'salt',
            // Common across payment gateways
            'live_secret_key',
            'test_secret_key',
            'sandbox_api_password',
            'sandbox_api_signature',
            'production_api_password',
            'production_api_signature',
        );
    }

    /**
     * Sanitize a string (code content, description, etc.)
     *
     * @param string $text      The text to sanitize.
     * @param string $context   Context hint: 'code', 'settings', 'pii', 'general'.
     * @return string           Sanitized text.
     */
    public function sanitize_text( $text, $context = 'general' ) {
        if ( ! is_string( $text ) || empty( $text ) ) {
            return $text;
        }

        foreach ( $this->patterns as $p ) {
            // Skip context-specific patterns if context doesn't match
            if ( isset( $p['context'] ) && $p['context'] !== $context && $context !== 'all' ) {
                continue;
            }

            $text = preg_replace( $p['pattern'], $p['label'], $text );
        }

        return $text;
    }

    /**
     * Sanitize an array of settings, redacting sensitive keys.
     *
     * @param array  $settings  Key-value settings array.
     * @return array            Sanitized settings.
     */
    public function sanitize_settings( $settings ) {
        if ( ! is_array( $settings ) ) {
            return $settings;
        }

        $sanitized = array();
        foreach ( $settings as $key => $value ) {
            $key_lower = strtolower( $key );

            // Check if this key is in the sensitive list
            if ( in_array( $key_lower, $this->sensitive_keys, true ) ) {
                $sanitized[ $key ] = '[REDACTED]';
                continue;
            }

            // Check if key contains sensitive words
            if ( preg_match( '/(?:secret|password|passwd|token|key|salt|hash|nonce|credential)/i', $key_lower ) ) {
                // Only redact if value looks like a real secret (length > 8, not a boolean/simple value)
                if ( is_string( $value ) && strlen( $value ) > 8 && ! in_array( $value, array( 'yes', 'no', 'true', 'false', 'enabled', 'disabled' ), true ) ) {
                    $sanitized[ $key ] = '[REDACTED]';
                    continue;
                }
            }

            // Recursively sanitize nested arrays
            if ( is_array( $value ) ) {
                $sanitized[ $key ] = $this->sanitize_settings( $value );
            } elseif ( is_string( $value ) ) {
                $sanitized[ $key ] = $this->sanitize_text( $value, 'settings' );
            } else {
                $sanitized[ $key ] = $value;
            }
        }

        return $sanitized;
    }

    /**
     * Sanitize code content (snippets, functions.php, theme files).
     * More aggressive — also strips IPs and embedded credentials.
     *
     * @param string $code  The code to sanitize.
     * @return string       Sanitized code.
     */
    public function sanitize_code( $code ) {
        if ( ! is_string( $code ) || empty( $code ) ) {
            return $code;
        }

        // First pass: all patterns including code-specific
        $code = $this->sanitize_text( $code, 'all' );

        // Second pass: catch define() statements with secrets
        $code = preg_replace(
            "/define\s*\(\s*['\"](?:DB_PASSWORD|DB_USER|AUTH_KEY|SECURE_AUTH_KEY|LOGGED_IN_KEY|NONCE_KEY|AUTH_SALT|SECURE_AUTH_SALT|LOGGED_IN_SALT|NONCE_SALT|AWS_SECRET_ACCESS_KEY|STRIPE_SECRET_KEY)['\"][\s,]+['\"]([^'\"]+)['\"]\s*\)/i",
            "define( '$1', '[REDACTED]' )",
            $code
        );

        return $code;
    }

    /**
     * Get a summary of what patterns are being applied (for admin debug view).
     */
    public function get_pattern_summary() {
        $summary = array();
        foreach ( $this->patterns as $p ) {
            $summary[] = array(
                'label'   => $p['label'],
                'context' => $p['context'] ?? 'all',
            );
        }
        return $summary;
    }
}
