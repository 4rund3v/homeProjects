# Lab: the registry (artifact repo) exercises

The local registry is not just "where the image lives." It is the release pipeline, and release pipelines are where most production incidents start.

## 1. Tag hygiene

```
docker tag shop-api local:<nodeport>/shop-api:v0.1.0
docker tag shop-api local:<nodeport>/shop-api:latest
docker push local:<nodeport>/shop-api:v0.1.0
docker push local:<nodeport>/shop-api:latest
```

Deploy with `image: ...:v0.1.0`. Then in another terminal:

```
docker tag <a different build> local:<nodeport>/shop-api:latest
docker push local:<nodeport>/shop-api:latest
kubectl -n shop rollout restart deploy/shop-api   # pulls :latest
```

Watch `kubectl -n shop get pods` for which digest the new pod has. The Deployment still says `:v0.1.0` but the pull was `:latest`. One bad tag, all replicas now run the bad code, and the Deployment spec *lied* to you.

**Question:** which two lines in a GitOps pipeline prevent this? (`image: ...:v0.1.0` + a `Digest` check, or `imagePullPolicy: IfNotPresent` + pinned tag.)

## 2. Registry outage

```
kubectl -n artifacts delete pod registry-xxxxxxxx
```

Now deploy a new version. The pod stays `ContainerCreating` → `ImagePullBackOff`.

**Question:** how many replicas of the registry do you need for this not to be a problem? (Answer: at least 2, and pinned to node anti-affinity.)

## 3. Registry slow

```
kubectl -n artifacts exec registry-xxxx -- sha256sum some-large-blob
```

Or `tc qdisc add dev eth0 root netem delay 200ms 50%` on the registry's node.

Push a 500 MB image. Time it. Now the same push at normal latency.

**Question:** in a cloud, which piece of infrastructure is your registry in front of? (S3 / GCS / ECR — the answer changes which latency SLO you set.)

## 4. TLS / insecure-registry

The `insecure-registries` config from `02-deploy.md` — now remove it and re-push.

**Question:** why is this a real incident and not a "just fix the config" issue? (Because 6 hours after a TLS cert rotation, every node that still trusts the old will keep running the app, and the new will keep `ImagePullBackOff`. The two states coexist.)
