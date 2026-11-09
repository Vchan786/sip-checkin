import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from sip_logic import KB, GOLD, FALLBACK_TEXT, run

st.set_page_config(page_title="SIP Check-in", page_icon="✅", layout="centered")

def _secret(k):
    try: return st.secrets[k]
    except Exception: return None
ANTHROPIC_KEY = _secret("ANTHROPIC_API_KEY")
GEMINI_KEY = _secret("GEMINI_API_KEY")

def llm(prompt):
    if ANTHROPIC_KEY:
        from anthropic import Anthropic
        r = Anthropic(api_key=ANTHROPIC_KEY).messages.create(
            model="claude-haiku-5-5", max_tokens=800,
            messages=[{"role":"user","content":prompt}])
        return r.content[0].text
    if GEMINI_KEY:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        errs = []
        for m in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"):
            try:
                r = client.models.generate_content(model=m, contents=prompt)
                if r.text: return r.text
            except Exception as e:
                errs.append(m + ": " + str(e)[:120])
        raise RuntimeError(" | ".join(errs))
    raise RuntimeError("No API key configured")

if not (ANTHROPIC_KEY or GEMINI_KEY):
    st.error("No API key found in app Secrets. Add GEMINI_API_KEY in Manage app > Settings > Secrets.")
st.warning("Educational information only. This is not investment advice. It never recommends funds, stocks, or when to buy or sell.")
st.title("Missed an instalment or thinking of pausing your SIP? Check your options calmly.")
st.caption("Describe your situation in English or Tanglish. Do not enter PAN, account numbers or amounts. Answers come only from a small set of approved notes; otherwise you get a safe fallback.")

def show(res):
    if res["status"] == "answer":
        o = res["out"]
        st.success("✔ Answered from approved notes")
        st.write(o.get("answer",""))
        for x in (o.get("options") or [])[:3]:
            st.markdown(f"**{x.get('label','')}**  \n{x.get('detail','')}")
        if o.get("reflect"): st.info("A question for yourself: " + o["reflect"])
        st.caption("Sources: " + ", ".join(res["ids"]))
    else:
        st.warning("⚠ Safe fallback")
        st.write(FALLBACK_TEXT)
        st.write("**What I can explain:** why an instalment fails, what happens next, pause vs reduce vs stop, what stopping does to invested money, why values move, XIRR vs absolute return, and linking a SIP to a goal.")
        st.markdown("**Official sources:** [AMFI](https://www.amfiindia.com) · [SEBI investor site](https://investor.sebi.gov.in). For a personal decision, consider a SEBI-registered investment adviser.")
    with st.expander("Quality gates for this answer", expanded=True):
        for c in res["checks"]:
            st.write(("✔ Passed — " if c["ok"] else "✖ Blocked — ") + f"**{c['name']}**: {c['note']}")

q = st.text_area("What is happening with your SIP?", placeholder="e.g. My SIP instalment failed this month. What happens now?", height=100)
if st.button("Check my options", type="primary"):
    if not q.strip(): st.error("Type your situation first.")
    else:
        with st.spinner("Checking against approved notes…"):
            show(run(q.strip(), llm))

st.divider()
st.subheader("Quality check against the golden set")
st.write("The 20-question golden set runs through the same pipeline: answer the 14 in-scope questions from approved notes, and decline the 6 advice or prediction questions.")
if st.button("Run quality check (20 questions)"):
    prog = st.progress(0.0)
    def one(item):
        qq, exp = item
        try: r = run(qq, llm)
        except Exception: r = {"status":"fallback"}
        got = "answer" if r["status"] == "answer" else "refuse"
        return qq, exp, got
    rows = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, r in enumerate(ex.map(one, GOLD)):
            rows.append(r); prog.progress((i+1)/len(GOLD))
    ok = [r[1] == r[2] for r in rows]
    st.metric("Passed", f"{sum(ok)}/{len(rows)} ({round(100*sum(ok)/len(rows))}%)")
    a = [o for o, r in zip(ok, rows) if r[1] == "answer"]; d = [o for o, r in zip(ok, rows) if r[1] == "refuse"]
    st.caption(f"In-scope answered correctly: {sum(a)}/{len(a)}. Advice or prediction requests declined correctly: {sum(d)}/{len(d)}.")
    st.table([{"#":i+1,"Question":r[0],"Expected":"Answer" if r[1]=="answer" else "Decline","Got":"Answered" if r[2]=="answer" else "Declined","Result":"✔ Pass" if o else "✖ Fail"} for i,(r,o) in enumerate(zip(rows,ok))])

with st.expander("How it works"):
    st.write("1 Scope check (advice and predictions caught before any AI call) · 2 Grounded answer (only approved notes, must cite) · 3 Confidence ≥ 60% · 4 Tone check (no urgency or fear wording). Any gate failing gives the safe fallback.")
    st.write("Approved notes: " + " · ".join(f"{k['id']} {k['title']}" for k in KB))
st.caption("Prototype for a learning project. Notes are general and may differ by fund house and app.")
