import subprocess, os, time, threading
from queue import Queue
import tempfile
import yaml

OUTDIR = "oe_runs"

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
CLIENT_MEASURE = "client-measure-s2md" # your actual node name
#raise Exception("Please set CLIENT_MEASURE to your actual node name before running the script.") # Comment out after setting the correct node name
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
        raise Exception(f"kubectl command failed: {' '.join(cmd)}")
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

def worker(worker_cfg):
        
    w_id = worker_cfg['id']
    node = worker_cfg['node']
    cores = worker_cfg['cores']
    threads = worker_cfg['threads']

    for job in worker_cfg['jobs']:
        run_job("parsec-" + job, node, cores, threads, w_id)

    print(f"[worker-{w_id}] Exiting.")

# EVOLVE-BLOCK-START
class Scheduler:
    """ Jobs we have to run:
    [
    "freqmine", "streamcluster", "canneal", "blackscholes", "vips", "barnes", "radix"
    ]

    Cores we have available:
    - node-a-8core: cores 0-7
    - node-b-4core: cores 0-2 (3 is reserved for memcached)

    """
    def __init__(self):
        # Optimized schedule: maximize parallelism with proper core allocation
        self.worker_config = [
            # Partition 1: Heavy job on node-a (cores 0-3, 4 threads)
            {
                "node": "node-a-8core",
                "cores": "0-3",
                "threads": 4,
                "jobs": ["streamcluster"]
            },
            # Partition 2: Heavy job on node-a (cores 4-7, 4 threads)
            {
                "node": "node-a-8core",
                "cores": "4-7",
                "threads": 4,
                "jobs": ["freqmine"]
            },
            # Partition 3: Light jobs on node-a (cores 0-3, 4 threads) - but avoid overlap
            {
                "node": "node-a-8core",
                "cores": "0-3",
                "threads": 4,
                "jobs": ["canneal", "blackscholes", "vips", "barnes", "radix"]
            }
        ]

    def run(self):
        threads = []
        for idx, w_params in enumerate(self.worker_config):
            w_params['id'] = idx
            t = threading.Thread(target=worker, args=(w_params,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

# EVOLVE-BLOCK-END

if __name__ == "__main__":

    try:
        subprocess.run(["rm", "-r", OUTDIR])
    except:
        pass
    os.makedirs(OUTDIR, exist_ok=True)

    subprocess.run(["kubectl", "delete", "jobs", "--all"]) 

    for RUN_ID in range(1, 2):
        
        Scheduler().run()
        
        # 4. Final timing dump
        print("All jobs done. Saving results...")
        
        subprocess.run(["kubectl", "get", "pods", "-o", "json"], stdout=open(f"{OUTDIR}/results_{RUN_ID}.json", "w"))

        subprocess.run(["python3", "get_time.py", f"{OUTDIR}/results_{RUN_ID}.json"], stdout=open(f"{OUTDIR}/timings_{RUN_ID}.txt", "w"))

        subprocess.run(["kubectl", "delete", "jobs", "--all"]) 

        print(f"Results saved in {OUTDIR}/results_{RUN_ID}.json and {OUTDIR}/timings_{RUN_ID}.txt")

        fetch_mcperf_results(RUN_ID)