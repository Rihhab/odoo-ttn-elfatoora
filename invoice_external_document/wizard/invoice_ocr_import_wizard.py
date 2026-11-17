# -*- coding: utf-8 -*-
import base64
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..services.ai_client import AIInvoiceClient
from ..services.json_normalizer import normalize_invoice_json
from ..services.odoo_matcher import InvoiceOdooMatcher


class InvoiceOcrImportWizard(models.TransientModel):
    _name = 'invoice.ocr.import.wizard'
    _description = 'Import External Invoice via OCR'

    def _get_context_move(self):
        move_id = self.env.context.get('default_move_id')
        if not move_id and self.env.context.get('active_model') == 'account.move':
            move_id = self.env.context.get('active_id')
        return self.env['account.move'].browse(move_id).exists() if move_id else self.env['account.move']

    def _default_target_move_type(self):
        move = self._get_context_move()
        if move.move_type in ('out_invoice', 'in_invoice'):
            return move.move_type
        context_move_type = self.env.context.get('default_target_move_type') or self.env.context.get('default_move_type')
        return context_move_type if context_move_type in ('out_invoice', 'in_invoice') else 'out_invoice'

    def _default_config_id(self):
        return self.env['invoice.ocr.config'].get_active_config(self._default_target_move_type())

    move_id = fields.Many2one('account.move')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    target_move_type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Vendor Bill'),
    ], string='Import Type', default=_default_target_move_type, required=True, readonly=True)
    file_data = fields.Binary(string='Invoice File', required=True)
    filename = fields.Char(required=True)
    state = fields.Selection([('upload', 'Upload'), ('preview', 'Preview')], default='upload')
    config_id = fields.Many2one(
        'invoice.ocr.config',
        domain="[('active', '=', True), ('company_id', '=', company_id), ('default_move_type', '=', target_move_type)]",
        default=_default_config_id,
    )
    response_json = fields.Text(readonly=True)
    normalized_json = fields.Text(readonly=True)
    raw_text = fields.Text(readonly=True)

    @api.onchange('move_id', 'target_move_type')
    def _onchange_target_move_type(self):
        for wizard in self:
            if wizard.move_id.move_type in ('out_invoice', 'in_invoice'):
                wizard.target_move_type = wizard.move_id.move_type
            if wizard.config_id and wizard.config_id.default_move_type != wizard.target_move_type:
                wizard.config_id = self.env['invoice.ocr.config'].get_active_config(wizard.target_move_type)

    def _get_file_bytes(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Please upload a file.'))
        data = base64.b64decode(self.file_data)
        max_size = (self.config_id.max_file_size_mb or 10) * 1024 * 1024
        if len(data) > max_size:
            raise UserError(_('File too large. Maximum size is %s MB.') % self.config_id.max_file_size_mb)
        return data

    def action_extract(self):
        self.ensure_one()
        if not self.config_id:
            raise UserError(_('Please configure OCR first.'))
        if self.config_id.default_move_type != self.target_move_type:
            raise UserError(_('Please select an OCR configuration matching the invoice type.'))
        file_bytes = self._get_file_bytes()
        log = self.env['invoice.ocr.import.log'].create({
            'name': self.filename or 'OCR Import',
            'filename': self.filename,
            'provider': self.config_id.provider,
            'state': 'draft',
        })
        try:
            raw = AIInvoiceClient(self.config_id).extract_invoice(file_bytes, self.filename)
            normalized = normalize_invoice_json(raw)
            self.response_json = json.dumps(raw, ensure_ascii=False, indent=4)
            self.normalized_json = json.dumps(normalized, ensure_ascii=False, indent=4)
            self.state = 'preview'
            log.write({'state': 'success', 'response_json': self.normalized_json})
        except Exception as exc:
            log.write({'state': 'error', 'error_message': str(exc)})
            raise
        return {
            'name': _('Import External Invoice via OCR'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_invoice(self):
        self.ensure_one()
        if not self.normalized_json:
            raise UserError(_('Extract the invoice before creating the record.'))
        if self.config_id.default_move_type != self.target_move_type:
            raise UserError(_('Please select an OCR configuration matching the invoice type.'))
        data = json.loads(self.normalized_json)
        matcher = InvoiceOdooMatcher(self.env, self.config_id)
        vals = matcher.build_move_vals(data, self.filename)
        move = self.move_id or self.env['account.move'].create(vals)
        if self.move_id:
            move.write(vals)
        attachment = self.env['ir.attachment'].create({
            'name': self.filename,
            'res_model': 'account.move',
            'res_id': move.id,
            'type': 'binary',
            'datas': self.file_data,
            'mimetype': 'application/octet-stream',
        })
        move.write({
            'external_ocr_json': self.normalized_json,
            'external_ocr_text': self.raw_text or False,
            'external_ocr_attachment_id': attachment.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }
