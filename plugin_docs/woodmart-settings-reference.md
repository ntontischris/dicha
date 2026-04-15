# Woodmart Theme — Features & Capabilities Guide

This document describes the built-in WooCommerce features of the Woodmart theme.
Use `search_settings("theme", "setting_name")` to check actual values per shop.

---

## Shipping Progress Bar

Shows customers how much more they need to spend to qualify for free shipping. Displays a visual progress bar on cart, mini-cart, checkout, or single product pages.

**Admin:** Theme Options > Shop > Shipping Progress Bar

| Setting ID | Description |
|---|---|
| `shipping_progress_bar_enabled` | Enable/disable the free shipping progress bar |
| `shipping_progress_bar_calculation` | How to calculate threshold: "default" (from WC shipping settings) or "custom" (manual amount) |
| `shipping_progress_bar_amount` | Free shipping threshold amount (used when calculation = "custom") |
| `shipping_progress_bar_base_price` | Base price for calculation (subtotal before/after discounts) |
| `shipping_progress_bar_include_coupon` | Whether to include or exclude coupon discounts from the calculation |
| `shipping_progress_bar_location_card_page` | Show on cart page |
| `shipping_progress_bar_location_mini_cart` | Show in mini cart widget |
| `shipping_progress_bar_location_checkout` | Show on checkout page |
| `shipping_progress_bar_location_single_product` | Show on single product page |
| `shipping_progress_bar_message_initial` | Message shown before threshold is met. Use `[remainder]` placeholder for remaining amount |
| `shipping_progress_bar_message_success` | Message shown when free shipping is achieved |

---

## Buy Now Button

Adds a "Buy Now" button alongside "Add to Cart" that takes the customer directly to checkout, skipping the cart page.

**Admin:** Theme Options > Shop > Buy Now

| Setting ID | Description |
|---|---|
| `buy_now_enabled` | Enable/disable the Buy Now button on product pages |
| `buy_now_redirect` | Where to redirect after click: "checkout" or "cart" |

---

## Visitor Counter

Displays a live (or simulated) count of people currently viewing a product to create urgency.

**Admin:** Theme Options > Shop > Visitor Counter

| Setting ID | Description |
|---|---|
| `counter_visitor_enabled` | Enable/disable the visitor counter |
| `counter_visitor_data_source` | Data source: "live_data" (real) or "fake_data" (random range) |
| `counter_visitor_data_source_min_number` | Minimum fake visitor count |
| `counter_visitor_data_source_max_number` | Maximum fake visitor count |
| `counter_visitor_live_mode` | Enable real-time live counter updates |
| `counter_visitor_ajax_update` | Use AJAX to update the counter without page reload |
| `counter_visitor_live_duration` | Duration in seconds between live counter updates |

---

## Sold Counter

Shows how many units of a product have been sold recently, creating social proof.

**Admin:** Theme Options > Shop > Sold Counter

| Setting ID | Description |
|---|---|
| `sold_counter_enabled` | Enable/disable the sold counter |
| `sold_counter_sales_type` | Data source: "real_data" (actual orders) or "fake_data" (random range) |
| `sold_counter_shown_after` | Minimum number of sales before showing the counter |
| `sold_counter_min_count` | Minimum fake sold count |
| `sold_counter_max_count` | Maximum fake sold count |
| `sold_counter_hide_on_outofstock` | Hide counter for out-of-stock products |
| `sold_counter_timeframe` | Timeframe number for "sold in the last X" display |
| `sold_counter_timeframe_period` | Timeframe unit: "minutes", "hours", "days" |
| `sold_counter_transient_hours` | Cache duration in hours for sold data |

---

## Frequently Bought Together

Displays a bundle of products commonly purchased together on the single product page, encouraging higher order values.

**Admin:** Theme Options > Shop > Frequently Bought Together

| Setting ID | Description |
|---|---|
| `bought_together_enabled` | Enable/disable the frequently bought together section |
| `bought_together_column` | Number of product columns on desktop |
| `bought_together_column_tablet` | Number of product columns on tablet |
| `bought_together_column_mobile` | Number of product columns on mobile |
| `bought_together_form_width` | Width of the bought-together form section |

---

## Free Gifts

Allows offering free gift products when cart conditions are met (e.g., spend thresholds).

**Admin:** Theme Options > Shop > Free Gifts

| Setting ID | Description |
|---|---|
| `free_gifts_enabled` | Enable/disable the free gifts feature |
| `free_gifts_limit` | Maximum number of free gifts per order |
| `free_gifts_allow_multiple_identical_gifts` | Allow the same gift product to be added more than once |
| `free_gifts_price_format` | How to display the gift price: "text" (e.g., "Free") or "price" (shows original crossed out) |
| `free_gift_on_cart` | Show free gift selection on cart page |
| `free_gifts_table_location` | Position of the gifts table on the cart page |
| `free_gift_on_checkout` | Show free gift selection on checkout page |

---

## Estimate Delivery

Displays estimated delivery dates on product pages, cart, checkout, and order emails.

**Admin:** Theme Options > Shop > Estimate Delivery

| Setting ID | Description |
|---|---|
| `estimate_delivery_enabled` | Enable/disable estimated delivery display |
| `estimate_delivery_show_on_single_product` | Show on single product page |
| `estimate_delivery_show_on_mini_cart` | Show in mini cart widget |
| `estimate_delivery_show_on_cart_page` | Show on cart page |
| `estimate_delivery_show_on_checkout_page` | Show on checkout page |
| `estimate_delivery_show_on_order_details` | Show on order details page |
| `estimate_delivery_show_on_email_order` | Show in order confirmation email |
| `estimate_delivery_show_overall` | Show overall delivery estimate for the entire order |
| `estimate_delivery_display_format` | Display format template for the delivery text |
| `estimate_delivery_date_format` | Date format: "default" (WP setting) or custom format |
| `estimate_delivery_fragments_enable` | Use AJAX fragments to update delivery estimates dynamically |

---

## Waitlist (Back in Stock Notifications)

Lets customers subscribe to out-of-stock products and get notified when they are restocked.

**Admin:** Theme Options > Shop > Waitlist

| Setting ID | Description |
|---|---|
| `waitlist_enabled` | Enable/disable the waitlist feature |
| `waitlist_for_loggined` | Restrict waitlist to logged-in users only |
| `waitlist_form_state` | Form display state: "current_state" (show for out-of-stock) |
| `waitlist_fragments_enable` | Use AJAX fragments for waitlist button |
| `waitlist_wait_interval` | Minimum interval in seconds between notification emails |
| `waitlist_enable_privacy_checkbox` | Show privacy consent checkbox on waitlist form |
| `waitlist_privacy_checkbox_text` | Text for the privacy consent checkbox |

---

## Price Tracker (Price Drop Alerts)

Allows customers to subscribe to price changes on products they are interested in.

**Admin:** Theme Options > Shop > Price Tracker

| Setting ID | Description |
|---|---|
| `price_tracker_enabled` | Enable/disable the price tracker feature |
| `price_tracker_for_loggined` | Restrict to logged-in users only |
| `price_tracker_use_loggedin_email` | Auto-fill email for logged-in users |
| `price_tracker_desired_price` | Allow customers to set a desired target price |
| `price_tracker_enable_privacy_checkbox` | Show privacy consent checkbox |
| `price_tracker_fragments_enable` | Use AJAX fragments for the tracker button |

---

## Abandoned Cart Recovery

Tracks abandoned carts and can send recovery emails with optional discount coupons.

**Admin:** Theme Options > Shop > Abandoned Cart

| Setting ID | Description |
|---|---|
| `cart_recovery_enabled` | Enable/disable abandoned cart tracking |
| `recover_guest_cart_enabled` | Track guest (non-logged-in) carts via email capture |
| `recover_guest_cart_enable_privacy_checkbox` | Show privacy checkbox for guest email capture |
| `recover_guest_cart_privacy_checkbox_text` | Privacy checkbox text |
| `abandoned_cart_timeframe` | Time before a cart is considered abandoned (number) |
| `abandoned_cart_timeframe_period` | Abandoned cart timeframe unit in seconds (e.g., 86400 = 1 day) |
| `abandoned_cart_delete_timeframe` | Days before abandoned cart data is deleted |
| `abandoned_cart_delete_timeframe_period` | Delete timeframe unit in seconds |
| `abandoned_cart_coupon_enabled` | Auto-generate discount coupons for recovery emails |
| `abandoned_cart_coupon_prefix` | Prefix for generated coupon codes |
| `abandoned_cart_coupon_amount` | Discount amount for recovery coupons |
| `abandoned_cart_coupon_discount_type` | Discount type: "percent" or "fixed_cart" |
| `abandoned_cart_delete_used_coupons` | Delete coupons after they are used |
| `abandoned_cart_delete_expired_coupons` | Delete expired recovery coupons |
| `abandoned_cart_coupon_timeframe` | Coupon validity period (number) |
| `abandoned_cart_coupon_timeframe_period` | Coupon validity unit in seconds |

---

## Wishlist

Built-in wishlist functionality. Customers can save products and optionally organize them into multiple lists.

**Admin:** Theme Options > Shop > Wishlist

| Setting ID | Description |
|---|---|
| `wishlist` | Enable/disable wishlist |
| `wishlist_page` | Page ID containing the `[woodmart_wishlist]` shortcode |
| `wishlist_logged` | Restrict wishlist to logged-in users only |
| `wishlist_bulk_action` | Enable bulk move/remove actions in wishlist |
| `wishlist_empty_text` | Text shown when wishlist is empty |
| `wishlist_expanded` | Enable multiple wishlists (customers can create named lists) |
| `wishlist_show_popup` | Show popup for selecting which wishlist to add to |
| `product_loop_wishlist` | Show wishlist button on product grid/loop |
| `wishlist_save_button_state` | Remember button state for already-wishlisted products (incompatible with full-page cache) |

---

## Compare

Side-by-side product comparison table. Customers can add products and compare attributes.

**Admin:** Theme Options > Shop > Compare

| Setting ID | Description |
|---|---|
| `compare` | Enable/disable product compare |
| `compare_page` | Page ID containing the `[woodmart_compare]` shortcode |
| `fields_compare` | Fields shown in compare table (e.g., description, sku, availability) |
| `empty_compare_text` | Text shown when compare list is empty |
| `compare_on_grid` | Show compare button on product grid/loop |
| `compare_save_button_state` | Remember button state for already-compared products |
| `compare_by_category` | Group compared products by category |
| `show_more_products_btn` | Show "Compare more products" button linking to the category |

---

## Quick View

AJAX-powered popup that shows product details without leaving the shop page.

**Admin:** Theme Options > Shop > Quick View

| Setting ID | Description |
|---|---|
| `quick_view` | Enable/disable quick view |
| `quick_view_layout` | Layout: "horizontal" or "vertical" |
| `quickview_width` | Popup width in pixels |
| `quick_view_variable` | Show variation selectors inside quick view |

---

## Quick Shop (Variable Products)

Allows purchasing variable products directly from the shop grid without opening the product page.

**Admin:** Theme Options > Shop > Quick Shop

| Setting ID | Description |
|---|---|
| `quick_shop_variable` | Enable quick shop for variable products |
| `quick_shop_variable_type` | Type: "select_options" (dropdown) or "add_to_cart" (direct add) |
| `quick_shop_clear_action` | What happens when clearing a selected variation |

---

## Catalog Mode

Hides all purchase functionality (add to cart buttons, cart, checkout) to use the shop as a product catalog only.

**Admin:** Theme Options > Shop > Catalog Mode

| Setting ID | Description |
|---|---|
| `catalog_mode` | Enable/disable catalog mode (hides all shopping functionality) |
| `login_prices` | Require login to see prices and add-to-cart buttons |

---

## Discount Rules (Quantity-Based Pricing)

Built-in quantity discount tables displayed on the product page.

**Admin:** Theme Options > Shop > Discounts

| Setting ID | Description |
|---|---|
| `discounts_enabled` | Enable/disable quantity discount rules |
| `show_discounts_table` | Show the discount pricing table on product pages |

---

## Product Labels (Badges)

Automatic and manual product badges: Sale, New, Hot (Featured), Out of Stock, and custom attribute labels.

**Admin:** Theme Options > Shop > Product Labels

| Setting ID | Description |
|---|---|
| `label_shape` | Badge shape: "rounded", "rectangular", etc. |
| `percentage_label` | Show sale discount as percentage instead of "Sale" text |
| `sale_label_bg_color` | Sale label background color |
| `sale_label_text_color` | Sale label text color |
| `new_label` | Enable "New" badge |
| `new_label_days_after_create` | Auto-apply "New" label for X days after product creation (0 = manual only) |
| `new_label_bg_color` | New label background color |
| `hot_label` | Enable "Hot" badge for Featured products |
| `hot_label_bg_color` | Hot label background color |
| `stock_label_bg_color` | Out of stock label background color |
| `attribute_label_bg_color` | Attribute-based label background color |

---

## Variable Products & Swatches

Controls how product variations are displayed — color/image swatches, variation galleries, and pricing behavior.

**Admin:** Theme Options > Shop > Variable Products

| Setting ID | Description |
|---|---|
| `grid_swatches_attribute` | Which attribute to show as swatches on the product grid |
| `swatches_limit` | Collapse long swatch lists on grid |
| `swatches_limit_count` | Max visible swatches before "show more" |
| `single_product_swatches_limit` | Collapse swatches on single product page |
| `single_product_swatches_limit_count` | Max visible swatches on single product |
| `swatches_use_variation_images` | Use variation images for swatch thumbnails instead of attribute term images |
| `swatches_labels_name` | Show selected option name as text label next to attribute title |
| `swatches_scroll_top_desktop` | Scroll to top when selecting a variation on desktop |
| `swatches_scroll_top_mobile` | Scroll to top when selecting a variation on mobile |
| `variation_gallery` | Enable additional image galleries per variation |
| `variation_gallery_storage_method` | Data storage: "new" or "old" (affects import/export compatibility) |
| `ajax_variation_threshold` | Number of variations before switching to AJAX loading |
| `show_filtered_variation_image` | Show variation image matching the selected filter on grid |
| `hide_larger_price` | Hide the higher price in variable product price ranges |
| `single_product_variations_price` | Remove duplicate price display when a variation is selected |
| `linked_variations` | Enable linked variations (show each variation as a separate product) |
| `show_single_variation` | Show individual variations in shop catalog |
| `hide_variation_parent` | Hide the parent variable product when showing single variations |

---

## Product Page Layout & Gallery

Controls the single product page layout, image gallery, thumbnails, and zoom behavior.

**Admin:** Theme Options > Product > Layout / Gallery

| Setting ID | Description |
|---|---|
| `single_product_style` | Page layout style (numbered presets affecting image/content width ratio) |
| `product_design` | Design preset: "default", "sticky", etc. |
| `product_sticky` | Make product description sticky on scroll |
| `product_summary_shadow` | Add shadow to the product summary block |
| `single_full_width` | Stretch product page to full container width |
| `image_action` | Main image click: "zoom" (lens zoom), "popup" (photoswipe lightbox), or "none" |
| `photoswipe_icon` | Show "Click to enlarge" icon |
| `product_slider_auto_height` | Auto-adjust carousel height for different image sizes |
| `thums_position` | Thumbnail gallery position: "left", "bottom", "right", or "without" |
| `single_product_thumbnails_vertical_items` | Number of visible thumbnails in vertical layout |
| `single_product_thumbnails_items_desktop` | Number of visible thumbnails in horizontal layout |
| `single_product_main_gallery_video` | Show product video in the main gallery carousel |
| `main_gallery_center_mode` | Enable center mode in the main gallery carousel |

---

## Add to Cart Behavior

Controls what happens when a product is added to the cart and sticky add-to-cart bar behavior.

**Admin:** Theme Options > Shop / Product

| Setting ID | Description |
|---|---|
| `add_to_cart_action` | After add to cart: "widget" (open mini cart), "popup" (confirmation popup), or "nothing" |
| `add_to_cart_action_timeout` | Auto-hide the mini cart widget after adding |
| `add_to_cart_action_timeout_number` | Seconds before auto-hiding the widget |
| `mini_cart_quantity` | Show quantity +/- controls inside the mini cart widget |
| `single_ajax_add_to_cart` | Enable AJAX add to cart on single product page |
| `single_sticky_add_to_cart` | Show sticky add-to-cart bar when scrolling down |
| `mobile_single_sticky_add_to_cart` | Enable sticky add-to-cart on mobile devices |

---

## SKU Display Options

Controls where SKU numbers are shown throughout the shop.

**Admin:** Theme Options > Shop > SKU

| Setting ID | Description |
|---|---|
| `show_sku_in_mini_cart` | Show SKU in mini cart widget |
| `show_sku_in_cart` | Show SKU on cart page |
| `show_sku_in_checkout_page` | Show SKU on checkout page |
| `show_sku_in_thank_you_page` | Show SKU on order details / thank you page |
| `show_sku_in_email_order` | Show SKU in order confirmation emails |
| `show_sku_on_ajax` | Show SKU in AJAX search results |

---

## Product Archive (Shop Page)

Controls the shop page grid, filters, pagination, and AJAX navigation.

**Admin:** Theme Options > Product Archive

| Setting ID | Description |
|---|---|
| `ajax_shop` | Enable AJAX for filters, categories, and pagination (no page reload) |
| `ajax_scroll` | Scroll to top after AJAX filter/pagination |
| `shop_view` | Default view mode: "grid" or "list" |
| `products_columns` | Products per row on desktop |
| `products_columns_tablet` | Products per row on tablet |
| `products_columns_mobile` | Products per row on mobile |
| `products_spacing` | Gap between products in grid (pixels) |
| `shop_per_page` | Products per page |
| `per_page_links` | Show "per page" selector |
| `per_page_options` | Available per-page options (comma-separated, -1 = show all) |
| `shop_pagination` | Pagination type: "pagination", "load_more", "infinite" |
| `per_row_columns_selector` | Show column count selector for customers |
| `products_masonry` | Enable masonry grid for products with different heights |
| `products_different_sizes` | Enable mixed-size grid (some products double width) |
| `products_hover` | Predefined hover layout: "base", "alt", "icons", "quick", etc. |
| `hover_image` | Show secondary image on hover |
| `grid_gallery` | Show product gallery thumbnails on grid |
| `product_quantity` | Show quantity input on product hover in grid |
| `shop_countdown` | Show sale countdown timer on grid products |
| `categories_under_title` | Show product category under title in grid |
| `brands_under_title` | Show product brand under title in grid |
| `sku_under_title` | Show SKU under title in grid |
| `stock_status_position` | Stock status badge position: "thumbnail" or "content" |
| `grid_stock_progress_bar` | Show stock progress bar on grid products |
| `products_bordered_grid` | Add borders between products |
| `products_with_background` | Add background color to product cards |
| `products_shadow` | Add shadow to product cards |
| `base_hover_mobile_click` | On mobile: first click opens product (true) or shows hover content (false) |

---

## Shop Sidebar & Filters

Controls sidebar position, off-canvas filters, and filter widget behavior.

**Admin:** Theme Options > Product Archive > Sidebar / Filters

| Setting ID | Description |
|---|---|
| `shop_layout` | Sidebar position: "sidebar-left", "sidebar-right", "full-width" |
| `shop_sidebar_width` | Sidebar width (column count out of 12) |
| `shop_hide_sidebar_desktop` | Use off-canvas sidebar on desktop |
| `shop_hide_sidebar_tablet` | Use off-canvas sidebar on tablet |
| `shop_hide_sidebar` | Use off-canvas sidebar on mobile |
| `sticky_filter_button` | Sticky filter button fixed on screen for mobile |
| `shop_filters` | Enable top-of-page filter area (above products) |
| `shop_filters_type` | Filter content: "widgets" or HTML block |
| `shop_filters_always_open` | Keep filter area always expanded |
| `shop_filters_close` | Prevent filter area from closing after clicking a filter |
| `categories_toggle` | Accordion toggle for category widget (useful with many subcategories) |
| `widgets_scroll` | Enable scroll inside filter widgets |
| `widget_heights` | Max height for filter widgets before scrolling (pixels) |
| `shop_widgets_collapse` | Collapse sidebar widgets: "disable", "all", or "filters_only" |

---

## Shop Page Title & Categories

Controls the shop page header area including category navigation and title.

**Admin:** Theme Options > Product Archive > Page Title / Categories

| Setting ID | Description |
|---|---|
| `shop_title` | Show/hide shop page title |
| `shop_page_breadcrumbs` | Show breadcrumbs on shop page |
| `cat_desc_position` | Category description position: "before" or "after" products |
| `shop_categories` | Show categories menu in page title area |
| `shop_categories_ancestors` | Show only ancestor categories of the current category |
| `show_categories_neighbors` | Show sibling categories when current has no children |
| `shop_products_count` | Show product count next to each category |
| `shop_page_title_hide_empty_categories` | Hide categories with no products |

---

## Product Tabs

Controls the tabs (Description, Additional Info, Reviews, Custom) on single product pages.

**Admin:** Theme Options > Product > Tabs

| Setting ID | Description |
|---|---|
| `product_tabs_layout` | Tab style: "tabs", "accordion", or "all_open" |
| `product_tabs_location` | Tab position: "standard" or "after_image" |
| `product_accordion_state` | Accordion default: "first" open or "all_closed" |
| `hide_tabs_titles` | Hide redundant headings inside tab content |
| `enable_description_tab` | Show description tab |
| `enable_additional_info_tab` | Show additional information tab |
| `enable_reviews_tab` | Show reviews tab |
| `custom_product_tabs_enabled` | Enable custom product tabs (per-product) |
| `legacy_product_tabs_enabled` | Enable the 3 legacy global custom tabs |
| `additional_tab_title` | First custom tab title (empty = disabled) |
| `additional_tab_2_title` | Second custom tab title |
| `additional_tab_3_title` | Third custom tab title |

---

## Reviews

Controls product review display, rating criteria, and image uploads in reviews.

**Admin:** Theme Options > Product > Reviews

| Setting ID | Description |
|---|---|
| `reviews_location` | Where reviews appear: "tabs" or "after_content" |
| `reviews_section_columns` | Layout: "one-column" or "two-column" |
| `reviews_form_location` | Form position: "before" or "after" existing reviews |
| `reviews_style` | Review card style preset |
| `reviews_columns` | Number of review columns on desktop |
| `reviews_enable_pros_cons` | Enable pros/cons fields in review form |
| `reviews_enable_likes` | Enable like/dislike voting on reviews |
| `show_reviews_purchased_indicator` | Show "Verified Buyer" badge |
| `reviews_sorting` | Enable review sorting options |
| `single_product_comment_images` | Allow image uploads in reviews |
| `single_product_comment_images_count` | Max images per review |
| `single_product_comment_images_upload_size` | Max image upload size (MB) |
| `single_product_comment_images_required` | Require at least one image in reviews |
| `reviews_rating_summary` | Show rating summary bar chart |
| `reviews_rating_summary_filter` | Allow filtering reviews by star rating |
| `reviews_rating_by_criteria` | Enable multi-criteria ratings (e.g., Quality, Value) |
| `review_reminder_enabled` | Send review reminder emails after purchase |
| `review_reminder_sending_timeframe` | Days after order completion before sending reminder |

---

## Cart Page

Controls cart page layout and behavior.

**Admin:** Theme Options > Shop > Cart

| Setting ID | Description |
|---|---|
| `cart_totals_layout` | Cart totals section layout: "layout-1" or "layout-2" |
| `update_cart_quantity_change` | Auto-update cart when quantity changes (no "Update cart" button needed) |
| `empty_cart_text` | Text shown when cart is empty |

---

## Checkout Page

Controls checkout page enhancements.

**Admin:** Theme Options > Shop > Checkout

| Setting ID | Description |
|---|---|
| `checkout_fields_enabled` | Enable custom checkout field editor |
| `checkout_show_product_image` | Show product images in checkout order review |
| `checkout_product_quantity` | Show quantity controls in checkout order review |
| `checkout_remove_button` | Show remove button in checkout order review |
| `checkout_link_to_product` | Link product names to product pages in checkout |

---

## Thank You Page

Customize the order confirmation / thank you page.

**Admin:** Theme Options > Shop > Thank You Page

| Setting ID | Description |
|---|---|
| `thank_you_page_content_type` | Extra content type: "text" or "html_block" |
| `thank_you_page_extra_content` | Custom text content for the thank you page |
| `thank_you_page_html_block` | HTML Block ID for thank you page content |
| `thank_you_page_default_content` | Show/hide default WooCommerce order details |

---

## Brands

Custom taxonomy for product brands, shown on product pages and as a filter.

**Admin:** Theme Options > Shop > Brands

| Setting ID | Description |
|---|---|
| `brands_attribute` | Which product attribute to use as "Brand" |
| `product_page_brand` | Show brand logo/name on single product page |
| `product_brand_location` | Brand position: "about_title" (above title) or other locations |
| `brand_tab` | Show a dedicated tab with brand description |
| `brand_tab_name` | Use brand name as tab title (e.g., "About Nike") |
| `show_product_brand` | Show brand in product meta section |

---

## Size Guides

Enables product-specific or global size guide tables displayed in a popup.

**Admin:** Theme Options > Shop > Size Guides

| Setting ID | Description |
|---|---|
| `size_guides` | Enable/disable size guides feature |

---

## AJAX Search

Enhanced product search with live results, SKU search, and synonym support.

**Admin:** Theme Options > General > Search

| Setting ID | Description |
|---|---|
| `search_by_sku` | Include SKU in search results |
| `search_by_product_categories` | Search within category names |
| `search_by_product_tag` | Search within tag names |
| `search_by_product_attributes` | Search within attribute values |
| `search_by_product_brands` | Search within brand names |
| `enqueue_posts_results` | Show blog post results alongside product results |
| `popular_requests` | Predefined popular search terms shown as quick buttons |
| `search_synonyms` | Search synonym definitions (format: "key = value1, value2") |
| `relevanssi_search` | Use Relevanssi plugin for AJAX search (if installed) |

---

## Performance (WooCommerce-Related)

Performance settings that affect shop loading and behavior.

**Admin:** Theme Options > Performance

| Setting ID | Description |
|---|---|
| `lazy_loading` | Lazy load images (load on scroll) |
| `lazy_loading_bg_images` | Lazy load background images in Gutenberg blocks |
| `lazy_loading_offset` | Start loading images X pixels before they enter viewport |
| `lazy_effect` | Image appearance animation: "none" or "fade" |
| `disable_wordpress_lazy_loading` | Disable native WordPress loading="lazy" attribute |
| `disable_owl_mobile_devices` | Disable Swiper slider on mobile (use native scroll) |
| `inline_critical_css` | Inline large CSS files to reduce render-blocking |
| `rocket_delay_js_exclusions` | Add WoodMart JS files to WP Rocket delay exclusion list |
| `local_google_fonts` | Host Google Fonts locally (GDPR compliance + performance) |
| `preload_lcp_image` | Priority-load the Largest Contentful Paint image |
| `mobile_optimization` | Remove desktop header DOM on mobile devices |

---

## Promo & Marketing Popups

Promotional popups, header banners, and cookie consent notices.

**Admin:** Theme Options > General

| Setting ID | Description |
|---|---|
| `promo_popup` | Enable promotional popup |
| `promo_popup_hide_mobile` | Hide promo popup on mobile devices |
| `popup_event` | Trigger: "time" (delay) or "scroll" |
| `promo_timeout` | Popup delay in milliseconds |
| `popup_pages` | Pages visited before showing popup |
| `promo_version` | Increment to re-show popup to users who closed it |
| `header_banner` | Enable thin promotional banner above header |
| `header_banner_link` | URL for the entire banner area |
| `header_close_btn` | Show close button on header banner |
| `header_banner_version` | Increment to re-show banner to users who closed it |
| `cookies_info` | Enable cookie consent notice bar |
| `cookies_text` | Cookie notice message text |
| `cookies_policy_page` | Link to privacy policy page |
| `age_verify` | Enable age verification popup |

---

## Mobile Bottom Navbar

Sticky navigation bar at the bottom of mobile screens with quick-access buttons.

**Admin:** Theme Options > General > Mobile Bottom Navbar

| Setting ID | Description |
|---|---|
| `sticky_toolbar` | Enable/disable mobile sticky navbar |
| `sticky_toolbar_label` | Show text labels under navbar icons |
| `sticky_toolbar_fields` | Buttons to display (array: shop, sidebar, wishlist, cart, account, etc.) |

---

## Login / My Account

Controls the login/registration page and my account dashboard.

**Admin:** Theme Options > Login

| Setting ID | Description |
|---|---|
| `login_tabs` | Show tabs for login/register forms |
| `reg_title` | Registration form title |
| `reg_text` | Registration description text |
| `login_title` | Login form title |
| `login_text` | Login description text |
| `my_account_links` | Show icon-based navigation on my account dashboard |

---

## Email Marketing Consent

Collect marketing email consent during checkout or account registration.

**Admin:** Theme Options > Shop > Email Marketing

| Setting ID | Description |
|---|---|
| `email_marketing_consent_enabled` | Enable marketing consent checkbox |
| `email_subscription_individual_control` | Allow customers to manage individual email preferences |

---

## Out of Stock Sorting

Controls whether out-of-stock products are pushed to the end of catalog listings.

**Admin:** Theme Options > Shop

| Setting ID | Description |
|---|---|
| `show_out_of_stock_at_the_end` | Move out-of-stock products to the end of shop listings |

---

## Quick Summary for AI Interpretation

When a customer asks about a Woodmart theme feature, use this mapping:

| Customer asks about... | Check these settings |
|---|---|
| Free shipping bar / progress bar | `shipping_progress_bar_*` |
| Buy now / skip cart | `buy_now_*` |
| How many people viewing / urgency | `counter_visitor_*` |
| Products sold / social proof | `sold_counter_*` |
| Bundle / bought together | `bought_together_*` |
| Free gift / gift with purchase | `free_gifts_*` |
| Delivery date / shipping estimate | `estimate_delivery_*` |
| Back in stock / notify me | `waitlist_*` |
| Price drop alert / price watch | `price_tracker_*` |
| Abandoned cart / recovery email | `cart_recovery_*`, `abandoned_cart_*` |
| Wishlist / favorites | `wishlist*` |
| Compare products | `compare*` |
| Quick view / preview | `quick_view*` |
| Color swatches / size swatches | `swatches_*`, `grid_swatches_*`, `variation_gallery*` |
| Product labels / badges / sale tag | `label_shape`, `percentage_label`, `new_label*`, `hot_label*` |
| Catalog mode / hide prices | `catalog_mode`, `login_prices` |
| Quantity discounts / bulk pricing | `discounts_*` |
| Size chart / size guide | `size_guides` |
| Product tabs / custom tabs | `product_tabs_*`, `additional_tab_*`, `custom_product_tabs_*` |
| Reviews / ratings | `reviews_*`, `single_product_comment_images*` |
| Shop layout / columns | `products_columns*`, `shop_per_page`, `shop_view` |
| Filters / sidebar | `shop_layout`, `shop_filters*`, `shop_hide_sidebar*` |
| AJAX / no page reload | `ajax_shop`, `single_ajax_add_to_cart` |
| Search / find products | `search_by_*`, `popular_requests`, `search_synonyms` |
| Performance / speed | `lazy_loading*`, `mobile_optimization`, `inline_critical_css` |
| Popup / promotion | `promo_popup*`, `header_banner*` |
| Cookie notice / GDPR | `cookies_*`, `local_google_fonts` |
| Checkout customization | `checkout_*` |
| Review reminder email | `review_reminder_*` |
