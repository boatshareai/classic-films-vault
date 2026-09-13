/* ------------------------------------------------------------------
   Classic Films Vault — form configuration

   Set ENDPOINT to the URL that receives inquiries. Until you do, the
   form shows a "not connected yet" notice instead of pretending to send.

   Two supported options (see README.md for full instructions):

   1. Serverless function (recommended — gives the exact personalised
      auto-reply wording). Deploy functions/inquiry.js and point
      ENDPOINT at it, e.g. "/api/inquiry".

   2. A form-to-email service such as Web3Forms or FormSubmit. Paste the
      endpoint they give you and set MODE to "service". Note that these
      send a fixed auto-reply body rather than a personalised one.
   ------------------------------------------------------------------ */

window.CFV_CONFIG = {
  // e.g. "/api/inquiry"  or  "https://api.web3forms.com/submit"
  ENDPOINT: "",

  // "function" = our serverless handler  |  "service" = third-party form service
  MODE: "function",

  // Only used when MODE is "service": the access key that service issues you.
  ACCESS_KEY: "",

  // Where internal notifications go. The serverless function reads its own
  // env var for this; it is here only so "service" mode can pass it along.
  NOTIFY_TO: "",
};
