import subprocess, os, time, threading
from queue import Queue
import tempfile
from matplotlib.pylab import delete
import yaml
import json

OUTDIR = "oe_runs"

# --- Job definitions: (job_name, yaml_file, preferred_node) ---
# preferred_node hints which YAML variant to use, but all pull from same queue
JOBS = {
    "parsec-barnes": {
        "image": "anakli/cca:splash2x_barnes",
        "suite": "splash2x",
        "benchmark": "barnes"
    },
    "parsec-blackscholes": {
        "image": "anakli/cca:parsec_blackscholes",
        "suite": "parsec",
        "benchmark": "blackscholes"
    },
    "parsec-canneal": {
        "image": "anakli/cca:parsec_canneal",
        "suite": "parsec",
        "benchmark": "canneal"
    },
    "parsec-freqmine": {
        "image": "anakli/cca:parsec_freqmine",
        "suite": "parsec",
        "benchmark": "freqmine"
    },
    "parsec-radix": {
        "image": "anakli/cca:splash2x_radix",
        "suite": "splash2x",
        "benchmark": "radix"
    },
    "parsec-streamcluster": {
        "image": "anakli/cca:parsec_streamcluster",
        "suite": "parsec",
        "benchmark": "streamcluster"
    },
    "parsec-vips": {
        "image": "anakli/cca:parsec_vips",
        "suite": "parsec",
        "benchmark": "vips"
    }
}

# -------------------------------------------------------------------
CLIENT_MEASURE = "client-measure-hf5z"  # your actual node name
SSH_KEY = "~/.ssh/cloud-computing"
ZONE = "europe-west1-b"

PROJECT = "cca-eth-2026-group-57"

def gcloud_ssh(host, command):
    subprocess.run([
        "gcloud", "compute", "ssh", f"ubuntu@{host}",
        "--ssh-key-file", SSH_KEY,
        "--zone", ZONE,
        "--project", PROJECT,
        "--command", command
    ])

def gcloud_scp(src, dst):
    subprocess.run([
        "gcloud", "compute", "scp",
        src, dst,
        "--ssh-key-file", SSH_KEY,
        "--zone", ZONE,
        "--project", PROJECT
    ])

def fetch_mcperf_results(run_id):
    gcloud_scp(
        f"ubuntu@{CLIENT_MEASURE}:~/memcache-perf-dynamic/mcperf_results.txt",
        f"{OUTDIR}/mcperf_{run_id}.txt"
    )
    gcloud_ssh(CLIENT_MEASURE, "truncate -s 0 ~/memcache-perf-dynamic/mcperf_results.txt")
    
    # Give agents a moment after measure was killed
    time.sleep(5)

def run_parsec_job(job_name, nodetype, cores, n_threads):
    """
    job_name:   e.g. "parsec-barnes"
    nodetype:   e.g. "node-b-4core" or "node-a-8core"
    cores:      e.g. "2-3" or "2-7"
    n_threads:  e.g. 2
    """
    delete_job(job_name)

    image = JOBS[job_name]["image"]
    suite = JOBS[job_name]["suite"]
    benchmark = JOBS[job_name]["benchmark"]


    core_str = cores if isinstance(cores, str) else f"{cores[0]}-{cores[1]}"

    job_manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "labels": {"name": job_name}
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [{
                        "image": image,
                        "name": job_name,
                        "imagePullPolicy": "Always",
                        "command": ["/bin/sh"],
                        "args": ["-c", f"taskset -c {core_str} ./run -a run -S {suite} -p {benchmark} -i native -n {n_threads}"]
                    }],
                    "restartPolicy": "Never",
                    "nodeSelector": {
                        "cca-project-nodetype": nodetype
                    }
                }
            }
        }
    }

    # Write to a temp YAML and apply
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(job_manifest, f)
        tmp_path = f.name

    create_job(tmp_path)
    os.remove(tmp_path)

def kubectl(cmd, capture=False):
    result = subprocess.run(["kubectl"] + cmd, capture_output=capture, text=True)
    if result.returncode != 0 and not capture:
        print(f"[kubectl error] {result.stderr}")
    return result.stdout if capture else None

def create_job(yaml_file):
    kubectl(["create", "-f", yaml_file])

def wait_for_job(job_name, timeout=300):
    kubectl(["wait", "--for=condition=complete",
             f"job/{job_name}", f"--timeout={timeout}s"])

def save_logs(job_name):
    pod_name = kubectl(
        ["get", "pods", f"--selector=job-name={job_name}",
         "--output=jsonpath={.items[0].metadata.name}"],
        capture=True
    ).strip()
    logs = kubectl(["logs", pod_name], capture=True)
    with open(f"{OUTDIR}/{job_name}.txt", "w") as f:
        f.write(logs)
    pod_json = kubectl(["get", "pod", pod_name, "-o", "json"], capture=True)
    with open(f"{OUTDIR}/{job_name}_pod.json", "w") as f:
        f.write(pod_json)

def delete_job(job_name):
    kubectl(["delete", "job", job_name, "--ignore-not-found=true"])

def run_job(job_name, node_type, cores, n_threads, worker_id):
    print(f"[worker-{worker_id}] Starting {job_name}")
    run_parsec_job(job_name, node_type, cores, n_threads)
    wait_for_job(job_name)
    #save_logs(job_name)
    #delete_job(job_name)
    print(f"[worker-{worker_id}] Finished {job_name}")

# -------------------------------------------------------------------

# EVOLVE-BLOCK-START
WORKER_CONFIG = [
    {"initial": "parsec-freqmine", "node": "node-a-8core", "cores": "0-3", "threads": 4},
    {"initial": "parsec-streamcluster", "node": "node-a-8core", "cores": "4-7", "threads": 4},
    {"initial": "parsec-canneal", "node": "node-b-4core", "cores": "2-3", "threads": 2}
]

QUEUE_JOBS = ["parsec-blackscholes", "parsec-vips", "parsec-barnes", "parsec-radix"]

def worker(worker_cfg, queue):
    
    w_id = worker_cfg['id']
    node = worker_cfg['node']
    cores = worker_cfg['cores']
    threads = worker_cfg['threads']

    # 1. Run the initial assigned job
    if worker_cfg.get('initial'):
        run_job(worker_cfg['initial'], node, cores, threads, w_id)

    # 2. Consume from the shared pool
    while not queue.empty():
        try:
            job_name = queue.get_nowait()
            run_job(job_name, node, cores, threads, w_id)
            queue.task_done()
        except:
            break
    
    print(f"[worker-{w_id}] Exiting.")

if __name__ == "__main__":

    try:
        subprocess.run(["rm", "-r", OUTDIR])
    except:
        pass
    os.makedirs(OUTDIR, exist_ok=True)

    subprocess.run(["kubectl", "delete", "jobs", "--all"])

    for RUN_ID in range(1, 2):
        job_queue = Queue()

        # These are the 'extra' jobs to be load-balanced
        for job in QUEUE_JOBS:
            job_queue.put(job)

        threads = []
        for idx, w_params in enumerate(WORKER_CONFIG):
            # Ensure ID is set
            w_params['id'] = idx
            t = threading.Thread(target=worker, args=(w_params, job_queue))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()
# EVOLVE-BLOCK-END
        # 4. Final timing dump
        print("All jobs done. Saving results...")

        """
        all_pods = {"items": []}

        for job_name in JOBS.keys():
            pod_json_path = f"{OUTDIR}/{job_name}_pod.json"
            if os.path.exists(pod_json_path):
                with open(pod_json_path) as f:
                    pod = json.load(f)
                    all_pods["items"].append(pod)

        with open(f"{OUTDIR}/results.json", "w") as f:
            json.dump(all_pods, f) """
        
        subprocess.run(["kubectl", "get", "pods", "-o", "json"], stdout=open(f"{OUTDIR}/results_{RUN_ID}.json", "w"))

        subprocess.run(["python3", "get_time.py", f"{OUTDIR}/results_{RUN_ID}.json"], stdout=open(f"{OUTDIR}/timings_{RUN_ID}.txt", "w"))

        for job_name in JOBS.keys():
            delete_job(job_name)

        print(f"Results saved in {OUTDIR}/results_{RUN_ID}.json and {OUTDIR}/timings_{RUN_ID}.txt")

        fetch_mcperf_results(RUN_ID)