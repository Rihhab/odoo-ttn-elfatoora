# -*- coding: utf-8 -*-
from odoo import fields


class InvoiceOdooMatcher:
    def __init__(self, env, config):
        self.env = env
        self.config = config

    def find_or_create_partner(self, customer):
        Partner = self.env['res.partner'].sudo()
        vat = (customer.get('vat') or '').strip()
        name = (customer.get('name') or vat or 'OCR Partner').strip()
        partner = Partner.browse()

        if vat:
            partner = Partner.search(['|', ('vat', '=', vat), ('ref', '=', vat)], limit=1)

        if not partner and name:
            partner = Partner.search([('name', '=ilike', name)], limit=1)

        if not partner and self.config.create_missing_partner:
            partner = Partner.create({
                'name': name,
                'email': customer.get('email') or False,
                'vat': vat or False,
                'street': customer.get('street') or False,
                'company_type': 'company',
            })

        return partner

    def find_currency(self, currency_name):
        return self.env['res.currency'].search([('name', '=', currency_name or 'TND')], limit=1)

    def find_or_create_product(self, line):
        Product = self.env['product.product'].sudo()
        code = (line.get('product_code') or '').strip()
        name = (line.get('name') or code or 'OCR Product').strip()
        product = Product.browse()

        if code:
            product = Product.search(['|', ('default_code', '=', code), ('barcode', '=', code)], limit=1)

        if not product:
            product = Product.search([('name', '=ilike', name)], limit=1)

        if not product and self.config.create_missing_product:
            product = Product.create({
                'name': name,
                'default_code': code or False,
                'type': 'service',
                'list_price': line.get('price_unit') or 0.0,
            })

        return product

    def find_tax(self, tax_rate, move_type):
        if tax_rate in (None, False, ''):
            return self.config.default_tax_id

        try:
            amount = float(str(tax_rate).replace(',', '.'))
        except Exception:
            return self.config.default_tax_id

        use = 'sale' if move_type == 'out_invoice' else 'purchase'

        return self.env['account.tax'].search([
            ('type_tax_use', '=', use),
            ('amount', '=', amount),
            ('company_id', 'in', [False, self.env.company.id]),
        ], limit=1) or self.config.default_tax_id

    def find_taxes(self, line, move_type):
        use = 'sale' if move_type == 'out_invoice' else 'purchase'
        Tax = self.env['account.tax'].sudo()
        tax_ids = []

        taxes = line.get('taxes') or []

        if not taxes and line.get('tax_rate'):
            taxes = [{'name': 'TVA', 'rate': line.get('tax_rate')}]

        for tax in taxes:
            if isinstance(tax, str):
                tax_name = tax
                tax_rate = ''.join(ch for ch in tax if ch.isdigit() or ch in '.,')
                tax = {'name': tax_name, 'rate': tax_rate}

            name = (tax.get('name') or '').strip()
            rate = tax.get('rate')

            try:
                amount = float(str(rate).replace(',', '.'))
            except Exception:
                continue

            domain = [
                ('type_tax_use', '=', use),
                ('amount', '=', amount),
                ('company_id', 'in', [False, self.env.company.id]),
            ]

            if name:
                domain.append(('name', 'ilike', name))

            tax_record = Tax.search(domain, limit=1)

            if not tax_record and amount == 1:
                tax_record = Tax.search([
                    ('type_tax_use', '=', use),
                    ('amount', '=', 1),
                    ('name', 'ilike', 'FODEC'),
                    ('company_id', 'in', [False, self.env.company.id]),
                ], limit=1)

            if tax_record:
                tax_ids.append(tax_record.id)

        if not tax_ids and self.config.default_tax_id:
            tax_ids = self.config.default_tax_id.ids

        return Tax.browse(tax_ids)

    def build_move_vals(self, data, filename=False):
        move_type = self.config.default_move_type
        partner = self.find_or_create_partner(data.get('customer') or {})
        currency = self.find_currency(data.get('currency'))
        invoice_lines = []

        for line in data.get('invoice_lines') or []:
            product = self.find_or_create_product(line)
            taxes = self.find_taxes(line, move_type)

            invoice_lines.append((0, 0, {
                'product_id': product.id if product else False,
                'name': line.get('name') or (product.display_name if product else 'OCR Line'),
                'quantity': line.get('quantity') or 1.0,
                'price_unit': line.get('price_unit') or 0.0,
                'discount': line.get('discount') or 0.0,
                'tax_ids': [(6, 0, taxes.ids)] if taxes else False,
            }))

        return {
            'move_type': move_type,
            'partner_id': partner.id if partner else False,
            'invoice_date': data.get('invoice_date') or fields.Date.context_today(self.env.user),
            'invoice_date_due': data.get('due_date') or False,
            'currency_id': currency.id if currency else self.env.company.currency_id.id,
            'ref': data.get('invoice_number') or False,
            'invoice_line_ids': invoice_lines,
            'is_created_from_external_ocr': True,
            'external_ocr_source_filename': filename,
        }