import pytest
from app.services.mail_triage import classify


@pytest.mark.parametrize('subject,body,category,priority',[
    ('Urgent fiber cut','Service down at FN659353','outage','high'),
    ('Customer escalation','Customer complaint: delayed installation','customer_escalation','high'),
    ('SLA deadline','Please investigate','sla_risk','high'),
    ('Installation request','CUSTOMER NAME: Example, SERVICE PACKAGE: 100Mbps','installation_request','normal'),
    ('Service restored','Earlier outage resolved; restoration confirmed','restoration_update','normal'),
    ('Newsletter','Weekly bulletin: unsubscribe','routine','low'),
    ('Please check','The customer asked about an unfamiliar situation','uncertain','normal'),
])
def test_operational_hints_and_uncertain_fallback(subject,body,category,priority):
    result=classify(subject,body)
    assert result['category']==category and result['priority']==priority
    assert result['signals'] and result['rule_version']=='preview-rules-v1'


def test_conflicting_restoration_requires_fault_review_and_normalizes_references():
    result=classify('Service restored but still down','fn659353 co31888772 tn_im_09102026_0001')
    assert result['category']=='outage'
    assert result['references']=={'fn':['FN659353'],'work_order':['CO31888772'],'tt':['TN_IM_09102026_0001']}
    assert classify('Newsletter: urgent service down','unsubscribe')['category']=='outage'
