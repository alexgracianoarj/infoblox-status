import os
import requests
import urllib3
import jmespath
from dotenv import load_dotenv
import logging
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

urllib3.disable_warnings()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler("logs/{day}.log".format(day=datetime.now().strftime("%Y-%m-%d")))
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - Ln %(lineno)d - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


load_dotenv(dotenv_path=os.path.join(".", ".env"))

try:
    url = "https://{infoblox_host}/wapi/v2.7/member?_return_fields%2B=node_info,host_name,service_status".format(infoblox_host=os.getenv("INFOBLOX_HOST"))
    response = requests.get(url, verify=False, headers={"Accept": "application/json"}, auth=(os.getenv("INFOBLOX_USER"), os.getenv("INFOBLOX_PASS")))
    response.raise_for_status()
    data = response.json()
    query = jmespath.search(
        """
        [*].{
            HOST_NAME: host_name,
            HWTYPE: node_info[0].hwtype,
            NODE_STATUS: node_info[0].service_status[0].status,
            SERVICE_STATUS: node_info[0].service_status,
            DHCP_STATUS: service_status[0].status,
            DHCP_DESCRIPTION: service_status[0].description
        }
        """,
        data,
    )
    nodes_status = []
    for item in query:
        node = {}
        node["HOST_NAME"] = item["HOST_NAME"] if item["HOST_NAME"] is not None else ""
        node["HWTYPE"] = item["HWTYPE"] if item["HWTYPE"] is not None else ""
        node["NODE_STATUS"] = item["NODE_STATUS"] if item["NODE_STATUS"] is not None else ""
        disk = jmespath.search("[?service=='DISK_USAGE'].{status: status, description: description}", item["SERVICE_STATUS"])
        node["DISK_STATUS"] = disk[0]["status"] if len(disk) > 0 else ""
        node["DISK_USAGE"] = disk[0]["description"] if len(disk) > 0 else ""
        cpu = jmespath.search("[?service=='CPU_USAGE'].{status: status, description: description}", item["SERVICE_STATUS"])
        node["CPU_STATUS"] = cpu[0]["status"] if len(cpu) > 0 else ""
        node["CPU_USAGE"] = cpu[0]["description"] if len(cpu) > 0 else ""
        memory = jmespath.search("[?service=='MEMORY'].{status: status, description: description}", item["SERVICE_STATUS"])
        node["MEMORY_STATUS"] = memory[0]["status"] if len(memory) > 0 else ""
        node["MEMORY_USAGE"] = memory[0]["description"] if len(memory) > 0 else ""
        node["DHCP_STATUS"] = item["DHCP_STATUS"] if item["DHCP_STATUS"] is not None else ""
        node["DHCP_DESCRIPTION"] = item["DHCP_DESCRIPTION"] if item["DHCP_DESCRIPTION"] is not None else ""
        nodes_status.append(node)
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <style type="text/css">
        table {
            border-radius:3px;
            border-collapse: collapse;
            height: auto;
            max-width: 900px;
            padding:5px;
            width: 100%;
        }
        th {
            background:#CACFD2;
            font-size:13px;
            font-weight: 300;
            padding:10px;
            text-align:center;
            border: 2px solid;
        }
        tr {
            font-size:16px;
            font-weight:normal;
            border: 2px solid;
        }
        td {
            padding:10px;
            text-align:left;
            font-weight:300;
            font-size:13px;
            border: 2px solid;
        }
        </style>
    </head>
    <body>
        <table>
            <thead>
                <tr>
                    <th>
"""
    html += "</th><th>".join(nodes_status[0].keys())
    html += """
                    </th>
                </tr>
            </thead>
            <tbody>        
"""
    for node in nodes_status:
        values = list(node.values())
        html += "<tr>"
        for idx in range(11):
            if idx in [4, 6, 8] and values[idx] != "":
                usage = int(re.search(r"\d+", values[idx]).group())
                if usage >= 60 and usage < 80:
                    html += '<td style="background:#F9E79F">' + values[idx] + "</td>"
                elif usage >= 80:
                    html += '<td style="background:#F5B7B1">' + values[idx] + "</td>"
                else:
                    html += "<td>" + values[idx] + "</td>"
            else:
                html += "<td>" + values[idx] + "</td>"
        html += "</tr>"
    html += """      
             </tbody>
        </table>
  </body>
</html>"""
    message = MIMEMultipart("alternative")
    message["subject"] = os.getenv("SUBJECT_MAIL")
    message["from"] = os.getenv("FROM_EMAIL")
    message["to"] = os.getenv("TO_EMAILS")
    content = MIMEText(html, "html", "utf-8")
    message.attach(content)
    smtp_server = smtplib.SMTP(os.getenv("SMTP_HOST"), os.getenv("SMTP_PORT"))
    # smtp_server.set_debuglevel(1)
    smtp_server.ehlo()
    smtp_server.starttls()
    smtp_server.ehlo()
    smtp_server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
    smtp_server.sendmail(os.getenv("FROM_EMAIL"), os.getenv("TO_EMAILS").split(","), message.as_string())
    smtp_server.quit()
except Exception as error:
    logger.error(error)
