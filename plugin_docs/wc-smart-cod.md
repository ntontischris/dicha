All settings for this plugin are stored in the WordPress option **`woocommerce_cod_settings`** (same option used by WooCommerce's native COD gateway, extended by this plugin). You can retrieve them with:

```php
$settings = get_option('woocommerce_cod_settings');
```

---

### Native WooCommerce COD Settings (also present in this option)

These are the base WooCommerce COD fields, also visible in the same settings page:

| Key | Type | Description |
|---|---|---|
| `enabled` | `yes`/`no` | Whether the COD payment method is active at all. |
| `title` | string | The label shown to the customer at checkout (e.g. "Cash on delivery"). |
| `description` | string | Description shown to the customer when COD is selected. |
| `instructions` | string | Text added to the order confirmation email and thank-you page. |
| `enable_for_methods` | array of strings | If non-empty, COD is only available for these shipping method instance IDs (native WC zone-method restriction). When this is set, the plugin's own `shipping_zone_method_restriction` is ignored. |
| `enable_for_virtual` | `yes`/`no` | Whether COD is available for virtual/downloadable-only orders. |

---

### Smart COD — Restriction Settings

Each restriction can operate in two modes: **exclude** (disable COD when condition matches) or **include** (enable COD only when condition matches). The mode per restriction is stored as a JSON-encoded object in `restriction_settings` (see below).

| Key | Type | Description |
|---|---|---|
| `shipping_zone_restrictions` | array of zone IDs (integers) | Restrict COD based on WooCommerce shipping zones. Zone IDs are WC internal IDs. |
| `country_restrictions` | array of country codes | Restrict COD for specific countries (ISO 2-letter codes, e.g. `["GR","DE"]`). |
| `state_restrictions` | array of strings | Restrict COD for specific states/regions. Format: `COUNTRY_STATE` (e.g. `"GR_I"` for Attica, Greece). |
| `restrict_postals` | string (comma-separated) | Restrict COD for specific postal codes. Supports ranges with `...` delimiter (e.g. `55133,55400...55600`). |
| `city_restrictions` | string (comma-separated) | Restrict COD for specific cities (case-insensitive, free-text match). Note: unreliable since city is a free-text field. |
| `cart_amount_restriction` | numeric (price) | Restrict COD if cart total is **greater than or equal to** this amount. What counts as "cart total" is controlled by `cart_amount_mode`. |
| `user_role_restriction` | array of role slugs | Restrict COD for specific user roles (e.g. `["subscriber","guest"]`). `guest` is a special value for non-logged-in users. |
| `category_restriction` | array of term IDs | Restrict COD when cart contains products from these product categories. |
| `category_restriction_mode` | `one_product` / `all_products` | Controls when category restriction triggers: `one_product` = at least one cart item is in a restricted category; `all_products` = all cart items must be in restricted categories. |
| `product_restriction` | array of product/variation IDs | Restrict COD when cart contains specific products. |
| `product_restriction_mode` | `one_product` / `all_products` | Same logic as `category_restriction_mode` but for specific products. |
| `shipping_class_restriction` | array of shipping class term IDs | Restrict COD when cart contains products with specific shipping classes. |
| `shipping_class_restriction_mode` | `one_product` / `all_products` | Same logic as above but for shipping classes. |
| `shipping_zone_method_restriction` | array of strings | Restrict COD for specific shipping methods within specific zones. Format: `{zone_id}_{method_instance_id}` (e.g. `"2_5"`). **Ignored if `enable_for_methods` is set (native WC handles it instead).** |

#### `restriction_settings` (meta key)
- **Key:** `restriction_settings`
- **Type:** JSON-encoded object
- **Description:** Stores the **mode** (include=`1` / exclude=`0`) for each restriction key above. Example:
  ```json
  {
    "shipping_zone_restrictions": 0,
    "country_restrictions": 1,
    "restrict_postals": 0
  }
  ```
  - `0` = **exclude mode**: COD is disabled when the condition matches.
  - `1` = **include mode**: COD is enabled **only** when the condition matches (whitelist).

---

### Smart COD — Extra Fee Settings

| Key | Type | Description |
|---|---|---|
| `extra_fee` | numeric | The base extra fee charged for COD. Can be a fixed amount or a percentage (see `fee_settings`). Leave blank/zero for no charge. |
| `extra_fee_tax` | `enable` / `disable` | Whether the extra COD fee is taxable. Default: `disable`. |
| `percentage_rounding` | `round_up` / `round_down` | When the fee is a percentage, how to round the result. `round_up` = `ceil()`, `round_down` = `floor()`. Default: `round_up`. |
| `nocharge_amount` | numeric (price) | If the cart total reaches this amount, the extra COD fee is waived (set to 0). Works in both exclude and include mode (controlled via `restriction_settings`). |
| `cart_amount_mode` | array: `["tax","shipping"]` | Defines what is included in the "cart total" used for `cart_amount_restriction` and `nocharge_amount` checks. Can include `tax` (add taxes to total) and/or `shipping` (add shipping cost to total). |
| `different_charge_{zone_id}` | numeric | Override the extra fee for a specific shipping zone. Key format: `different_charge_2` for zone ID 2. |
| `zonemethod_different_charge_{zone_id}_method_{instance_id}` | numeric | Override the extra fee for a specific shipping method within a specific zone. Key format: `zonemethod_different_charge_2_method_5`. |
| `method_different_charge_{method_id}` | numeric | Override the extra fee for a specific shipping method type (by method slug, not instance). Key format: `method_different_charge_flat_rate`. |
| `include_country_different_charge_{country_code}` | numeric | Override the extra fee for a specific country (only active when `country_restrictions` is in **include/whitelist** mode). Key format: `include_country_different_charge_GR`. |

#### `fee_settings` (meta key)
- **Key:** `fee_settings`
- **Type:** JSON-encoded object
- **Description:** Stores the **fee type** (`fixed` or `percentage`) for each fee key. Example:
  ```json
  {
    "extra_fee": "percentage",
    "different_charge_2": "fixed",
    "method_different_charge_flat_rate": "fixed"
  }
  ```
  - `fixed` = the value is a flat currency amount.
  - `percentage` = the value is a % of the cart total (rounded per `percentage_rounding`).

---

### Smart COD — Messaging

| Key | Type | Description |
|---|---|---|
| `cod_unavailable_message` | array (keyed by reason) | Custom messages shown to the customer when COD is not available. Each key corresponds to a restriction reason. If a specific reason message is empty, falls back to `generic`. Keys: `generic`, `shipping_method`, `shipping_zone`, `country`, `state`, `postal`, `city`, `cart_amount`, `user_role`, `category`, `product`, `shipping_class`, `shipping_zone_method`. |

---

### Fee Priority Logic (how the plugin picks the fee at runtime)

The plugin applies the **first matching fee** from this priority order:

1. `nocharge_amount` — if cart is over/under the limit, fee = 0 (overrides everything)
2. `include_country_different_charge_{country}` — country-specific fee (include mode only)
3. `zonemethod_different_charge_{zone}_{method}` — zone + method specific fee
4. `different_charge_{zone}` — zone-specific fee
5. `method_different_charge_{method}` — method-specific fee
6. `extra_fee` — the default/base COD fee

---

### Quick Summary for AI Interpretation

When analyzing a store's COD setup, look for:

- **Is COD enabled?** → `enabled = yes`
- **What is the COD fee?** → `extra_fee` (check `fee_settings` for fixed vs %)
- **Are there zone/method-specific fees?** → keys starting with `different_charge_`, `zonemethod_different_charge_`, `method_different_charge_`
- **Is the fee waived above a certain order amount?** → `nocharge_amount`
- **Is COD restricted by country/zone/postal/city/role/product/category?** → check the respective restriction keys + `restriction_settings` for include/exclude mode
- **Is there a cart amount threshold that disables COD?** → `cart_amount_restriction`
- **Does the cart amount calculation include tax/shipping?** → `cart_amount_mode`
- **Are there custom unavailability messages?** → `cod_unavailable_message`
