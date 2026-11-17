{
    "name": "Elfatoora TTN - Local Demo API",
    "version": "19.0.1.0",
    "category": "Accounting/Localization",
    "summary": "Local REST simulator for demonstrating the Elfatoora invoice flow",
    "description": """
        Provides local REST endpoints with saveEfact, consultEfact, and
        verifyQrCode operations for project demonstrations. It validates TEIF
        structure using the bundled 1.8.8 schema and simulates asynchronous
        processing. It does not submit invoices to TTN or create official
        fiscal references.
    """,
    "author": "Rihab Boubaker",
    "license": "LGPL-3",
    "depends": ["elfatoora_ttn_base"],
    "external_dependencies": {"python": ["lxml", "qrcode"]},
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
