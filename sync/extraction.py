"""Auto-extract metadata from code: hooks, functions, category, language."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExtractedMeta:
    hooks: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    category: str = "general"
    subcategory: str = ""
    language: str = ""
    keywords: list[str] = field(default_factory=list)


# -- Regex patterns ----------------------------------------------------

_PHP_HOOKS = re.compile(
    r"(?:add_action|add_filter|do_action|apply_filters)"
    r"\s*\(\s*['\"]([^'\"]+)",
)
_PHP_FUNCTIONS = re.compile(r"function\s+(\w+)\s*\(")
_PHP_CLASSES = re.compile(r"class\s+(\w+)")
_JS_HOOKS = re.compile(r"wp\.hooks\.(?:addFilter|addAction)\s*\(\s*['\"]([^'\"]+)")
_JS_JQUERY = re.compile(r"(?:jQuery|\$)\s*\(\s*['\"]([^'\"]{2,40})['\"]")


# -- Category rules (hook pattern → category) -------------------------

_CATEGORY_RULES: list[tuple[str, str, str]] = [
    # (pattern, category, subcategory)
    ("shipping|package_rates|shipping_method|shipping_zone", "shipping", ""),
    ("flat_rate", "shipping", "flat_rate"),
    ("free_shipping", "shipping", "free_shipping"),
    ("table_rate", "shipping", "table_rate"),
    ("payment_gateway|available_payment|checkout_payment|woocommerce_payment", "payments", ""),
    ("stripe", "payments", "stripe"),
    ("checkout_field|checkout_process|checkout_order|checkout_update", "checkout", ""),
    ("cart_calculate|before_calculate_totals|cart_item|cart_contents|add_to_cart", "cart", ""),
    ("tax_rate|tax_class|calculate_tax|tax_display", "tax", ""),
    ("product_get_price|product_type|single_product|product_cat|product_loop", "products", ""),
    ("order_status|new_order|order_item|order_created|order_complete", "orders", ""),
    ("email_header|email_content|email_recipient|woocommerce_email", "emails", ""),
    ("enqueue_scripts|wp_head|template_redirect|template_include|wp_footer|body_class", "theme", ""),
    ("login|register|authenticate|password|user_role|capabilities", "security", ""),
    ("transient|cache|object_cache|preload", "performance", ""),
]


def _categorize_by_hooks(hooks: list[str], text: str = "") -> tuple[str, str]:
    """Determine category from hooks and text content."""
    combined = " ".join(hooks).lower() + " " + text.lower()

    for pattern, category, subcategory in _CATEGORY_RULES:
        if re.search(pattern, combined):
            return category, subcategory

    return "general", ""


# -- Language detection ------------------------------------------------

def _detect_language(code: str, file_path: str = "") -> str:
    """Detect programming language from code content or file extension."""
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    ext_map = {
        "php": "php",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "css": "css",
        "scss": "css",
        "html": "html",
        "twig": "html",
        "md": "markdown",
        "json": "json",
        "sql": "sql",
    }

    if ext in ext_map:
        return ext_map[ext]

    # Content-based detection
    if "<?php" in code or "function " in code and "$" in code:
        return "php"
    if "document." in code or "function(" in code or "=>" in code:
        return "javascript"
    if "{" in code and "}" in code and ":" in code and ";" in code and "$" not in code:
        return "css"

    return "php"  # default for WooCommerce context


# -- Main extraction ---------------------------------------------------

def extract_metadata(
    code: str,
    title: str = "",
    tags: str = "",
    file_path: str = "",
) -> ExtractedMeta:
    """Extract all metadata from a code chunk.

    Returns hooks, functions, classes, category, language, and keywords.
    """
    meta = ExtractedMeta()

    # Language
    meta.language = _detect_language(code, file_path)

    # Extract hooks and functions based on language
    if meta.language in ("php", ""):
        meta.hooks = list(dict.fromkeys(_PHP_HOOKS.findall(code)))
        meta.functions = list(dict.fromkeys(_PHP_FUNCTIONS.findall(code)))
        meta.classes = list(dict.fromkeys(_PHP_CLASSES.findall(code)))
    elif meta.language == "javascript":
        meta.hooks = list(dict.fromkeys(
            _JS_HOOKS.findall(code) + _PHP_HOOKS.findall(code)  # WP inline PHP+JS
        ))
        meta.functions = list(dict.fromkeys(_PHP_FUNCTIONS.findall(code)))

    # Category from hooks + title + tags
    search_text = f"{title} {tags}"
    meta.category, meta.subcategory = _categorize_by_hooks(meta.hooks, search_text)

    # Build keywords: title words + function names + hook names + tags
    kw_sources = [
        title,
        tags,
        " ".join(meta.functions),
        " ".join(meta.hooks[:5]),  # limit hook keywords
    ]
    raw_keywords = " ".join(kw_sources).split()
    # Deduplicate, filter short/common words
    seen: set[str] = set()
    for kw in raw_keywords:
        kw_clean = kw.strip(",.;:()[]{}\"'").lower()
        if len(kw_clean) > 2 and kw_clean not in seen:
            seen.add(kw_clean)
            meta.keywords.append(kw_clean)

    return meta
