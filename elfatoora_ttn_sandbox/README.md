# Elfatoora Local Demo API

This add-on provides a REST service for demonstrating the invoice submission flow when a TTN account is not available. It is a simulator: it does not submit data to TTN and its references and validation results are not official.

## Setup

1. Install `elfatoora_ttn_sandbox` after `elfatoora_ttn_base`, then restart the Odoo service so its HTTP controller route is registered.
2. Open Elfatoora Configuration and choose **Local Demo API**.
3. Set the API login, API password, and company matricule. The incoming API requests must use the same values.
4. Set the Local Demo API URL to `http://127.0.0.1:8070/elfatoora/sandbox/v1` for this Odoo installation. Adjust the host and port if needed.
5. Sign a posted invoice and use **Submit to Service**. In demo mode, the button sends the invoice to this local service. The first status check moves a schema-valid invoice from pending to validated (demo).

When calling the endpoints directly from PowerShell, send the `X-Odoo-Database` header with your database name if `db_name` is empty in `odoo.conf`. For this setup, the database name shown in the Odoo log is `test`. The Odoo client adds the active database automatically.

The service checks XML well-formedness, TEIF version 1.8.8 structure using an in-memory XSD 1.0 compatibility projection of the bundled `facture_INVOIC_V1.8.8_withoutSig.xsd`, sender matricule, and presence of a non-empty XML Signature value. The projection is needed because Odoo's `lxml/libxml2` validator does not support the XSD 1.1 conditional type alternatives or assertions in the source schema. Those XSD 1.1-only constraints are not evaluated by the local demo. The service does not verify the cryptographic signature, certificate chain, revocation status, TTN rules, tax-law compliance, or official acceptance.

## Endpoints

All operations use `POST` with JSON and the credentials below:

```json
{
  "login": "demo-login",
  "password": "demo-password",
  "matricule": "company-matricule"
}
```

### `POST /elfatoora/sandbox/v1/saveEfact`

Add `documentEfact` containing the signed XML encoded as base64. A valid XML invoice is stored with `pending` status and an `idSaveEfact` tracking number. Invalid documents are stored as rejected with an explanation.

```json
{
  "login": "demo-login",
  "password": "demo-password",
  "matricule": "company-matricule",
  "documentEfact": "BASE64_SIGNED_TEIF_XML"
}
```

### `POST /elfatoora/sandbox/v1/consultEfact`

Add `efactCriteria` with either `idSaveEfact`, `generatedRef`, or `documentNumber`. The first check of an accepted invoice returns a simulated validation result, a `SIM-...` reference, and `xmlContent` encoded as base64. The returned XML includes `RefTtnVal/ReferenceCEV` containing a PNG QR image encoded as base64.

```json
{
  "login": "demo-login",
  "password": "demo-password",
  "matricule": "company-matricule",
  "efactCriteria": { "idSaveEfact": 1 }
}
```

### `POST /elfatoora/sandbox/v1/verifyQrCode`

Add `qrCode` containing the decoded QR payload. The response says whether the payload belongs to a validated invoice in this Odoo database.

```json
{
  "login": "demo-login",
  "password": "demo-password",
  "matricule": "company-matricule",
  "qrCode": "ELFATOORA-SANDBOX|SIM-00000001|INV/2026/0001"
}
```

Use HTTPS when the API is reached over a network. The built-in default URL is intended only for a local development machine.
