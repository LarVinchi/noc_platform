"""Explainable preview rules, not an AI model or mailbox connector."""
import re

RULE_VERSION='preview-rules-v1'


def classify(subject,body):
    content=f'{subject}\n{body}'
    checks=[
        ('outage','high',r'\b(still down|service down|link down|outage|fib(?:er|re) cut|loss of signal|no connectivity)\b','Possible service outage or cable fault'),
        ('customer_escalation','high',r'\b(escalation|escalate|escalated|customer complaint)\b','Escalation or customer complaint language'),
        ('sla_risk','high',r'\b(sla|breach|deadline)\b','SLA or deadline reference requires review'),
        ('installation_request','normal',r'\b(ftth request|installation request|schedule installation|customer name|service package)\b','Possible FTTH installation request'),
        ('engineering_action','normal',r'\b(engineer|dispatch|investigate|maintenance|work order)\b','Engineering action or work-order reference'),
    ]
    signals=[{'category':category,'priority':priority,'reason':reason,'matched':match.group(0)}
             for category,priority,pattern,reason in checks if (match:=re.search(pattern,content,re.I))]
    restored=bool(re.search(r'\b(service restored|link restored|restoration confirmed|resolved outage)\b',content,re.I))
    still_down=bool(re.search(r'\b(still down|remains down|not restored)\b',content,re.I))
    if restored and not still_down:
        signals.insert(0,{'category':'restoration_update','priority':'normal','reason':'Restoration language needs verification against the incident','matched':'restoration wording'})
    urgent=bool(re.search(r'\b(urgent|asap|immediately)\b',content,re.I))
    if not signals and urgent:
        signals.append({'category':'attention','priority':'high','reason':'Urgency wording without enough operational context','matched':'urgency wording'})
    if signals:
        category=signals[0]['category'];priority='high' if urgent or (signals[0]['priority']=='high') else 'normal'
    elif re.search(r'\b(newsletter|unsubscribe|weekly bulletin)\b',content,re.I):
        category='routine';priority='low'
        signals=[{'category':category,'priority':priority,'reason':'Possible routine bulletin; verify before dismissal','matched':'bulletin wording'}]
    else:
        category='uncertain';priority='normal'
        signals=[{'category':category,'priority':priority,'reason':'No clear operational rule matched; manual review required','matched':None}]
    references={
        'fn':sorted(set(re.findall(r'\bFN\d{3,20}\b',content,re.I))),
        'work_order':sorted(set(re.findall(r'\bCO\d{3,20}\b',content,re.I))),
        'tt':sorted(set(re.findall(r'\b[A-Z]{2}_IM_\d{8}_\d+\b',content,re.I))),
    }
    return {'category':category,'priority':priority,'signals':signals,'references':{key:[value.upper() for value in values] for key,values in references.items()},'rule_version':RULE_VERSION}
