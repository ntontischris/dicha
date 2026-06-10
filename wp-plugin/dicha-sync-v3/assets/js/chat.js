/**
 * ASA Chat — Handles chat communication with the AI agent.
 * Used by both the full admin page and the floating bubble.
 */
(function () {
  "use strict";

  var API_URL = (window.asaConfig && window.asaConfig.apiUrl) || "";
  var PROJECT_ID = (window.asaConfig && window.asaConfig.projectId) || "";
  var TOKEN = (window.asaConfig && window.asaConfig.token) || "";

  function getSessionId() {
    var key = "asa_session_" + PROJECT_ID;
    var sid = localStorage.getItem(key);
    if (!sid) {
      sid =
        "wp-" + Date.now() + "-" + Math.random().toString(36).substring(2, 10);
      localStorage.setItem(key, sid);
    }
    return sid;
  }

  function resetSession() {
    var key = "asa_session_" + PROJECT_ID;
    localStorage.removeItem(key);
  }

  /** Simple markdown-to-HTML (code blocks, inline code, bold, lists) */
  function renderMarkdown(text) {
    // 1. Extract code blocks to placeholders (prevent processing inside code)
    var codeBlocks = [];
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
      var idx = codeBlocks.length;
      codeBlocks.push(
        '<pre><code class="language-' +
          lang +
          '">' +
          escapeHtml(code.trim()) +
          "</code></pre>",
      );
      return "\n%%CODEBLOCK_" + idx + "%%\n";
    });

    // Inline code
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Bold
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // Italic
    text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");

    // Ordered lists (must come before unordered to avoid conflict)
    text = text.replace(/(^\d+\. .+$\n?)+/gm, function (match) {
      var items = match.trim().split("\n");
      var lis = items
        .map(function (item) {
          return "<li>" + item.replace(/^\d+\.\s*/, "") + "</li>";
        })
        .join("");
      return "<ol>" + lis + "</ol>";
    });

    // Unordered lists
    text = text.replace(/(^- .+$\n?)+/gm, function (match) {
      var items = match.trim().split("\n");
      var lis = items
        .map(function (item) {
          return "<li>" + item.replace(/^-\s*/, "") + "</li>";
        })
        .join("");
      return "<ul>" + lis + "</ul>";
    });

    // Paragraphs (double newline)
    text = text.replace(/\n\n/g, "</p><p>");
    // Single newline → <br>
    text = text.replace(/\n/g, "<br>");
    text = "<p>" + text + "</p>";

    // 2. Restore code blocks outside of <p> tags
    text = text.replace(/<p>%%CODEBLOCK_(\d+)%%<\/p>/g, function (_, idx) {
      return codeBlocks[parseInt(idx, 10)];
    });
    text = text.replace(/%%CODEBLOCK_(\d+)%%/g, function (_, idx) {
      return codeBlocks[parseInt(idx, 10)];
    });

    return text;
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function appendMessage(container, role, text) {
    var div = document.createElement("div");
    div.className = "asa-msg asa-msg-" + role;
    if (role === "agent") {
      div.innerHTML = renderMarkdown(text);
    } else {
      div.textContent = text;
    }
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  function showTyping(container) {
    var div = document.createElement("div");
    div.className = "asa-typing";
    div.id = "asa-typing-indicator";
    div.innerHTML = "<span></span><span></span><span></span>";
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  function hideTyping() {
    var el = document.getElementById("asa-typing-indicator");
    if (el) el.remove();
  }

  async function sendMessage(messagesContainer, input, sendBtn, tierSelect) {
    var text = input.value.trim();
    if (!text || !API_URL) return;

    appendMessage(messagesContainer, "user", text);
    input.value = "";
    input.style.height = "auto";
    sendBtn.disabled = true;

    showTyping(messagesContainer);

    try {
      var response = await fetch(API_URL + "/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + TOKEN,
          "X-Webhook-Secret": TOKEN,
        },
        body: JSON.stringify({
          project_id: PROJECT_ID,
          message: text,
          session_id: getSessionId(),
          model_tier: tierSelect ? tierSelect.value : "fast",
        }),
      });

      hideTyping();

      if (!response.ok) {
        var errText = await response.text();
        appendMessage(
          messagesContainer,
          "agent",
          "Error: " + response.status + " — " + errText,
        );
        sendBtn.disabled = false;
        return;
      }

      var data = await response.json();

      // Update session_id if server assigned one
      if (data.session_id) {
        localStorage.setItem("asa_session_" + PROJECT_ID, data.session_id);
      }

      var msgEl = appendMessage(messagesContainer, "agent", data.reply);

      // Show usage info
      if (data.usage && data.usage.cost_usd) {
        var meta = document.createElement("div");
        meta.className = "asa-msg-meta";
        meta.textContent =
          "Tools: " +
          (data.tools_used || []).join(", ") +
          " | Cost: $" +
          data.usage.cost_usd.toFixed(4);
        msgEl.appendChild(meta);
      }
    } catch (err) {
      hideTyping();
      appendMessage(
        messagesContainer,
        "agent",
        "Connection error: " + err.message,
      );
    }

    sendBtn.disabled = false;
    input.focus();
  }

  /** Initialize a chat UI (works for both admin page and bubble) */
  function initChat(containerEl) {
    var messagesEl = containerEl.querySelector("[data-asa-messages]");
    var inputEl = containerEl.querySelector("[data-asa-input]");
    var sendBtn = containerEl.querySelector("[data-asa-send]");
    var clearBtn = containerEl.querySelector("[data-asa-clear]");
    var tierSelect = containerEl.querySelector("[data-asa-tier]");

    if (!messagesEl || !inputEl || !sendBtn) return;

    sendBtn.addEventListener("click", function () {
      sendMessage(messagesEl, inputEl, sendBtn, tierSelect);
    });

    inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(messagesEl, inputEl, sendBtn, tierSelect);
      }
    });

    // Auto-resize textarea
    inputEl.addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        messagesEl.innerHTML = "";
        resetSession();
        appendMessage(
          messagesEl,
          "agent",
          "Session cleared. How can I help you?",
        );
      });
    }

    // Welcome message
    if (messagesEl.children.length === 0) {
      appendMessage(
        messagesEl,
        "agent",
        "Hi! I'm your WooCommerce AI assistant for **" +
          PROJECT_ID +
          "**.\nHow can I help you today?",
      );
    }
  }

  /** Initialize floating bubble */
  function initBubble() {
    var bubbleBtn = document.getElementById("asa-bubble-btn");
    var bubbleWindow = document.getElementById("asa-bubble-window");
    var closeBtn = document.getElementById("asa-bubble-close");

    if (!bubbleBtn || !bubbleWindow) return;

    bubbleBtn.addEventListener("click", function () {
      bubbleWindow.classList.toggle("open");
      if (bubbleWindow.classList.contains("open")) {
        var input = bubbleWindow.querySelector("[data-asa-input]");
        if (input) input.focus();
      }
    });

    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        bubbleWindow.classList.remove("open");
      });
    }

    initChat(bubbleWindow);
  }

  /** Initialize docs tab */
  function initDocs() {
    var docsContainer = document.getElementById("asa-docs-container");
    if (!docsContainer) return;

    loadDocs(docsContainer);

    var uploadForm = document.getElementById("asa-doc-upload-form");
    if (uploadForm) {
      uploadForm.addEventListener("submit", function (e) {
        e.preventDefault();
        uploadDoc(uploadForm, docsContainer);
      });
    }
  }

  async function loadDocs(container) {
    var listEl = container.querySelector(".asa-docs-list");
    if (!listEl) return;

    listEl.innerHTML = '<div style="padding:16px;color:#999;">Loading...</div>';

    try {
      var response = await fetch(
        API_URL + "/docs?project_id=" + encodeURIComponent(PROJECT_ID),
        {
          headers: {
            Authorization: "Bearer " + TOKEN,
            "X-Webhook-Secret": TOKEN,
          },
        },
      );
      var data = await response.json();

      if (!data.documents || data.documents.length === 0) {
        listEl.innerHTML =
          '<div style="padding:16px;color:#999;">No documents found for this project.</div>';
        return;
      }

      listEl.innerHTML = "";
      data.documents.forEach(function (doc) {
        var item = document.createElement("div");
        item.className = "asa-doc-item";
        item.innerHTML =
          "<div>" +
          "<strong>" +
          escapeHtml(doc.title || "Untitled") +
          "</strong>" +
          '<br><small style="color:#999;">' +
          (doc.type || "") +
          " | " +
          (doc.category || "") +
          " | " +
          (doc.scope || "") +
          "</small></div>" +
          '<button class="button button-link-delete" data-doc-id="' +
          doc.id +
          '">Delete</button>';
        listEl.appendChild(item);

        // Wire delete button
        var deleteBtn = item.querySelector("[data-doc-id]");
        deleteBtn.addEventListener("click", function () {
          var docId = this.getAttribute("data-doc-id");
          if (!confirm("Delete this document?")) return;
          deleteDoc(docId, item, container);
        });
      });
    } catch (err) {
      listEl.innerHTML =
        '<div style="padding:16px;color:#d63638;">Error loading docs: ' +
        err.message +
        "</div>";
    }
  }

  async function deleteDoc(docId, itemEl, docsContainer) {
    try {
      var response = await fetch(
        API_URL + "/docs/" + encodeURIComponent(docId),
        {
          method: "DELETE",
          headers: {
            Authorization: "Bearer " + TOKEN,
            "X-Webhook-Secret": TOKEN,
          },
        },
      );
      if (response.ok) {
        itemEl.remove();
      } else {
        alert("Delete failed: " + response.status);
      }
    } catch (err) {
      alert("Delete error: " + err.message);
    }
  }

  async function uploadDoc(form, docsContainer) {
    var title = form.querySelector('[name="doc_title"]').value.trim();
    var category = form.querySelector('[name="doc_category"]').value;
    var content = form.querySelector('[name="doc_content"]').value.trim();

    if (!title || !content) {
      alert("Title and content are required.");
      return;
    }

    var submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = "Uploading...";

    try {
      var response = await fetch(API_URL + "/docs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + TOKEN,
          "X-Webhook-Secret": TOKEN,
        },
        body: JSON.stringify({
          project_id: PROJECT_ID,
          type: "project_doc",
          title: title,
          content: content,
          category: category,
        }),
      });

      if (response.ok) {
        form.reset();
        loadDocs(docsContainer);
      } else {
        alert("Upload failed: " + response.status);
      }
    } catch (err) {
      alert("Upload error: " + err.message);
    }

    submitBtn.disabled = false;
    submitBtn.textContent = "Upload Document";
  }

  /** Initialize history tab */
  function initHistory() {
    var container = document.getElementById("asa-history-container");
    if (!container) return;
    var filterEl = container.querySelector(".asa-history-filter");
    var refreshBtn = container.querySelector(".asa-history-refresh");
    function reload() {
      loadLogs(container, filterEl ? filterEl.value : "");
    }
    if (filterEl) filterEl.addEventListener("change", reload);
    if (refreshBtn) refreshBtn.addEventListener("click", reload);
    reload();
  }

  async function loadLogs(container, statusFilter) {
    var listEl = container.querySelector(".asa-history-list");
    if (!listEl) return;
    listEl.innerHTML = '<div style="padding:16px;color:#999;">Loading...</div>';

    try {
      var url =
        API_URL +
        "/api/logs?project_id=" +
        encodeURIComponent(PROJECT_ID) +
        "&limit=100";
      if (statusFilter) url += "&status=" + encodeURIComponent(statusFilter);

      var response = await fetch(url, {
        headers: {
          Authorization: "Bearer " + TOKEN,
          "X-Webhook-Secret": TOKEN,
        },
      });
      var data = await response.json();

      if (!data.logs || data.logs.length === 0) {
        listEl.innerHTML =
          '<div style="padding:16px;color:#999;">Δεν υπάρχουν εγγραφές.</div>';
        return;
      }

      listEl.innerHTML = "";
      data.logs.forEach(function (log) {
        var item = document.createElement("div");
        item.className = "asa-history-item";
        item.style.cssText =
          "border:1px solid #e0e0e0;border-radius:6px;margin-bottom:8px;background:#fff;overflow:hidden;";
        var dot =
          log.status === "no_info"
            ? '<span title="Δεν απάντησε" style="color:#d63638;">&#9679;</span>'
            : '<span title="Απάντησε" style="color:#00a32a;">&#9679;</span>';
        var when = log.created_at
          ? new Date(log.created_at).toLocaleString()
          : "";
        item.innerHTML =
          // Clickable header — only the question is shown until expanded.
          '<div class="asa-history-header" style="display:flex;align-items:center;gap:8px;padding:10px 12px;cursor:pointer;">' +
          '<span class="asa-history-arrow" style="color:#999;font-size:11px;transition:transform .15s;">&#9656;</span>' +
          dot +
          '<span style="flex:1;font-weight:600;">' +
          escapeHtml(log.question || "") +
          "</span>" +
          '<span style="font-size:11px;color:#999;white-space:nowrap;">' +
          escapeHtml(when) +
          "</span></div>" +
          // Collapsible body — the answer, hidden by default.
          '<div class="asa-history-body" style="display:none;padding:0 12px 12px 32px;border-top:1px solid #f0f0f0;">' +
          '<div style="white-space:pre-wrap;color:#333;margin-top:10px;">' +
          escapeHtml(log.answer || "") +
          "</div>" +
          (log.tools_used
            ? '<div style="font-size:11px;color:#999;margin-top:8px;">&#128295; ' +
              escapeHtml(log.tools_used) +
              "</div>"
            : "") +
          "</div>";
        var header = item.querySelector(".asa-history-header");
        var body = item.querySelector(".asa-history-body");
        var arrow = item.querySelector(".asa-history-arrow");
        header.addEventListener("click", function () {
          var willOpen = body.style.display === "none";
          body.style.display = willOpen ? "block" : "none";
          arrow.style.transform = willOpen ? "rotate(90deg)" : "rotate(0deg)";
        });
        listEl.appendChild(item);
      });
    } catch (err) {
      listEl.innerHTML =
        '<div style="padding:16px;color:#d63638;">Σφάλμα: ' +
        escapeHtml(err.message) +
        "</div>";
    }
  }

  /** Tabs */
  function initTabs() {
    var tabs = document.querySelectorAll(".asa-tab");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var target = this.getAttribute("data-tab");
        document.querySelectorAll(".asa-tab").forEach(function (t) {
          t.classList.remove("active");
        });
        document.querySelectorAll(".asa-tab-content").forEach(function (c) {
          c.classList.remove("active");
        });
        this.classList.add("active");
        var contentEl = document.getElementById("asa-tab-" + target);
        if (contentEl) contentEl.classList.add("active");
      });
    });
  }

  // Auto-initialize on DOM ready
  document.addEventListener("DOMContentLoaded", function () {
    // Full admin page chat
    var adminChat = document.getElementById("asa-admin-chat");
    if (adminChat) {
      initChat(adminChat);
      initTabs();
      initDocs();
      initHistory();
    }

    // Floating bubble
    initBubble();
  });
})();
