# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class InvoiceOcrConfig(models.Model):
    _name = 'invoice.ocr.config'
    _description = 'Invoice OCR AI Configuration'
    _inherit = ['mail.thread']
    _check_company_auto = True

    name = fields.Char(required=True, default='Invoice OCR Configuration', tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    provider = fields.Selection([
        ('gemini', 'Google Gemini'),
        ('groq', 'Groq'),
        ('custom', 'Custom OCR API'),
    ], required=True, default='gemini', tracking=True)
    api_key = fields.Char(string='API Key / Token')
    model_name = fields.Char(default='gemini-2.5-flash')
    endpoint_url = fields.Char(string='Endpoint URL')
    create_missing_partner = fields.Boolean(default=True)
    create_missing_product = fields.Boolean(default=True)
    default_move_type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Vendor Bill'),
    ], default='out_invoice', required=True)
    default_tax_id = fields.Many2one('account.tax', domain="[('type_tax_use', 'in', ['sale','purchase'])]")
    max_file_size_mb = fields.Integer(default=10)

    _sql_constraints = [
        (
            'company_provider_move_type_unique',
            'unique(company_id, provider, default_move_type)',
            'Only one provider configuration per company and invoice type is recommended.'
        ),
    ]

    def init(self):
        self.env.cr.execute(
            'ALTER TABLE invoice_ocr_config '
            'DROP CONSTRAINT IF EXISTS invoice_ocr_config_company_provider_unique'
        )

    @api.constrains('max_file_size_mb')
    def _check_size(self):
        for rec in self:
            if rec.max_file_size_mb <= 0:
                raise ValidationError(_('Maximum file size must be greater than 0.'))

    @api.model
    def get_active_config(self, default_move_type=False):
        domain = [('active', '=', True), ('company_id', '=', self.env.company.id)]
        if default_move_type:
            domain.append(('default_move_type', '=', default_move_type))
        return self.search(domain, limit=1)
