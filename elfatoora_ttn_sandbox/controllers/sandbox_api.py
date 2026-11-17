import hmac
import json
import logging

from odoo import http, _
from odoo.http import request


_logger = logging.getLogger(__name__)


class ElfatooraSandboxAPI(http.Controller):
    def _response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            headers=[("Content-Type", "application/json; charset=utf-8")],
        )

    def _authenticate(self, payload):
        login = str(payload.get("login") or "")
        password = str(payload.get("password") or "")
        matricule = str(payload.get("matricule") or "")
        if not login or not password or not matricule:
            return False

        configs = request.env["digiit_model_elfatoora.config"].sudo().search([("company_vat", "=", matricule)])
        for config in configs:
            if hmac.compare_digest(str(config.api_username or ""), login) and hmac.compare_digest(str(config.api_password or ""), password):
                return config
        return False

    @http.route(
        "/elfatoora/sandbox/v1/<string:operation>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def call(self, operation, **kwargs):
        if operation not in {"saveEfact", "consultEfact", "verifyQrCode"}:
            return self._response({"message": _("Unknown operation.")}, status=404)

        payload = request.httprequest.get_json(silent=True)
        if not isinstance(payload, dict):
            return self._response({"message": _("A JSON object is required.")}, status=400)

        config = self._authenticate(payload)
        if not config:
            return self._response({"message": _("Invalid API credentials or matricule.")}, status=401)

        service = request.env["elfatoora.sandbox.submission"].sudo()
        if operation == "saveEfact":
            encoded_xml = payload.get("documentEfact")
            if not isinstance(encoded_xml, str) or not encoded_xml:
                return self._response({"message": _("documentEfact must contain base64-encoded XML.")}, status=400)
            if len(encoded_xml) > 16 * 1024 * 1024:
                return self._response({"message": _("Invoice XML exceeds the 16 MiB demo limit.")}, status=413)
            try:
                import base64

                document_xml = base64.b64decode(encoded_xml, validate=True)
            except Exception:
                return self._response({"message": _("documentEfact is not valid base64.")}, status=400)
            result = service.submit_document(config, document_xml)
            return self._response(result)

        if operation == "consultEfact":
            criteria = payload.get("efactCriteria") or {}
            if not isinstance(criteria, dict):
                return self._response({"message": _("efactCriteria must be a JSON object.")}, status=400)
            result = service.find_for_consult(config, criteria)
            if not result:
                return self._response(
                    {
                        "status": "pending",
                        "message": _("No demo invoice matched the supplied criteria."),
                        "tracking_number": str(criteria.get("idSaveEfact") or ""),
                    }
                )
            return self._response(result)

        result = service.verify_demo_qr(config, payload.get("qrCode"))
        return self._response(result)
