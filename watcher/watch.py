"""Watches the private data repo and dispatches the workflows its pushes used to trigger.

Why: workflows run in this public repo (free Actions minutes); the data stays in
alibingul-dev/axi-epias-data (private). A push to a private repo cannot trigger a
workflow here, so this job polls the private repo every POLL seconds and, for each
new commit that is not made by github-actions[bot] (same rule as before: bot pushes
never triggered workflows), dispatches every workflow whose former push paths match.
Prints only commit SHAs, file counts and workflow names: never file contents.
"""
import json, os, re, time, urllib.request, urllib.error

DATA = "alibingul-dev/axi-epias-data"
SELF = os.environ.get("GITHUB_REPOSITORY", "alibingul-dev/axi-runner")
TOKEN = os.environ["PAT"]
POLL = int(os.environ.get("POLL", "60"))
RUN_MIN = int(os.environ.get("RUN_MIN", "340"))
LOOKBACK_H = float(os.environ.get("LOOKBACK_H", "12"))
HERE = os.path.dirname(os.path.abspath(__file__))
ROUTES = json.load(open(os.path.join(HERE, "routes.json")))


def api(method, path, body=None):
    req = urllib.request.Request("https://api.github.com" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + TOKEN,
                                          "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        t = r.read()
        return json.loads(t) if t else None


def glob_re(p):
    s, i = "", 0
    while i < len(p):
        if p.startswith("**/", i): s += "(?:.*/)?"; i += 3
        elif p.startswith("**", i): s += ".*"; i += 2
        elif p[i] == "*": s += "[^/]*"; i += 1
        else: s += re.escape(p[i]); i += 1
    return re.compile("^" + s + "$")


RX = {wf: [glob_re(p) for p in ps] for wf, ps in ROUTES.items()}


def is_bot(c):
    n = (c.get("commit", {}).get("author", {}) or {}).get("name", "") + (c.get("author") or {}).get("login", "")
    return "[bot]" in n


def state_get():
    try:
        d = api("GET", f"/repos/{SELF}/contents/state/last_sha?ref=state")
        import base64
        return base64.b64decode(d["content"]).decode().strip(), d["sha"]
    except urllib.error.HTTPError:
        return None, None


def state_put(sha, blob):
    import base64
    body = {"message": "watcher state", "branch": "state",
            "content": base64.b64encode(sha.encode()).decode()}
    if blob: body["sha"] = blob
    try:
        return api("PUT", f"/repos/{SELF}/contents/state/last_sha", body)["content"]["sha"]
    except urllib.error.HTTPError as e:
        print("state save failed", e.code); return blob


def new_commits(last, head):
    if last:
        try:
            return api("GET", f"/repos/{DATA}/compare/{last}...{head}")["commits"]
        except urllib.error.HTTPError as e:
            print("compare failed", e.code, "-> lookback")
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - LOOKBACK_H * 3600))
    return list(reversed(api("GET", f"/repos/{DATA}/commits?sha=main&per_page=100&since={since}")))


# Clock-driven dispatches (UTC "HH:MM", workflow, inputs): GitHub cron runs late, the watcher does not.
TIMED = [("09:31", "forecast-card.yml", {"mode": "make"}),   # 12:31 Istanbul, after the day-ahead gate
         ("04:05", "forecast-card.yml", {"mode": "score"})]  # 07:05 Istanbul


def dispatch(wf, inputs=None):
    try:
        api("POST", f"/repos/{SELF}/actions/workflows/{wf}/dispatches", {"ref": "main", "inputs": inputs or {"via": "push"}})
        print("  dispatched", wf); return True
    except urllib.error.HTTPError as e:
        print("  dispatch failed", wf, e.code); return False


def main():
    end = time.time() + RUN_MIN * 60
    last, blob = state_get()
    saved_at = time.time()
    print("start, last =", (last or "none")[:7])
    retry = set()  # workflows whose dispatch failed; retried every poll until accepted
    fired = set()  # (day, HH:MM) of timed dispatches already sent by this run
    while time.time() < end:
        try:
            now = time.gmtime()
            hm, day = time.strftime("%H:%M", now), time.strftime("%Y-%m-%d", now)
            for at, wf, inp in TIMED:
                if at <= hm < at[:3] + "%02d" % (int(at[3:]) + 20) and (day, at) not in fired:
                    if dispatch(wf, dict(inp, via="timer")):
                        fired.add((day, at))
            if retry:
                retry = {wf for wf in sorted(retry) if not dispatch(wf)}
            head = api("GET", f"/repos/{DATA}/commits/main")["sha"]
            if head != last:
                files = set(); n = 0
                for c in new_commits(last, head):
                    if is_bot(c): continue
                    n += 1
                    files |= {f["filename"] for f in api("GET", f"/repos/{DATA}/commits/{c['sha']}").get("files", [])}
                hit = sorted(wf for wf, rxs in RX.items() if any(r.match(f) for r in rxs for f in files))
                print(time.strftime("%H:%MZ", time.gmtime()), head[:7], f"{n} human commits, {len(files)} files ->", hit or "-")
                retry |= {wf for wf in hit if not dispatch(wf)}
                last = head
            if time.time() - saved_at > 3600:
                blob = state_put(last, blob); saved_at = time.time()
        except Exception as e:  # never die on a transient error
            print("poll error:", type(e).__name__, str(e)[:120])
        time.sleep(POLL)
    if last: state_put(last, blob)
    dispatch("watcher.yml")  # hand over to the next run


if __name__ == "__main__":
    main()
