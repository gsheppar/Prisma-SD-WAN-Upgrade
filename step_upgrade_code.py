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
import re
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

def download(cgx, lists_from_csv, goal_image_version):
    
    image_options = []
    image_id2n = {}
    image_n2id = {}
    for images in cgx.get.element_images().cgx_content["items"]:
        image_options.append(images['version'])
        image_n2id[images['version']] = images['id']
        image_id2n[images['id']] = images['version']
        
    ########## Check if image is available ##########
    
    if goal_image_version not in image_options:
        print("The image: " + goal_image_version + " is not an option in your tenant")
        return
    
    ########## Get list of IONs ##########
    
    print("Getting all IONs and checking if they are online\n")
    element_id_list = []
    element_id2n = {}
    for name in lists_from_csv:
        for elements in cgx.get.elements().cgx_content["items"]:
            if name == elements["name"]:
                for machine in cgx.get.machines().cgx_content["items"]:
                    try:
                        if machine['em_element_id'] == elements['id']:
                            if machine["connected"]:
                                element_id_list.append(elements["id"])
                                element_id2n[elements["id"]] = elements["name"]
                            else:
                                print(elements["name"] + " is currently offline so will not download code\n")
                    except:
                        pass

    ########## Check if image is already upgraded ##########

    check_element_list = element_id_list
    for element_id in check_element_list:
        time_stamp = 0
        for software in cgx.get.software_status(element_id=element_id).cgx_content["items"]:
            current_timestamp = software.get("_created_on_utc", 0)    
            if current_timestamp >= time_stamp:
                status = software
                time_stamp = current_timestamp
        
        if image_id2n[status['active_image_id']] == goal_image_version:
            print(element_id2n[element_id] + " already has been upgraded to " + goal_image_version)
            element_id_list.remove(element_id)
                
                
    
    ########## Start upgrade ##########
    if element_id_list:
        complete_upgrade(cgx, goal_image_version, element_id_list, element_id2n)
        print("\nCode upgrade has been complete on all sites\n")
    else:
        print("\nCode upgrade has already been complete on all sites\n")
    return


def complete_upgrade(cgx, goal_image_version, element_id_list, element_id2n):

    images_id2n = {}
    images_n2id = {}
    images_dict = {}
    goal_image_id = None
    upgrade_dict = {}

    for image in cgx.get.element_images().cgx_content["items"]:
        image_version = image['version']
        image_id = image['id']
        images_id2n[image_id] = image_version
        images_n2id[image_version] = image_id
        images_dict[image_version] = image
        if image['version'] == goal_image_version:
            goal_image_id = image['id']

    all_upgraded = False
    upgrade_list = []
    master_list = []
    max_steps = 1
    while not all_upgraded:
        if max_steps > 5:
            print("Error max steps of 5 has been reached")
            return
        if len(element_id_list) == 0:
            if check:
                print ("All element code changes are complete")
                return
            else:
                return
        # check current image
        for element_id in element_id_list:
            resp = cgx.get.software_status(element_id)
            if not resp.cgx_status:
                master_list.remove(element_id)
                name = element_id2n[element_id]
                print("Error unable to get software state for " + name)
                skip = True
            else:
                active_image_id = resp.cgx_content.get('active_image_id')
                skip = False
                if active_image_id is None:
                    software_status_list = resp.cgx_content.get('items', [])
                    latest_timestamp = 0
                    latest_status = {}
                    if len(software_status_list) > 1:
                        for current_status in software_status_list:
                            current_timestamp = current_status.get("_created_on_utc", 0)
                            name = element_id2n[element_id]
                            if current_timestamp > latest_timestamp:
                                latest_timestamp = current_timestamp
                                latest_status = current_status
                        active_image_id = latest_status.get('active_image_id')
                        active_version_name = latest_status.get('active_version')
                    else:
                        active_image_id = software_status_list[0].get('active_image_id')
                        active_version_name = software_status_list[0].get('active_version')
                    try:
                        if active_image_id is None:
                            head_tail = active_version_name.split("-")
                            data = head_tail[0].strip()
                            active_version_name = data.replace("-","")
                            for image in images_dict:
                                if active_version_name in image:
                                    active_image_id = images_n2id[image]
                        if active_image_id is None:
                            active_version_name = active_version_name[:-2]
                            for image in images_dict:
                                if active_version_name in image:
                                    active_image_id = images_n2id[image]
                    except:
                        print("Error failed to do an image ID conversion for " + active_version_name)
                if active_image_id is not None:
                    active_image_name = images_id2n[active_image_id]
                if active_image_id is None:
                    name = element_id2n[element_id]
                    print("Error unable to get active image id for " + name)
                    skip = True
                elif active_image_id == goal_image_id:
                    name = element_id2n[element_id]
                    print("Element " + name + " code is at correct version " + goal_image_version)
                    skip = True
                elif major_minor(goal_image_version) > major_minor(active_image_name):
                    name = element_id2n[element_id]
                    print("Performing step upgrade for " + name + " to " + goal_image_version)
                    for path in upgrade_path_regex.keys():
                        if re.match(path, active_image_name):
                            if type(upgrade_path_regex[path]) == list:
                                for upgrade_version in upgrade_path_regex[path]:
                                    if major_minor(goal_image_version) > major_minor(upgrade_version):
                                        new_version = get_exact_version(upgrade_version, images_dict)
                                        if not new_version:
                                            continue
                                        new_image_id = images_dict[new_version]['id'] if new_version else None
                                        break
                                    else:
                                        new_version = goal_image_version
                                        new_image_id = goal_image_id
                                        break
                                else:
                                    continue

                                break
                            else:
                                if major_minor(goal_image_version) > major_minor(upgrade_path_regex[path]):
                                    new_version = get_exact_version(upgrade_path_regex[path], images_dict)
                                    new_image_id = images_dict[new_version]['id'] if new_version else None
                                    break
                                else:
                                    new_version = goal_image_version
                                    new_image_id = goal_image_id
                                    break

                elif major_minor(goal_image_version) < major_minor(active_image_name):
                    name = element_id2n[element_id]
                    print("Performing step downgrade for " + name + " to " + goal_image_version)
                    for path in downgrade_path_regex.keys():
                        if re.match(path, active_image_name):
                            if type(downgrade_path_regex[path]) == list:
                                for downgrade_version in downgrade_path_regex[path]:
                                    if major_minor(goal_image_version) < major_minor(downgrade_version):
                                        new_version = get_exact_version(downgrade_version, images_dict)
                                        if not new_version:
                                            continue
                                        new_image_id = images_dict[new_version]['id'] if new_version else None
                                        break
                                    else:
                                        new_version = goal_image_version
                                        new_image_id = goal_image_id
                                        break
                                else:
                                    continue

                                break
                            else:
                                if major_minor(goal_image_version) < major_minor(downgrade_path_regex[path]):
                                    new_version = get_exact_version(downgrade_path_regex[path], images_dict)
                                    new_image_id = images_dict[new_version]['id'] if new_version else None
                                    break
                                else:
                                    new_version = goal_image_version
                                    new_image_id = goal_image_id
                                    break
                else:
                    new_version = goal_image_version
                    new_image_id = goal_image_id

                if not skip:
                    if not new_version:
                        name = element_id2n[element_id]
                        print("Error unable to find new version of code for " + name)
                    else:
                        software_state_describe_response = cgx.get.software_state(element_id)
                        if not software_state_describe_response.cgx_status:
                            name = element_id2n[element_id]
                            print("Error unable to get element state: " + name)
                        else:
                            software_state_change = software_state_describe_response.cgx_content
                            software_state_change['image_id'] = new_image_id
                            software_state_modify_response = cgx.put.software_state(element_id, software_state_change)
                            if not software_state_modify_response.cgx_status:
                                name = element_id2n[element_id]
                                print("Error upgrade command failed for " + name)
                            else:
                                upgrade_list.append(element_id)
                                name = element_id2n[element_id]
                                print("Performing code change for " + name + " to " + new_version)
                                upgrade_dict[element_id] = new_image_id
        
        if len(upgrade_list) != 0:
            master_list = upgrade_check(cgx, upgrade_list, element_id2n, upgrade_dict, images_dict, images_n2id)
            upgrade_list.clear()
            max_steps += 1
            element_id_list = master_list.copy()
        else:
            all_upgraded = True
    return


def upgrade_check(cgx, upgrade_list, element_id2n, upgrade_dict, images_dict, images_n2id):

    print("\nPlease wait while devices are upgraded\n")

    orginal_list = upgrade_list.copy()

    ready = False
    time_elapsed = 0
    while not ready:
        for element_id in upgrade_list:
            resp = cgx.get.software_status(element_id)
            if not resp.cgx_status:
                orginal_list.remove(element_id)
                upgrade_list.remove(element_id)
                name = element_id2n[element_id]
                print("Error could not query element software status for element " + name)
            active_image_id = resp.cgx_content.get('active_image_id')
            if active_image_id is None:
                software_status_list = resp.cgx_content.get('items', [])
                latest_timestamp = 0
                latest_status = {}
                for current_status in software_status_list:
                    current_timestamp = current_status.get("_created_on_utc", 0)
                    name = element_id2n[element_id]
                    if current_timestamp > latest_timestamp:
                        latest_timestamp = current_timestamp
                        latest_status = current_status
                active_image_id = latest_status.get('active_image_id')
                active_version_name = latest_status.get('active_version')
                try:
                    if active_image_id is None:
                        head_tail = active_version_name.split("-")
                        data = head_tail[0].strip()
                        active_version_name = data.replace("-","")
                        for image in images_dict:
                            if active_version_name in image:
                                active_image_id = images_n2id[image]
                    if active_image_id is None:
                        active_version_name = active_version_name[:-2]
                        for image in images_dict:
                            if active_version_name in image:
                                active_image_id = images_n2id[image]
                except:
                    pass
            if time_elapsed > 1200:
                orginal_list.remove(element_id)
                upgrade_list.remove(element_id)
                name = element_id2n[element_id]
                print("Error element " + name + " did not upgrade in time")
            if active_image_id != upgrade_dict[element_id]:
                name = element_id2n[element_id]
                print("Element " + name + " is not yet at the right image yet")
            else:
                upgrade_list.remove(element_id)
                name = element_id2n[element_id]
                print("Element " + name + " has been upgraded")
        if len(upgrade_list) == 0:
            ready = True
            print("\nUpgrade check for all elements is complete\n")
        else:
            time.sleep(10)
            time_elapsed += 10
            print("\nWaited so far " + str(time_elapsed) + " seconds out of 1200\n")
    return orginal_list

upgrade_path_regex = {
    "4\.5\..*" : "4.7.1", ### 4.5.xyz -> 4.7.1
    "4\.7\..*" : "5.0.3", ### 4.7.xyz -> 5.0.3
    "5\.0\..*" : "5.2.7", ### 5.0.xyz -> 5.2.7
    "5\.1\..*" : "5.2.7", ### 5.1.xyz -> 5.2.7
    "5\.2\..*" : ["5.5..*", "5.4..*", "5.3..*"], ### 5.2.xyz -> 5.5.3 # Fix for CGCBL-566
    "5\.3\..*" : ["5.5..*", "5.4..*"], ### 5.3.xyz -> 5.5.3
    "5\.4\..*" : ["5.6..*", "5.5..*"], ### 5.4.xyz -> 5.6.1
    "5\.5\..*" : "5.6.1", ### 5.5.xyz -> 5.6.1
}

downgrade_path_regex = {
    "4\.7\..*" : "4.5.3", ### 4.7.xyz -> 4.5.3
    "5\.0\..*" : "4.7.1", ### 5.0 to 4.7.1
    "5\.1\..*" : "4.7.1", ### 5.1 to 4.7.1
    "5\.2\..*" : "5.0.3", ### 5.2 to 5.0.3
    "5\.3\..*" : "5.2.7", ### 5.3 to 5.2.7
    "5\.4\..*" : ["5.2..*", "5.3..*"], ### 5.4 to 5.2.7 # Fix for CGCBL-566
    "5\.5\..*" : ["5.2..*", "5.3..*", "5.4..*"], ### 5.5 to 5.2.7
    "5\.6\..*" : ["5.4..*", "5.5..*"], ### 5.6 to 5.4.1
}

def major_minor(version):
    """
    Parse a software version to get major, minor and micro version numbers.
    :param version: Software version to parse.
    :return: major+minor version
    """

    major, minor = re.search('(\d+)\.(\d+)\..+', version).groups()
    return major + '.' + minor

def get_exact_version(version, image_dict):
    """
    Get the full version string matching the version from the available images
    :param version: Upgrade/Downgrade version
    :param image_dict: Available images dict
    :return: Image version
    """

    for image_version in image_dict.keys():
        if re.search(str(version), image_version):
            return image_version
    return None 

                                          
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
    cgx = cloudgenix.API(controller=args["controller"], ssl_verify=args["verify"])

    # set debug
    cgx.set_debug(args["debug"])

    ##
    # ##########################################################################
    # Draw Interactive login banner, run interactive login including args above.
    ############################################################################
    print("{0} v{1} ({2})\n".format(SCRIPT_NAME, SCRIPT_VERSION, cgx.controller))

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
        cgx.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if cgx.tenant_id is None:
            print("AUTH_TOKEN login failure, please check token.")
            sys.exit()

    else:
        while cgx.tenant_id is None:
            cgx.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not cgx.tenant_id:
                user_email = None
                user_password = None

    ############################################################################
    # End Login handling, begin script..
    ############################################################################

    # get time now.
    curtime_str = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')

    # create file-system friendly tenant str.
    tenant_str = "".join(x for x in cgx.tenant_name if x.isalnum()).lower()
    cgx = cgx
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
    cgx.get.logout()

if __name__ == "__main__":
    go()