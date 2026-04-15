This is a simple WooCommerce payment gateway plugin. All settings are stored in the WordPress option **`woocommerce_cop_settings`**. You can retrieve them with:

```php
$settings = get_option('woocommerce_cop_settings');
```

The gateway ID is `cop`.

---

### Settings Reference

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | `yes`/`no` | `no` | Whether the Cash on Pickup payment method is active at checkout. |
| `title` | string | `"Cash on pickup"` | The label shown to the customer at checkout. |
| `description` | string | `"Pay with cash on pickup."` | Description shown to the customer when this payment method is selected. |
| `instructions` | string | `"Pay with cash on pickup."` | Text added to the thank-you page after order placement. Also included in customer emails (only when the order has the `default_order_status` status). |
| `enable_for_methods` | array of strings | `[]` (empty = all methods) | If non-empty, Cash on Pickup is only available when the customer selects one of these shipping methods. Values are shipping rate IDs in `method_id:instance_id` format (e.g. `local_pickup:3`), or just `method_id` to match any instance of that method type (e.g. `local_pickup`). Leave empty to allow for all shipping methods. |
| `default_order_status` | string (WC status slug without `wc-` prefix) | `on-hold` | The order status automatically assigned when a Cash on Pickup order is placed (e.g. `on-hold`, `processing`, `pending`). |
| `exclusive_for_local` | `yes`/`no` | `no` | If `yes`, when the customer selects a **local pickup** shipping method, Cash on Pickup becomes the **only** available payment method (all other gateways are hidden). |
| `enable_for_virtual` | `yes`/`no` | `yes` | Whether Cash on Pickup is available for orders that contain only virtual/downloadable products (i.e. no physical shipping needed). |

---

### How `enable_for_methods` Works at Runtime

- If the array is **empty**: COP is available for all shipping methods.
- If the array is **non-empty**: COP is only shown when **all** chosen shipping packages use one of the listed methods. It matches both exact `method_id:instance_id` and generic `method_id` entries.

### How `exclusive_for_local` Works at Runtime

- When enabled (`yes`) and the customer selects **only local pickup** shipping methods at checkout, all other payment gateways are removed and only COP is shown.
- This uses `strpos($method, 'local_pickup')` to detect local pickup methods, so it also covers plugins like "Local Pickup Plus".

---

### Quick Summary for AI Interpretation

When analyzing a store's Cash on Pickup setup, look for:

- **Is it enabled?** → `enabled = yes`
- **What label does the customer see?** → `title`
- **What order status is set on placement?** → `default_order_status` (default: `on-hold`)
- **Is it restricted to specific shipping methods?** → `enable_for_methods` (empty = no restriction)
- **Does it force COP-only when local pickup is chosen?** → `exclusive_for_local = yes`
- **Is it available for virtual-only orders?** → `enable_for_virtual`
- **What text appears on the thank-you page and in emails?** → `instructions`

> **Note:** This plugin has **no extra fee functionality** and **no geographic/role/product restrictions** — unlike `wc-smart-cod`. It is a straightforward "Cash on Pickup" gateway with shipping method filtering and a local-pickup exclusivity feature only.
