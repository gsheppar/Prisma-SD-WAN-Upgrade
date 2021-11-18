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
SCRIPT_NAME = 'CloudGenix: Example script: Upgrade Code'
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

def download(cgx, lists_from_csv, image):
    
    image_options = []
    image_id2n = {}
    image_n2id = {}
    for images in cgx.get.element_images().cgx_content["items"]:
        image_options.append(images['version'])
        image_n2id[images['version']] = images['id']
        image_id2n[images['id']] = images['version']
        
    ########## Check if image is available ##########
    
    if image not in image_options:
        print("The image: " + image + " is not an option in your tenant")
        return
    image_upgrade = image_n2id[image]
    
    ########## Get list of IONs ##########
    
    element_list = []
    element_id2n = {}
    for name in lists_from_csv:
        for elements in cgx.get.elements().cgx_content["items"]:
            if name == elements["name"]:
                for machine in cgx.get.machines().cgx_content["items"]:
                    if machine['em_element_id'] == elements['id']:
                        if machine["connected"]:
                            element_list.append(elements["id"])
                            element_id2n[elements["id"]] = elements["name"]
                        else:
                            print(elements["name"] + " is currewntly offline so will not download code")

    ########## Check if image is already downloaded ##########

    check_element_list = element_list
    for element_id in check_element_list:
        time_stamp = 0
        for software in cgx.get.software_status(element_id=element_id).cgx_content["items"]:
            current_timestamp = software.get("_created_on_utc", 0)    
            if current_timestamp >= time_stamp:
                status = software
                time_stamp = current_timestamp
        
        if image_id2n[status['active_image_id']] == image:
            print(element_id2n[element_id] + " already has been upgraded to " + image)
            element_list.remove(element_id)
                
                
    
    ########## Start upgrade ##########
    
    if len(element_list) != 0:
        print("\nStarting to initiate upgrades")
        for element_id in element_list:
            resp = cgx.get.software_state(element_id=element_id).cgx_content
            data = {"_etag":resp['_etag'],"_schema":resp['_schema'],"image_id":image_upgrade,"scheduled_upgrade":None,"scheduled_download":None,"download_interval":None,"upgrade_interval":None,"interface_ids":None}
            resp = cgx.put.software_state(element_id=element_id, data=data).cgx_content
            if not resp:
                print(str(jdout(resp)))
                element_list.remove(element_id)
            else:
                print("Upgrading to " + image + " on " + element_id2n[element_id])
    
    ########## Track download status ##########
    
    if len(element_list) != 0:
        print("\nStarting to check on upgrade status")
        time_check = 0
        while time_check < 1800:
            check_element_list = element_list
            for element_id in check_element_list:
                time_stamp = 0
                for software in cgx.get.software_status(element_id=element_id).cgx_content["items"]:
                    current_timestamp = software.get("_created_on_utc", 0)    
                    if current_timestamp >= time_stamp:
                        status = software
                        time_stamp = current_timestamp
                if status['active_image_id'] == image_upgrade:
                    print(element_id2n[element_id] + " has finished its upgrade to " + image)
                    element_list.remove(element_id)
        
            if len(element_list) == 0:
                break
            print("Time elapse: " + str(time_check) + " seconds out of 1800 " + str(len(element_list)) + " IONs left")
            time.sleep(10)
            time_check += 10
        if len(element_list) != 0:
            for element_id in element_list:
                print("Upgrading " + image + " on " + element_id2n[element_id] + " did not complete in time please check the ION.")
    
    print("\nCode upgrade has been complete on all sites\n")
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
    config_group.add_argument('--image', '-V', help='Image', required=True)
    
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
    image = args['image']
    try:
        with open(args['file'], "r") as csvfile:
            csvreader = DictReader(csvfile)
            lists_from_csv = []
            for row in csvreader:
                lists_from_csv.append(row['ION_Name'])
    except:
        print("Error importing CSV. Please check column name ION_Name is there")
        return
    
    download(cgx, lists_from_csv, image)
    
    # end of script, run logout to clear session.
    cgx_session.get.logout()

if __name__ == "__main__":
    go()