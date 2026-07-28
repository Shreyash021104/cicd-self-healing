"""Record a captioned walkthrough: a healthy rolling deploy, a zero-downtime
upgrade, a broken build that gets auto-rolled-back by the smoke test, and a
crashed replica that self-heals. Prereqs: API running on :8097 (fresh) +
playwright + chromium. Usage: python scripts/record_demo.py [out_dir]"""
from __future__ import annotations

import os
import sys
import time

from playwright.sync_api import sync_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/deploy-demo"
URL = "http://127.0.0.1:8097"
os.makedirs(OUT, exist_ok=True)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1120, "height": 900}, device_scale_factor=2,
                            record_video_dir=OUT, record_video_size={"width": 1120, "height": 900})
        pg = ctx.new_page()

        def cap(text, hold=0.0):
            pg.evaluate("""(t)=>{let e=document.getElementById('__c');if(!e){e=document.createElement('div');e.id='__c';e.style.cssText='position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:99999;background:rgba(10,12,18,.95);color:#fff;padding:12px 22px;border-radius:999px;font:600 16px/1.25 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;box-shadow:0 10px 34px rgba(0,0,0,.5);border:1px solid #2a3446;';document.body.appendChild(e);}e.textContent=t;}""", text)
            if hold:
                time.sleep(hold)

        def click_wait(sel, wait):
            pg.click(sel)
            time.sleep(wait)

        pg.goto(URL)
        time.sleep(1.0)
        cap("Helm — a self-healing deployment controller (mini-Kubernetes)", 3.0)

        cap("Deploy v1 — a rolling update, each replica gated on a readiness probe", 1.5)
        click_wait("#good", 4.0)

        cap("Deploy v2 — zero-downtime rolling upgrade", 1.5)
        click_wait("#good", 4.0)

        cap("Now deploy a broken build — passes CI, but the critical path is broken", 2.0)
        click_wait("#bad", 1.0)
        cap("Readiness passes… but the post-deploy smoke test fails", 3.0)
        cap("→ automatic rollback — traffic never left the last good version (v2)", 4.0)

        cap("Self-healing: crash a running replica", 1.5)
        click_wait("#crash", 1.0)
        cap("A replica is down (2/3)… the liveness monitor notices", 3.0)
        time.sleep(2.5)
        cap("…and restarts it automatically — back to 3/3 healthy", 4.0)

        ctx.close()
        b.close()

    video = next((f for f in os.listdir(OUT) if f.endswith(".webm")), None)
    print(os.path.join(OUT, video) if video else "no video")


if __name__ == "__main__":
    main()
