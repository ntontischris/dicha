"""Pydantic models for webhook payload and doc ingestion."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


# -- Webhook payload (matches WooCommerce plugin output exactly) -------

class PaymentGateway(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    title: str = ""
    method_title: str = ""
    enabled: str = "no"
    description: str = ""
    supports: list[str] = []
    settings: dict = {}
    form_fields_meta: dict = {}
    _error: str | None = None

    @field_validator("settings", "form_fields_meta", mode="before")
    @classmethod
    def coerce_list_to_dict(cls, v: object) -> dict:
        """PHP sends empty arrays as [] instead of {}."""
        if isinstance(v, list):
            return {}
        return v


class ShippingLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str = ""
    type: str = ""


class ShippingMethod(BaseModel):
    model_config = ConfigDict(extra="ignore")

    instance_id: int | None = None
    method_id: str = ""
    method_title: str = ""
    enabled: str = "no"
    cost: str | None = None
    tax_status: str = "taxable"
    requires: str | None = None
    min_amount: str | None = None
    class_costs: dict | None = None
    no_class_cost: str | None = None
    settings: dict = {}
    form_fields_meta: dict = {}

    @field_validator("settings", "form_fields_meta", mode="before")
    @classmethod
    def coerce_list_to_dict(cls, v: object) -> dict:
        """PHP sends empty arrays as [] instead of {}."""
        if isinstance(v, list):
            return {}
        return v


class ShippingZone(BaseModel):
    model_config = ConfigDict(extra="ignore")

    zone_id: int = 0
    zone_name: str = ""
    locations: list[ShippingLocation] = []
    methods: list[ShippingMethod] = []
    _error: str | None = None


class TaxSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tax_enabled: str = "no"
    prices_include_tax: str = "no"
    tax_based_on: str = ""
    tax_display_shop: str = ""
    tax_display_cart: str = ""
    tax_classes: list[str] = []
    tax_rates: list[dict] = []
    _error: str | None = None


class GeneralSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    currency: str = ""
    currency_position: str = ""
    store_country: str = ""
    store_city: str = ""
    enable_coupons: str = "no"
    enable_guest_checkout: str = "no"
    manage_stock: str = "no"
    _error: str | None = None


class WooCommerceData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str = ""
    active: bool = False
    payment_gateways: list[PaymentGateway] = []
    shipping_zones: list[ShippingZone] = []
    tax_settings: TaxSettings = TaxSettings()
    general_settings: GeneralSettings = GeneralSettings()


class CodeSnippet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str = 0
    name: str = ""
    code: str = ""
    description: str = ""
    source: str = ""
    active: bool = False
    scope: str = ""
    tags: str = ""
    _error: str | None = None


class FunctionsPhpEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str = ""


class FunctionsPhp(BaseModel):
    model_config = ConfigDict(extra="ignore")

    child_theme: FunctionsPhpEntry | None = None


class ThemeFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = ""
    extension: str = ""
    code: str = ""
    _error: bool | None = None
    _truncated: bool | None = None


class ThemeParent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""


class ThemeInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    version: str = ""
    is_child: bool = False
    parent: ThemeParent | None = None


class ThemeSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    theme_mods: dict = {}
    source: str = "customizer"
    framework: str = ""
    framework_options: dict = {}
    framework_option_key: str = ""


class ActivePlugin(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    version: str = ""
    author: str = ""
    description: str = ""
    file: str = ""


class PluginSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plugin_slug: str = ""
    plugin_name: str = ""
    plugin_file: str = ""
    settings: dict = {}


class WebhookInnerData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    woocommerce: WooCommerceData = WooCommerceData()
    active_plugins: list[ActivePlugin] = []
    plugin_settings: list[PluginSettings] = []
    code_snippets: list[CodeSnippet] = []
    functions_php: FunctionsPhp = FunctionsPhp()
    theme_files: list[ThemeFile] = []
    theme_info: ThemeInfo = ThemeInfo()
    theme_settings: ThemeSettings = ThemeSettings()


class WebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_id: str
    site_url: str = ""
    timestamp: str = ""
    wordpress_version: str = ""
    php_version: str = ""
    data: WebhookInnerData = WebhookInnerData()


# -- Doc ingestion payloads -------------------------------------------

class DocPayload(BaseModel):
    """Single document upload (company doc or project doc)."""

    project_id: str = "_global"
    type: str = "company_doc"
    title: str
    content: str
    category: str = "general"
    subcategory: str = ""
    tags: list[str] = []
    priority: int = 3


class BulkDocPayload(BaseModel):
    """Bulk document upload."""

    project_id: str = "_global"
    type: str = "company_doc"
    category: str = "general"
    documents: list[DocPayload]
