sudo helm install ymredis oci://registry-1.docker.io/bitnamicharts/redis --kubeconfig /etc/rancher/k3s/k3s.yaml
#
export REDIS_PASSWORD=$(sudo kubectl get secret --namespace default ymredis -o jsonpath="{.data.redis-password}" | base64 -d)
echo $REDIS_PASSWORD
