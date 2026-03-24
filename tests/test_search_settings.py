"""Tests for search_settings tool and settings-code bridge."""
from __future__ import annotations

from sync.extraction import detect_settings_domains


def test_detect_settings_domains_payments():
    hooks = ["woocommerce_available_payment_gateways", "init"]
    domains = detect_settings_domains(hooks)
    assert "settings:payments" in domains


def test_detect_settings_domains_shipping():
    hooks = ["woocommerce_package_rates"]
    domains = detect_settings_domains(hooks)
    assert "settings:shipping" in domains


def test_detect_settings_domains_checkout():
    hooks = ["woocommerce_cart_calculate_fees"]
    domains = detect_settings_domains(hooks)
    assert "settings:checkout" in domains


def test_detect_settings_domains_tax():
    hooks = ["woocommerce_tax_rate_data"]
    domains = detect_settings_domains(hooks)
    assert "settings:tax" in domains


def test_detect_settings_domains_none():
    hooks = ["wp_enqueue_scripts"]
    domains = detect_settings_domains(hooks)
    assert len(domains) == 0


def test_detect_settings_domains_multiple():
    hooks = ["woocommerce_available_payment_gateways", "woocommerce_package_rates"]
    domains = detect_settings_domains(hooks)
    assert "settings:payments" in domains
    assert "settings:shipping" in domains
