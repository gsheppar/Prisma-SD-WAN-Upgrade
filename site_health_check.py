#!/usr/bin/env python3

# 20201020 - Add a function to add a single prefix to a local prefixlist - Dan
import cloudgenix
import argparse
from cloudgenix import jd, jd_detailed
import cloudgenix_settings
import sys
import logging
import os
import datetime
import collections
import csv
from csv import DictReader
import time
from datetime import datetime, timedelta
jdout = cloudgenix.jdout


# Global Vars
TIME_BETWEEN_API_UPDATES = 60       # seconds
REFRESH_LOGIN_TOKEN_INTERVAL = 7    # hours
SDK_VERSION = cloudgenix.version
SCRIPT_NAME = 'CloudGenix: Example script: Download Code'
SCRIPT_VERSION = "v1"

# Set NON-SYSLOG logging to use function name
logger = logging.getLogger(__name__)


####################################################################
# Read cloudgenix_settings file for auth token or username/password
####################################################################

sys.path.append(os.getcwd())
try:
    from cloudgenix_settings import CLOUDGENIX_AUTH_TOKEN

except ImportError:
    # Get AUTH_TOKEN/X_AUTH_TOKEN from env variable, if it exists. X_AUTH_TOKEN takes priority.
    if "X_AUTH_TOKEN" in os.environ:
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
    elif "AUTH_TOKEN" in os.environ:
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
    else:
        # not set
        CLOUDGENIX_AUTH_TOKEN = None

try:
    from cloudgenix_settings import CLOUDGENIX_USER, CLOUDGENIX_PASSWORD

except ImportError:
    # will get caught below
    CLOUDGENIX_USER = None
    CLOUDGENIX_PASSWORD = None

def health_check(cgx, lists_from_csv):
        
    site_check_list = []
    elem_id2n = {}
    elem_n2id = {}
    for site in cgx.get.sites().cgx_content['items']:
        site_name = site["name"]
        if site_name in lists_from_csv:
            print("Checking site " + site["name"])
            site_data = {}
            site_data["Site_Name"] = site_name
            if site["element_cluster_role"] == "SPOKE":
                site_data["Site_Type"] = "Branch"
            else:
                site_data["Site_Type"] = "DC"
            num = 0
            ############################## check if connected ######################################
            element_list = []
            for elements in cgx.get.elements().cgx_content["items"]:
                if elements["site_id"] == site["id"]:
                    element_list.append(elements["id"])
                    num += 1
                    if elements["name"] == None:
                        element_name = "no-name"
                    else:
                        element_name = elements["name"]
                    elem_id2n[elements["id"]] = element_name
                    elem_n2id[element_name] = elements["id"]
                    site_data["ION" + str(num) + "_Name"] =  element_name
                    machine_status = None
                    for machine in cgx.get.machines().cgx_content["items"]:
                        try:
                            if machine['em_element_id'] == elements['id']:
                                if machine["connected"]:
                                    machine_status = "connected"
                                else:
                                    machine_status = "disconnected"
                        except:
                            pass
                    if machine_status:
                        site_data["ION" + str(num) + "_Status"] = machine_status
                    else:
                        site_data["ION" + str(num) + "_Status"] = "Unknown"
            if num == 1:
                site_data["ION2_Name"] =  "N/A"
                site_data["ION2_Status"] =  "N/A"                         
                
            
            ############################## check HA status ######################################
            
            active_ion = None
            if site_data["Site_Type"] == "Branch":
                check_ha = False
                for item in cgx.get.spokeclusters(site["id"]).cgx_content["items"]:
                    for ha_item in cgx.get.spokeclusters_status(site_id=site["id"], spokecluster_id=item['id'] ).cgx_content["cluster_members"]:
                        if ha_item["status"] == "active":
                            active_ion = ha_item['element_id']
                            site_data["Active_ION"] = elem_id2n[ha_item['element_id']]
                            check_ha = True
                if check_ha == False:
                    site_data["Active_ION"] = "N/A"
            else:
                site_data["Active_ION"] = "N/A"
            
            ############################## Interface status ######################################
            
            interface_total = 0
            interface_up = 0
            for element in element_list:
                for interface in cgx.get.interfaces(site_id=site['id'], element_id=element).cgx_content["items"]:
                    if interface['admin_up'] == True:
                        resp = cgx.get.interfaces_status(site_id=site['id'], element_id=element, interface_id=interface["id"]).cgx_content
                        try:
                            if resp["operational_state"] == "up":
                                interface_up += 1
                            interface_total += 1
                        except:
                            pass            
            site_data["Int_Status"] =  str(interface_up) + " of " +str(interface_total)
            
            ############################## check VPN status ######################################
                
            topology_filter = '{"type":"basenet","nodes":["' +  site["id"] + '"]}'
            resp = cgx.post.topology(topology_filter)
            if resp.cgx_status:
                topology_list = resp.cgx_content.get("links", None)
                vpn_count = 0
                vpn_up = 0
                for links in topology_list:
                    if links['type'] == 'public-anynet' or links['type'] == 'private-anynet':
                        vpn_count += 1
                        if links["status"] == "up":
                            vpn_up += 1
                site_data["VPN_Status"] =  str(vpn_up) + " of " +str(vpn_count)
            else:
                print("Failed to get VPN status for " + site_name)
                site_data["VPN_Status"] =  "N/A"
            
            ############################## check BGP status ######################################
            bgp_count = 0
            bgp_up = 0
            bgp_adv = 0
            if site_data["Site_Type"] == "Branch":
                if active_ion == None:
                    active_ion = elem_n2id[site_data["ION1_Name"]]
                for bgpstatus in cgx.get.bgppeers_status(site_id=site["id"], element_id=active_ion).cgx_content["items"]:
                    bgp_count += 1
                    if bgpstatus["state"] == "Established":
                        bgp_up += 1
                        try:
                            prefixes = cgx.get.bgppeers_advertisedprefixes(site_id=site["id"], element_id=active_ion, bgppeer_id=bgpstatus['id']).cgx_content['advertised_prefixes']["ipv4_set"]
                            bgp_adv = len(prefixes)
                        except:
                            pass
                    
                site_data["BGP_Status"] = str(bgp_up) + " of " +str(bgp_count)
                site_data["BGP_ADV"] = str(bgp_adv)
            else:
                for elements in cgx.get.elements().cgx_content["items"]:
                    if elements["site_id"] == site["id"]:
                        for bgpstatus in cgx.get.bgppeers_status(site_id=site["id"], element_id=elements['id']).cgx_content["items"]:
                            bgp_count += 1
                            if bgpstatus["state"] == "Established":
                                bgp_up += 1
                                try:
                                    prefixes = cgx.get.bgppeers_advertisedprefixes(site_id=site["id"], element_id=elements['id'], bgppeer_id=bgpstatus['id']).cgx_content['advertised_prefixes']["ipv4_set"]
                                    bgp_adv += len(prefixes)
                                except:
                                    pass
                                    
                        site_data["BGP_Status"] = str(bgp_up) + " of " +str(bgp_count)
                        site_data["BGP_ADV"] = str(bgp_adv)

                

                    
                
            
            
            site_check_list.append(site_data)
            
    
    csv_columns = []
    if site_check_list:
        for key in site_check_list[0].keys():
            csv_columns.append(key)
    csv_file = "site_health_check.csv"
    try:
        with open(csv_file, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in site_check_list:
                writer.writerow(data)
            print("Saved site_health_check.csv file")
    except IOError:
        print("CSV Write Failed")
        
    return    

                                          
def go():
    ############################################################################
    # Begin Script, parse arguments.
    ############################################################################

    # Parse arguments
    parser = argparse.ArgumentParser(description="{0}.".format(SCRIPT_NAME))

    # Allow Controller modification and debug level sets.
    controller_group = parser.add_argument_group('API', 'These options change how this program connects to the API.')
    controller_group.add_argument("--controller", "-C",
                                  help="Controller URI, ex. "
                                       "Alpha: https://api-alpha.elcapitan.cloudgenix.com"
                                       "C-Prod: https://api.elcapitan.cloudgenix.com",
                                  default=None)
    controller_group.add_argument("--insecure", "-I", help="Disable SSL certificate and hostname verification",
                                  dest='verify', action='store_false', default=True)
    login_group = parser.add_argument_group('Login', 'These options allow skipping of interactive login')
    login_group.add_argument("--email", "-E", help="Use this email as User Name instead of prompting",
                             default=None)
    login_group.add_argument("--pass", "-PW", help="Use this Password instead of prompting",
                             default=None)
    debug_group = parser.add_argument_group('Debug', 'These options enable debugging output')
    debug_group.add_argument("--debug", "-D", help="Verbose Debug info, levels 0-2", type=int,
                             default=0)
    config_group = parser.add_argument_group('Config', 'These options change how the configuration is generated.')
    config_group.add_argument('--file', '-F', help='A CSV file name', required=True)
    
    args = vars(parser.parse_args())
                             
    ############################################################################
    # Instantiate API
    ############################################################################
    cgx_session = cloudgenix.API(controller=args["controller"], ssl_verify=args["verify"])

    # set debug
    cgx_session.set_debug(args["debug"])

    ##
    # ##########################################################################
    # Draw Interactive login banner, run interactive login including args above.
    ############################################################################
    print("{0} v{1} ({2})\n".format(SCRIPT_NAME, SCRIPT_VERSION, cgx_session.controller))

    # login logic. Use cmdline if set, use AUTH_TOKEN next, finally user/pass from config file, then prompt.
    # figure out user
    if args["email"]:
        user_email = args["email"]
    elif CLOUDGENIX_USER:
        user_email = CLOUDGENIX_USER
    else:
        user_email = None

    # figure out password
    if args["pass"]:
        user_password = args["pass"]
    elif CLOUDGENIX_PASSWORD:
        user_password = CLOUDGENIX_PASSWORD
    else:
        user_password = None

    # check for token
    if CLOUDGENIX_AUTH_TOKEN and not args["email"] and not args["pass"]:
        cgx_session.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if cgx_session.tenant_id is None:
            print("AUTH_TOKEN login failure, please check token.")
            sys.exit()

    else:
        while cgx_session.tenant_id is None:
            cgx_session.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not cgx_session.tenant_id:
                user_email = None
                user_password = None

    ############################################################################
    # End Login handling, begin script..
    ############################################################################

    # get time now.
    curtime_str = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')

    # create file-system friendly tenant str.
    tenant_str = "".join(x for x in cgx_session.tenant_name if x.isalnum()).lower()
    cgx = cgx_session
    
    try:
        with open(args['file'], "r") as csvfile:
            csvreader = DictReader(csvfile)
            lists_from_csv = []
            for row in csvreader:
                lists_from_csv.append(row['Site_Name'])
    except:
        print("Error importing CSV. Please check column name ION_Name is there")
        return
    
    health_check(cgx, lists_from_csv)
    
    # end of script, run logout to clear session.
    cgx_session.get.logout()

if __name__ == "__main__":
    go()