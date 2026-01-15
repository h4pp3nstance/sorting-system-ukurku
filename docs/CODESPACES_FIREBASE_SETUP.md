# Firebase Setup untuk GitHub Codespaces

## 🔐 Setup Firebase Credentials (Secrets)

Firebase credentials **TIDAK BOLEH** di-commit ke repository. Gunakan GitHub Codespaces Secrets:

### Step 1: Buat Codespace Secret

1. Buka https://github.com/settings/codespaces
2. Scroll ke **"Codespaces secrets"**
3. Click **"New secret"**
4. Name: `FIREBASE_CREDENTIALS`
5. Value: Copy isi dari `firebase_credentials.json` (format JSON)
6. Repository access: Pilih `h4pp3nstance/sorting-system-ukurku`
7. Click **"Add secret"**

### Step 2: Create Secret File in Codespace

Setelah Codespace running, jalankan:

```bash
# Script akan auto-create dari secret
echo $FIREBASE_CREDENTIALS > config/firebase_credentials.json
```

### Step 3: Verify Firebase Connection

```bash
python -c "from storage.firebase_handler import FirebaseHandler; h = FirebaseHandler(); print('Firebase Connected!' if h.db else 'Failed')"
```

## 🔄 Alternative: Manual Setup

Jika tidak ingin pakai Secrets, copy file manual:

```bash
# Di Codespaces terminal, paste JSON content langsung:
cat > config/firebase_credentials.json << 'EOF'
{
  "type": "service_account",
  "project_id": "ukurku-c94e7",
  ... (paste full JSON here)
}
EOF
```

## ⚠️ PENTING

- **JANGAN** commit `firebase_credentials.json` ke repo
- File ini sudah di-exclude via `.gitignore`
- Setiap Codespace baru perlu setup ulang (ephemeral)

## 🧪 Test Firebase

```bash
# Run Firebase tests
python -m pytest tests/test_firebase.py -v
```
