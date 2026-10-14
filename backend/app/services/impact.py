from sqlalchemy.orm import selectinload
from app.models.allocations import CoreAllocation, DropAllocation
from app.models.infrastructure import FiberCore, FiberCable, DropCable, NAP, PFS, PFP
from app.models.crm import Service


def service_paths(db):
    result = {}

    def append(service, path):
        if not service or service.status != "active":
            return
        key = str(service.service_id)
        row = result.setdefault(key, {"service_id": key, "customer_id": str(service.customer_id),
                                     "customer": service.customer.customer_name,
                                     "service_type": service.service_type, "paths": []})
        row["paths"].append(path)

    for alloc in db.query(CoreAllocation).options(
        selectinload(CoreAllocation.core).selectinload(FiberCore.cable).selectinload(FiberCable.route),
        selectinload(CoreAllocation.service).selectinload(Service.customer)
    ).filter(CoreAllocation.end_date.is_(None)).all():
        cable = alloc.core.cable
        append(alloc.service, {"route_id": str(cable.route_id), "cable_id": str(cable.cable_id),
                               "core_id": str(alloc.core_id), "role": alloc.allocation_role,
                               "cable": cable.cable_name, "route": cable.route.route_name, "core": alloc.core.core_number})
    for alloc in db.query(DropAllocation).options(
        selectinload(DropAllocation.service).selectinload(Service.customer),
        selectinload(DropAllocation.drop_cable).selectinload(DropCable.nap)
            .selectinload(NAP.pfs).selectinload(PFS.pfp).selectinload(PFP.core).selectinload(FiberCore.cable).selectinload(FiberCable.route)
    ).filter(DropAllocation.is_active.is_(True)).all():
        drop = alloc.drop_cable
        # DropCable uses a backref created on NAP.drop_cables in the ORM.
        nap = drop.nap
        core = nap.pfs.pfp.core
        append(alloc.service, {"route_id": str(core.cable.route_id), "cable_id": str(core.cable_id),
                               "core_id": str(core.core_id), "pfp_id": str(nap.pfs.pfp_id),
                               "pfs_id": str(nap.pfs_id), "nap_id": str(nap.nap_id),
                               "drop_cable_id": str(drop.drop_cable_id), "port": alloc.nap_port_number,
                               "cable": core.cable.cable_name, "route": core.cable.route.route_name,
                               "core": core.core_number, "pfp": nap.pfs.pfp.name,
                               "pfs": nap.pfs.name, "nap": nap.nap_code, "drop": drop.drop_cable_code,
                               "role": "access"})
    return list(result.values())


def impact_for_route(db, route_id=None, cable_id=None):
    key, identifier = ("cable_id", str(cable_id)) if cable_id else ("route_id", str(route_id))
    affected = []
    for row in service_paths(db):
        matched = [path for path in row["paths"] if path[key] == identifier]
        if matched:
            affected.append({**row, "affected_paths": matched,
                             "alternate_path_recorded": any(p[key] != identifier for p in row["paths"]),
                             "impact": "potentially_affected", "service_health": "not_verified"})
    return {key: identifier, "services": affected, "service_count": len(affected),
            "customer_count": len({row["customer_id"] for row in affected})}
