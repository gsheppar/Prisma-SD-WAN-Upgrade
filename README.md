# Prisma SD-WAN Upgrade (Preview)
The purpose of this script is to pre-stage code to a set of IONs from a CSV file and then upgrade a set of IONs from a CSV file.  

#### Features
 - ./get_ions.py can be used to get all branch IONs. You can then remove any IONs you want before using this to run your download and upgrade scripts
 
 - ./download_code.py can be used to pre-stage an ION code to a set of devices from a CSV file
 
 - ./upgrade_code.py can be used to pre-stage an ION code to a set of devices from a CSV file
 
 - ./code_check_.py can be used find out all active and downloaded code then export it to a CSV fil code_check.csv
 

#### License
MIT

#### Requirements
* Active CloudGenix Account - Please generate your API token and add it to cloudgenix_settings.py
* Python >=3.6

#### Installation:
 Scripts directory. 
 - **Github:** Download files to a local directory, manually run the scripts. 
 - pip install -r requirements.txt

### Examples of usage:
 Please generate your API token and add it to cloudgenix_settings.py
 
 - Use the get_ions.py to get a list of all the ION element names
 1. ./get_ions.py
      - Will produce a csv called upgrade_list.csv which you can remove IONs you don't want to be upgraded
 
 - Use the download_code.py to pre-stage code to the IONs elements in the CSV file
 1. ./download_code.py -F upgrade_list.csv -V 5.5.5-b
      - -F is the CSV file and -V is the ION code

 - Use the upgrade_code.py to upgrade code to the IONs elements in the CSV file
 1. ./upgrade_code.py -F upgrade_list.csv -V 5.5.5-b
      - -F is the CSV file and -V is the ION code
      - Please note if the code has not been pre-staged with the previous script it will have to download the code before upgrading 
	  
 - Use the code_check.py to export to a CSV file all IONs active and download image versions 
 1. ./code_check.py
 
 
### Caveats and known issues:
 - This is a PREVIEW release, hiccups to be expected. Please file issues on Github for any problems.

#### Version
| Version | Build | Changes |
| ------- | ----- | ------- |
| **1.0.0** | **b1** | Initial Release. |


#### For more info
 * Get help and additional Prisma SD-WAN Documentation at <https://docs.paloaltonetworks.com/prisma/cloudgenix-sd-wan.html>
