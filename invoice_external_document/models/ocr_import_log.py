# -*- coding: utf-8 -*-
from odoo import fields, models


class InvoiceOcrImportLog(models.Model):
    _name = 'invoice.ocr.import.log'
    _description = 'Invoice OCR Import Log'
    _order = 'create_date desc'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    provider = fields.Char()
    filename = fields.Char()
    move_id = fields.Many2one('account.move')
    state = fields.Selection([('draft', 'Draft'), ('success', 'Success'), ('error', 'Error')], default='draft')
    request_payload = fields.Text()
    response_json = fields.Text()
    error_message = fields.Text()
