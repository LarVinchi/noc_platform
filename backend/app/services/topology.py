"""Build a cable's topology from its actual inventory relationships."""


def build_cable_topology(cable):
    nodes, edges = {}, {}

    def node(identifier, node_type, label, display_type, badge):
        identifier = str(identifier)
        nodes[identifier] = {
            "id": identifier, "type": node_type, "position": {"x": 0, "y": 0},
            "data": {"label": label, "type": display_type, "badge": badge},
        }
        return identifier

    def edge(source, target, color):
        source, target = str(source), str(target)
        identifier = f"e-{source}-{target}"
        edges[identifier] = {
            "id": identifier, "source": source, "target": target,
            "animated": True, "style": {"stroke": color},
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
                node(identifier, kind, customer.customer_name if customer else "Unknown", label, badge)
            edge(cable.cable_id, identifier, "#f97316")

        for pfp in core.pfps:
            pfp_id = node(pfp.pfp_id, "primary_splitter", pfp.name,
                          "Primary Splitter Cabinet", f"{pfp.split_ratio} Split")
            edge(cable.cable_id, pfp_id, "#a855f7")
            for pfs in pfp.pfss:
                pfs_id = node(pfs.pfs_id, "secondary_splitter", pfs.name,
                              "Secondary Splitter Enclosure", f"{pfs.split_ratio} Split")
                edge(pfp_id, pfs_id, "#a855f7")
                for nap in pfs.naps:
                    nap_id = node(nap.nap_id, "access_point", nap.nap_code,
                                  "Service Access Terminal", f"{nap.total_ports} Ports")
                    edge(pfs_id, nap_id, "#a855f7")
                    for drop in nap.drop_cables:
                        for allocation in drop.allocations:
                            if not allocation.is_active or allocation.service is None:
                                continue
                            customer = allocation.service.customer
                            cpe_id = node(f"cpe-{allocation.allocation_id}", "cpe_outlet",
                                          customer.customer_name if customer else "FTTH Sub",
                                          "Customer Premise (ONT/Router)",
                                          f"Port {allocation.nap_port_number}")
                            edge(nap_id, cpe_id, "#f97316")

    return {"nodes": list(nodes.values()), "edges": list(edges.values())}
