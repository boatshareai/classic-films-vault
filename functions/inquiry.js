/**
 * Classic Films Vault — licensing inquiry handler.
 *
 * Sends the two emails the site promises:
 *   1. an auto-reply to the person who submitted the form
 *   2. a notification to the Classic Films Vault inbox
 *
 * No database. Nothing is stored — the emails *are* the record.
 *
 * Standard fetch handler, so it runs unmodified on Cloudflare Workers /
 * Cloudflare Pages Functions, and with a one-line shim on Netlify or Vercel
 * (see README.md).
 *
 * Required environment variables:
 *   RESEND_API_KEY  API key from your transactional email provider
 *   FROM_EMAIL      verified sender, e.g. "licensing@classicfilmsvault.com"
 *   NOTIFY_TO       inbox that should receive inquiry notifications
 * Optional:
 *   ALLOW_ORIGIN    site origin for CORS (defaults to "*")
 */

const USES = [
  "Streaming platform",
  "Broadcast",
  "Home video or digital sell-through",
  "Educational or institutional",
  "Other",
];
const VOLUMES = [
  "Single title",
  "Small package (2–10)",
  "Full or near-full catalog",
];

function clean(v, max = 2000) {
  return typeof v === "string" ? v.trim().slice(0, max) : "";
}

function validEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);
}

function esc(s) {
  return String(s).replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );
}

async function sendEmail(env, { to, subject, text, html, replyTo }) {
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: `Classic Films Vault <${env.FROM_EMAIL}>`,
      to: [to],
      subject,
      text,
      html,
      ...(replyTo ? { reply_to: replyTo } : {}),
    }),
  });
  if (!res.ok) {
    throw new Error(`email provider returned ${res.status}: ${await res.text()}`);
  }
}

export default {
  async fetch(request, env) {
    const origin = env.ALLOW_ORIGIN || "*";
    const cors = {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers: cors });
    }

    const json = (body, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { ...cors, "Content-Type": "application/json" },
      });

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "Invalid JSON body." }, 400);
    }

    const name = clean(body.name, 200);
    const company = clean(body.company, 200);
    const email = clean(body.email, 200);
    const titles = clean(body.titles, 1000);
    const message = clean(body.message, 5000);
    // Only accept the values the form actually offers.
    const use = USES.includes(clean(body.use)) ? clean(body.use) : "";
    const volume = VOLUMES.includes(clean(body.volume)) ? clean(body.volume) : "";

    if (!name || !company || !validEmail(email)) {
      return json(
        { error: "Name, company, and a valid email address are required." },
        400
      );
    }

    const notSpecified = "(not specified)";
    const about = titles || "the catalog";

    /* ---- 1. auto-reply to the inquirer ------------------------------- */
    const replyText =
      `Hi ${name},\n\n` +
      `Thanks for reaching out about ${about}. We'll review your request and ` +
      `get back to you within a few business days with availability, territory, ` +
      `and licensing terms.\n\n` +
      `If you need something sooner, feel free to reply directly to this email.\n\n` +
      `— Classic Films Vault`;

    const replyHtml =
      `<p>Hi ${esc(name)},</p>` +
      `<p>Thanks for reaching out about ${esc(about)}. We'll review your request ` +
      `and get back to you within a few business days with availability, ` +
      `territory, and licensing terms.</p>` +
      `<p>If you need something sooner, feel free to reply directly to this email.</p>` +
      `<p>&mdash; Classic Films Vault</p>`;

    /* ---- 2. internal notification ------------------------------------ */
    const rows = [
      ["Name", name],
      ["Company", company],
      ["Email", email],
      ["Titles of interest", titles || notSpecified],
      ["Intended use", use || notSpecified],
      ["Estimated volume", volume || notSpecified],
      ["Message", message || "(none)"],
    ];

    const notifyText = rows.map(([k, v]) => `${k}: ${v}`).join("\n");
    const notifyHtml =
      `<table cellpadding="6" style="border-collapse:collapse;font-family:sans-serif;font-size:14px">` +
      rows
        .map(
          ([k, v]) =>
            `<tr><td style="border-bottom:1px solid #e5e5e5;color:#666;vertical-align:top"><strong>${esc(
              k
            )}</strong></td><td style="border-bottom:1px solid #e5e5e5;white-space:pre-wrap">${esc(
              v
            )}</td></tr>`
        )
        .join("") +
      `</table>`;

    try {
      // The notification matters most — send it first and let it fail loudly.
      await sendEmail(env, {
        to: env.NOTIFY_TO,
        subject: `New licensing inquiry — ${company}`,
        text: notifyText,
        html: notifyHtml,
        replyTo: email,
      });

      // A failed auto-reply shouldn't lose us the lead, so don't fail the
      // request over it — just report it.
      let autoReplySent = true;
      try {
        await sendEmail(env, {
          to: email,
          subject: "We received your Classic Films Vault inquiry",
          text: replyText,
          html: replyHtml,
        });
      } catch (e) {
        autoReplySent = false;
        console.error("auto-reply failed:", e.message);
      }

      return json({ ok: true, autoReplySent });
    } catch (e) {
      console.error("inquiry failed:", e.message);
      return json({ error: "Could not send the inquiry. Please email us directly." }, 502);
    }
  },
};
