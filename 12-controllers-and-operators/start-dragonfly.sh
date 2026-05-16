#sudo helm pull oci://ghcr.io/dragonflydb/dragonfly-operator/helm --version v1.2.1 --kubeconfig /etc/racher/k3s/k3s.yaml
sudo helm install dragonfly-operator oci://ghcr.io/dragonflydb/dragonfly-operator/helm --version v1.4.0 --namespace dragonfly-system --create-namespace --kubeconfig /etc/rancher/k3s/k3s.yaml
#
#export REDIS_PASSWORD=$(sudo kubectl get secret --namespace default ymredis -o jsonpath="{.data.redis-password}" | base64 -d)
#echo $REDIS_PASSWORD
