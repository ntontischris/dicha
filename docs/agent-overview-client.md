# WooCommerce AI Agent — Πλήρης Τεκμηρίωση

## Τι είναι

Ένας AI assistant εξειδικευμένος σε WooCommerce, που γνωρίζει **τον κώδικα, τις ρυθμίσεις και τα plugins** του κάθε shop ξεχωριστά. Απαντάει σε ερωτήσεις, εντοπίζει bugs, προτείνει αλλαγές κώδικα και εξηγεί πώς λειτουργεί το κάθε shop.

---

## Πώς λειτουργεί — Επισκόπηση

```
WooCommerce Shop                         AI Agent
     │                                      │
     │  1. Sync (αυτόματο)                  │
     ├──────────────────────────────────────►│
     │  Plugin στέλνει όλα τα δεδομένα      │
     │  (κώδικας, ρυθμίσεις, plugins)       │
     │                                      │
     │  2. Ερώτηση χρήστη                   │
     │  "Πώς αλλάζω τα μεταφορικά;"        │
     ├──────────────────────────────────────►│
     │                                      │  ← Ψάχνει στον κώδικα & ρυθμίσεις
     │                                      │  ← Βρίσκει σχετικά snippets
     │                                      │  ← Δίνει απάντηση με κώδικα
     │  3. Απάντηση                         │
     │◄────────────────────────────────────┤
     │  Έτοιμος κώδικας + εξήγηση          │
```

---

## Φάση 1: Sync — Τι δεδομένα συλλέγονται

Ένα WordPress plugin εγκαθίσταται στο shop και στέλνει **αυτόματα** τα παρακάτω δεδομένα στο σύστημα:

### Κώδικας
| Τι | Παράδειγμα |
|----|-----------|
| Code Snippets | Κανόνες μεταφορικών, custom checkout fields, price modifications |
| functions.php | Custom functions του theme |
| Theme files | Templates, single-product.php, cart.php κλπ |

### Ρυθμίσεις WooCommerce
| Τι | Παράδειγμα |
|----|-----------|
| Payment Gateways | Stripe, PayPal, Τραπεζική κατάθεση — ποια είναι ενεργά |
| Shipping Zones | Ηπειρωτική, Νησιά, Αθήνα — ζώνες & μέθοδοι αποστολής |
| Shipping Methods | Flat rate κόστη, free shipping thresholds, class costs |
| Tax Settings | ΦΠΑ, τιμές με/χωρίς φόρο |
| General Settings | Νόμισμα, τοποθεσία, stock management, guest checkout |

### Plugins
| Τι | Παράδειγμα |
|----|-----------|
| Active Plugins | Όνομα, version, author |
| Plugin Settings | Αναλυτικές ρυθμίσεις κάθε plugin |

**Σημαντικό:** Κάθε shop έχει τα δικά του δεδομένα, πλήρως απομονωμένα. Ο agent ενός shop δεν βλέπει δεδομένα άλλου shop.

---

## Φάση 2: Επεξεργασία Δεδομένων

Μόλις ληφθούν τα δεδομένα, γίνεται αυτόματη επεξεργασία σε 2 κλάδους:

### Κλάδος Α — Δομημένα Δεδομένα (8 πίνακες)
Τα δεδομένα αποθηκεύονται σε σχεσιακούς πίνακες για γρήγορη πρόσβαση:
- Πληροφορίες project (URL, versions, theme)
- Payment gateways
- Shipping zones & methods (με instance_id, κόστη, class costs)
- Tax settings & rates
- General settings
- Active plugins & ρυθμίσεις plugins

### Κλάδος Β — AI Αναζήτηση (Vector Pipeline)
Ο κώδικας περνάει από 5 στάδια επεξεργασίας:

```
1. Chunking        → Κόβει τον κώδικα σε λογικά κομμάτια (ανά function)
2. Extraction      → Εντοπίζει hooks, functions, κατηγορία (shipping, checkout κλπ)
3. Context         → AI δημιουργεί σύντομη περιγραφή κάθε κομματιού
4. Embedding       → Μετατρέπει σε vector για semantic search
5. Αποθήκευση      → Parent (πλήρες αρχείο) + Children (κομμάτια με embeddings)
```

**Γιατί τόσα στάδια;** Για να βρίσκει ο agent τον σωστό κώδικα ακόμα κι αν ο χρήστης ρωτήσει με δικά του λόγια (π.χ. "πώς λειτουργούν τα μεταφορικά" βρίσκει functions που ασχολούνται με shipping).

---

## Φάση 3: Αναζήτηση & Απάντηση

Όταν ο χρήστης κάνει ερώτηση, ο agent ακολουθεί αυτή τη διαδικασία:

### Βήμα 1 — Κατανόηση ερώτησης
Ο agent αναγνωρίζει τον τύπο ερώτησης:
- **Feature Request** → Γράφει νέο ή τροποποιημένο κώδικα
- **Bug Report** → Ψάχνει τον υπάρχοντα κώδικα, εντοπίζει το πρόβλημα, προτείνει fix
- **Ερώτηση ρυθμίσεων** → Εξηγεί πώς να αλλάξει κάτι στο WooCommerce admin
- **Εννοιολογική ερώτηση** → Εξηγεί πώς λειτουργεί κάτι

### Βήμα 2 — Αναζήτηση (Hybrid Search)
Ο agent χρησιμοποιεί **4 εξειδικευμένα εργαλεία**:

| Εργαλείο | Τι κάνει | Παράδειγμα |
|----------|---------|-----------|
| `search` | Ψάχνει κώδικα & docs με AI + keywords | "free shipping rules" |
| `search_by_hook` | Βρίσκει κώδικα που χρησιμοποιεί συγκεκριμένο hook | "woocommerce_package_rates" |
| `get_shop_config` | Φέρνει όλες τις ρυθμίσεις του shop | Payment, shipping, tax, plugins |
| `search_plugin_settings` | Ψάχνει ρυθμίσεις plugins | "WooCommerce PDF Invoices" |

**Η αναζήτηση είναι υβριδική (3 σήματα):**
1. **Vector Search** — Βρίσκει σημασιολογικά παρόμοιο κώδικα (AI)
2. **Full-Text Search** — Βρίσκει ακριβείς λέξεις-κλειδιά (keywords)
3. **RRF Fusion** — Συνδυάζει τα 2 σήματα σε ενιαίο score

**+ Cohere Reranking** — Ένα δεύτερο AI μοντέλο ξαναβαθμολογεί τα αποτελέσματα για μέγιστη ακρίβεια.

### Βήμα 3 — Απάντηση
Ο agent παράγει:
- **2-3 γραμμές** εξήγηση τι υπάρχει & τι αλλάζει
- **Πλήρη PHP κώδικα** (copy-paste ready)
- **1 γραμμή** πού να τον τοποθετήσει
- Χρησιμοποιεί **πραγματικά IDs** από τις ρυθμίσεις του shop (όχι placeholders)

---

## 3 Επίπεδα Περιεχομένου

| Επίπεδο | Τι περιέχει | Ποιος το βλέπει |
|---------|-------------|----------------|
| **Project Code** | Code snippets, functions.php, theme files | Μόνο το συγκεκριμένο shop |
| **Company Docs** | Οδηγοί, knowledge base, best practices | Όλα τα shops |
| **Project Docs** | Σημειώσεις πελάτη, custom οδηγίες | Μόνο το συγκεκριμένο shop |

---

## Τρόποι χρήσης

### 1. Web Chat (Streamlit)
- URL-based interface
- Ιστορικό συνομιλίας
- Εμφάνιση κόστους ανά ερώτηση

### 2. API (`POST /chat`)
- Για ενσωμάτωση σε 3rd party εφαρμογές
- Stateful sessions (κρατάει ιστορικό)
- Επιστρέφει: απάντηση, session_id, εργαλεία που χρησιμοποίησε, usage

### 3. CLI (Command Line)
- Για developers
- Rich markdown rendering
- Logging ανά session

---

## Τεχνικά Χαρακτηριστικά

### Μοντέλα AI
| Χρήση | Μοντέλο | Γιατί |
|-------|---------|------|
| Tool calling (αναζήτηση) | GPT-4.1-mini | Γρήγορο, ακριβές, χαμηλό κόστος |
| Τελική απάντηση | GPT-4.1-mini | Ποιοτική απάντηση |
| Contextual Retrieval | GPT-4o-mini | Σύντομες περιγραφές ανά chunk |
| Embeddings | text-embedding-3-large | 1536 διαστάσεις, υψηλή ακρίβεια |
| Reranking | Cohere rerank-v3.5 | Cross-encoder reranking |

### Performance
- **Caching:** Config 5 λεπτά, search 10 λεπτά, embeddings 1 ώρα
- **Parallel execution:** Εργαλεία εκτελούνται παράλληλα
- **Context management:** Αυτόματο trimming παλιών μηνυμάτων
- **Session cleanup:** Αυτόματο μετά 30 λεπτά αδράνειας

### Ασφάλεια
- Κάθε shop βλέπει **μόνο** τα δικά του δεδομένα
- Webhook authentication με secret key
- Τα global docs (company knowledge base) είναι κοινά σε όλα τα shops
- Row Level Security στη βάση δεδομένων

### Deployment
- **Platform:** Railway
- **Runtime:** Python 3.11
- **Health check:** `GET /health`
- **Auto-restart:** On failure (max 3 retries)

---

## Παράδειγμα Ροής

### Ερώτηση: "Θέλω να βάλω δωρεάν μεταφορικά πάνω από 50 ευρώ μόνο για Αθήνα"

```
1. Ο agent αναγνωρίζει: Feature Request → χρειάζεται κώδικα

2. Tool Round 1 (παράλληλα):
   ├─ search("free shipping threshold Athens")
   │  → Βρίσκει υπάρχοντα κώδικα μεταφορικών
   └─ get_shop_config()
      → Βλέπει shipping zones: Αθήνα (zone_id: 3), instance_id: 15

3. Ανάλυση αποτελεσμάτων:
   - Υπάρχει ήδη function dc_custom_shipping() → θα τη τροποποιήσει
   - Zone Αθήνα = zone_id 3, free_shipping instance = 15
   - Threshold τώρα: 0€ (disabled)

4. Απάντηση:
   "Υπάρχει ήδη η dc_custom_shipping(). Προσθέτω condition
    για free shipping στην Αθήνα πάνω από 50€:"

   [Πλήρης PHP κώδικας με πραγματικά IDs]

   "Τοποθέτησε στο Code Snippets → dc_custom_shipping"
```

---

## Τι το κάνει διαφορετικό από ChatGPT/Generic AI

| | Generic ChatGPT | WooCommerce AI Agent |
|---|---|---|
| Γνωρίζει τον κώδικά σου | Όχι | Ναι — ψάχνει στον πραγματικό κώδικα |
| Χρησιμοποιεί πραγματικά IDs | Όχι — βάζει placeholders | Ναι — instance_id, zone_id, gateway_id |
| Γνωρίζει τις ρυθμίσεις σου | Όχι | Ναι — payment, shipping, tax, plugins |
| Βρίσκει bugs στον κώδικά σου | Όχι | Ναι — ψάχνει, εντοπίζει, προτείνει fix |
| Reuses τα helpers σου | Όχι | Ναι — χρησιμοποιεί υπάρχοντα dc_/dicha_ functions |
| Multi-tenant | N/A | Κάθε shop έχει απομονωμένα δεδομένα |
| Ελληνικά | Βασική υποστήριξη | Πλήρης — αναζήτηση, expansion, απάντηση |

---

## Endpoints API

| Method | Path | Περιγραφή |
|--------|------|----------|
| `POST` | `/webhook` | Sync δεδομένων από WooCommerce plugin |
| `POST` | `/chat` | Αποστολή ερώτησης & λήψη απάντησης |
| `POST` | `/docs` | Upload εγγράφου (company/project doc) |
| `POST` | `/docs/bulk` | Bulk upload εγγράφων |
| `GET` | `/docs` | Λίστα εγγράφων ανά project |
| `GET` | `/docs/{id}` | Λήψη εγγράφου |
| `DELETE` | `/docs` | Διαγραφή εγγράφων |
| `GET` | `/health` | Health check |
| `GET` | `/admin` | Admin dashboard |
| `GET` | `/api/projects` | Λίστα projects |
| `POST` | `/api/re-ingest` | Επανεπεξεργασία εγγράφων |

---

## Κόστος Λειτουργίας

Το κόστος εξαρτάται από τη χρήση:

| Λειτουργία | Κόστος | Πότε |
|-----------|--------|------|
| Sync (per shop) | ~$0.05-0.15 | Κάθε φορά που γίνεται sync |
| Ερώτηση (απλή) | ~$0.002-0.005 | 1 tool round |
| Ερώτηση (σύνθετη) | ~$0.005-0.015 | 2 tool rounds |
| Reranking (Cohere) | ~$0.001/query | Ανά αναζήτηση |
| Embeddings | ~$0.0001/query | Cached 1 ώρα |

*Τιμές ενδεικτικές, εξαρτώνται από μέγεθος κώδικα & μήκος συνομιλίας.*
