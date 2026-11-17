import base64
import io
import os
from copy import deepcopy
from datetime import datetime

import qrcode
from lxml import etree

from odoo import api, fields, models, _


DS_NS = "http://www.w3.org/2000/09/xmldsig#"
QR_NS = {"ds": DS_NS}


class ElfatooraSandboxSubmission(models.Model):
    _name = "elfatoora.sandbox.submission"
    _description = "Local Elfatoora Demo Submission"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, default="New", copy=False)
    company_id = fields.Many2one("res.company", required=True, index=True, ondelete="cascade")
    document_number = fields.Char(index=True)
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("validated", "Validated (Demo)"),
            ("rejected", "Rejected"),
        ],
        required=True,
        default="pending",
        index=True,
    )
    message = fields.Text()
    document_xml = fields.Binary(attachment=True, required=True)
    returned_xml = fields.Binary(attachment=True)
    generated_ref = fields.Char(index=True)
    qr_payload = fields.Char()
    processing_date = fields.Datetime()
    validation_date = fields.Datetime()
    poll_count = fields.Integer(default=0)

    @api.model
    def _schema(self):
        schema_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "schemas", "facture_INVOIC_V1.8.8_withoutSig.xsd")
        )
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        schema_doc = etree.parse(schema_path, parser)
        # The bundled TTN schema is XSD 1.1, while lxml/libxml2 only supports
        # XSD 1.0. Compile a compatibility copy in memory: keep the declared
        # structure, use the shared partner type where the schema has a
        # conditional type alternative, and omit XSD 1.1 assertions.
        xs_ns = "http://www.w3.org/2001/XMLSchema"
        alternatives = schema_doc.xpath("//xs:element[xs:alternative]", namespaces={"xs": xs_ns})
        for element in alternatives:
            element.set("type", "PartDetailType")
            for child in element.findall(f"{{{xs_ns}}}alternative"):
                element.remove(child)
        for assertion in schema_doc.xpath("//xs:assert", namespaces={"xs": xs_ns}):
            assertion.getparent().remove(assertion)
        return etree.XMLSchema(schema_doc)

    @api.model
    def _read_and_validate(self, document_xml, company_vat):
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, recover=False)
        try:
            root = etree.fromstring(document_xml, parser)
        except (etree.XMLSyntaxError, ValueError) as exc:
            return False, _("Invalid XML: %s") % str(exc), False

        if etree.QName(root).localname != "TEIF":
            return False, _("The document root must be TEIF."), False
        if root.get("version") != "1.8.8":
            return False, _("The demo API accepts TEIF version 1.8.8 only."), False

        sender = root.findtext("InvoiceHeader/MessageSenderIdentifier")
        if not sender:
            return False, _("MessageSenderIdentifier is missing."), False
        if sender.strip() != (company_vat or "").strip():
            return False, _("MessageSenderIdentifier does not match the configured company matricule."), False

        signatures = root.findall("ds:Signature", namespaces=QR_NS)
        if not signatures:
            return False, _("A signed TEIF document is required."), False
        if any(not (signature.findtext("ds:SignatureValue", namespaces=QR_NS) or "").strip() for signature in signatures):
            return False, _("Every XML Signature must contain a SignatureValue."), False

        unsigned_for_schema = deepcopy(root)
        for signature in unsigned_for_schema.findall("ds:Signature", namespaces=QR_NS):
            unsigned_for_schema.remove(signature)

        try:
            self._schema().assertValid(unsigned_for_schema)
        except etree.DocumentInvalid as exc:
            detail = exc.error_log.last_error.message if exc.error_log.last_error else str(exc)
            return False, _("TEIF 1.8.8 schema validation failed: %s") % detail, False
        except (OSError, etree.XMLSchemaParseError, etree.XMLSyntaxError) as exc:
            return False, _("Could not load the bundled TEIF schema: %s") % str(exc), False

        document_number = root.findtext("InvoiceBody/Bgm/DocumentIdentifier") or ""
        return True, False, document_number.strip()

    @api.model
    def submit_document(self, config, document_xml):
        is_valid, error_message, document_number = self._read_and_validate(document_xml, config.company_vat)
        vals = {
            "company_id": config.company_id.id,
            "document_number": document_number,
            "status": "pending" if is_valid else "rejected",
            "message": _("Invoice received by the local demo service.") if is_valid else error_message,
            "document_xml": base64.b64encode(document_xml),
            "processing_date": fields.Datetime.now(),
        }
        submission = self.sudo().create(vals)
        submission.name = self.env["ir.sequence"].sudo().next_by_code("elfatoora.sandbox.submission") or f"SIM-{submission.id}"
        return submission._as_api_result()

    def _as_api_result(self):
        self.ensure_one()
        result = {
            "idSaveEfact": self.id,
            "tracking_number": str(self.id),
            "status": self.status,
            "message": self.message or "",
            "processing_date": fields.Datetime.to_string(self.processing_date) if self.processing_date else False,
            "generatedRef": self.generated_ref or False,
            "ttn_ref": self.generated_ref or False,
            "validation_date": fields.Datetime.to_string(self.validation_date) if self.validation_date else False,
        }
        if self.returned_xml:
            result["xmlContent"] = base64.b64encode(base64.b64decode(self.returned_xml)).decode("ascii")
        return result

    def _build_demo_return_xml(self):
        self.ensure_one()
        xml_bytes = base64.b64decode(self.document_xml)
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        root = etree.fromstring(xml_bytes, parser)

        self.generated_ref = self.name
        self.qr_payload = f"ELFATOORA-SANDBOX|{self.generated_ref}|{self.document_number or ''}"
        qr_image = qrcode.make(self.qr_payload)
        image_buffer = io.BytesIO()
        qr_image.save(image_buffer, format="PNG")
        qr_b64 = base64.b64encode(image_buffer.getvalue()).decode("ascii")

        ref_ttn = etree.Element("RefTtnVal")
        etree.SubElement(ref_ttn, "ReferenceTTN", refID="I-88").text = self.generated_ref
        reference_date = etree.SubElement(ref_ttn, "ReferenceDate")
        date_text = etree.SubElement(reference_date, "DateText", format="ddMMyyHHmm", functionCode="I-37")
        date_text.text = datetime.utcnow().strftime("%d%m%y%H%M")
        etree.SubElement(ref_ttn, "ReferenceCEV").text = qr_b64

        first_signature = root.find("ds:Signature", namespaces=QR_NS)
        insert_at = list(root).index(first_signature) if first_signature is not None else len(root)
        root.insert(insert_at, ref_ttn)
        return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=False)

    def consult(self, generated_ref=None, tracking_number=None, document_number=None):
        self.ensure_one()
        if self.status == "pending":
            now = fields.Datetime.now()
            returned_xml = self._build_demo_return_xml()
            self.write(
                {
                    "status": "validated",
                    "message": _("TEIF structure accepted by the local demo validator. This is not TTN validation."),
                    "processing_date": now,
                    "validation_date": now,
                    "returned_xml": base64.b64encode(returned_xml),
                }
            )
        return self._as_api_result()

    @api.model
    def find_for_consult(self, config, criteria):
        criteria = criteria or {}
        domain = [("company_id", "=", config.company_id.id)]
        generated_ref = criteria.get("generatedRef") or criteria.get("generated_ref")
        tracking_number = criteria.get("idSaveEfact") or criteria.get("tracking_number")
        document_number = criteria.get("documentNumber") or criteria.get("document_number")

        if generated_ref:
            domain.append(("generated_ref", "=", str(generated_ref)))
        elif tracking_number:
            try:
                domain.append(("id", "=", int(tracking_number)))
            except (TypeError, ValueError):
                return False
        elif document_number:
            domain.append(("document_number", "=", str(document_number)))
        else:
            return False

        submission = self.sudo().search(domain, limit=1)
        return submission.consult(generated_ref=generated_ref, tracking_number=tracking_number) if submission else False

    @api.model
    def verify_demo_qr(self, config, qr_payload):
        if not qr_payload:
            return {"valid": False, "message": _("QR value is required.")}
        submission = self.sudo().search(
            [
                ("company_id", "=", config.company_id.id),
                ("qr_payload", "=", str(qr_payload)),
                ("status", "=", "validated"),
            ],
            limit=1,
        )
        if not submission:
            return {"valid": False, "message": _("QR value was not issued by this local demo service.")}
        return {
            "valid": True,
            "status": "validated_demo",
            "generatedRef": submission.generated_ref,
            "message": _("QR value is valid in the local demo database only."),
        }
