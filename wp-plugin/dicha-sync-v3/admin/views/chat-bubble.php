<?php
/**
 * Floating chat bubble — rendered on ALL WP admin pages.
 * Only visible to users with manage_woocommerce capability.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}
?>
<!-- Floating Bubble Button -->
<button id="asa-bubble-btn" class="asa-bubble-btn" title="AI Agent Chat">
    <span class="dashicons dashicons-format-chat" style="font-size:28px;line-height:1;"></span>
</button>

<!-- Floating Chat Window -->
<div id="asa-bubble-window" class="asa-bubble-window">
    <div class="asa-bubble-header">
        <span>AI Agent — <?php echo esc_html( get_option( 'asa_project_id', 'Shop' ) ); ?></span>
        <button id="asa-bubble-close" class="asa-bubble-close">&times;</button>
    </div>
    <div class="asa-bubble-messages" data-asa-messages></div>
    <div class="asa-bubble-input-area">
        <select class="asa-tier-select" data-asa-tier aria-label="Ταχύτητα μοντέλου" title="Δυνατό = πιο ακριβές, λίγο πιο αργό">
            <option value="fast" selected>Γρήγορο</option>
            <option value="powerful">Δυνατό</option>
        </select>
        <textarea class="asa-bubble-input" data-asa-input placeholder="Ask something..." rows="1"></textarea>
        <button class="asa-bubble-send" data-asa-send>Send</button>
    </div>
</div>
