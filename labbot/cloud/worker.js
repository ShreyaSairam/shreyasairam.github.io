// LabBot cloud parser: a Cloudflare Worker that asks Gemini to turn a lab
// command into tool calls. It returns the same {steps, unknown} shape as the
// on-device parser in core.js, so the page can fall back to that at any time.
//
// Secrets / vars:  GEMINI_API_KEY (secret), GEMINI_MODEL (optional), ALLOW_ORIGIN (optional)

const PLACES = ["A", "B", "C", "fridge", "centrifuge", "rack", "dock", "auto"];

const TOOL = {
  name: "plan_lab_tasks",
  description: "Plan the robot's tasks from the user's command, in the order they should run.",
  parameters: {
    type: "OBJECT",
    properties: {
      steps: {
        type: "ARRAY",
        items: {
          type: "OBJECT",
          properties: {
            op: { type: "STRING", enum: ["move", "goto"], description: "move a sample, or drive somewhere" },
            sample: { type: "INTEGER", description: "sample id 1-6 (same as bed number). Only for move." },
            to: { type: "STRING", enum: PLACES, description: "A/B/C analysers, fridge, centrifuge, rack (reception), dock (charge), or auto = the right analyser for the test" }
          },
          required: ["op", "to"]
        }
      },
      unknown: { type: "ARRAY", items: { type: "STRING" }, description: "parts of the command that are not lab tasks" }
    },
    required: ["steps"]
  }
};

function prompt(text, samples) {
  return [
    "You control LabBot, a hospital lab robot. Samples (id = bed number):",
    JSON.stringify(samples),
    "Analyser A runs blood count, B runs chemistry, C runs urine.",
    "Rules: urgent samples first; 'all' and 'the rest' mean samples not done and not already named;",
    "if the user names an analyser, pass it as given (the app checks it); otherwise use 'auto'.",
    "Command: " + text
  ].join("\n");
}

function clean(out) {
  const steps = (out.steps || []).filter(s =>
    s && (s.op === "move" || s.op === "goto") && PLACES.includes(s.to) &&
    (s.op === "goto" ? s.to !== "auto" : Number.isInteger(s.sample) && s.sample >= 1 && s.sample <= 999 && s.to !== "dock")
  ).slice(0, 20).map(s => s.op === "goto" ? { op: "goto", to: s.to } : { op: "move", sample: s.sample, to: s.to });
  const unknown = (out.unknown || []).filter(u => typeof u === "string").slice(0, 5).map(u => u.slice(0, 80));
  return { steps, unknown };
}

export default {
  async fetch(req, env) {
    const cors = {
      "access-control-allow-origin": env.ALLOW_ORIGIN || "https://shreyasairam.github.io",
      "access-control-allow-methods": "POST, OPTIONS",
      "access-control-allow-headers": "content-type"
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "POST") return new Response("POST only", { status: 405, headers: cors });

    let body;
    try { body = await req.json(); } catch { return Response.json({ error: "bad json" }, { status: 400, headers: cors }); }
    const text = String(body.text || "").slice(0, 300);
    const samples = Array.isArray(body.samples) ? body.samples.slice(0, 6) : [];
    if (!text) return Response.json({ steps: [], unknown: [] }, { headers: cors });

    const model = env.GEMINI_MODEL || "gemini-2.5-flash";
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: prompt(text, samples) }] }],
        tools: [{ functionDeclarations: [TOOL] }],
        toolConfig: { functionCallingConfig: { mode: "ANY", allowedFunctionNames: [TOOL.name] } },
        generationConfig: { temperature: 0 }
      })
    });
    if (!r.ok) return Response.json({ error: "llm unavailable" }, { status: 502, headers: cors });
    const j = await r.json();
    const call = j?.candidates?.[0]?.content?.parts?.find(p => p.functionCall)?.functionCall;
    return Response.json(clean(call?.args || {}), { headers: cors });
  }
};
