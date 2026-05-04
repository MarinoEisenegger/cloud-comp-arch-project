```bash
PROJECT=`gcloud config get-value project`
kops create -f part3.yaml
kops update cluster --name part3.k8s.local --yes --admin
kops validate cluster --wait 10m
```

```bash
kubectl get nodes -o wide
```

```bash
gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@client-agent-a- --zone europe-west1-b
gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@client-agent-b- --zone europe-west1-b
gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@client-measure- --zone europe-west1-b
```

```bash
sudo sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources
sudo apt-get update
sudo apt-get install libevent-dev libzmq3-dev git make g++ --yes
sudo apt-get build-dep memcached --yes
git clone https://github.com/eth-easl/memcache-perf-dynamic.git
cd memcache-perf-dynamic
make
```

```bash
kubectl label nodes node-a-8core- cca-project-nodetype="node-a-8core"
kubectl label nodes node-b-4core- cca-project-nodetype="node-b-4core"
```

```bash
kubectl create -f memcache_node_b_2core.yaml
kubectl expose pod some-memcached --name some-memcached-11211 \
    --type LoadBalancer --port 11211 \
    --protocol TCP
sleep 60
kubectl get service some-memcached-11211
```

```bash
./mcperf -T 2 -A

./mcperf -T 4 -A

export MEMCACHED_IP=100.70.77.158
export INTERNAL_AGENT_A_IP=10.0.16.3
export INTERNAL_AGENT_B_IP=10.0.16.8
./mcperf -s $MEMCACHED_IP --loadonly
while true; do
    ./mcperf -s $MEMCACHED_IP -a $INTERNAL_AGENT_A_IP -a $INTERNAL_AGENT_B_IP \
    --noload -T 6 -C 4 -D 4 -Q 1000 -c 4 -t 10 \
    --scan 30000:30500:5 >> mcperf_results.txt
done
```

```bash
kubectl delete job parsec-barnes
kubectl delete job parsec-blackscholes
kubectl delete job parsec-canneal
kubectl delete job parsec-freqmine
kubectl delete job parsec-streamcluster
kubectl delete job parsec-vips
kubectl delete job parsec-radix
```