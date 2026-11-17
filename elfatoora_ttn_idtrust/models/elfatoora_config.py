from odoo import fields, models


class ElfatooraConfig(models.Model):
    _inherit = "digiit_model_elfatoora.config"

    idtrust_local_service_url = fields.Char(
        string="ID-Trust Local Service URL",
        default="http://127.0.0.1:8765",
        help="Local middleware URL on the user's workstation. It must expose certificate and signing endpoints.",
    )
    idtrust_certificate_endpoint = fields.Char(
        string="Certificate Endpoint",
        default="/certificate",
        help="Endpoint returning JSON with public_cert_b64 and optional credential_id.",
    )
    idtrust_sign_endpoint = fields.Char(
        string="Sign Endpoint",
        default="/sign",
        help="Endpoint accepting JSON with hash_b64 and returning signature_value.",
    )
