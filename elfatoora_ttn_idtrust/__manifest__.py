{
    "name": "Elfatoora TTN - ID-Trust USB",
    "version": "19.0.1.0",
    "category": "Accounting/Localization",
    "summary": "ID-Trust USB token signing provider for Elfatoora TTN",
    "description": """
        Adds an ID-Trust USB token signing flow through a local workstation
        middleware service.
    """,
    "author": "Rihab Boubaker",
    "website": "https://www.tradenet.com.tn/elfatoora.html",
    "license": "LGPL-3",
    "depends": ["elfatoora_ttn_base"],
    "data": [
        "views/elfatoora_config_idtrust_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "elfatoora_ttn_idtrust/static/src/js/idtrust_signing_action.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
