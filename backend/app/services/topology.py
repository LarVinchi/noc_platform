"""Build a cable's topology from its actual inventory relationships."""


def build_cable_topology(cable):
    nodes, edges = {}, {}

    def node(identifier, node_type, label, display_type, badge, **metadata):
        identifier = str(identifier)
        nodes[identifier] = {
            "id": identifier, "type": node_type, "position": {"x": 0, "y": 0},
            "data": {"label": label, "type": display_type, "badge": badge, **metadata},
        }
        return identifier

    def edge(source, target, color, **metadata):
        source, target = str(source), str(target)
        identifier = f"e-{source}-{target}"
        previous = edges.get(identifier, {}).get("data", {})
        core_numbers = sorted(set(previous.get("core_numbers", []) + metadata.pop("core_numbers", [])))
        edges[identifier] = {
            "id": identifier, "source": source, "target": target,
            "animated": False, "style": {"stroke": color},
            "data": {**previous, **metadata, "core_numbers": core_numbers},
        }

    for core in cable.cores:
        for allocation in core.allocations:
            if allocation.end_date is not None or allocation.service is None:
                continue
            service = allocation.service
            customer = service.customer
            kind, label = {
                "DARKFIBER": ("dark_fiber_endpoint", "Dark Fiber Patch Panel"),
                "LAYER2": ("layer2_endpoint", "Layer 2 UNI (Network Interface)"),
            }.get(service.service_type, ("dia_endpoint", "DIA Demarcation (Enterprise)"))
            badge = f"Core {core.core_number}"
            if service.service_type != "DARKFIBER":
                badge += f" | {service.bandwidth_mbps or 'N/A'} Mbps"
            identifier = f"srv-{service.service_id}"
            # A service may occupy multiple cores; display one endpoint and retain
            # each core's label rather than overwrite or duplicate its node.
            if identifier in nodes:
                previous = nodes[identifier]["data"]["badge"]
                nodes[identifier]["data"]["badge"] = f"{previous}; {badge}"
            else:
                node(identifier, kind, customer.customer_name if customer else "Unknown", label, badge,
                     service_id=str(service.service_id), service_type=service.service_type)
            edge(cable.cable_id, identifier, "#f97316", kind="service_core",
                 cable_id=str(cable.cable_id), cable_name=getattr(cable, "cable_name", "Backbone cable"),
                 core_numbers=[core.core_number])

        for pfp in core.pfps:
            pfp_id = node(pfp.pfp_id, "primary_splitter", pfp.name,
                          "Primary Splitter Cabinet", f"{pfp.split_ratio} Split", split_ratio=pfp.split_ratio)
            edge(cable.cable_id, pfp_id, "#a855f7", kind="feeder",
                 cable_id=str(cable.cable_id), cable_name=getattr(cable, "cable_name", "Feeder cable"), core_numbers=[core.core_number])
            for pfs in pfp.pfss:
                pfs_id = node(pfs.pfs_id, "secondary_splitter", pfs.name,
                              "Secondary Splitter Enclosure", f"{pfs.split_ratio} Split", split_ratio=pfs.split_ratio)
                links = [link for link in getattr(pfp, "dist_fibers_out", []) if str(link.dest_pfs_id) == str(pfs.pfs_id)]
                edge(pfp_id, pfs_id, "#a855f7", kind="distribution", cable_name=" / ".join(dict.fromkeys(link.cable_name for link in links)) or None,
                     core_numbers=[link.fiber_number for link in links], recorded_fibres=len(links))
                for nap in pfs.naps:
                    nap_id = node(nap.nap_id, "access_point", nap.nap_code,
                                  "Service Access Terminal", f"{nap.total_ports} Ports", total_ports=nap.total_ports)
                    links = [link for link in getattr(pfs, "dist_fibers_out", []) if str(link.dest_nap_id) == str(nap.nap_id)]
                    edge(pfs_id, nap_id, "#a855f7", kind="distribution", cable_name=" / ".join(dict.fromkeys(link.cable_name for link in links)) or None,
                         core_numbers=[link.fiber_number for link in links], recorded_fibres=len(links))
                    for drop in nap.drop_cables:
                        for allocation in drop.allocations:
                            if not allocation.is_active or allocation.service is None:
                                continue
                            customer = allocation.service.customer
                            cpe_id = node(f"cpe-{allocation.allocation_id}", "cpe_outlet",
                                          customer.customer_name if customer else "FTTH Sub",
                                          "Customer Premise (ONT/Router)",
                                          f"Port {allocation.nap_port_number}", service_id=str(allocation.service.service_id), service_type=allocation.service.service_type)
                            edge(nap_id, cpe_id, "#f97316", kind="drop", cable_name=getattr(drop, "drop_cable_code", None), port=allocation.nap_port_number)

    return {"nodes": list(nodes.values()), "edges": list(edges.values())}
