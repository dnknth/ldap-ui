# LDAP-UI in Kubernetes
The files provided are examples and have not been extensively tested. Make sure to test and customize them for your deployment.

# Installation

It is recommended to install in the same namespace as the LDAP server. It is most likely possible to connect to LDAP servers outside of the cluster, but this has not been tested.

Notes:
- Run all commands from the root of the cloned repository.
- Customize namespaces to reflect your cluster's setup.
## Service
The service can be deployed without modification for most uses. The service will take traffic from port 80 (http) and reroute them to port 5000 on the container. (This is where ldap-ui is being served.) I recommend using an ingress controller like traefik to handle https.  

To install, run:
```
kubectl apply -f kubernetes/ldap-ui-service.yaml --namespace ldap
```
## Deployment
The environment variables (`spec.template.spec.containers.env`)will need to be updated before deploying. 
1. Edit `LDAP_URL` to the service name of your LDAP deployment. Example:
   ```
   kubectl get services
   
   $ NAME                                       TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)           AGE
   $ openldap-helm-openldap-stack-ha            ClusterIP   10.152.183.178   <none>        389/TCP,636/TCP   105m
   ```
   - Based on the example, change `value: "ldap://ldap.cluster.local"` to `value: "ldap://openldap-helm-openldap-stack-ha"`
1. Update the `BASE_DN` from `value: "dc=example,dc=org"` to reflect your LDAP base dn.
1. Change the base dn for `BIND_PATTERN` to reflect your LDAP base dn. Do not change `cn%s`.
   - See [Main Readme](../README.md) for more details and additional environment variables.  

Once these change have been made, the deployment can be installed by running:
```
kubectl apply -f kubernetes/ldap-ui-deployment.yaml --namespace ldap
``` 

## Ingress (Optional)
If you already have Ingress setup on your cluster, you can install the example Ingress file to gain access to the interface. Please note that this example only uses http, not https, to expose the app. Use HTTPS for production.

Modify `- host: ldapui.example.org` to use your FQDN (Fully Qualified Domain Name). Then run:
```
kubectl apply -f kubernetes/ldap-ui-ingress.yam --namespace ldap
``` 

# Troubleshooting
- Everything is a DNS issue. Install the official [busybox DNS](https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/) utils pod in your namespace to help with dns troubleshooting.
- Again, everything is a DNS issue. Double check your dns policy settings. Look into your ndots settings. 
- If you are able to reach the web-ui, but you don't receive a login prompt, your ldap-ui pod probably isn't able to reach your DNS server. Double check your LDAP server is running and refer to the previous two troubleshooting tips.
  - You can get that your ldap server is running by use the ldapsearch program: `ldapsearch -x -H ldapL//ldap.example.cluster.local`
  - For debian based pods, install ldap client utils by running: `apt install ldap-utils`
  - For alpine based pods, install ldap client utils by running: `apk add openldap-clients`
- If you verified your ldap server is running and you received a login prompt but it the web ui returns a 500 error after you tried authenticating and the ui does not prompt you to try logging in again, you may have not set your authentication method correctly in the container environment variable. Review [Authentication Methods](../README.md#authentication-methods) and double check your deployment.
