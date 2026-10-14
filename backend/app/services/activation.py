"""Activate an accepted FTTH order on the existing CRM/inventory path."""
import re
from app.models.crm import Customer, Service
from app.models.allocations import DropAllocation


def activate_ftth(order, db):
    if order.activated_service_id:
        return order.activated_service_id
    customer = db.query(Customer).filter_by(service_id_code=order.service_order_number).first()
    if customer is None:
        customer = Customer(customer_name=order.customer_name, service_id_code=order.service_order_number,
                            customer_type="METROREACH" if order.isp.value == "METROREACH" else "ISP",
                            email=order.email, phone=order.phone_number, address=order.service_address)
        db.add(customer)
        db.flush()
    match = re.fullmatch(r"([\d.]+)(Mbps|Gbps)", order.bandwidth)
    speed = round(float(match[1]) * (1000 if match[2] == "Gbps" else 1)) if match else None
    service = Service(customer_id=customer.customer_id, service_type="FTTH",
                      bandwidth_mbps=speed, status="active")
    db.add(service)
    db.flush()
    db.add(DropAllocation(service_id=service.service_id, drop_cable_id=order.drop_cable_id,
                          nap_port_number=order.nap_port, is_active=True))
    order.activated_service_id = service.service_id
    return service.service_id
