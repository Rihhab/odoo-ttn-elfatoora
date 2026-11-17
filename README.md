# Odoo El Fatoora and OCR addons

Addons Odoo 19 pour préparer des factures TEIF, les signer via des fournisseurs configurés, simuler localement le flux de soumission El Fatoora et importer des factures externes avec OCR.

> **Projet de fin d’études / prototype.** Le module Local Demo API simule les échanges de soumission et de consultation. Il ne se connecte pas à TTN, ne reçoit aucune référence fiscale officielle et ne valide pas une facture auprès de TTN. Le statut, la référence `SIM-...` et le QR code produits en mode local sont des résultats de démonstration.

## Contenu du dépôt

| Addon | Rôle | Dépendances Odoo |
|---|---|---|
| `elfatoora_ttn_base` | Configuration El Fatoora, génération TEIF 1.8.8, signature XML, suivi des envois et consultation de statut | `base`, `account`, `contacts`, `barcodes` |
| `elfatoora_ttn_digigo` | Fournisseur de signature DigiGo via OAuth2 et service distant | `elfatoora_ttn_base` |
| `elfatoora_ttn_enterprise` | Signature locale avec certificat PKCS#12 Enterprise-ID (`.p12`/`.pfx`) | `elfatoora_ttn_base` |
| `elfatoora_ttn_idtrust` | Flux de signature avec jeton ID-Trust et middleware local du poste utilisateur | `elfatoora_ttn_base` |
| `elfatoora_ttn_sandbox` | API REST locale de démonstration : `saveEfact`, `consultEfact`, `verifyQrCode` | `elfatoora_ttn_base` |
| `invoice_external_document` | Extraction OCR de factures externes et création d’une facture client ou fournisseur en brouillon | `account`, `mail` |

## Prérequis

- Odoo 19.0 et PostgreSQL, avec une base de données Odoo fonctionnelle.
- Python dans le même environnement que celui utilisé par le service Odoo.
- Pour le socle El Fatoora : `zeep`, `cryptography`, `lxml` et `requests`.
- Pour l’API locale : `qrcode` (et sa dépendance image Pillow, installée normalement avec l’extra Pillow de qrcode).
- Pour l’OCR : une clé API du fournisseur choisi (Gemini, Groq ou API personnalisée) et un accès réseau à ce fournisseur.
- Pour traiter un PDF avec Groq : PyMuPDF (`fitz`) ou `pypdfium2`. Ce sont des dépendances facultatives ; Groq reçoit une image et le code convertit la première page du PDF.
- Pour la signature ID-Trust : le middleware local doit être installé et démarré sur le poste utilisateur, selon les routes configurées dans Odoo.

Les manifestes déclarent les dépendances Python requises par les addons. Installez les paquets dans l’environnement Python d’Odoo, pas dans un autre Python présent sur le poste.

## Installation dans Odoo

1. Copiez les six dossiers d’addons dans un répertoire présent dans `addons_path`.
2. Redémarrez le service Odoo.
3. Activez le mode développeur, puis mettez à jour la liste des applications.
4. Installez `elfatoora_ttn_base`.
5. Installez les fournisseurs de signature souhaités (`elfatoora_ttn_digigo`, `elfatoora_ttn_enterprise`, `elfatoora_ttn_idtrust`). Ils dépendent du socle.
6. Pour le parcours local de démonstration, installez `elfatoora_ttn_sandbox` et redémarrez Odoo afin que son contrôleur REST soit chargé.
7. Installez séparément `invoice_external_document` si vous souhaitez activer l’import OCR.

Après une modification de code Python, redémarrez Odoo. Après l’ajout ou la modification de vues, de données ou de champs, mettez également à niveau l’addon concerné depuis Apps ou avec la commande de mise à niveau de votre installation.

## Parcours de facture électronique en mode local

1. Dans **Configuration → Elfatoora**, choisissez **Local Demo API**.
2. Renseignez le matricule fiscal de l’entreprise, un login et un mot de passe de démonstration. La configuration de l’API doit utiliser les mêmes valeurs.
3. Indiquez l’URL de base de l’API, par exemple `http://127.0.0.1:8070/elfatoora/sandbox/v1`. Adaptez le port à votre instance.
4. Activez un fournisseur de signature et complétez sa configuration. Pour un essai, utilisez uniquement des certificats et comptes de test.
5. Préparez la fiche du client, les produits et les taxes.
6. Créez une facture client, vérifiez les lignes et les montants, puis cliquez sur **Post**.
7. Cliquez sur **Sign Invoice** et terminez l’assistant de signature. Odoo génère le XML TEIF signé.
8. Cliquez sur **Submit to Service**. Le simulateur enregistre le XML et renvoie un numéro de suivi avec le statut **Pending** ou **Rejected**.
9. Pour une facture en attente, cliquez sur **Check Elfatoora Status**. Le simulateur passe une facture acceptée à **Validated by Service** et renvoie une référence `SIM-...` ainsi qu’un QR code local.
10. Consultez l’onglet **Elfatoora** de la facture pour voir le suivi, le XML retourné et le QR code. **Service Submissions** ouvre l’historique des requêtes.

Le QR code est également ajouté au rapport PDF **Invoice PDF**, quel que soit le mode d’envoi (TTN SOAP ou Local Demo API), dès qu’il a été extrait du XML retourné et enregistré sur la facture. En SOAP, le service doit retourner le XML validé avec son élément QR ; en mode local, le simulateur le génère lors de la consultation du statut.

Une facture rejetée peut être corrigée puis signée de nouveau via **Resign Invoice**. Le prochain envoi crée un nouvel enregistrement ; l’ancien reste dans l’historique.

### Routes REST du simulateur

Toutes les routes requièrent `POST` avec du JSON et les champs `login`, `password` et `matricule`.

| Route | Fonction |
|---|---|
| `/elfatoora/sandbox/v1/saveEfact` | Reçoit le XML TEIF signé encodé en base64 dans `documentEfact` et retourne un numéro de suivi. Limite de taille : 16 Mio. |
| `/elfatoora/sandbox/v1/consultEfact` | Consulte une soumission à l’aide de `efactCriteria`, par exemple `{"idSaveEfact": 3}`. |
| `/elfatoora/sandbox/v1/verifyQrCode` | Vérifie si le contenu d’un QR appartient à une facture validée dans cette base de démonstration. |

Si la base Odoo n’est pas sélectionnée automatiquement (par exemple lorsque `db_name` est vide), le client Odoo du module envoie `X-Odoo-Database`. Les appels directs doivent aussi fournir cet en-tête avec le nom de la base.

## Import OCR de factures externes

L’addon `invoice_external_document` permet de téléverser une image ou un PDF, d’envoyer le document à un fournisseur OCR configuré, de visualiser les données extraites puis de créer une facture client ou fournisseur en brouillon. Selon la configuration, les partenaires et produits manquants peuvent être créés automatiquement.

L’OCR peut se tromper sur les numéros, dates, taxes, quantités et montants. Contrôlez le partenaire, les lignes, la devise, les taxes et les totaux avant de publier la facture. Les documents et données extraites sont conservés dans Odoo ; le fournisseur externe reçoit le fichier envoyé pour extraction.

## Limites et points de sécurité

- Le mode local est un simulateur, pas une passerelle TTN. Les références et QR `SIM-...` ne sont pas officiels et ne doivent pas être présentés comme tels.
- La validation du simulateur utilise une projection XSD 1.0 du schéma TEIF fourni. Elle retire les assertions et alternatives conditionnelles XSD 1.1, car le validateur `lxml/libxml2` ne les prend pas en charge. Elle ne remplace pas la validation TTN.
- Le simulateur vérifie la structure, le numéro de version, le matricule émetteur et la présence d’une valeur de signature. Ce contrôle d’envoi ne vérifie pas la chaîne du certificat, la révocation ou l’acceptation fiscale officielle.
- L’intégration SOAP par défaut ne peut fonctionner qu’avec une URL WSDL accessible et des identifiants TTN autorisés. L’accès réel dépend de TTN.
- Le code actuel désactive la vérification TLS (`verify=False`) dans les clients SOAP/DigiGo. Avant tout usage réel, il faut corriger ce point et vérifier les URL, les callbacks OAuth et la gestion des secrets avec les fournisseurs concernés.
- Les mots de passe API, secrets OAuth, clés OCR et certificats sont des données sensibles. Limitez l’accès aux configurations et protégez les sauvegardes de la base et du filestore.
- Ne publiez jamais de clés API, mots de passe, certificats privés, exports de base, factures réelles ou documents clients dans GitHub. Utilisez des secrets de test et un dépôt privé si le code contient des éléments sensibles.
- L’import OCR crée une facture à vérifier ; il ne doit pas être considéré comme une validation comptable automatique.

## Résolution de problèmes

- **Connexion refusée** : vérifiez que le service Odoo tourne et que l’hôte/port configurés correspondent à cette instance.
- **HTTP 404 en ouvrant l’URL de base dans un navigateur** : les routes du simulateur sont des opérations `POST`; l’URL racine seule n’est pas une page d’état.
- **HTTP 404 au clic sur Submit to Service** : vérifiez l’installation de `elfatoora_ttn_sandbox`, le chemin complet de la route, la base de données Odoo et redémarrez le service après installation.
- **Rejet TEIF** : ouvrez le dernier envoi dans **Service Submissions** et consultez son message. Vérifiez le XML, la version, le matricule émetteur et la présence de la signature.
- **Bouton de signature absent** : vérifiez qu’un fournisseur est installé et activé dans la configuration et que la facture est publiée.
- **Référence ou QR absent** : consultez le statut après soumission. Le simulateur ne les crée qu’après consultation d’une facture en attente acceptée.

## État de la revue

Les six addons ont été parcourus au niveau des manifestes, modèles principaux, services, contrôleur local, vues et règles d’accès présentes. Aucun dossier de tests automatisés n’a été trouvé dans l’arborescence inspectée ; les tests n’ont pas été exécutés. Le projet doit être revu et testé dans l’environnement cible avant une utilisation réelle.

## Licence

Les manifestes des addons El Fatoora et OCR indiquent LGPL-3. Consultez les obligations de cette licence et gardez les informations de licence cohérentes avant la publication du dépôt.
