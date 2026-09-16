import json
import subprocess
import threading
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = "http://127.0.0.1:8021"

def http_json(path, method="GET", data=None, timeout=30):
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

class ControlCenter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Job Application Control Center v1.4.8")
        self.geometry("1260x760")
        self.minsize(1050, 650)
        self.status_var = tk.StringVar(value="API: checking...")
        self.search_var = tk.StringVar(value="Ready")
        self.resume_var = tk.StringVar(value="Resume index: checking...")
        self.gmail_var = tk.StringVar(value="Gmail: checking...")
        self.build_ui()
        self.refresh_all()

    def build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Job Application Control Center v1.4.8",
                  font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.status_var).pack(side="right")

        bar = ttk.Frame(self, padding=(10,0,10,8))
        bar.pack(fill="x")
        ttk.Button(bar, text="Start API", command=self.start_api).pack(side="left", padx=3)
        ttk.Button(bar, text="Refresh", command=self.refresh_all).pack(side="left", padx=3)
        ttk.Button(bar, text="Reload All 3 Resumes",
                   command=self.reload_resumes).pack(side="left", padx=3)
        ttk.Button(bar, text="Authorize Gmail", command=self.authorize_gmail).pack(side="left", padx=3)
        ttk.Button(bar, text="Sync Gmail", command=self.sync_gmail).pack(side="left", padx=3)
        ttk.Label(bar, textvariable=self.gmail_var).pack(side="right", padx=10)
        ttk.Label(bar, textvariable=self.resume_var).pack(side="right")

        stats_frame = ttk.LabelFrame(self, text="Pipeline", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=(0,10))
        self.stat_labels = {}
        for key in ["jobs_saved","strong_review","review_match","low_match","approved","hold","applied","interview","rejected","offer"]:
            frame = ttk.Frame(stats_frame)
            frame.pack(side="left", expand=True, fill="x")
            ttk.Label(frame, text=key.replace("_"," ").title()).pack()
            label = ttk.Label(frame, text="0", font=("Segoe UI", 15, "bold"))
            label.pack()
            self.stat_labels[key] = label

        search = ttk.LabelFrame(self, text="Discovery - all jobs are compared against all 3 resumes", padding=10)
        search.pack(fill="x", padx=10, pady=(0,10))
        ttk.Button(search, text="Search Everything",
                   command=lambda:self.run_discovery("all")).pack(side="left", padx=4)
        ttk.Button(search, text="Cybersecurity / SOC",
                   command=lambda:self.run_discovery("cybersecurity")).pack(side="left", padx=4)
        ttk.Button(search, text="Cloud / DevOps",
                   command=lambda:self.run_discovery("cloud")).pack(side="left", padx=4)
        ttk.Button(search, text="IT / Systems / Network",
                   command=lambda:self.run_discovery("it support")).pack(side="left", padx=4)
        ttk.Label(search, textvariable=self.search_var).pack(side="right")

        queue_frame = ttk.LabelFrame(self, text="Application Queue", padding=10)
        queue_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))

        cols = ("job_id","status","recommendation","score","title","company","location","resume","source")
        self.tree = ttk.Treeview(queue_frame, columns=cols, show="headings", height=17)
        widths = {
            "job_id":55,"status":80,"recommendation":100,"score":60,"title":235,"company":160,
            "location":160,"resume":155,"source":95
        }
        for c in cols:
            self.tree.heading(c, text=c.replace("_"," ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True)

        actions = ttk.Frame(queue_frame)
        actions.pack(fill="x", pady=(8,0))
        for label, status in [
            ("Approve","approved"),("Hold","hold"),("Mark Applied","applied"),
            ("Interview","interview"),("Rejected","rejected"),("Offer","offer")
        ]:
            ttk.Button(actions, text=label,
                       command=lambda s=status:self.set_status(s)).pack(side="left", padx=3)
        ttk.Button(actions, text="Application Assistant", command=self.assist_selected_job).pack(side="right", padx=3)
        ttk.Button(actions, text="Open Application", command=self.open_selected_job).pack(side="right", padx=3)

    def start_api(self):
        try:
            http_json("/", timeout=2)
            self.status_var.set("API: RUNNING")
            return
        except Exception:
            pass
        python = ROOT / ".venv" / "Scripts" / "python.exe"
        if not python.exists():
            messagebox.showerror("Missing environment", "Run install_v1_4_8.ps1 first.")
            return
        subprocess.Popen(
            [str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8021"],
            cwd=ROOT
        )
        self.after(1800, self.refresh_all)

    def refresh_all(self):
        try:
            root = http_json("/", timeout=3)
            self.status_var.set("API: RUNNING")
            profile = http_json("/profile", timeout=5)
            statuses = profile.get("resume_status", {})
            found = sum(1 for x in statuses.values() if x.get("exists"))
            terms = sum(x.get("unique_terms_indexed",0) for x in statuses.values())
            self.resume_var.set(f"Resume index: {found}/3 found | {terms} terms indexed")

            try:
                gs=http_json("/gmail/status", timeout=5)
                self.gmail_var.set("Gmail: CONNECTED" if gs.get("connected") else "Gmail: OAuth needed")
            except Exception:
                self.gmail_var.set("Gmail: unavailable")

            stats = http_json("/stats")
            for key, label in self.stat_labels.items():
                label.config(text=str(stats.get(key,0)))

            last = stats.get("last_discovery")
            if last:
                self.search_var.set(
                    f"Last: {last.get('qualified',0)} qualified | "
                    f"{last.get('title_rejected',0)} title rejected | "
                    f"{last.get('blocked_seniority',0)} senior blocked | "
                    f"{last.get('location_excluded',0)} location excluded | "
                    f"{last.get('below_score',0)} below score"
                )

            queue = http_json("/queue")
            for item in self.tree.get_children():
                self.tree.delete(item)
            for row in queue:
                self.tree.insert("", "end", values=(
                    row.get("job_id"), row.get("status"), row.get("recommendation"), row.get("match_score"),
                    row.get("title"), row.get("company"), row.get("location"),
                    row.get("recommended_resume"), row.get("source")
                ))
        except Exception:
            self.status_var.set("API: STOPPED")

    def authorize_gmail(self):
        self.gmail_var.set("Gmail: opening OAuth...")
        def worker():
            try:
                result=http_json("/gmail/authorize","POST",{},timeout=180)
                self.after(0,lambda:self.gmail_var.set("Gmail: CONNECTED"))
                self.after(0,lambda:messagebox.showinfo("Gmail OAuth",f"Authorized: {result.get('email','Gmail')}"))
            except Exception as e:
                self.after(0,lambda:messagebox.showerror("Gmail OAuth failed",str(e)))
                self.after(0,lambda:self.gmail_var.set("Gmail: OAuth needed"))
        threading.Thread(target=worker,daemon=True).start()

    def sync_gmail(self):
        self.gmail_var.set("Gmail: syncing...")
        def worker():
            try:
                r=http_json("/gmail/sync?days=30&max_results=100","POST",{},timeout=120)
                text=f"Gmail: {r.get('processed',0)} checked / {r.get('linked_to_jobs',0)} linked / {r.get('application_status_updates',0)} updated"
                self.after(0,lambda:self.gmail_var.set(text)); self.after(0,self.refresh_all)
            except Exception as e:
                self.after(0,lambda:messagebox.showerror("Gmail sync failed",str(e)))
                self.after(0,lambda:self.gmail_var.set("Gmail: sync failed"))
        threading.Thread(target=worker,daemon=True).start()

    def reload_resumes(self):
        try:
            result = http_json("/resumes/reload", "POST", {}, timeout=20)
            statuses = result.get("resume_status", {})
            found = sum(1 for x in statuses.values() if x.get("exists"))
            terms = sum(x.get("unique_terms_indexed",0) for x in statuses.values())
            self.resume_var.set(f"Resume index: {found}/3 found | {terms} terms indexed")
        except Exception as e:
            messagebox.showerror("Resume reload failed", str(e))

    def run_discovery(self, query):
        self.search_var.set(f"Searching {query}...")
        def worker():
            try:
                result = http_json("/discover/multi", "POST", {
                    "query": query,
                    "limit_per_source": 100,
                    "min_score": 35,
                    "us_compatible_only": True,
                    "save_matches": True
                }, timeout=120)
                summary = (
                    f"{result.get('qualified',0)} qualified | "
                    f"{result.get('title_rejected',0)} title rejected | "
                    f"{result.get('blocked_seniority',0)} senior blocked | "
                    f"{result.get('location_excluded',0)} location excluded | "
                    f"{result.get('below_score',0)} below score"
                )
                if result.get("errors"):
                    summary += f" | {len(result['errors'])} source warning(s)"
                self.after(0, lambda:self.search_var.set(summary))
                self.after(0, self.refresh_all)
            except Exception as e:
                self.after(0, lambda:self.search_var.set(f"Search error: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def selected_job_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select job", "Select a job first.")
            return None
        return int(self.tree.item(sel[0], "values")[0])

    def set_status(self, status):
        job_id = self.selected_job_id()
        if job_id is None:
            return
        try:
            http_json(f"/queue/{job_id}/review", "POST", {"status":status})
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Update failed", str(e))

    def assist_selected_job(self):
        job_id=self.selected_job_id()
        if job_id is None:return
        try:
            r=http_json(f"/jobs/{job_id}/assist",timeout=10)
            messagebox.showinfo("Application Assistant",
                f"Job ID: {job_id}\nRecommended resume: {r.get('recommended_resume') or 'Review'}\n\n{r.get('resume_path') or ''}\n\nOpen the application in your normal browser, click the Adrian Job Application Assistant extension, enter Job ID {job_id}, then click Fill Known Fields. Final Submit remains manual.")
        except Exception as e:
            messagebox.showerror("Assistant failed",str(e))

    def open_selected_job(self):
        job_id = self.selected_job_id()
        if job_id is None:
            return
        try:
            http_json(f"/jobs/{job_id}/open", "POST", {})
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

if __name__ == "__main__":
    ControlCenter().mainloop()
