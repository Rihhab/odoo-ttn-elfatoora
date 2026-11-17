import base64

from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _submit_with_enterprise_cert(self):
        self.ensure_one()

        from odoo.addons.elfatoora_ttn_base.services.digital_signature import DigitalSignature
        from odoo.addons.elfatoora_ttn_base.services.teif_generator import TEIFGenerator

        config = self.env["digiit_model_elfatoora.config"].search([("company_id", "=", self.company_id.id)], limit=1)
        if not config:
            raise UserError(_("Elfatoora configuration not found for this company."))
        if not config.enterprise_p12_file:
            raise UserError(_("Please upload the Enterprise-ID certificate in Elfatoora Configuration."))

        try:
            xml_content = TEIFGenerator(self).generate_xml()
            p12_content = base64.b64decode(config.enterprise_p12_file)
            signer = DigitalSignature(
                p12_content=p12_content,
                p12_password=config.enterprise_p12_password,
            )
            signed_xml = signer.sign_xml(xml_content)
            self._save_signed_submission(signed_xml, config)
            return True
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("Enterprise-ID signing failed: %s") % str(e))
