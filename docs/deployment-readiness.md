# Deployment readiness

M3 supplies local packaging and a synthetic restore exercise. It does not
configure a host, hostname, reverse proxy, HTTPS, identity integration, remote
access, cloud storage, or external backups. Those choices and their validation
belong to a separately authorized deployment milestone.

Before a future deployment, decide how to protect the private managed volume,
store and rotate authentication and provider secrets, configure encrypted
transport and identity, monitor the API and worker, and test recoverable
backups. Bind and network policy must be revisited for the chosen host; the
current Compose setup is for local loopback access. Portable restores require
new password provisioning and external environment/source-root configuration.

Remaining evidence limits: extraction drafts are review-only; detailed
page-by-page correction times and error counts and live vision fidelity have
not been measured. Real-song PDF text, dimensions, font embedding and local
raster generation were checked, but real-song raster pages were not visually
inspected. Phone checks used viewport emulation, not a physical device.
