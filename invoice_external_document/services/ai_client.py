# -*- coding: utf-8 -*-
import base64
import io
import json
import mimetypes
import requests
from odoo.exceptions import UserError


PROMPT = '''
Extract invoice data from this PDF/image and return ONLY valid JSON with this schema:
{
  "customer": {
    "name": string|null,
    "email": string|null,
    "vat": string|null,
    "street": string|null
  },
  "invoice_date": "YYYY-MM-DD"|null,
  "due_date": "YYYY-MM-DD"|null,
  "payment_terms": string|null,
  "currency": "TND"|null,
  "invoice_number": string|null,
  "amount_untaxed": number|null,
  "amount_tax": number|null,
  "amount_total": number|null,
  "invoice_lines": [
    {
      "product_code": string|null,
      "name": string,
      "quantity": number,
      "price_unit": number,
      "discount": number|null,
      "taxes": [
        {"name": "TVA", "rate": number},
        {"name": "FODEC", "rate": number}
      ]
    }
  ]
}
Rules:
- normalize dates to YYYY-MM-DD
- numbers as decimals
- no markdown
- no comments
- extract taxes per invoice line
- if TVA exists, add it as {"name": "TVA", "rate": 19} or the detected rate
- if FODEC exists, add it as {"name": "FODEC", "rate": 1}
- do not apply FODEC to all lines unless the invoice clearly applies FODEC to all lines
- if FODEC applies only to one line, include FODEC only on that line
- discount must be a percentage value, example 5% => 5.0, not an amount
'''

GROQ_VISION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'


def _extract_json(text):
    text = (text or '').strip()
    if text.startswith('```'):
        text = text.strip('`')
        text = text.replace('json\n', '', 1).replace('JSON\n', '', 1)
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end >= start:
        text = text[start:end + 1]
    return json.loads(text)


def _guess_mime(filename):
    return mimetypes.guess_type(filename or '')[0] or 'application/octet-stream'


def _is_pdf(file_bytes, filename, mime):
    return mime == 'application/pdf' or (file_bytes or b'').lstrip().startswith(b'%PDF')


def _pdf_first_page_to_png(file_bytes):
    try:
        import fitz
        with fitz.open(stream=file_bytes, filetype='pdf') as document:
            if not document.page_count:
                raise UserError('The PDF has no pages to process.')
            page = document.load_page(0)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            return pixmap.tobytes('png')
    except ImportError:
        pass
    except UserError:
        raise
    except Exception as exc:
        raise UserError('Could not convert PDF page to image for Groq Vision: %s' % exc)

    try:
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(file_bytes)
        if len(document) == 0:
            raise UserError('The PDF has no pages to process.')
        page = document[0]
        bitmap = page.render(scale=2)
        image = bitmap.to_pil()
        if image.mode != 'RGB':
            image = image.convert('RGB')
        output = io.BytesIO()
        image.save(output, format='PNG', optimize=True)
        return output.getvalue()
    except ImportError:
        raise UserError('Install PyMuPDF or pypdfium2 to use PDF files with Groq Vision.')
    except UserError:
        raise
    except Exception as exc:
        raise UserError('Could not convert PDF page to image for Groq Vision: %s' % exc)


def _get_groq_model(model_name):
    model = (model_name or '').strip()
    if not model or model.startswith('gemini-') or model.startswith('models/'):
        return GROQ_VISION_MODEL
    if model.startswith('llama-4-'):
        return 'meta-llama/%s' % model
    if model == 'meta-llama/llama-3.3-70b-versatile':
        return GROQ_VISION_MODEL
    return model


class AIInvoiceClient:
    def __init__(self, config):
        self.config = config

    def extract_invoice(self, file_bytes, filename):
        provider = self.config.provider
        if provider == 'gemini':
            return self._call_gemini(file_bytes, filename)
        if provider == 'groq':
            return self._call_groq(file_bytes, filename)
        return self._call_custom_api(file_bytes, filename)

    def _call_custom_api(self, file_bytes, filename):
        if not self.config.endpoint_url:
            raise UserError('Custom OCR endpoint URL is not configured.')
        files = {'file': (filename, file_bytes, _guess_mime(filename))}
        data = {'prompt': PROMPT, 'model': self.config.model_name or ''}
        headers = {}
        if self.config.api_key:
            headers['Authorization'] = 'Bearer %s' % self.config.api_key
        res = requests.post(self.config.endpoint_url, files=files, data=data, headers=headers, timeout=120)
        if res.status_code >= 400:
            raise UserError('OCR API error %s: %s' % (res.status_code, res.text[:500]))
        payload = res.json()
        return payload.get('response') or payload

    def _call_gemini(self, file_bytes, filename):
        if not self.config.api_key:
            raise UserError('Gemini API key is not configured.')

        model = (self.config.model_name or 'gemini-2.5-flash').strip()
        model = model.replace('models/', '')

        url = 'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s' % (
            model,
            self.config.api_key
        )

        mime = _guess_mime(filename)

        body = {
            'contents': [{
                'parts': [
                    {'text': PROMPT},
                    {
                        'inline_data': {
                            'mime_type': mime,
                            'data': base64.b64encode(file_bytes).decode()
                        }
                    },
                ]
            }],
            'generationConfig': {
                'temperature': 0.0,
                'responseMimeType': 'application/json'
            }
        }

        res = requests.post(url, json=body, timeout=120)

        if res.status_code >= 400:
            raise UserError('Gemini error %s: %s' % (res.status_code, res.text[:500]))

        text = res.json()['candidates'][0]['content']['parts'][0].get('text', '{}')
        return _extract_json(text)

    def _call_groq(self, file_bytes, filename):
        if not self.config.api_key:
            raise UserError('Groq API key is not configured.')

        mime = _guess_mime(filename)

        if _is_pdf(file_bytes, filename, mime):
            file_bytes = _pdf_first_page_to_png(file_bytes)
            mime = 'image/png'

        if not mime.startswith('image/'):
            raise UserError('Groq accepts image files only for vision OCR.')

        # Groq base64 image limit is 4MB encoded
        image_b64 = base64.b64encode(file_bytes).decode()
        if len(image_b64.encode('utf-8')) > 4 * 1024 * 1024:
            raise UserError('Image too large for Groq Vision. Please compress or resize it.')

        model = _get_groq_model(self.config.model_name)

        url = 'https://api.groq.com/openai/v1/chat/completions'

        body = {
            'model': model,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': PROMPT
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': 'data:%s;base64,%s' % (mime, image_b64)
                            }
                        }
                    ]
                }
            ],
            'temperature': 0,
            'response_format': {
                'type': 'json_object'
            }
        }

        headers = {
            'Authorization': 'Bearer %s' % self.config.api_key,
            'Content-Type': 'application/json'
        }

        res = requests.post(url, json=body, headers=headers, timeout=120)

        if res.status_code >= 400:
            raise UserError('Groq error %s with model %s: %s' % (res.status_code, model, res.text[:500]))

        payload = res.json()
        text = payload['choices'][0]['message'].get('content', '{}')

        return _extract_json(text)
