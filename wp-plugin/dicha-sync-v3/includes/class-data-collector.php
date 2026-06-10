<?php
/**
 * ASA_Data_Collector
 *
 * Collects all data specified in the TRD:
 * - Source 1: WooCommerce Settings (payment gateways, shipping, tax, plugins)
 * - Source 2: Code Snippets (DB table) + functions.php + child theme files
 *
 * All data is sanitized before being returned.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class ASA_Data_Collector {

    private $sanitizer;

    public function __construct( ASA_Data_Sanitizer $sanitizer ) {
        $this->sanitizer = $sanitizer;
    }

    /**
     * Collect ALL data. Returns a structured array ready for JSON encoding.
     *
     * @return array
     */
    public function collect_all() {
        $data = array(
            // ─── Source 1: WooCommerce Settings ───
            'woocommerce' => array(
                'active'           => $this->is_woocommerce_active(),
                'version'          => $this->get_wc_version(),
                'payment_gateways' => $this->collect_payment_gateways(),
                'shipping_zones'   => $this->collect_shipping_zones(),
                'shipping_classes' => $this->collect_shipping_classes(),
                'tax_settings'     => $this->collect_tax_settings(),
                'general_settings' => $this->collect_general_settings(),
            ),

            // ─── Active Plugins ───
            'active_plugins' => $this->collect_active_plugins(),

            // ─── Plugin Settings ───
            'plugin_settings' => $this->collect_plugin_settings(),

            // ─── Source 2: Customizations ───
            'code_snippets' => $this->collect_code_snippets(),
            'functions_php' => $this->collect_functions_php(),
            'theme_files'   => $this->collect_theme_files(),
            'theme_info'    => $this->collect_theme_info(),
            'theme_settings'=> $this->collect_theme_settings(),

            // ─── Meta ───
            '_collection_meta' => array(
                'collected_at'  => current_time( 'c' ),
                'memory_used'   => round( memory_get_peak_usage( true ) / 1024 / 1024, 2 ) . 'MB',
                'wc_active'     => $this->is_woocommerce_active(),
                'snippets_found'=> 'counted_below',
            ),
        );

        // Update snippet count
        $data['_collection_meta']['snippets_found'] = count( $data['code_snippets'] );

        return $data;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // SOURCE 1: WooCommerce Settings
    // ═══════════════════════════════════════════════════════════════════════════

    private function is_woocommerce_active() {
        return class_exists( 'WooCommerce' );
    }

    private function get_wc_version() {
        if ( ! $this->is_woocommerce_active() ) {
            return null;
        }
        return defined( 'WC_VERSION' ) ? WC_VERSION : null;
    }

    /**
     * Payment Gateways
     */
    public function collect_payment_gateways() {
        if ( ! $this->is_woocommerce_active() || ! function_exists( 'WC' ) ) {
            return array( '_note' => 'WooCommerce not active' );
        }

        $gateways = array();

        try {
            $wc_gateways = WC()->payment_gateways();
            if ( ! $wc_gateways ) {
                return array( '_note' => 'Payment gateways not available' );
            }

            foreach ( $wc_gateways->payment_gateways() as $gateway ) {
                $settings = array();

                // Get settings but sanitize them
                if ( is_array( $gateway->settings ) ) {
                    $settings = $this->sanitizer->sanitize_settings( $gateway->settings );
                }

                // Also get form fields metadata (tells us WHAT settings exist)
                $form_fields = $this->collect_form_fields( $gateway );

                $gateways[] = array(
                    'id'                => $gateway->id,
                    'title'             => $gateway->get_title(),
                    'method_title'      => $gateway->get_method_title(),
                    'method_description'=> wp_strip_all_tags( $gateway->get_method_description() ),
                    'enabled'           => $gateway->enabled,
                    'description'       => $gateway->get_description(),
                    'supports'          => isset( $gateway->supports ) ? $gateway->supports : array(),
                    'has_fields'        => $gateway->has_fields(),
                    'countries'         => isset( $gateway->countries ) ? $gateway->countries : array(),
                    'availability'      => isset( $gateway->availability ) ? $gateway->availability : '',
                    'settings'          => $settings,
                    'form_fields_meta'  => $form_fields,
                );
            }
        } catch ( \Throwable $e ) {
            return array( '_error' => 'Failed to collect payment gateways: ' . $e->getMessage() );
        }

        return $gateways;
    }

    /**
     * Shipping Zones & Methods
     */
    public function collect_shipping_zones() {
        if ( ! $this->is_woocommerce_active() ) {
            return array( '_note' => 'WooCommerce not active' );
        }

        $zones = array();

        try {
            // Include "Rest of the World" zone (id = 0)
            $raw_zones = WC_Shipping_Zones::get_zones();

            // Add zone 0 (Rest of World)
            $zone_zero = new WC_Shipping_Zone( 0 );
            $raw_zones[0] = array(
                'zone_id'        => 0,
                'zone_name'      => $zone_zero->get_zone_name(),
                'zone_locations' => $zone_zero->get_zone_locations(),
                'shipping_methods'=> $zone_zero->get_shipping_methods(),
            );

            foreach ( $raw_zones as $zone_data ) {
                $methods = array();

                $zone_methods = isset( $zone_data['shipping_methods'] ) ? $zone_data['shipping_methods'] : array();
                foreach ( $zone_methods as $method ) {
                    $method_data = array(
                        'instance_id'  => isset( $method->instance_id ) ? $method->instance_id : null,
                        'method_id'    => $method->id,
                        'method_title' => $method->get_title(),
                        'enabled'      => $method->is_enabled() ? 'yes' : 'no',
                        'tax_status'   => $method->get_option( 'tax_status', 'taxable' ),
                    );

                    // Get cost if available (Flat Rate, etc.)
                    $cost = $method->get_option( 'cost', null );
                    if ( $cost !== null ) {
                        $method_data['cost'] = $cost;
                    }

                    // Free shipping settings
                    if ( $method->id === 'free_shipping' ) {
                        $method_data['requires']      = $method->get_option( 'requires', '' );
                        $method_data['min_amount']     = $method->get_option( 'min_amount', '' );
                        $method_data['ignore_discounts']= $method->get_option( 'ignore_discounts', 'no' );
                    }

                    // Flat rate class costs
                    if ( $method->id === 'flat_rate' ) {
                        $method_data['type']           = $method->get_option( 'type', 'class' );
                        $method_data['no_class_cost']  = $method->get_option( 'no_class_cost', '' );

                        // Per-class costs
                        $shipping_classes = WC()->shipping()->get_shipping_classes();
                        foreach ( $shipping_classes as $class ) {
                            $class_cost = $method->get_option( 'class_cost_' . $class->term_id, '' );
                            if ( $class_cost !== '' ) {
                                if ( ! isset( $method_data['class_costs'] ) ) {
                                    $method_data['class_costs'] = array();
                                }
                                $method_data['class_costs'][ $class->slug ] = $class_cost;
                            }
                        }
                    }

                    // Local Pickup
                    if ( $method->id === 'local_pickup' ) {
                        $method_data['cost'] = $method->get_option( 'cost', '' );
                    }

                    // Force initialization (needed for lazy-loading methods)
                    if ( method_exists( $method, 'init_instance_settings' ) ) {
                        $method->init_instance_settings();
                    }
                    if ( method_exists( $method, 'init_form_fields' ) ) {
                        $method->init_form_fields();
                    }

                    // Full instance settings (catches ALL method types including 3rd-party)
                    $instance_settings = array();
                    if ( ! empty( $method->instance_settings ) && is_array( $method->instance_settings ) ) {
                        $instance_settings = $method->instance_settings;
                    } elseif ( ! empty( $method->settings ) && is_array( $method->settings ) ) {
                        $instance_settings = $method->settings;
                    } else {
                        // Tier 3: build from form_fields via get_option()
                        $form_fields = method_exists( $method, 'get_form_fields' ) ? $method->get_form_fields() : array();
                        if ( ! empty( $form_fields ) && is_array( $form_fields ) ) {
                            foreach ( $form_fields as $key => $field ) {
                                $instance_settings[ $key ] = $method->get_option( $key );
                            }
                        }
                    }
                    if ( ! empty( $instance_settings ) ) {
                        $instance_settings = $this->sanitizer->sanitize_settings( $instance_settings );
                    }
                    $method_data['settings'] = $instance_settings;

                    // Form fields metadata — self-documenting labels
                    $method_data['form_fields_meta'] = $this->collect_form_fields( $method );

                    $methods[] = $method_data;
                }

                // Parse locations
                $locations = array();
                $zone_locations = isset( $zone_data['zone_locations'] ) ? $zone_data['zone_locations'] : array();
                foreach ( $zone_locations as $loc ) {
                    $code = '';
                    $type = '';
                    if ( is_object( $loc ) ) {
                        $code = isset( $loc->code ) ? $loc->code : '';
                        $type = isset( $loc->type ) ? $loc->type : '';
                    } elseif ( is_array( $loc ) ) {
                        $code = isset( $loc['code'] ) ? $loc['code'] : '';
                        $type = isset( $loc['type'] ) ? $loc['type'] : '';
                    }
                    $locations[] = array(
                        'code' => $code,
                        'type' => $type,
                    );
                }

                $zones[] = array(
                    'zone_id'   => isset( $zone_data['zone_id'] ) ? $zone_data['zone_id'] : 0,
                    'zone_name' => isset( $zone_data['zone_name'] ) ? $zone_data['zone_name'] : 'Unknown',
                    'locations' => $locations,
                    'methods'   => $methods,
                );
            }
        } catch ( \Throwable $e ) {
            return array( '_error' => 'Failed to collect shipping zones: ' . $e->getMessage() );
        }

        return $zones;
    }

    /**
     * Shipping Classes
     */
    public function collect_shipping_classes() {
        if ( ! $this->is_woocommerce_active() ) {
            return array();
        }

        try {
            $classes = WC()->shipping()->get_shipping_classes();
            $result = array();
            foreach ( $classes as $class ) {
                $result[] = array(
                    'term_id'     => $class->term_id,
                    'name'        => $class->name,
                    'slug'        => $class->slug,
                    'description' => $class->description,
                    'count'       => $class->count,
                );
            }
            return $result;
        } catch ( \Throwable $e ) {
            return array( '_error' => $e->getMessage() );
        }
    }

    /**
     * Theme Settings — intentionally NOT collected.
     *
     * Theme options (Woodmart Customizer / Redux framework) are out of scope:
     * the client does not want them stored. Returning an empty array keeps the
     * payload shape stable while the downstream sync guards skip the
     * theme_settings table row and the "Settings: … theme" document.
     */
    public function collect_theme_settings() {
        return array();
    }

    /**
     * Tax Settings
     */
    public function collect_tax_settings() {
        if ( ! $this->is_woocommerce_active() ) {
            return array( '_note' => 'WooCommerce not active' );
        }

        try {
            $settings = array(
                'tax_enabled'           => get_option( 'woocommerce_calc_taxes', 'no' ),
                'prices_include_tax'    => get_option( 'woocommerce_prices_include_tax', 'no' ),
                'tax_based_on'          => get_option( 'woocommerce_tax_based_on', 'shipping' ),
                'tax_round_at_subtotal' => get_option( 'woocommerce_tax_round_at_subtotal', 'no' ),
                'tax_display_shop'      => get_option( 'woocommerce_tax_display_shop', 'excl' ),
                'tax_display_cart'      => get_option( 'woocommerce_tax_display_cart', 'excl' ),
                'tax_total_display'     => get_option( 'woocommerce_tax_total_display', 'itemized' ),
                'tax_classes'           => WC_Tax::get_tax_classes(),
            );

            // Get actual tax rates
            $rates = array();

            // Standard rate
            $standard_rates = WC_Tax::get_rates_for_tax_class( '' );
            if ( ! empty( $standard_rates ) ) {
                foreach ( $standard_rates as $rate ) {
                    $rates[] = array(
                        'class'    => 'Standard',
                        'country'  => $rate->tax_rate_country,
                        'state'    => $rate->tax_rate_state,
                        'rate'     => $rate->tax_rate,
                        'name'     => $rate->tax_rate_name,
                        'priority' => $rate->tax_rate_priority,
                        'compound' => $rate->tax_rate_compound,
                        'shipping' => $rate->tax_rate_shipping,
                    );
                }
            }

            // Other classes
            foreach ( WC_Tax::get_tax_classes() as $class ) {
                $class_rates = WC_Tax::get_rates_for_tax_class( $class );
                foreach ( $class_rates as $rate ) {
                    $rates[] = array(
                        'class'    => $class,
                        'country'  => $rate->tax_rate_country,
                        'state'    => $rate->tax_rate_state,
                        'rate'     => $rate->tax_rate,
                        'name'     => $rate->tax_rate_name,
                        'priority' => $rate->tax_rate_priority,
                        'compound' => $rate->tax_rate_compound,
                        'shipping' => $rate->tax_rate_shipping,
                    );
                }
            }

            $settings['tax_rates'] = $rates;

            return $settings;
        } catch ( \Throwable $e ) {
            return array( '_error' => $e->getMessage() );
        }
    }

    /**
     * General WooCommerce settings (currency, store address, etc.)
     */
    public function collect_general_settings() {
        if ( ! $this->is_woocommerce_active() ) {
            return array();
        }

        return array(
            'currency'              => get_woocommerce_currency(),
            'currency_position'     => get_option( 'woocommerce_currency_pos', 'left' ),
            'thousand_separator'    => get_option( 'woocommerce_price_thousand_sep', '.' ),
            'decimal_separator'     => get_option( 'woocommerce_price_decimal_sep', ',' ),
            'num_decimals'          => get_option( 'woocommerce_price_num_decimals', '2' ),
            'store_country'         => get_option( 'woocommerce_default_country', '' ),
            'store_address'         => get_option( 'woocommerce_store_address', '' ),
            'store_city'            => get_option( 'woocommerce_store_city', '' ),
            'store_postcode'        => get_option( 'woocommerce_store_postcode', '' ),
            'enable_coupons'        => get_option( 'woocommerce_enable_coupons', 'yes' ),
            'calc_discounts_seq'    => get_option( 'woocommerce_calc_discounts_sequentially', 'no' ),
            'checkout_page_id'      => get_option( 'woocommerce_checkout_page_id', '' ),
            'cart_page_id'          => get_option( 'woocommerce_cart_page_id', '' ),
            'myaccount_page_id'     => get_option( 'woocommerce_myaccount_page_id', '' ),
            'enable_guest_checkout' => get_option( 'woocommerce_enable_guest_checkout', 'yes' ),
            'enable_signup_login'   => get_option( 'woocommerce_enable_signup_and_login_from_checkout', 'no' ),
            'manage_stock'          => get_option( 'woocommerce_manage_stock', 'yes' ),
            'stock_format'          => get_option( 'woocommerce_stock_format', '' ),
        );
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // ACTIVE PLUGINS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Active Plugins
     */
    public function collect_active_plugins() {
        $active = get_option( 'active_plugins', array() );
        $plugins = array();

        foreach ( $active as $plugin_file ) {
            $plugin_path = WP_PLUGIN_DIR . '/' . $plugin_file;
            if ( ! file_exists( $plugin_path ) ) {
                continue;
            }

            $plugin_data = get_plugin_data( $plugin_path, false, false );

            $plugins[] = array(
                'name'        => isset( $plugin_data['Name'] ) ? $plugin_data['Name'] : basename( $plugin_file ),
                'version'     => isset( $plugin_data['Version'] ) ? $plugin_data['Version'] : 'unknown',
                'author'      => wp_strip_all_tags( isset( $plugin_data['Author'] ) ? $plugin_data['Author'] : '' ),
                'plugin_uri'  => isset( $plugin_data['PluginURI'] ) ? $plugin_data['PluginURI'] : '',
                'description' => wp_strip_all_tags( isset( $plugin_data['Description'] ) ? $plugin_data['Description'] : '' ),
                'file'        => $plugin_file,
                'requires_wp' => isset( $plugin_data['RequiresWP'] ) ? $plugin_data['RequiresWP'] : '',
                'requires_php'=> isset( $plugin_data['RequiresPHP'] ) ? $plugin_data['RequiresPHP'] : '',
            );
        }

        return $plugins;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PLUGIN SETTINGS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Collect settings/configuration of all active plugins.
     *
     * Explicit opt-in only: settings are collected solely for plugins whose
     * option prefixes are declared in get_option_prefixes() (or added via the
     * 'dicha_sync_plugin_prefixes' filter). Unknown plugins are skipped — no
     * slug-based guessing, so we never collect the wrong or noisy options.
     */
    public function collect_plugin_settings() {
        try {
            $active_plugins = get_option( 'active_plugins', array() );
            $results = array();

            foreach ( $active_plugins as $plugin_file ) {
                $slug = dirname( $plugin_file );
                if ( $slug === '.' ) {
                    continue;
                }

                try {
                    $prefixes = $this->get_option_prefixes( $slug );
                    $options  = $this->fetch_plugin_options( $prefixes );

                    if ( empty( $options ) ) {
                        continue;
                    }

                    $options = $this->sanitizer->sanitize_settings( $options );

                    $json = wp_json_encode( $options );
                    if ( strlen( $json ) > 50000 ) {
                        $options = array( '_truncated' => true, '_size' => strlen( $json ) );
                    }

                    $plugin_data = get_plugin_data( WP_PLUGIN_DIR . '/' . $plugin_file, false, false );

                    $results[] = array(
                        'plugin_slug' => $slug,
                        'plugin_name' => isset( $plugin_data['Name'] ) ? $plugin_data['Name'] : $slug,
                        'plugin_file' => $plugin_file,
                        'settings'    => $options,
                    );
                } catch ( \Throwable $e ) {
                    continue;
                }
            }

            return $results;
        } catch ( \Throwable $e ) {
            return array();
        }
    }

    /**
     * Option-name prefixes to collect per plugin slug.
     *
     * Explicit map only — no slug-based guessing. A plugin not listed here
     * returns an empty array (nothing collected) on purpose: precision over
     * recall, so we never grab the wrong or noisy wp_options rows.
     *
     * Site owners can support additional plugins WITHOUT editing this file,
     * via the 'dicha_sync_plugin_prefixes' filter in a mu-plugin or snippet:
     *
     *     add_filter( 'dicha_sync_plugin_prefixes', function ( $known ) {
     *         $known['my-plugin-slug'] = array( 'my_option_prefix_' );
     *         return $known;
     *     } );
     *
     * @param string $slug Plugin folder slug (e.g. 'wc-smart-cod').
     * @return string[] Option-name prefixes to fetch, or empty array if unknown.
     */
    /**
     * The built-in default plugins we always collect (slug => option prefixes).
     * Public so the admin UI can list them. Edit only to change the shipped defaults.
     */
    public function get_default_prefixes() {
        return array(
            'wp-rocket'                             => array( 'wp_rocket' ),
            'weight-based-shipping-for-woocommerce' => array( 'wbs', 'wbsng' ),
            'wc-smart-cod'                          => array( 'woocommerce_cod_settings' ),
            'wc-cash-on-pickup'                     => array( 'woocommerce_cop_settings' ),
        );
    }

    private function get_option_prefixes( $slug ) {
        $known = $this->get_default_prefixes();

        // Admin-managed additions from the settings page (no code edit needed):
        // option holds array( slug => array( 'prefix_', ... ) ).
        $custom = get_option( 'asa_plugin_prefixes', array() );
        if ( is_array( $custom ) ) {
            $known = array_merge( $known, $custom );
        }

        // Let site owners register their own plugins without touching this file.
        $known = apply_filters( 'dicha_sync_plugin_prefixes', $known );

        // Honor the admin "disabled" list (lets the owner turn off built-in plugins too).
        $disabled = get_option( 'asa_disabled_plugins', array() );
        if ( is_array( $disabled ) ) {
            foreach ( $disabled as $d ) {
                unset( $known[ $d ] );
            }
        }

        if ( isset( $known[ $slug ] ) ) {
            return $known[ $slug ];
        }

        return array();
    }

    private function fetch_plugin_options( $prefixes ) {
        global $wpdb;

        if ( empty( $prefixes ) ) {
            return array();
        }

        $like_clauses = array();
        foreach ( $prefixes as $prefix ) {
            $escaped = $wpdb->esc_like( $prefix );
            $like_clauses[] = $wpdb->prepare( 'option_name LIKE %s', $escaped . '%' );
        }
        $prefix_where = '(' . implode( ' OR ', $like_clauses ) . ')';

        $excludes = "AND option_name NOT LIKE '%\_transient\_%'"
                  . " AND option_name NOT LIKE '%\_site\_transient\_%'"
                  . " AND option_name NOT LIKE '%cron%'"
                  . " AND option_name NOT LIKE '%\_db\_version'"
                  . " AND option_name NOT LIKE '%\_activation\_redirect'"
                  . " AND option_name NOT LIKE '%\_install\_data'"
                  . " AND option_name NOT LIKE '%\_tracking%'"
                  . " AND option_name NOT LIKE '%\_usage\_tracking%'";

        // phpcs:ignore WordPress.DB.PreparedSQL.NotPrepared
        $results = $wpdb->get_results(
            "SELECT option_name, option_value FROM {$wpdb->options} WHERE {$prefix_where} {$excludes} LIMIT 100"
        );

        $options = array();
        if ( ! empty( $results ) ) {
            foreach ( $results as $row ) {
                $options[ $row->option_name ] = maybe_unserialize( $row->option_value );
            }
        }

        return $options;
    }

    /**
     * Extract form_fields metadata from any WC_Settings_API object.
     * Returns field labels, types, descriptions, defaults, and options.
     */
    private function collect_form_fields( $object ) {
        $fields = array();
        // Try instance_form_fields first (shipping methods), then form_fields (gateways), then get_form_fields()
        $source = null;
        if ( ! empty( $object->instance_form_fields ) && is_array( $object->instance_form_fields ) ) {
            $source = $object->instance_form_fields;
        } elseif ( ! empty( $object->form_fields ) && is_array( $object->form_fields ) ) {
            $source = $object->form_fields;
        } elseif ( method_exists( $object, 'get_form_fields' ) ) {
            $source = $object->get_form_fields();
        }
        if ( empty( $source ) || ! is_array( $source ) ) {
            return $fields;
        }
        foreach ( $source as $key => $field ) {
            $fields[ $key ] = array(
                'title'       => isset( $field['title'] ) ? $field['title'] : '',
                'type'        => isset( $field['type'] ) ? $field['type'] : 'text',
                'description' => wp_strip_all_tags( isset( $field['description'] ) ? $field['description'] : '' ),
                'default'     => isset( $field['default'] ) ? $field['default'] : '',
                'options'     => isset( $field['options'] ) ? $field['options'] : array(),
            );
        }
        return $fields;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // SOURCE 2: Customizations & Code Snippets
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Code Snippets
     *
     * Supports multiple snippet plugins:
     * - Code Snippets (by Code Snippets Pro) — table: wp_snippets
     * - WPCode (by WPCode) — custom post type: wpcode
     */
    public function collect_code_snippets() {
        $all_snippets = array();

        // ─── Method 1: Code Snippets plugin (wp_snippets table) ───
        $table_snippets = $this->collect_snippets_from_table();
        if ( ! empty( $table_snippets ) ) {
            $all_snippets = array_merge( $all_snippets, $table_snippets );
        }

        // ─── Method 2: WPCode plugin (custom post type) ───
        $wpcode_snippets = $this->collect_snippets_from_wpcode();
        if ( ! empty( $wpcode_snippets ) ) {
            $all_snippets = array_merge( $all_snippets, $wpcode_snippets );
        }

        return $all_snippets;
    }

    /**
     * Code Snippets plugin — reads from wp_snippets table.
     */
    private function collect_snippets_from_table() {
        global $wpdb;

        $table = $wpdb->prefix . 'snippets';

        // Check if table exists
        $table_exists = $wpdb->get_var(
            $wpdb->prepare( "SHOW TABLES LIKE %s", $table )
        );

        if ( $table_exists !== $table ) {
            return array();
        }

        $snippets = array();

        try {
            $rows = $wpdb->get_results(
                "SELECT id, name, description, code, tags, scope, priority, active, modified FROM {$table} ORDER BY active DESC, id ASC",
                ARRAY_A
            );

            if ( empty( $rows ) ) {
                return array();
            }

            foreach ( $rows as $row ) {
                $snippets[] = array(
                    'source'      => 'code_snippets_plugin',
                    'id'          => (int) $row['id'],
                    'name'        => isset( $row['name'] ) ? $row['name'] : '',
                    'description' => isset( $row['description'] ) ? $row['description'] : '',
                    'code'        => $this->sanitizer->sanitize_code( isset( $row['code'] ) ? $row['code'] : '' ),
                    'tags'        => isset( $row['tags'] ) ? $row['tags'] : '',
                    'scope'       => isset( $row['scope'] ) ? $row['scope'] : 'global',
                    'priority'    => isset( $row['priority'] ) ? $row['priority'] : 10,
                    'active'      => (bool) ( isset( $row['active'] ) ? $row['active'] : false ),
                    'modified'    => isset( $row['modified'] ) ? $row['modified'] : '',
                );
            }
        } catch ( \Throwable $e ) {
            return array( array( '_error' => 'Failed to read snippets table: ' . $e->getMessage() ) );
        }

        return $snippets;
    }

    /**
     * WPCode plugin — reads from custom post type 'wpcode'.
     */
    private function collect_snippets_from_wpcode() {
        if ( ! post_type_exists( 'wpcode' ) ) {
            return array();
        }

        $snippets = array();

        try {
            $posts = get_posts( array(
                'post_type'      => 'wpcode',
                'posts_per_page' => 200,
                'post_status'    => array( 'publish', 'draft' ),
                'orderby'        => 'date',
                'order'          => 'DESC',
            ) );

            foreach ( $posts as $post ) {
                $snippets[] = array(
                    'source'      => 'wpcode_plugin',
                    'id'          => $post->ID,
                    'name'        => $post->post_title,
                    'description' => isset( $post->post_excerpt ) ? $post->post_excerpt : '',
                    'code'        => $this->sanitizer->sanitize_code( isset( $post->post_content ) ? $post->post_content : '' ),
                    'active'      => $post->post_status === 'publish',
                    'type'        => get_post_meta( $post->ID, '_wpcode_type', true ) ? get_post_meta( $post->ID, '_wpcode_type', true ) : 'php',
                    'location'    => get_post_meta( $post->ID, '_wpcode_location', true ) ? get_post_meta( $post->ID, '_wpcode_location', true ) : '',
                    'modified'    => $post->post_modified,
                );
            }
        } catch ( \Throwable $e ) {
            return array( array( '_error' => 'Failed to read WPCode snippets: ' . $e->getMessage() ) );
        }

        return $snippets;
    }

    /**
     * functions.php
     */
    public function collect_functions_php() {
        $result = array(
            'theme'       => null,
            'child_theme' => null,
        );

        try {
            // Child theme (or current theme) functions.php
            $child_functions = get_stylesheet_directory() . '/functions.php';
            if ( file_exists( $child_functions ) ) {
                $size = filesize( $child_functions );
                if ( $size <= ASA_MAX_FILE_SIZE ) {
                    $result['child_theme'] = array(
                        'path'     => str_replace( ABSPATH, '', $child_functions ),
                        'size'     => $size,
                        'modified' => date( 'c', filemtime( $child_functions ) ),
                        'code'     => $this->sanitizer->sanitize_code( file_get_contents( $child_functions ) ),
                    );
                } else {
                    $result['child_theme'] = array(
                        'path'       => str_replace( ABSPATH, '', $child_functions ),
                        'size'       => $size,
                        '_truncated' => true,
                        '_reason'    => 'File exceeds ' . ( ASA_MAX_FILE_SIZE / 1024 ) . 'KB limit',
                        'code'       => $this->sanitizer->sanitize_code(
                            file_get_contents( $child_functions, false, null, 0, ASA_MAX_FILE_SIZE )
                        ),
                    );
                }
            }

            // Parent theme functions.php (if child theme is active)
            if ( is_child_theme() ) {
                $parent_functions = get_template_directory() . '/functions.php';
                if ( file_exists( $parent_functions ) ) {
                    $size = filesize( $parent_functions );
                    // Parent theme functions.php is usually huge — just collect metadata
                    $result['theme'] = array(
                        'path'     => str_replace( ABSPATH, '', $parent_functions ),
                        'size'     => $size,
                        'modified' => date( 'c', filemtime( $parent_functions ) ),
                        '_note'    => 'Parent theme functions.php — metadata only (full code not collected to save space)',
                    );
                }
            }
        } catch ( \Throwable $e ) {
            $result['_error'] = $e->getMessage();
        }

        return $result;
    }

    /**
     * Child Theme Files
     */
    public function collect_theme_files() {
        $files_data = array();
        $theme_dir  = get_stylesheet_directory();

        try {
            if ( ! is_dir( $theme_dir ) ) {
                return array( '_error' => 'Theme directory not found' );
            }

            // Collect PHP, CSS, JS files from child theme (not functions.php — that's separate)
            $allowed_extensions = array( 'php', 'css', 'js' );
            $skip_files = array( 'functions.php' ); // already collected separately
            $skip_dirs = array( 'node_modules', 'vendor', '.git', 'assets/fonts' );

            $files = $this->scan_directory( $theme_dir, $allowed_extensions, $skip_files, $skip_dirs );

            foreach ( $files as $file_path ) {
                $size = filesize( $file_path );
                $relative_path = str_replace( $theme_dir . '/', '', $file_path );
                $extension = pathinfo( $file_path, PATHINFO_EXTENSION );

                $file_entry = array(
                    'path'      => $relative_path,
                    'extension' => $extension,
                    'size'      => $size,
                    'modified'  => date( 'c', filemtime( $file_path ) ),
                );

                if ( $size <= ASA_MAX_FILE_SIZE ) {
                    $content = file_get_contents( $file_path );
                    $file_entry['code'] = ( $extension === 'php' )
                        ? $this->sanitizer->sanitize_code( $content )
                        : $this->sanitizer->sanitize_text( $content, 'code' );
                } else {
                    $file_entry['_truncated'] = true;
                    $file_entry['_reason'] = 'File exceeds size limit';
                }

                $files_data[] = $file_entry;
            }
        } catch ( \Throwable $e ) {
            return array( '_error' => $e->getMessage() );
        }

        return $files_data;
    }

    /**
     * Theme Info — basic metadata about active theme.
     */
    public function collect_theme_info() {
        $theme = wp_get_theme();
        $info = array(
            'name'         => $theme->get( 'Name' ),
            'version'      => $theme->get( 'Version' ),
            'author'       => $theme->get( 'Author' ),
            'template'     => $theme->get( 'Template' ),
            'is_child'     => is_child_theme(),
            'theme_uri'    => $theme->get( 'ThemeURI' ),
            'text_domain'  => $theme->get( 'TextDomain' ),
        );

        if ( is_child_theme() ) {
            $parent = wp_get_theme( $theme->get( 'Template' ) );
            $info['parent'] = array(
                'name'    => $parent->get( 'Name' ),
                'version' => $parent->get( 'Version' ),
            );
        }

        return $info;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // UTILITIES
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Recursively scan a directory for files with specific extensions.
     */
    private function scan_directory( $dir, $extensions, $skip_files = array(), $skip_dirs = array(), $depth = 0, $max_depth = 5 ) {
        $results = array();

        if ( $depth > $max_depth ) {
            return $results;
        }

        $items = @scandir( $dir );
        if ( ! is_array( $items ) ) {
            return $results;
        }

        foreach ( $items as $item ) {
            if ( $item === '.' || $item === '..' ) {
                continue;
            }

            $path = $dir . '/' . $item;

            if ( is_dir( $path ) ) {
                // Skip excluded directories
                $should_skip = false;
                foreach ( $skip_dirs as $skip ) {
                    if ( strpos( $path, $skip ) !== false ) {
                        $should_skip = true;
                        break;
                    }
                }
                if ( ! $should_skip ) {
                    $results = array_merge( $results, $this->scan_directory( $path, $extensions, $skip_files, $skip_dirs, $depth + 1, $max_depth ) );
                }
            } elseif ( is_file( $path ) ) {
                $extension = pathinfo( $item, PATHINFO_EXTENSION );
                if ( in_array( strtolower( $extension ), $extensions, true ) && ! in_array( $item, $skip_files, true ) ) {
                    $results[] = $path;
                }
            }

            // Safety: don't collect more than 100 files
            if ( count( $results ) >= 100 ) {
                break;
            }
        }

        return $results;
    }
}
