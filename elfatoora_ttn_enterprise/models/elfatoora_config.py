from odoo import fields, models


class ElfatooraConfig(models.Model):
    _inherit = "digiit_model_elfatoora.config"

    enterprise_p12_file = fields.Binary(
        string="Enterprise-ID Certificate (.p12/.pfx)",
        attachment=True,
        help="PKCS#12 certificate used to sign TEIF XML locally on the Odoo server.",
    )
    enterprise_p12_filename = fields.Char(string="Certificate Filename")
    enterprise_p12_password = fields.Char(
        string="Certificate Password",
        help="Password used to open the Enterprise-ID PKCS#12 certificate.",
    )
