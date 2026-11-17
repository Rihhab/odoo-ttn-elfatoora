import base64

from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_prepare_idtrust_signing(self, public_cert_b64=None, credential_id=None):
        self.ensure_one()
        if not public_cert_b64:
            raise UserError(_("No public certificate was returned by the ID-Trust middleware."))

        from odoo.addons.elfatoora_ttn_base.services.digital_signature import DigitalSignature
        from odoo.addons.elfatoora_ttn_base.services.teif_generator import TEIFGenerator

        config = self.env["digiit_model_elfatoora.config"].search([("company_id", "=", self.company_id.id)], limit=1)
        if not config:
            raise UserError(_("Elfatoora configuration not found for this company."))

        xml_content = TEIFGenerator(self).generate_xml()
        signer = DigitalSignature()
        digest_to_sign_bytes, context = signer.prepare_remote_signing(xml_content, public_cert_b64)
        hash_b64 = base64.b64encode(digest_to_sign_bytes).decode()

        from lxml import etree

        prepared_xml = etree.tostring(context["root"], pretty_print=False, encoding="UTF-8", xml_declaration=True).decode("utf-8")
        self.write(
            {
                "pending_signing_hash": hash_b64,
                "pending_signing_xml": prepared_xml,
                "pending_signing_credential_id": credential_id or False,
            }
        )
        return {"hash_b64": hash_b64, "credential_id": credential_id or False}

    def action_finalize_idtrust_signing(self, signature_value=None, middleware_response=None):
        self.ensure_one()
        if not signature_value:
            raise UserError(_("No signature value was returned by the ID-Trust middleware."))
        if not self.pending_signing_hash or not self.pending_signing_xml:
            raise UserError(_("No pending ID-Trust transaction found for this invoice."))

        from odoo.addons.elfatoora_ttn_base.services.digital_signature import DigitalSignature

        config = self.env["digiit_model_elfatoora.config"].search([("company_id", "=", self.company_id.id)], limit=1)
        if not config:
            raise UserError(_("Elfatoora configuration not found for this company."))

        signer = DigitalSignature()
        signed_xml = signer.embed_signature(self.pending_signing_xml, signature_value)
        self._save_signed_submission(signed_xml, config, extra_response=middleware_response)
        self.write(
            {
                "pending_signing_hash": False,
                "pending_signing_xml": False,
                "pending_signing_credential_id": False,
            }
        )
        return True
