# Κατάσταση Project — «Το από δω και πέρα»

**Ημερομηνία:** 2026-06-10 (go-live στη νέα υποδομή ολοκληρωμένο)

Αυτό το έγγραφο αποτυπώνει την **τρέχουσα** κατάσταση του WooCommerce AI Agent μετά τη μετάβαση στην υποδομή του πελάτη: τι υπάρχει και πού, τι δουλεύει, πώς γίνεται deploy, τι εκκρεμεί. Για το *πώς λειτουργεί* ο agent δες το [agent-overview-client.md](agent-overview-client.md)· για πλήρη οδηγό εγκατάστασης σε νέο server δες το [DEPLOYMENT.md](../DEPLOYMENT.md).

---

## 1. Τοπολογία — τι τρέχει πού

```
WooCommerce shops (plugin v2.5.5)
        │  HTTPS (sync + chat)
        ▼
https://woo.89-167-0-26.sslip.io          ← δημόσιο URL (Let's Encrypt)
        │  nginx vhost (woo-agent) → 127.0.0.1:8002
        ▼
Server 89.167.0.26 (Hetzner, Ubuntu 24.04 — ΚΟΙΝΟΣ με άλλες live εφαρμογές)
   Docker container `woo-agent` (1 process, port 8002→8000)
        │  REST / RPC
        ▼
Supabase project fxocmwpvpqeaucxoekgo (PostgreSQL 17.6 + pgvector)
   7+ δομημένοι πίνακες + documents (vectors) + chat_logs
        │
        ├─ OpenAI API (embeddings + chat: gpt-4.1-mini / gpt-4.1)
        └─ Cohere API (reranking — προαιρετικό, σιωπηλό fallback)
```

| Στοιχείο | Πού | Λεπτομέρειες |
|---|---|---|
| Κώδικας (πηγή αλήθειας) | `github.com/Digital-Challenge/woo-support-ai-agent`, branch `main` | Περιέχει και deployment artifacts (DEPLOYMENT.md, docker-compose.yml, setup-web.sh, deploy.sh) |
| Backend | Server `89.167.0.26`, `~/apps/woo-agent/` | Docker image `woo-agent:latest`, container `woo-agent`, `restart unless-stopped` |
| Ρυθμίσεις/μυστικά | `~/apps/woo-agent/.env` στον server (chmod 600) | OPENAI_API_KEY, SUPABASE_URL/KEY, COHERE_API_KEY, WEBHOOK_SECRET, tier models. **Ποτέ στο git.** |
| Βάση | Supabase `fxocmwpvpqeaucxoekgo` | Πλήρες αντίγραφο της παλιάς βάσης (schema + data + functions), sequences διορθωμένα |
| WP Plugin | Παραδίδεται ως zip (`dicha-sync-v3`, v2.5.5) | Δεν είναι στο repo του backend. Ρύθμιση από WP-admin: Endpoint URL, Webhook Secret, Project ID |
| Δημόσιο URL | `https://woo.89-167-0-26.sslip.io` | sslip.io wildcard DNS → IP. Προσωρινό αλλά πλήρως λειτουργικό· για δικό σας domain: `bash setup-web.sh your.domain.com` |

## 2. Τι δουλεύει (επιβεβαιωμένο 2026-06-10)

- **End-to-end λειτουργία στη νέα υποδομή:** `/health`, `/chat`, `/api/logs`, chat μέσα από το WP-admin.
- **Sync:** το demo shop (dicha-demo) έκανε πλήρη συγχρονισμό στο νέο endpoint — 346 γραμμές δομημένων δεδομένων + 213 vector documents, μηδέν σφάλματα.
- **Tests:** 20/20 smoke tests, 24/24 ποιοτικές ερωτήσεις (21 «άριστες»), 6/7 guide-retrieval checks (1 στοχαστική αστοχία).
- **Model tiers:** πεδίο `model_tier` στο `/chat` — `fast` → gpt-4.1-mini, `powerful` → gpt-4.1. ⚠️ Το πεδίο λέγεται `model_tier`· τυχόν `tier` αγνοείται σιωπηλά (πέφτει σε fast). Αλλαγή μοντέλων = μόνο env vars, όχι κώδικας.
- **Ιστορικό συνομιλιών (chat_logs):** δουλεύει ξανά μετά τη διόρθωση των sequences (βλ. §5).

## 3. Πώς γίνεται deploy

### Auto-deploy (ενεργό)
1. Push/merge στο `main` του `Digital-Challenge/woo-support-ai-agent`.
2. Ο server κάνει pull μέσω **read-only deploy key** (`~/.ssh/woo_deploy_key`, ssh alias `github-woo`) και τρέχει το `~/deploy.sh`: `git pull` → `docker build` → rm+run container.
3. Επιβεβαιώθηκε με test commit (`9298cf3 chore: verify auto-deploy pipeline`, 2026-06-10).

Το deploy key είναι repo-scoped και read-only — δεν δίνει πρόσβαση πουθενά αλλού. Νέα deploy keys/webhooks/secrets στο repo απαιτούν τον **admin** του οργανισμού Digital-Challenge.

### Χειροκίνητο deploy (fallback)
```bash
cd ~/apps/woo-agent-src && git pull
docker build -t woo-agent:latest .
docker rm -f woo-agent
docker run -d --name woo-agent --restart unless-stopped \
  --env-file ~/apps/woo-agent/.env -p 127.0.0.1:8002:8000 woo-agent:latest
```
⚠️ Το `--env-file` διαβάζεται **μόνο στο create** — αλλαγή στο `.env` σημαίνει `docker rm` + `docker run`, ΟΧΙ `docker restart`.

## 4. Σκληροί περιορισμοί — ΜΗΝ τους παραβιάσετε

1. **ΕΝΑ process, ΕΝΑ container.** Ο agent κρατά τα chat sessions in-memory. `--workers > 1` ή replicas σπάνε **σιωπηλά** τις πολλαπλές συνομιλίες (χωρίς error — απλώς ο agent «ξεχνάει»). Λεπτομέρειες στο [DEPLOYMENT.md](../DEPLOYMENT.md).
2. **Κοινός server.** Στο `89.167.0.26` τρέχουν και άλλες live εφαρμογές πίσω από το ίδιο nginx. Μην αγγίζετε άλλα vhosts/containers. Νέο vhost ΜΟΝΟ μέσω `setup-web.sh` (έχει guards: ελέγχει DNS, αρνείται υπάρχον vhost, `nginx -t` πριν reload).
3. **Plugin endpoint:** πρέπει να τελειώνει σε `/webhook` και να είναι HTTPS με έγκυρο certificate (το WP κάνει sslverify).

## 5. Γνωστά θέματα / αδυναμίες

- **3 κενά στον οδηγό Woodmart** (65 ενότητες): δεν καλύπτουν λογότυπο, sticky header, announcement bar → ο agent απαντά «μέτρια» σε αυτά. Διόρθωση: 3× `POST /docs` με scope `_global` όταν γραφτούν οι ενότητες.
- **sslip.io URL:** δεμένο με την IP του server. Αλλαγή server = αλλάζει το URL = επαναρύθμιση endpoint σε όλα τα shops. Με δικό σας domain αυτό λύνεται οριστικά.
- **Cohere reranking:** αν λείψει/λήξει το COHERE_API_KEY, ο agent συνεχίζει χωρίς rerank **χωρίς προειδοποίηση** (ελαφρώς χειρότερη ποιότητα ανάκτησης).
- **Μάθημα από το migration:** αντιγραφή δεδομένων με `json_populate_recordset ... overriding system value` ΔΕΝ προχωράει τα identity sequences → duplicate-key (409) στα inserts. Μετά από κάθε τέτοιο copy: `setval(pg_get_serial_sequence(...), max(id))` σε όλους τους πίνακες. (Έγινε ήδη στη νέα βάση — ισχύει για μελλοντικά αντίγραφα.)

## 6. Εκκρεμότητες

| # | Τι | Ποιος |
|---|---|---|
| 1 | Δικό σας domain αντί για sslip.io: `bash setup-web.sh your.domain.com` (ως root) + επαναρύθμιση endpoint στα shops | Dev πελάτη |
| 2 | Εγκατάσταση plugin v2.5.5 + sync σε κάθε κατάστημα (Endpoint, Webhook Secret, μοναδικό Project ID ανά shop) | Πελάτης |
| 3 | Συμπλήρωση 3 κενών Woodmart οδηγού (logo / sticky header / announcement bar) μέσω `POST /docs` | Συντηρητής περιεχομένου |
| 4 | Καθαρισμός προσωρινών secrets/εργαλείων migration από τον server (`~/dbcopy/`) και τοπικά αρχεία μετάβασης· αλλαγή root password | ntontis |

## 7. Πού να ψάξετε τι

| Θέλω να… | Δες |
|---|---|
| Καταλάβω πώς δουλεύει ο agent (sync → search → answer) | [docs/agent-overview-client.md](agent-overview-client.md) |
| Στήσω από το μηδέν σε νέο server | [DEPLOYMENT.md](../DEPLOYMENT.md) + `setup-web.sh` |
| Καταλάβω την αρχιτεκτονική του κώδικα | [CLAUDE.md](../CLAUDE.md) / [AGENTS.md](../AGENTS.md) |
| Δω/αλλάξω το schema της βάσης | `schema_full.sql` (⚠️ drop+recreate — μόνο σε άδεια βάση) |
| Αλλάξω μοντέλα AI (π.χ. αναβάθμιση tier) | env vars στο `.env` του server, μετά rm+run container |
| Δω το ιστορικό συνομιλιών | `GET /api/logs` ή καρτέλα «Ιστορικό» στο WP-admin |
