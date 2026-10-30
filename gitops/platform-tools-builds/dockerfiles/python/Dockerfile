# The platform engineer's template for a Python service (decision 48).
# The build context is the service's directory under apps/: its
# requirements.txt, its app.py, and anything else it ships, such as the
# store's static/covers.
#
# The base is Bitnami's Python on Photon 5 from Tanzu Hub, pulled through
# the Harbor proxy cache (decision 46). It runs as root, so this image
# sets a user: the pods run as 1000.
FROM depot.kube-system.svc/tanzu-platform-content/containers/photon-5/python:3.14.10-photon-5-r1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY --chown=1000:1000 . .
RUN chown 1000:1000 /app

USER 1000:1000
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
