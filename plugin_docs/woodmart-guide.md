# WoodMart Theme — Developer Feature Guide
> **Purpose:** This guide is a reference for junior developers working on WooCommerce sites built with the WoodMart theme. It covers the key built-in features, where to find their settings, and how they work at a high level. When a developer asks "can WoodMart do X?", this guide should help you answer confidently and point them in the right direction.

---

## HOW TO USE THIS GUIDE

Each feature entry follows a consistent structure:
- **What it does** — a plain-language description of the feature.
- **Where to set it up** — the exact WordPress admin path to find the settings.
- **How it works / key notes** — important details a developer needs to know.
- **Official docs** — link to the WoodMart documentation page (where available).

> **Agency note:** Some WoodMart built-in features are intentionally not used in our projects because we use dedicated third-party plugins instead (e.g. dynamic discounts, abandoned cart, free gifts, estimated delivery, checkout fields manager). Those features are listed and marked accordingly so you know they exist in the theme but are not activated on our builds.

---

## SECTION 1 — E-COMMERCE FEATURES

### 1.1 Wishlist

**What it does:** Allows customers to save products they like into a personal wishlist, and optionally share it with friends. Supports multiple wishlists per customer (e.g. "Holiday gifts", "Sports gear").

**Where to set it up:**
- Enable the feature: `Theme Settings → Shop → Wishlist` (toggle it on).
- Create the Wishlist page: `Dashboard → Pages → Add New`, then add the "Wishlist" element via WPBakery or Elementor.
- Set the Wishlist page: `Theme Settings → Shop → Wishlist → Select a page`.
- After saving, go to `Dashboard → Settings → Permalinks` and hit Save (required to flush rewrite rules).
- Add the Wishlist icon to the header: `WoodMart → Header Builder` → add the Wishlist element.

**Key notes:**
- Multiple wishlists is an optional sub-feature. Enable it at `Theme Settings → Shop → Wishlist → Enable multiple wishlists`. It is only available for logged-in users.
- "Show wishlists popup" lets customers choose which wishlist to add a product to directly from a popup.
- Admins can view all customer wishlists at `Dashboard → Products → Wishlists`, including a "Popular products" tab showing the most-wishlisted items.

**Official docs:** https://xtemos.com/docs-topic/wishlist/

---

### 1.2 Compare

**What it does:** Adds a product comparison feature, letting customers add products to a comparison table side-by-side to evaluate attributes and specs.

**Where to set it up:** `Theme Settings → Shop → Compare`. Enable the feature, select the compare page, and configure which attributes to show in the table.

**Key notes:** The compare button appears on product cards and product pages. Like Wishlist, you need to create a Compare page and assign it in the theme settings.

**Official docs:** https://xtemos.com/docs-topic/compare/

---

### 1.3 Frequently Bought Together

**What it does:** Displays a "Frequently bought together" block on the single product page, recommending additional products that customers commonly buy alongside the current one. This helps increase average order value.

**Where to set it up:** Configured on a per-product basis inside the product editor. Look for the "Frequently Bought Together" metabox on the product edit screen. You manually select which products to recommend.

**Key notes:** This is a theme-native feature — no plugin required. Products are set manually per product, not automatically calculated from order data.

**Official docs:** https://xtemos.com/docs-topic/frequently-bought-together/

---

### 1.4 Waitlist (for out-of-stock products)

**What it does:** When a product is out of stock, customers can register their email to be notified automatically when it becomes available again.

**Where to set it up:** `Theme Settings → Shop → Waitlist`. Enable the feature and configure the notification email content.

**Key notes:** Works for both simple and variable products. Customers who sign up appear in a list the admin can manage. The notification email is sent automatically when stock is updated.

**Official docs:** https://xtemos.com/docs-topic/waitlist/

---

### 1.5 Price Tracker & Price Drop Alerts

**What it does:** Allows customers to subscribe to price alerts on a specific product. If the price drops, they receive an email notification automatically.

**Where to set it up:** `Theme Settings → Shop → Price Tracker`. Enable it and configure the email notification settings.

**Key notes:** The "Track price" button appears on the product page. Customers enter their email and are notified when the price changes. Admins can see the list of tracked products and subscribers.

**Official docs:** https://xtemos.com/docs-topic/price-tracker/

---

### 1.6 Review Reminder Emails

**What it does:** Automatically sends an email to customers after they receive their order, asking them to leave a product review.

**Where to set it up:** `Theme Settings → Shop → Review Reminder`. Enable the feature and configure the delay (how many days after order completion to send the email) and the email content.

**Key notes:** This is WoodMart's built-in alternative to dedicated review plugin solutions. Works well for most stores without needing a separate plugin.

**Official docs:** https://xtemos.com/docs-topic/review-reminder/

---

### 1.7 Free Shipping Progress Bar

**What it does:** Shows a progress bar on the product page, mini cart, cart, and checkout indicating how much more the customer needs to spend to qualify for free shipping. A strong conversion tool to increase average order value.

**Where to set it up:** `Theme Settings → Shop → Free shipping bar`. From there you can configure:
- **Calculation** — either a fixed goal amount or based on WooCommerce shipping zones (dynamic per country).
- **Goal amount** — the cart total that unlocks free shipping.
- **Locations** — where the bar appears (mini cart, cart page, product page, etc.).
- **Messages** — customise the initial text (use the `[remainder]` shortcode to display the remaining amount) and the success message.
- **Coupon handling** — choose whether coupon discounts count toward or against the threshold.

**Important:** The progress bar is a visual indicator only. You also need to activate a "Free Shipping" method in `WooCommerce → Settings → Shipping` with the same minimum amount, otherwise free shipping won't actually be applied at checkout.

**Official docs:** https://xtemos.com/docs-topic/free-shipping-progress-bar/

---

### 1.8 Stock Progress Bar

**What it does:** Shows a visual progress bar on the product page indicating how much of the stock remains. Creates urgency (e.g. "Only 3 left!").

**Where to set it up:** `Theme Settings → Shop → Stock progress bar`. Enable it and set the threshold below which the bar becomes visible.

**Official docs:** https://xtemos.com/docs-topic/products-stock-progress-bar/

---

### 1.9 Product Sold Counter

**What it does:** Displays a "X sold" counter on the product page, showing social proof of how many units have been sold.

**Where to set it up:** `Theme Settings → Shop → Product sold counter`. Enable it and optionally configure what time period it counts (all time, last 30 days, etc.).

**Official docs:** https://xtemos.com/docs-topic/product-sold-counter/

---

### 1.10 Product Visitors Counter

**What it does:** Shows a live counter of how many people are currently viewing the product page (e.g. "🔥 8 people are looking at this right now"). Creates urgency.

**Where to set it up:** `Theme Settings → Shop → Product visitors counter`. Enable and configure the display text and counter behaviour.

**Official docs:** https://xtemos.com/docs-topic/product-visitors-counter/

---

### 1.11 Product Size Guides

**What it does:** Lets you create and attach size guide charts to products, which appear as a popup or tab on the product page when the customer clicks a "Size guide" link.

**Where to set it up:** Size guides are created as a custom post type: `Dashboard → WoodMart → Size Guides`. Once created, they can be assigned to individual products or product categories from the product editor.

**Official docs:** https://xtemos.com/docs-topic/size-guides/

---

### 1.12 Product Video

**What it does:** Allows you to embed a video on the product gallery — it appears alongside the product images as an extra gallery item (YouTube, Vimeo, or self-hosted).

**Where to set it up:** Inside the product editor, in the product gallery area. There is a field to add a video URL. No plugin or theme settings toggle needed — it's always available on each product.

**Official docs:** https://xtemos.com/docs-topic/product-video/

---

### 1.13 Advanced Product Reviews (with images)

**What it does:** Enhances WooCommerce's default review system. Customers can upload images with their reviews, giving social proof through real photos.

**Where to set it up:** `Theme Settings → Shop → Product Reviews`. Enable image uploads and configure moderation settings.

**Official docs:** https://xtemos.com/docs-topic/product-reviews/

---

### 1.14 Custom Product Labels

**What it does:** Lets you add stylised badges or labels to product images (e.g. "New", "Hot", "Best Seller") beyond WooCommerce's default "Sale" badge.

**Where to set it up:** Labels can be created at `Dashboard → WoodMart → Product Labels` and then assigned globally (by category/tag) or per-product inside the product editor.

**Official docs:** https://xtemos.com/docs-topic/product-labels/

---

### 1.15 Product Units of Measurement

**What it does:** Allows you to display a unit of measurement next to the product quantity input (e.g. "kg", "m", "pcs"), useful for stores selling products sold by weight or length.

**Where to set it up:** Configured per product inside the product editor. Look for the "Unit of measurement" field in the WoodMart product options metabox.

**Official docs:** https://xtemos.com/docs-topic/product-quantity-units-of-measurements/

---

### 1.16 Countdown Timer for Sale Products

**What it does:** Shows a live countdown timer on sale products, displaying how much time is left until the sale ends. Drives urgency.

**Where to set it up:** The countdown is triggered automatically from the sale end date set on each product (`Product → General → Sale price → Schedule`). Enable the display in `Theme Settings → Shop → Product countdown`.

**Official docs:** https://xtemos.com/docs-topic/product-sale-countdown/

---

### 1.17 Custom Product Tabs

**What it does:** Allows you to add custom content tabs to the single product page (alongside the default Description, Additional Information, and Reviews tabs). Useful for adding FAQs, care instructions, shipping info, etc.

**Where to set it up:** Custom tabs are created at `Dashboard → WoodMart → Custom Tabs`. They can be assigned globally (all products, specific categories) or per-product in the product editor.

**Official docs:** https://xtemos.com/docs-topic/custom-tabs/

---

### 1.18 Recently Viewed Products

**What it does:** Tracks which products a customer has visited and displays them in a product carousel or grid anywhere on the site — a helpful "come back to where you were" feature.

**Where to set it up:** Add a "Products (carousel or grid)" element anywhere via WPBakery or Elementor, and set the **Data source** option to "Recently viewed products". For sites using full-page caching (e.g. WP Rocket), also enable "Update with AJAX on page load" to ensure the list is personalised per visitor and not served from cache.

**Key notes:** To show this globally (e.g. in the pre-footer area on all pages), create an HTML Block (`Dashboard → WoodMart → HTML Blocks`) containing the element and place it in a global position.

**Official docs:** https://xtemos.com/docs-topic/recently-viewed-products/

---

### 1.19 Quick View

**What it does:** A modal popup that opens when a customer clicks a "Quick View" button on a product card in the shop grid, showing product images, title, price, description, and an add-to-cart button without navigating away from the shop page.

**Where to set it up:** `Theme Settings → Shop → Quick View`. Enable it and configure what content appears inside the popup.

---

### 1.20 Quick Shop

**What it does:** Similar to Quick View, but the add-to-cart functionality (including variation selection) opens inline on the shop grid card, without opening a separate popup. A faster experience for simple products.

**Where to set it up:** `Theme Settings → Shop → Quick Shop`.

---

### 1.21 Sticky Add to Cart Button

**What it does:** On the single product page, the Add to Cart button sticks to the top or bottom of the viewport as the user scrolls, so it's always visible and accessible.

**Where to set it up:** `Theme Settings → Shop → Sticky Add to Cart` (or configured via the Single Product Page Builder layout).

---

### 1.22 Buy Now Button

**What it does:** Adds a "Buy Now" button alongside the regular Add to Cart button, which adds the product to the cart and immediately redirects the customer to the checkout page — reducing steps to purchase.

**Where to set it up:** `Theme Settings → Shop → Buy Now Button`. Enable and optionally configure the button label.

**Official docs:** https://xtemos.com/docs-topic/buy-now-button/

---

### 1.23 Brands for Products (with Filter)

**What it does:** Adds a "Brands" taxonomy to your products, letting you assign a brand with logo and description to each product. Customers can filter and browse by brand on the shop page.

**Where to set it up:** Brands are managed at `Dashboard → Products → Brands`. Enable brand display in `Theme Settings → Shop → Brands`. A dedicated brand filter widget can be added to the shop sidebar using the filter builder.

**Official docs:** https://xtemos.com/docs-topic/product-brands/

---

### 1.24 Catalog Mode

**What it does:** Disables purchasing functionality site-wide (or per category/product), turning the store into a product catalogue without an Add to Cart button. Useful for B2B stores or showroom sites.

**Where to set it up:** `Theme Settings → Shop → Catalog Mode`. Enable globally or choose to configure it per product.

---

### 1.25 Search by SKU

**What it does:** Extends WooCommerce's default search to also search product SKUs, so customers or admins can find products by their SKU code.

**Where to set it up:** `Theme Settings → Shop → Search by SKU`. Toggle it on — no extra configuration needed.

---

## SECTION 2 — VARIABLE PRODUCTS & SWATCHES

### 2.1 Color & Image Swatches

**What it does:** Replaces the default WooCommerce dropdown selectors for variable product attributes (like color or size) with visual swatches — shown as colour circles, image thumbnails, or text buttons.

**Where to set it up:** Swatches work on **global attributes only** (not custom product-level attributes). Configure them at `Dashboard → Products → Attributes → [select attribute] → Configure items → Edit each value → Enable swatch`. From there, you can set a colour preview or image for each attribute value.

**Key notes:** Global display settings (e.g. which attribute drives swatches on the shop grid) are configured at `Theme Settings → Shop → Attribute swatches`.

**Official docs:** https://xtemos.com/docs-topic/variable-products-and-swatches/

---

### 2.2 Swatches on Shop Page (Grid)

**What it does:** Shows variation swatches directly on the product card in the shop grid, so customers can see and select a colour/size variant without visiting the product page.

**Where to set it up:** `Theme Settings → Shop → Attribute swatches → Grid swatch attribute to display`. Choose which attribute (e.g. color) to show on the grid cards.

---

### 2.3 Linked Variations

**What it does:** Allows different variations of a product to link to separate product pages. For example, a t-shirt in blue and red can each have their own URL and product page, while still being "linked" as variations of each other.

**Where to set it up:** Configured per product in the product editor. Requires products to be set up individually, then linked via the WoodMart Linked Variations metabox.

**Official docs:** https://xtemos.com/docs-topic/linked-variations/

---

### 2.4 Show Variations as Separate Products

**What it does:** Makes individual variations appear as standalone products in the shop grid (each with its own card, image, and Add to Cart), while still being variations of the same parent product.

**Where to set it up:** `Theme Settings → Shop → Show variations as products`, and/or enabled per attribute in the product attributes configuration.

**Official docs:** https://xtemos.com/docs-topic/show-single-variation/

---

### 2.5 Additional Variation Images Gallery

**What it does:** Each variation can have its own image gallery, not just a single featured image. When a customer selects a variation, the full gallery updates to show that variation's images.

**Where to set it up:** Inside the product editor, in the variation settings for each variation, there is a gallery field where multiple images can be uploaded.

---

### 2.6 AJAX Add to Cart for Variable & Grouped Products

**What it does:** By default, variable/grouped products in WooCommerce require a page reload to add to cart. WoodMart enables AJAX adding for these product types too, so the cart updates instantly without a page refresh.

**Where to set it up:** `Theme Settings → Shop → AJAX add to cart`. Enable globally.

---

## SECTION 3 — AJAX & PERFORMANCE

### 3.1 AJAX Shop Filters

**What it does:** Shop filters (by price, attribute, category, etc.) update the product grid dynamically without reloading the page. Much faster and more UX-friendly.

**Where to set it up:** This works automatically when you use WoodMart's built-in filter elements. Create filters via `Theme Settings → Shop → Filters` or the WooCommerce Layouts Builder (Shop Page Builder).

**Official docs (filters setup):** https://xtemos.com/docs-topic/how-to-create-filters-form/

---

### 3.2 AJAX Search with Live Results

**What it does:** The site search field shows live product suggestions as the customer types, including product images, names, and prices — without pressing Enter.

**Where to set it up:** `Theme Settings → Shop → Search`. Enable live search and configure the number of results and what to display (product image, SKU, price, etc.).

---

### 3.3 AJAX Add to Cart (All Product Types)

**What it does:** Adds products to the cart without a page reload on simple products, variable products, and grouped products.

**Where to set it up:** `Theme Settings → Shop → AJAX add to cart`.

---

### 3.4 Infinite Scroll & Load More

**What it does:** Instead of paginating the shop with numbered pages, WoodMart can automatically load more products as the user scrolls (infinite scroll) or via a "Load More" button.

**Where to set it up:** `Theme Settings → Shop → Pagination`. Choose between pagination, load more button, or infinite scroll.

---

### 3.5 Lazy Loading for Images

**What it does:** Images only load when they are about to enter the user's viewport, improving initial page load time and Core Web Vitals scores.

**Where to set it up:** `Theme Settings → Performance → Lazy loading`. Enable it (it may already be on by default in newer WoodMart versions).

**Official docs:** https://xtemos.com/docs-topic/image-lazy-loading/

---

### 3.6 LCP Preloading (Core Web Vitals)

**What it does:** WoodMart can preload the Largest Contentful Paint (LCP) image — usually the hero image or the first product image — so it loads as fast as possible and improves Google's Core Web Vitals score.

**Where to set it up:** `Theme Settings → Performance → Preload LCP Image`. Enable and configure which image to preload (typically the hero/banner image or main product image).

**Official docs:** https://xtemos.com/docs-topic/explanation-of-preload-lcp-image-option/

---

### 3.7 Smart Asset Loading (CSS/JS per page)

**What it does:** WoodMart only loads the CSS and JavaScript files needed for each specific page, instead of loading everything everywhere. This reduces page weight significantly on pages that don't use certain features.

**Where to set it up:** `Theme Settings → Performance → Smart assets loading`. This is a global toggle. Enable it and test thoroughly — on complex pages or with certain plugins, it may occasionally need exceptions.

---

## SECTION 4 — SHOP PAGE & PRODUCT GRID

### 4.1 Hover Image on Shop Page

**What it does:** When a customer hovers over a product card, the featured image swaps to a second product image (the first gallery image). Common in fashion/lifestyle stores.

**Where to set it up:** `Theme Settings → Shop → Product loop → Show second image on hover`. Enable it.

---

### 4.2 Products Per Page Selector

**What it does:** Adds a dropdown on the shop page letting customers choose how many products to display per page (e.g. 12, 24, 48).

**Where to set it up:** `Theme Settings → Shop → Products per page`. Enable the selector and define the available options.

---

### 4.3 Products Columns Selector

**What it does:** Lets customers switch the shop grid between different column layouts (e.g. 2, 3, or 4 columns) directly from the shop page.

**Where to set it up:** `Theme Settings → Shop → Columns switcher`. Enable it and configure which column options to offer.

---

### 4.4 Push Out-of-Stock Products to the End

**What it does:** Automatically moves out-of-stock products to the last pages of the shop grid, so in-stock products always appear first.

**Where to set it up:** `Theme Settings → Shop → Out-of-stock products` → enable "Show out-of-stock products at the end". Note: This requires WooCommerce's "Hide out of stock items from the catalog" to be disabled in `WooCommerce → Settings → Products → Inventory`.

**Official docs:** https://xtemos.com/docs-topic/automatically-push-out-of-stock-products-to-the-bottom-in-woodmart/

---

## SECTION 5 — SINGLE PRODUCT PAGE

### 5.1 Sticky Product Information

**What it does:** As the customer scrolls down the product page (past the image gallery), the product info column (title, price, Add to Cart) sticks to the top of the viewport so it's always visible.

**Where to set it up:** `Theme Settings → Shop → Single product → Sticky product info`. Enable it.

---

### 5.2 Sticky Product Images

**What it does:** Similarly, the product image gallery sticks to the viewport as the customer reads the product description below.

**Where to set it up:** `Theme Settings → Shop → Single product → Sticky product images`. Enable it.

---

### 5.3 Product Images Zoom

**What it does:** Allows customers to zoom into product images on hover or click, giving a magnified view for detail inspection.

**Where to set it up:** `Theme Settings → Shop → Single product → Images zoom`. Enable it and configure the zoom type (hover zoom or lightbox).

---

### 5.4 360° Product View

**What it does:** Supports a 360-degree rotating product view. You upload a series of images representing each angle of the product, and WoodMart plays them as a rotating animation when the customer drags or clicks.

**Where to set it up:** Inside the product editor, in the WoodMart product gallery area — look for the 360° gallery upload option.

---

### 5.5 Share Buttons on Product Page

**What it does:** Adds social sharing buttons (Facebook, Twitter/X, Pinterest, WhatsApp, etc.) to the product page.

**Where to set it up:** `Theme Settings → Shop → Single product → Share buttons`. Enable and choose which networks to show.

---

## SECTION 6 — HEADER & NAVIGATION

### 6.1 Header Builder

**What it does:** WoodMart includes a powerful drag-and-drop Header Builder that lets you construct completely custom headers with full control over layout, rows, columns, and which elements appear (logo, menu, search, cart, wishlist, etc.). You can create different headers for different pages or screen sizes.

**Where to set it up:** `WoodMart → Header Builder` in the WordPress admin. Create or edit header layouts there. Assign headers globally or per page.

**Official docs:** https://xtemos.com/docs-topic/woodmart-header-builder/

---

### 6.2 Sidebar Login Widget

**What it does:** A login form that can be added to a sidebar or off-canvas panel (rather than redirecting to the My Account page), keeping the customer on the current page.

**Where to set it up:** Add the "Login" widget to any sidebar or widget area via `Dashboard → Appearance → Widgets`, or place it in the header off-canvas panel via the Header Builder.

---

### 6.3 Mobile Bottom Navbar

**What it does:** A fixed navigation bar at the bottom of the screen on mobile devices, showing icons for Home, Shop, Cart, Account, and a customisable item. Common in modern mobile UX.

**Where to set it up:** `Theme Settings → Header → Mobile bottom navbar`. Enable and configure which icons appear.

---

### 6.4 Drill-Down Mobile Menu

**What it does:** On mobile, the navigation menu opens as a panel that "drills down" into sub-categories — tapping a parent category slides to reveal its children, rather than showing a full accordion expand.

**Where to set it up:** `Theme Settings → Header → Mobile menu type → Drill down`. This is a menu style option.

---

### 6.5 Custom Icons for Header Elements

**What it does:** Lets you upload and use custom SVG or image icons for header elements (cart icon, search icon, account icon, etc.) instead of the default WoodMart icons.

**Where to set it up:** Inside the Header Builder, when editing a header element (e.g. Cart), look for the icon upload option within that element's settings.

**Official docs:** https://xtemos.com/docs-topic/how-to-use-custom-icons/

---

## SECTION 7 — POPUPS & MARKETING TOOLS

### 7.1 Promo Popup (with Advanced Triggers)

**What it does:** A fully customisable promotional popup that can appear on any page. You control the content (text, images, forms, HTML blocks) and the trigger conditions — on page load, after X seconds, on scroll depth, on exit intent, or after X page views.

**Where to set it up:** `Dashboard → WoodMart → Popups` (or via the Popup Builder). Edit the content using WPBakery or Elementor. Configure triggers in the popup settings.

**Official docs (triggers):** https://xtemos.com/docs-topic/triggers/

---

### 7.2 Cookie Law / GDPR Popup

**What it does:** A cookie consent notification bar or popup shown to visitors to comply with GDPR and cookie law requirements.

**Where to set it up:** `Theme Settings → General → Cookie law info`. Enable it and customise the message and button text.

---

### 7.3 Age Verification Popup

**What it does:** Shows a popup asking visitors to confirm their age before entering the site. Useful for stores selling alcohol, tobacco, or adult products.

**Where to set it up:** `Theme Settings → General → Age verification`. Enable and customise the popup text and minimum age.

---

### 7.4 Maintenance Mode

**What it does:** Puts the site into maintenance mode, showing a custom page to visitors while the backend is accessible to admins.

**Where to set it up:** `Theme Settings → General → Maintenance mode`. Enable and select or create the maintenance page.

---

## SECTION 8 — CONTENT & LAYOUT TOOLS

### 8.1 HTML Blocks

**What it does:** A custom post type for reusable HTML/content blocks. You build content once (with WPBakery or Elementor) and can insert that block anywhere on the site using a shortcode or widget. Useful for global elements like a "Trusted by" strip, a promotional banner, or a Recently Viewed section.

**Where to set it up:** Create at `Dashboard → WoodMart → HTML Blocks`. Insert anywhere using the `[woodmart_html_block id="X"]` shortcode or the HTML Block element in the page builder.

**Official docs:** https://xtemos.com/docs-topic/html-blocks-usage/

---

### 8.2 WooCommerce Layout Builder

**What it does:** WoodMart includes a full WooCommerce layout builder for every major store page — single product, shop/archive, cart, checkout, thank you page, my account, and more. Lets you drag-and-drop the page structure without custom code.

**Where to set it up:** `WoodMart → WooCommerce Builder` (or access individual layouts: `WoodMart → Single Product Builder`, `WoodMart → Shop Builder`, etc.).

**Official docs:** https://xtemos.com/docs-topic/woodmart-woocommerce-layout-builder/

---

### 8.3 Custom 404 Page

**What it does:** Allows you to design a custom 404 error page using WPBakery or Elementor rather than relying on the default theme 404 template.

**Where to set it up:** Create a page and design it, then go to `Theme Settings → General → 404 page` and select it.

---

### 8.4 White Label Option

**What it does:** Hides WoodMart branding from the WordPress admin, useful when delivering client sites where you don't want the client to know which theme is used, or when building under your own agency brand.

**Where to set it up:** `Theme Settings → General → White label`. Enter your agency name and logo.

**Official docs:** https://xtemos.com/docs-topic/how-to-rebrand-the-theme-white-label/

---

## SECTION 9 — FEATURES WE DON'T USE (REPLACED BY THIRD-PARTY PLUGINS)

The following features exist natively in WoodMart but are intentionally not activated on our builds. We use dedicated third-party plugins for these instead, which offer more control and reliability.

**Dynamic Discounts & Tiered Pricing** — WoodMart has a built-in version, but we use a third-party plugin. (`Theme Settings → Shop → Dynamic discounts` — do not activate.)

**Free Gifts** — WoodMart has a built-in free gifts feature, but we use a third-party plugin. (`Theme Settings → Shop → Free gifts` — do not activate.)

**Abandoned Cart Recovery** — WoodMart has a basic built-in version, but we use a third-party plugin. (`Theme Settings → Shop → Abandoned cart` — do not activate.)

**Estimated Delivery Dates** — WoodMart has a built-in estimated delivery date display, but we use a third-party plugin. (`Theme Settings → Shop → Estimate delivery` — do not activate.)

**Checkout Fields Manager** — WoodMart has a built-in checkout field editor, but we use a third-party plugin. (`Theme Settings → Shop → Checkout fields manager` — do not activate.)

> If a client or project lead asks about any of these features, confirm the functionality exists but clarify that we handle it through a dedicated plugin — ask the project manager or lead developer which plugin is being used for that specific project.

---

## QUICK REFERENCE: WHERE ARE MOST SETTINGS?

Most WoodMart features live in one of these three places. When in doubt, start here:

**`Theme Settings`** (in the WordPress sidebar, labelled "WoodMart") — this is the main control panel for almost all theme features. It is organised into sections: General, Shop, Header, Performance, etc.

**`WoodMart → Header Builder`** — for anything header-related (layout, elements, responsive behaviour).

**`WoodMart → WooCommerce Builder`** — for the layout of shop pages, single product pages, cart, checkout, and account pages.

**Product editor (individual products)** — some features are configured per-product (size guides, product video, custom tabs, 360° gallery, linked variations).

**`Dashboard → Products → Attributes`** — for swatches configuration on global attributes.

---

## USEFUL LINKS

- Full WoodMart documentation: https://xtemos.com/documentation/woodmart/
- WoodMart support forum: https://xtemos.com/forums/forum/woodmart-premium-template/
- WoodMart YouTube tutorials: https://www.youtube.com/channel/UCu3loFwqqOQ9z-YTcnplK8w
