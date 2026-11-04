// All 23 interface catalogues (spec §6.5). Generated list — keep in step with config/languages.yaml
// (scripts/i18n_draft.py writes languages.json and drafts the files; CI checks every key exists).
import hiIN from "./hi-IN.json";
import bnIN from "./bn-IN.json";
import mrIN from "./mr-IN.json";
import teIN from "./te-IN.json";
import taIN from "./ta-IN.json";
import guIN from "./gu-IN.json";
import knIN from "./kn-IN.json";
import mlIN from "./ml-IN.json";
import orIN from "./or-IN.json";
import paIN from "./pa-IN.json";
import enIN from "./en-IN.json";
import gomIN from "./gom-IN.json";
import urIN from "./ur-IN.json";
import asIN from "./as-IN.json";
import neIN from "./ne-IN.json";
import ksIN from "./ks-IN.json";
import sdIN from "./sd-IN.json";
import satIN from "./sat-IN.json";
import mniIN from "./mni-IN.json";
import brxIN from "./brx-IN.json";
import maiIN from "./mai-IN.json";
import doiIN from "./doi-IN.json";
import saIN from "./sa-IN.json";

export const catalogues: Record<string, Record<string, string>> = {
  "hi-IN": hiIN,
  "bn-IN": bnIN,
  "mr-IN": mrIN,
  "te-IN": teIN,
  "ta-IN": taIN,
  "gu-IN": guIN,
  "kn-IN": knIN,
  "ml-IN": mlIN,
  "or-IN": orIN,
  "pa-IN": paIN,
  "en-IN": enIN,
  "gom-IN": gomIN,
  "ur-IN": urIN,
  "as-IN": asIN,
  "ne-IN": neIN,
  "ks-IN": ksIN,
  "sd-IN": sdIN,
  "sat-IN": satIN,
  "mni-IN": mniIN,
  "brx-IN": brxIN,
  "mai-IN": maiIN,
  "doi-IN": doiIN,
  "sa-IN": saIN,
};
