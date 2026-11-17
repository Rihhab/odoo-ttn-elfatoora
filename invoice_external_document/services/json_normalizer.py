# -*- coding: utf-8 -*-
from datetime import datetime


def as_float(value, default=0.0):
    if value in (None, False, ''):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).replace(' ', '').replace(',', '.')
    try:
        return float(value)
    except Exception:
        return default


def parse_date(value):
    if not value:
        return False
    value = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d-%m-%y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except Exception:
            pass
    return False


def normalize_invoice_json(data):
    data = data.get('response', data) if isinstance(data, dict) else {}
    customer = data.get('customer') or data.get('partner') or {}
    lines = []

    for line in data.get('invoice_lines') or data.get('lines') or []:
        name = line.get('name') or line.get('display_name') or line.get('label') or 'OCR Product'

        taxes = line.get('taxes') or []
        if not taxes and line.get('tax_rate'):
            taxes = [{'name': 'TVA', 'rate': line.get('tax_rate')}]

        lines.append({
            'product_code': line.get('product_code') or line.get('product_id') or line.get('default_code'),
            'name': name.replace('\n', ' ').strip() if isinstance(name, str) else str(name),
            'quantity': as_float(line.get('quantity'), 1.0),
            'price_unit': as_float(line.get('price_unit'), 0.0),
            'discount': as_float(line.get('discount'), 0.0),
            'tax_rate': line.get('tax_rate'),
            'taxes': taxes,
        })

    currency = data.get('currency')
    if isinstance(currency, dict):
        currency = currency.get('name') or currency.get('full_name')

    return {
        'customer': {
            'name': customer.get('name') or customer.get('display_name'),
            'email': customer.get('email'),
            'vat': customer.get('vat') or customer.get('partner_vat_placeholder'),
            'street': customer.get('street') or customer.get('address'),
        },
        'invoice_date': parse_date(data.get('invoice_date')),
        'due_date': parse_date(data.get('due_date')),
        'currency': currency or 'TND',
        'invoice_number': data.get('invoice_number') or data.get('reference'),
        'amount_untaxed': as_float(data.get('amount_untaxed'), 0.0),
        'amount_tax': as_float(data.get('amount_tax'), 0.0),
        'amount_total': as_float(data.get('amount_total'), 0.0),
        'invoice_lines': lines,
    }