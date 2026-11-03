# DioMasteR2D Grokbot — Android companion

Αυτό είναι native Android client για το υπάρχον PumpGrok Desk Gateway. Δεν είναι αυτόνομο Grok bot και δεν ενεργοποιεί live trading. Το gateway του repository αρνείται live mode· χρησιμοποίησε μόνο paper configuration.

## Εγκατάσταση στο repository
1. Αντέγραψε τον φάκελο `android/` στη ρίζα του repository.
2. Αντέγραψε το `.github/workflows/android-apk.yml` στο `.github/workflows/`.
3. Πρόσθεσε στο `ownership.yaml`, μέσα στο `ownership:` πριν από το CI section:
   ```yaml
   - pattern: "android/**"
     owner: bot-02-risk
   ```
4. Κάνε commit στο `bot-02-risk/android-companion-mvp`, όχι στο `main`.

## Δημιουργία APK
GitHub → Actions → Android companion APK → Run workflow. Όταν ολοκληρωθεί επιτυχώς, άνοιξε το run → Artifacts → `DioMasteR2D-Grokbot-debug-apk`. Είναι debug APK, όχι υπογεγραμμένο για Play Store.

## Σύνδεση
Χρειάζεται προσβάσιμο HTTPS URL του PumpGrok Desk Gateway, seat short name και bearer token του seat. Το gateway ακούει εξ ορισμού στο 127.0.0.1:8787· χρειάζεται ασφαλές HTTPS reverse proxy ή VPN endpoint. Μην εκθέσεις απευθείας το gateway στο δημόσιο internet.

Το token μένει μόνο στη μνήμη της εφαρμογής και καθαρίζεται στην αποσύνδεση ή όταν τερματιστεί η διεργασία. Δεν υπάρχει wallet integration. Μην εισάγεις seed phrase ή private keys.

## Πεδίο
JSON-RPC initialize, tools/list και tools/call· λίστα εργαλείων ανά seat· χειροκίνητα JSON arguments· HTTPS only. Δεν κάνει αυτόνομο trading ούτε live συναλλαγές.
