# Running in Kubernetes

- Make sure you have access to these yaml files:
    or use the combined yaml file:
    - `vwt_deploy.yaml`
    

Start the project:
```
kubectl apply -f vwt_deploy.yaml
```

Check that everything is running
```
kubectl get pods
NAME                               READY   STATUS    RESTARTS   AGE
levelcontroller-6b9d846cb4-f6qvm   1/1     Running   0          6s
nodered-68979fc6f-nqqdv            1/1     Running   0          6s
watertank-5ff9c9dbc8-rtdp6         1/1     Running   0          6s


kubectl get svc
NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
kubernetes        ClusterIP   10.96.0.1        <none>        443/TCP          37d
levelcontroller   NodePort    10.106.99.133    <none>        5051:30051/TCP   32s
nodered           NodePort    10.104.153.199   <none>        1880:30880/TCP   32s
watertank         NodePort    10.109.237.64    <none>        5050:30050/TCP   32s
```

Open your browser to your Kubernetes Node IP with port indicated in the services output. i.e.
```
http://10.10.10.2:30051  -- Level Controller App

http://10.10.10.2:30050  -- Virtual Watertank Display

http://10.10.10.2:30880  -- Node Red UI
```

Stop the project:
```
kubectl delete -f vwt_deploy.yaml
```