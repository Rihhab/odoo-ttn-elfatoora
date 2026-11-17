{
    "name": "Elfatoora TTN - Enterprise-ID",
    "version": "19.0.1.0",
    "category": "Accounting/Localization",
    "summary": "Enterprise certificate signing provider for Elfatoora TTN",
    "description": """
        Adds local server-side signing with an Enterprise-ID certificate
        (.p12/.pfx) for Elfatoora TTN invoices.
    """,
    "author": "Rihab Boubaker",
    "website": "https://www.tradenet.com.tn/elfatoora.html",
    "license": "LGPL-3",
    "depends": ["elfatoora_ttn_base"],
    "data": [
        "views/elfatoora_config_enterprise_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
