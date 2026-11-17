# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_created_from_external_ocr = fields.Boolean(string='Created by External OCR', copy=False)
    external_ocr_json = fields.Text(string='OCR JSON', copy=False)
    external_ocr_text = fields.Text(string='OCR Raw Text', copy=False)
    external_ocr_source_filename = fields.Char(string='OCR Source File', copy=False)
    external_ocr_attachment_id = fields.Many2one('ir.attachment', string='OCR Original File', copy=False)

    def action_open_external_ocr_import(self):
        self.ensure_one()
        return {
            'name': 'Import External Invoice via OCR',
            'type': 'ir.actions.act_window',
            'res_model': 'invoice.ocr.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_target_move_type': self.move_type,
            },
        }
