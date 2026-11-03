# /// script
# requires-python = ">=3.10"
# dependencies = ["pyvmomi>=8.0.3"]
# ///
"""Put a vSAN IOPS limit on the music store's cart and order disks, or take it off.

    uv run fault.py start <namespace> <volume>...
    uv run fault.py stop <namespace> <volume>...
    uv run fault.py status <namespace> <volume>...

<namespace> is the Supervisor Namespace music-store-<suffix>. Each <volume>
is a Supervisor PV name, the CNS volume behind one of the shop's PVCs.
fault.sh finds them; run that, not this.

start creates or updates the storage policy POLICY: vSAN Auto RAID, as the
lab's default policy, plus an IOPS limit of IOPS_LIMIT (10 unless set).
Then it moves the volumes' disks to it on the VKS worker VM they are
attached to. stop moves them back to the policy their StorageClass names.
The policy stays in vCenter between runs.

Reads VC_HOST and VC_USER, and VC_PASSWORD or asks for it. Prints no secret.
"""

from __future__ import annotations

import getpass
import os
import re
import ssl
import sys

from pyVim.connect import Disconnect, SmartConnect
from pyVim.task import WaitForTask
from pyVmomi import SoapStubAdapter, VmomiSupport, pbm, vim

POLICY = "Archive Tier - IOPS Limited"
DESCRIPTION = "GOAD storage troubleshooting demo (demos/storage-troubleshooting): vSAN Auto RAID with a low IOPS limit."


def slug(name: str) -> str:
    """The StorageClass name the Supervisor gives a storage policy."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]", "-", name.lower())).strip("-")


def connect():
    host = os.environ["VC_HOST"]
    password = os.environ.get("VC_PASSWORD") or getpass.getpass(f"vCenter password for {os.environ['VC_USER']}: ")
    context = ssl._create_unverified_context()
    si = SmartConnect(host=host, user=os.environ["VC_USER"], pwd=password, sslContext=context)
    VmomiSupport.GetRequestContext()["vcSessionCookie"] = si._stub.cookie.split('"')[1]
    stub = SoapStubAdapter(host=host, path="/pbm/sdk", version="pbm.version.version11", sslContext=context)
    profiles = pbm.ServiceInstance("ServiceInstance", stub).RetrieveContent().profileManager
    return si, profiles


def all_policies(profiles):
    kind = pbm.profile.ResourceType(resourceType="STORAGE")
    return profiles.PbmRetrieveContent(profiles.PbmQueryProfile(resourceType=kind, profileCategory="REQUIREMENT"))


def vsan_rule(rule: str, value):
    return pbm.capability.CapabilityInstance(
        id=pbm.capability.CapabilityMetadata.UniqueId(namespace="VSAN", id=rule),
        constraint=[pbm.capability.ConstraintInstance(propertyInstance=[pbm.capability.PropertyInstance(id=rule, value=value)])],
    )


def ensure_cap_policy(profiles, limit: int) -> str:
    rules = pbm.profile.SubProfileCapabilityConstraints(
        subProfiles=[
            pbm.profile.SubProfileCapabilityConstraints.SubProfile(
                name="VSAN sub-profile",
                capability=[vsan_rule("autoManagedRAID", True), vsan_rule("iopsLimit", limit)],
            )
        ]
    )
    for policy in all_policies(profiles):
        if policy.name == POLICY:
            profiles.PbmUpdate(policy.profileId, pbm.profile.CapabilityBasedProfileUpdateSpec(constraints=rules))
            return policy.profileId.uniqueId
    spec = pbm.profile.CapabilityBasedProfileCreateSpec(
        name=POLICY, description=DESCRIPTION, resourceType=pbm.profile.ResourceType(resourceType="STORAGE"), constraints=rules
    )
    return profiles.PbmCreate(spec).uniqueId


def find_disks(si, namespace: str, volumes: set[str]):
    """Yield (vm, disk, volume) for each volume's disk on a VM in the namespace."""
    content = si.content
    pools = content.viewManager.CreateContainerView(content.rootFolder, [vim.ResourcePool], True).view
    pool = next((p for p in pools if p.name == namespace), None)
    if pool is None:
        sys.exit(f"No resource pool {namespace} in vCenter.")
    vsom = content.vStorageObjectManager
    for vm in content.viewManager.CreateContainerView(pool, [vim.VirtualMachine], True).view:
        for disk in vm.config.hardware.device:
            if not isinstance(disk, vim.vm.device.VirtualDisk) or not disk.vDiskId:
                continue
            name = vsom.RetrieveVStorageObject(disk.vDiskId, disk.backing.datastore).config.name
            if name in volumes:
                yield vm, disk, name


def main() -> None:
    if len(sys.argv) < 4 or sys.argv[1] not in ("start", "stop", "status"):
        sys.exit(__doc__)
    action, namespace, volumes = sys.argv[1], sys.argv[2], set(sys.argv[3:])
    storage_class = os.environ.get("STORAGE_CLASS", "")

    si, profiles = connect()
    try:
        if action == "start":
            target = ensure_cap_policy(profiles, int(os.environ.get("IOPS_LIMIT", "10")))
        names = {p.profileId.uniqueId: p.name for p in all_policies(profiles)}
        if action == "stop":
            target = next((i for i, n in names.items() if slug(n) == storage_class), None)
            if target is None:
                sys.exit(f"No storage policy matches StorageClass {storage_class!r}.")
        found = set()
        for vm, disk, volume in find_disks(si, namespace, volumes):
            found.add(volume)
            if action != "status":
                change = vim.vm.device.VirtualDeviceSpec(
                    operation="edit", device=disk, profile=[vim.vm.DefinedProfileSpec(profileId=target)]
                )
                WaitForTask(vm.ReconfigVM_Task(vim.vm.ConfigSpec(deviceChange=[change])))
            policy = profiles.PbmQueryAssociatedProfile(
                pbm.ServerObjectRef(objectType="virtualDiskId", key=f"{vm._moId}:{disk.key}")
            )
            current = names.get(policy[0].uniqueId, "none") if policy else "none"
            print(f"{volume}  {vm.name}  {disk.deviceInfo.label}  policy: {current}")
        missing = volumes - found
        if missing:
            sys.exit(f"Not attached to a VM in {namespace}: {', '.join(sorted(missing))}")
    finally:
        Disconnect(si)


if __name__ == "__main__":
    main()
