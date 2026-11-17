# -*- coding: utf-8 -*-
{
    'name': 'Invoice External OCR Import',
    'version': '19.0.1.0.0',
    'summary': 'Import external invoices from PDF/Image using AI OCR and create Odoo invoices',
    'category': 'Accounting/Accounting',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['account', 'mail'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'views/ocr_config_views.xml',
        'views/account_move_views.xml',
        'wizard/invoice_ocr_import_wizard_views.xml',
        'data/ocr_config_data.xml',
    ],
    'installable': True,
    'application': False,
}
