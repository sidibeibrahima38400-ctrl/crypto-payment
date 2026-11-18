# CRYPTO PAYMENT — démonstrateur de demandes de paiement

Application Flask permettant à un commerçant de créer des liens de paiement pour ETH, BNB, SOL, BTC et USDT (ERC-20 / BEP-20).

## Fonctionnement
1. L'administrateur configure ses adresses publiques de réception dans les variables d'environnement.
2. Il se connecte à `/login` puis crée une facture dans `/admin/create`.
3. Le client reçoit un lien `/pay/<jeton>` avec montant, actif, réseau et adresse.
4. Le client effectue lui-même le transfert depuis son wallet et peut soumettre le hash de transaction.
5. L'administrateur vérifie le hash sur l'explorateur officiel du réseau et marque la facture comme payée.

## Sécurité et limites importantes
- Ce projet ne connecte pas automatiquement les wallets et ne signe aucune transaction.
- Il ne collecte jamais de phrase secrète, clé privée ou fichier keystore.
- Un hash soumis par le client n'est pas une preuve suffisante : vérifier l'adresse destinataire, le montant, le réseau, les confirmations et le hash sur l'explorateur avant de marquer payé.
- Les prix ne sont pas convertis : le montant est exprimé dans l'actif choisi (ex. 0.01 ETH ou 25 USDT).
- USDT est proposé sur Ethereum ERC-20 et BNB Smart Chain BEP-20. Toujours vérifier le réseau choisi avant paiement.
- BTC, SOL, ETH et BNB utilisent des adresses publiques de réception.
- Le projet est un prototype. Avant usage commercial, ajouter HTTPS, protection anti-abus/rate limiting, sauvegardes, base de données persistante, journaux d'audit et vérification blockchain automatisée via un fournisseur fiable.
- Ne jamais mettre de clés privées ou seed phrases sur le serveur.

## Lancement local
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```
Définir `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` et les adresses publiques, puis :
```bash
python app.py
```
Ouvrir http://127.0.0.1:10000

## Déploiement Render
1. Importer le contenu du dépôt GitHub.
2. Créer un Web Service depuis le dépôt.
3. Build Command : `pip install -r requirements.txt`
4. Start Command : `gunicorn app:app`
5. Ajouter les variables d'environnement listées dans `.env.example`.
6. Prévoir une base persistante : SQLite sur le disque éphémère d'un hébergement gratuit peut perdre les factures lors d'un redéploiement ou redémarrage.
