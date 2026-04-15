This plugin has **two separate UIs** that coexist:
- **Legacy UI** (classic, "wbs") — the original interface, still fully supported
- **New UI** ("wbsng") — the newer recommended interface

Both register as WooCommerce shipping methods and support **shipping zones** (zone-instanced methods) as well as a **global method** (not tied to any zone).

---

### How Configs Are Stored

#### Legacy UI (wbs)
Each shipping method instance stores its config in a dedicated WordPress option:

```
wbs_{instance_id}_config   ← for zone-instanced methods (e.g. wbs_3_config, wbs_7_config)
wbs_config                 ← for the global (non-zoned) method (instance_id = 0)
```

Retrieve with:
```php
$config = get_option('wbs_3_config'); // example for instance ID 3
```

#### New UI (wbsng)
Same pattern, but with `wbsng` prefix:
```
wbsng_{instance_id}_config  ← for zone-instanced methods (e.g. wbsng_3_config)
wbsng_config                ← for the global method
```

Retrieve with:
```php
$config = get_option('wbsng_3_config');
```

#### Global Plugin Settings
```php
$settings = get_option('wbs_settings');       // global behavior settings
$globalMethods = get_option('wbs_global_methods'); // which UI handles the global method
```

---

### Global Plugin Settings (`wbs_settings`)

| Key | Type | Default | Description |
|---|---|---|---|
| `preferCustomPackagePrice` | `bool` | `true` | When `true`, uses custom/overridden package prices instead of the standard WooCommerce cart item price for shipping calculations. |
| `includeNonShippableItems` | `bool` | `false` | When `true`, items marked as non-shippable (virtual/downloadable) are included in weight/price calculations. Can also be overridden via the `wbs_include_non_shippable_items` filter. |

#### Global Method UI Switch (`wbs_global_methods`)

| Value | Meaning |
|---|---|
| `only-wbs` | Only the legacy UI handles the global shipping method. |
| `only-wbsng` | Only the new UI handles the global shipping method (default if wbsng is active). |
| `both` | Both UIs are active for the global method. |

---

### Legacy UI Config Structure (`wbs_*_config`)

The config is a PHP array with the following top-level keys:

```php
[
  'enabled' => true,   // bool — whether this method instance is active
  'rules'   => [ ... ] // array of rule objects (see below)
]
```

#### Rule Object (legacy)

Each item in `rules` is an array:

```php
[
  'meta' => [
    'enabled' => true,         // bool — whether this rule is active (default: true)
    'title'   => 'My Rule',    // string — label shown to customer for this rate
    'taxable' => true,         // bool — whether shipping charge is taxable
  ],
  'conditions' => [
    'destination' => [
      'mode'      => 'include', // 'include' | 'exclude' | 'all'
      'locations' => ['GR', 'GR:I', 'DE'] // array of country codes or "CC:STATE" strings
    ],
    'weight' => [
      'range' => [
        'min' => 0,    // numeric — minimum cart weight (in store weight unit, e.g. kg)
        'max' => 10,   // numeric — maximum cart weight (exclusive upper bound)
        'minInclusive' => true,
        'maxInclusive' => true,
      ]
    ],
    'subtotal' => [
      'range' => [
        'min' => 0,    // numeric — minimum cart subtotal
        'max' => 100,  // numeric — maximum cart subtotal
      ],
      'tax'      => false, // bool — include taxes in subtotal for condition check
      'discount' => true,  // bool — apply discounts to subtotal for condition check
    ],
  ],
  'charges' => [
    'base'   => 5.00,  // numeric — flat base fee added to every matching shipment
    'weight' => [
      'cost' => 1.50,  // numeric — cost per weight unit (or per step)
      'step' => 1,     // numeric — weight step size (charge is applied per step)
      'skip' => 0,     // numeric — initial weight to skip before charging per-weight
    ],
    'shippingClasses' => [  // array — per-shipping-class overrides
      [
        'shippingClass' => '5',  // string — WC shipping class term_id
        'charges' => [
          'base'   => 2.00,
          'weight' => [ 'cost' => 0.5, 'step' => 1, 'skip' => 0 ]
        ]
      ]
    ]
  ],
  'modifiers' => [
    'clamp' => [
      'range' => [
        'min' => 0,    // numeric — minimum final charge (floor)
        'max' => 50,   // numeric — maximum final charge (ceiling/cap)
      ]
    ]
  ]
]
```

#### Charge Calculation Logic (legacy)

1. Start with `charges.base` (flat fee).
2. Add per-weight cost: `charges.weight.cost` × (weight − `skip`) / `step` (rounded up to next step).
3. If shipping classes are defined in `charges.shippingClasses`, items matching those classes use their own `base` + `weight` charges instead of the default.
4. Apply `modifiers.clamp` to cap the result between min and max.

---

### New UI Config Structure (`wbsng_*_config`)

The config is a PHP array (stored as a WordPress option) with this top-level structure:

```php
[
  'methods'  => [ ... ],  // array of Method objects
  'settings' => [ ... ],  // document-level settings
]
```

#### Document-Level Settings

```php
'settings' => [
  'disableSplitShipping' => false, // bool — when true, prevents splitting a cart across multiple methods/rules
]
```

#### Method Object (new UI)

Each item in `methods`:

```php
[
  'disabled' => false,   // bool — if true, this method is inactive
  'name'     => 'Standard Shipping', // string — label shown to customer
  'rules'    => [ ... ], // array of Rule objects (see below)
  'settings' => [
    'price' => [
      'afterTaxes'     => false, // bool — use tax-inclusive price for price conditions
      'afterDiscounts' => true,  // bool — use discounted price for price conditions (default: true)
    ]
  ]
]
```

#### Rule Object (new UI)

Each item in `rules`:

```php
[
  'disabled' => false,   // bool — if true, this rule is skipped
  'name'     => '',      // string — optional label override for this rate (falls back to method name)

  'locations' => [       // destination condition
    'include' => true,   // bool — true = whitelist, false = blacklist
    'tree'    => 'all'   // 'all' = match everywhere, OR nested array: ['GR' => ['I' => 'all'], 'DE' => 'all']
                         // Keys are country codes; nested keys are state codes
  ],

  'shclasses' => [       // shipping class condition
    'include' => true,   // bool — true = only these classes, false = exclude these classes
    'items'   => ['5', '8'] // array of WC shipping class term_id strings
  ],

  'weight' => [          // weight range condition (null = no restriction)
    'min' => 0,          // numeric — minimum cart weight (inclusive)
    'max' => 10,         // numeric — maximum cart weight (exclusive)
  ],

  'price' => [           // cart price range condition (null = no restriction)
    'min' => 0,          // numeric — minimum cart price (inclusive)
    'max' => 100,        // numeric — maximum cart price (exclusive)
  ],

  'charge' => [          // the shipping cost formula
    'base' => 5.00,      // numeric — flat base fee
    'rate' => 1.50,      // numeric — cost per weight unit (or per step)
    'step' => 1,         // numeric — weight step size (0 = continuous, not stepped)
    'skip' => 0,         // numeric — initial weight to skip before applying rate
  ],

  'action' => null,      // null = 'pass' (default), OR:
                         // ['type' => 'finish']  — stop processing further rules after this one
                         // ['type' => 'cancel']  — deny/block shipping entirely if this rule matches
                         // ['type' => 'require'] — deny shipping if this rule does NOT match
                         // ['type' => 'drop', 'items' => null] — drop matched items (exclude from further rules)
]
```

#### Charge Calculation Logic (new UI)

Same formula as legacy:
1. `base` flat fee.
2. Plus: `rate` × ceil((weight − `skip`) / `step`) — if `step` is 0, it's `rate × (weight − skip)` continuously.
3. Result is the shipping cost for items matched by this rule.

Multiple rules within a method are **additive** — each matching rule's charge is summed. Rules are processed in order; `action` controls flow (stop, deny, drop items, require).

---

### How to Read All Instances

To find all configured WBS instances, query the `wp_options` table for options matching the naming pattern:

```sql
SELECT option_name, option_value
FROM wp_options
WHERE option_name REGEXP '^wbs(ng)?(_[0-9]+)?_config$';
```

Or in PHP:
```php
global $wpdb;
$rows = $wpdb->get_results(
    "SELECT option_name, option_value FROM {$wpdb->options}
     WHERE option_name REGEXP '^wbs(ng)?(_[0-9]+)?_config$'"
);
```

Each row is one shipping method instance. The instance ID is the number in the option name (e.g. `wbsng_5_config` → instance ID 5). No number = global method.

---

### Quick Summary for AI Interpretation

When analyzing a store's weight-based shipping setup, look for:

- **Which UI is in use?** → Check `wbs_global_methods`. Options with `wbs_` prefix = legacy UI; `wbsng_` prefix = new UI. Both may coexist.
- **How many shipping method instances exist?** → Count options matching `wbs(ng)?(_\d+)?_config`.
- **What are the shipping rates?** → Each instance has `rules` (legacy) or `methods[].rules` (new UI). Each rule defines conditions + a charge formula.
- **What triggers a rate?** → Conditions: destination (country/state), weight range, price range, shipping class.
- **What is the cost?** → `charge.base` (flat) + `charge.rate` per weight unit/step, after skipping `charge.skip` weight.
- **Are there per-shipping-class overrides?** → Legacy: `charges.shippingClasses[]`. New UI: separate rules with `shclasses` condition.
- **Is there a cost cap/floor?** → Legacy: `modifiers.clamp.range`. New UI: not present (use multiple rules with `cancel` action instead).
- **Does the method apply to all destinations or specific ones?** → `conditions.destination` (legacy) or `rule.locations` (new UI). `mode: 'all'` / `tree: 'all'` = worldwide.
- **Does price calculation include taxes/discounts?** → New UI: `method.settings.price.afterTaxes` / `afterDiscounts`. Legacy: `conditions.subtotal.tax` / `discount`.
- **Is split shipping disabled?** → New UI only: `settings.disableSplitShipping`.
- **Are non-shippable items included in weight?** → Global setting: `wbs_settings.includeNonShippableItems`.
