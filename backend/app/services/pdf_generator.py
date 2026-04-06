import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
from app.models.provisioning import ServiceOrder

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
TEMPLATE_DIR = os.path.join(BASE_DIR, "app/templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "static/documents/acceptances")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_acceptance_pdf(order: ServiceOrder, noc_signature_url: str = None) -> str:
    """Generates a PDF document for FTTH Acceptance and returns the file path."""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("ftth_acceptance.html")

    html_out = template.render(
        order=order, 
        metrics=order.metrics,
        base_dir=BASE_DIR,
        noc_signature_url=noc_signature_url
    )

    # --- UPDATED NAMING CONVENTION LOGIC ---
    # Use the actual installation (completion) date if it exists, otherwise fallback to today
    if order.completion_date:
        date_str = order.completion_date.strftime("%d%m%Y")
    else:
        date_str = datetime.now().strftime("%d%m%Y")
        
    fn_num = order.fn_number or "NA"
    isp_val = order.isp.value if order.isp else "UNKNOWN"
    
    # Clean the customer name just in case it has trailing spaces
    clean_customer_name = order.customer_name.strip()
    
    # Format: FTTH Installation Acceptance-<FN_NUMBER>-<ISP>-<Customer_Name>- <DDMMYYYY>.pdf
    file_name = f"FTTH Installation Acceptance-{fn_num}-{isp_val}-{clean_customer_name}- {date_str}.pdf"
    file_path = os.path.join(OUTPUT_DIR, file_name)
    # ----------------------------------------

    with open(file_path, "w+b") as result_file:
        pisa_status = pisa.CreatePDF(
            src=html_out, 
            dest=result_file
        )

    if pisa_status.err:
        raise Exception("Error generating PDF document")

    return f"/static/documents/acceptances/{file_name}"