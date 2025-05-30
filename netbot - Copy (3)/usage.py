#!/usr/bin/python

from getpass import getpass
import os
from pyproach import api
# from win_pass import GET_WINAPROACH_USERNAME_AND_PASSWORD
def GET_WINAPROACH_USERNAME_AND_PASSWORD():
    pwdFilePath = os.path.expanduser('~/.netrc')
    pwdFileExists = os.path.isfile(pwdFilePath)
    if not pwdFileExists:
        wa_username = "mhemanth"
        wa_password = "##Hemanth138##"        
        # wa_username = input("\n\nPlease enter your Win@proach username: ")
        # wa_password = getpass(prompt="Please enter your Winaproach password: ")
    else:
        wa_username = ""
        wa_password = ""
        with open(pwdFilePath) as pwd_file:
            #full_line = pwd_file.read()
            # here replacing "\n" symbols with space and making a list out of long string
            #full_line = full_line.replace("\n", " ").split(" ")
            #wa_username = full_line[3]
            #wa_password = full_line[5]
            for line in pwd_file:
                if "login" in line:
                    wa_username = line.split(" ")[-1].strip()
                    print("Winaproach Username taken from ~/.netrc file")
                elif "password" in line:
                    wa_password = line.split(" ")[-1].strip()
                    print("Winaproach password taken from ~/.netrc file")
        if wa_password == "":
            wa_username = "mhemanth"
            wa_password = "##Hemanth138##"
            # wa_username = input("\n\nPlease enter your Win@proach username: ")
            # wa_password = getpass(prompt="Please enter your Winaproach password: ")            
    return wa_username, wa_password

wa_username, wa_password = GET_WINAPROACH_USERNAME_AND_PASSWORD()
winapi = api.Aproach(username=wa_username, password=wa_password)
# confirm = input("\033[1m" +"Are you want to create a TR:"+"\033[0m")
confirm= "yes"
source_ip= '1.1.1.1'
destination_ip='1.2.2.2'
data= 'Routing check request '+'source IP:'+source_ip+'destination ip:'+destination_ip

if confirm == 'yes' :
    # data2= input("\033[1m" +"Please enter parent CR:"+"\033[0m") # type: ignore
    my_TR = winapi.create_record(
    record_type='TR',
    title=data,
    assignee_group='OCISNWE',
    assignee_name='N. E',
    severity='4',
    overview= data)

    my_TR.save()
    print(my_TR.id)

    

