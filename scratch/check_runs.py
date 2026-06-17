import requests
import json
import sys

# Reconfigure stdout to support unicode/emojis
sys.stdout.reconfigure(encoding="utf-8")

repo = "DrShahidIslam/Nailosmetic-Pinterest-Automation-App"
url = f"https://api.github.com/repos/{repo}/actions/runs?per_page=30"

response = requests.get(url)
if response.status_code != 200:
    print(f"Error fetching runs: {response.status_code}")
    print(response.text)
    exit(1)

runs = response.json().get("workflow_runs", [])
print(f"Total runs fetched: {len(runs)}")
print(f"{'ID':<15} | {'Run #':<5} | {'Workflow Name':<30} | {'Conclusion':<10} | {'Created At':<20}")
print("-" * 90)

for run in runs:
    run_id = run["id"]
    run_num = run["run_number"]
    name = run["name"]
    conclusion = run["conclusion"] or run["status"]
    created_at = run["created_at"]
    
    print(f"{run_id:<15} | {run_num:<5} | {name[:30]:<30} | {conclusion:<10} | {created_at:<20}")
    
    if run["conclusion"] == "failure":
        # Get details about what failed
        jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
        jobs_resp = requests.get(jobs_url)
        if jobs_resp.status_code == 200:
            jobs = jobs_resp.json().get("jobs", [])
            for job in jobs:
                print(f"   Job: {job['name']} ({job['conclusion']})")
                for step in job.get("steps", []):
                    if step["conclusion"] == "failure":
                        print(f"     ❌ Step Failed: {step['name']} (Number: {step['number']})")
        else:
            print(f"   Could not fetch job info: {jobs_resp.status_code}")
