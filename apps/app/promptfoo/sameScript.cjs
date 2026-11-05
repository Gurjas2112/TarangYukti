// promptfoo assertion: the reply body is written in the script of the requested language (spec §6.5).
// Same Unicode ranges and thresholds as the agent's validator (apps/agent/src/validator.py).
const SCRIPTS = {
  Latn: /[A-Za-z]/gu, Deva: /[ऀ-ॿ]/gu, Beng: /[ঀ-৿]/gu, Guru: /[਀-੿]/gu,
  Gujr: /[઀-૿]/gu, Orya: /[଀-୿]/gu, Taml: /[஀-௿]/gu, Telu: /[ఀ-౿]/gu,
  Knda: /[ಀ-೿]/gu, Mlym: /[ഀ-ൿ]/gu, Arab: /[؀-ۿݐ-ݿ]/gu,
  Olck: /[᱐-᱿]/gu, Mtei: /[ꯀ-꯿]/gu,
};

module.exports = (output, context) => {
  const script = context.vars.script || "Latn";
  const letters = output.replace(/\[K\d+\]/g, "").replace(/[\s\d.,:;!?()[\]\-–—'"/%°|।꯫۔]+/gu, "");
  const ours = (letters.match(SCRIPTS[script] || SCRIPTS.Latn) || []).length;
  const share = letters.length ? ours / letters.length : 0;
  const need = script === "Latn" ? 0.6 : 0.3;
  return { pass: share >= need, score: share, reason: `${Math.round(share * 100)}% of letters in ${script} (need ${need * 100}%)` };
};
