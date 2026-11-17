/** @odoo-module **/

import { registry } from "@web/core/registry";

function joinUrl(base, endpoint) {
    const cleanBase = (base || "").replace(/\/+$/, "");
    const cleanEndpoint = (endpoint || "").replace(/^\/?/, "/");
    return `${cleanBase}${cleanEndpoint}`;
}

export async function idTrustSigningAction(env, action) {
    const orm = env.services.orm;
    const actionService = env.services.action;
    const notification = env.services.notification;
    const invoiceId = action.params.invoice_id;
    try {
        const [invoice] = await orm.read("account.move", [invoiceId], ["company_id"]);
        const configs = await orm.searchRead(
                "digiit_model_elfatoora.config",
                [["company_id", "=", invoice.company_id[0]]],
                ["idtrust_local_service_url", "idtrust_certificate_endpoint", "idtrust_sign_endpoint"],
                { limit: 1 }
        );
        if (!configs.length) {
            throw new Error("Elfatoora configuration not found for this company.");
        }
        const config = configs[0];
        const certResponse = await fetch(joinUrl(config.idtrust_local_service_url, config.idtrust_certificate_endpoint), {
            method: "GET",
            headers: { Accept: "application/json" },
        });
        if (!certResponse.ok) {
            throw new Error(`ID-Trust certificate request failed (${certResponse.status}).`);
        }
        const certData = await certResponse.json();
        const prepared = await orm.call("account.move", "action_prepare_idtrust_signing", [invoiceId], {
            public_cert_b64: certData.public_cert_b64 || certData.certificate,
            credential_id: certData.credential_id || certData.credentialId || false,
        });

        const signResponse = await fetch(joinUrl(config.idtrust_local_service_url, config.idtrust_sign_endpoint), {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({
                hash_b64: prepared.hash_b64,
                credential_id: prepared.credential_id,
            }),
        });
        if (!signResponse.ok) {
            throw new Error(`ID-Trust signing request failed (${signResponse.status}).`);
        }
        const signData = await signResponse.json();
        const signature = signData.signature_value || signData.signature || signData.value;
        await orm.call("account.move", "action_finalize_idtrust_signing", [invoiceId], {
            signature_value: signature,
            middleware_response: JSON.stringify(signData),
        });
        notification.add("Invoice signed with ID-Trust USB token.", { type: "success" });
        return actionService.doAction({ type: "ir.actions.client", tag: "reload" });
    } catch (error) {
        notification.add(error.message || String(error), {
            type: "danger",
            title: "ID-Trust signing failed",
            sticky: true,
        });
        return actionService.doAction({ type: "ir.actions.client", tag: "reload" });
    }
}

registry.category("actions").add("idtrust_start_signing", idTrustSigningAction);
