<?php
/**
 * AI Agent admin page — Chat + Documents tabs.
 * Rendered under WooCommerce > AI Agent menu.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}
?>
<div class="wrap asa-chat-wrap">
    <h1>
        <span class="dashicons dashicons-format-chat" style="font-size:28px;margin-right:8px;"></span>
        AI Agent
        <span style="font-size:12px;color:#999;margin-left:10px;">Project: <?php echo esc_html( get_option( 'asa_project_id', '' ) ); ?></span>
    </h1>

    <!-- Tabs -->
    <div class="asa-tabs">
        <button class="asa-tab active" data-tab="chat">Chat</button>
        <button class="asa-tab" data-tab="docs">Documents</button>
        <button class="asa-tab" data-tab="history">Ιστορικό</button>
    </div>

    <!-- Chat Tab -->
    <div id="asa-tab-chat" class="asa-tab-content active">
        <div id="asa-admin-chat" class="asa-chat-container">
            <div class="asa-chat-messages" data-asa-messages></div>
            <div class="asa-chat-input-area">
                <select class="asa-tier-select" data-asa-tier aria-label="Ταχύτητα μοντέλου" title="Δυνατό = πιο ακριβές, λίγο πιο αργό">
                    <option value="fast" selected>Γρήγορο</option>
                    <option value="powerful">Δυνατό</option>
                </select>
                <textarea class="asa-chat-input" data-asa-input placeholder="Ask about your WooCommerce shop..." rows="1"></textarea>
                <button class="asa-chat-send" data-asa-send>Send</button>
                <button class="button" data-asa-clear title="Clear conversation" style="padding:10px;">&#x21bb;</button>
            </div>
        </div>
    </div>

    <!-- Documents Tab -->
    <div id="asa-tab-docs" class="asa-tab-content">
        <div id="asa-docs-container">
            <h3>Project Documents</h3>
            <p class="description">Upload project-specific documentation that the AI agent can reference when answering questions about this shop.</p>

            <div class="asa-docs-list"></div>

            <form id="asa-doc-upload-form" class="asa-doc-upload-form">
                <h3>Upload New Document</h3>
                <table class="form-table">
                    <tr>
                        <th><label for="doc_title">Title</label></th>
                        <td><input type="text" name="doc_title" id="doc_title" class="regular-text" required placeholder="e.g., Checkout customization notes"></td>
                    </tr>
                    <tr>
                        <th><label for="doc_category">Category</label></th>
                        <td>
                            <select name="doc_category" id="doc_category">
                                <option value="general">General</option>
                                <option value="shipping">Shipping</option>
                                <option value="payments">Payments</option>
                                <option value="checkout">Checkout</option>
                                <option value="cart">Cart</option>
                                <option value="tax">Tax</option>
                                <option value="products">Products</option>
                                <option value="orders">Orders</option>
                                <option value="emails">Emails</option>
                                <option value="theme">Theme</option>
                                <option value="security">Security</option>
                                <option value="performance">Performance</option>
                            </select>
                        </td>
                    </tr>
                    <tr>
                        <th><label for="doc_content">Content</label></th>
                        <td>
                            <textarea name="doc_content" id="doc_content" rows="10" class="large-text" required placeholder="Paste your documentation content here (Markdown supported)..."></textarea>
                        </td>
                    </tr>
                </table>
                <button type="submit" class="button button-primary">Upload Document</button>
            </form>
        </div>
    </div>

    <!-- History Tab -->
    <div id="asa-tab-history" class="asa-tab-content">
        <div id="asa-history-container">
            <h3>Ιστορικό συνομιλιών</h3>
            <p class="description">Τι ρώτησαν και τι απάντησε ο agent. Φίλτραρε «Δεν απάντησε» για να δεις πού χρειάζεται εγχειρίδιο.</p>
            <div class="asa-history-toolbar" style="margin:10px 0;display:flex;gap:10px;align-items:center;">
                <select class="asa-history-filter">
                    <option value="">Όλα</option>
                    <option value="answered">Απάντησε</option>
                    <option value="no_info">Δεν απάντησε</option>
                </select>
                <button class="button asa-history-refresh">Ανανέωση</button>
            </div>
            <div class="asa-history-list"></div>
        </div>
    </div>
</div>
