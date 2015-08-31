#!flask/bin/python
from flask import Flask, jsonify
from flask import request
import re
import libvirt
import json
import sys

image_file = {}
pm_file = {}
present_vm_id = 32000
vm_database = []
def parse_pm_file(path):
    fd = open(path)
    pm = fd.read().split("\n")
    for i in range(0,len(pm)):
        pm_file[i+1] = pm[i]
    # print pm_file
    
def increment():
    global present_vm_id
    present_vm_id = present_vm_id+1

def append_data(tmp):
    global vm_database
    vm_database.append(tmp)


def parse_image_file(path):
    fd = open(path,"r")
    image = fd.read().split('\n')
    for i in range(0,len(image)):
        image_file[i+1] = image[i]
    # print image_file

def parse_flavor_file(path):
    f = open('flavor_file')
    file = json.loads(f.read())
    # print len(file['types'])
    for i in range(0,len(file['types'])):
        file['types'][i]['tid'] = i+1
    global flavor_file 
    # flavor_file = json.dumps(file)
    flavor_file = file
    global flavor_dict
    flavor_dict = file[u'types']
    # print "this is dict",
    # print flavor_dict

    


app = Flask(__name__)




@app.route("/")
def api_root():
    return "Welcome"




@app.route("/vm/create",methods = ['GET'])
def vmCreate():
    conn_created = 0
    vm_name = request.args.get('name')
    vm_type = request.args.get('instance_type')
    vm_image = request.args.get('image_id')
    vm_vcpu = ""
    vm_ram = ""
    vm_disk = ""
    vm_pm = ""
    if vm_type is None or vm_name is None or vm_image is None:
        return "Error in Url!!!! Check!!!!"
    if not vm_image or not vm_type or not vm_name:
        return "ERROR: One or more arguments are Null. Check the arguments"
    for i in flavor_dict:
        if i['tid'] == int(vm_type):
            vm_vcpu = str(i['cpu'])
            vm_disk = str(i['disk'])
            vm_ram = str(i['ram'] *1024)
    # print vm_vcpu
    # print vm_ram
    # print vm_disk
    # print image_file
    # print vm_image
    vm_image_path = image_file[int(vm_image)]
    # print vm_image_path
    
    fd = open("a.xml")

    
    print len(pm_file)
    for i in pm_file:
        try:
            connection = libvirt.open("qemu://"+ pm_file[i]+"/system")
            conn_created = 1
            vm_pm = i
            break

        except:
            print "error"
    if conn_created == 0:
        return  jsonify({"vmid":0})

    # connection = libvirt.open("qemu://++/system")
    tmp = {}
    try:
        increment()
        xml = fd.read()% (str(present_vm_id),vm_name,vm_ram,vm_ram,vm_vcpu,vm_image_path)
        dom_ref = connection.defineXML(xml)
        dom_ref.setAutostart(1)
        
        print present_vm_id
        # present_vm_id = present_vm_id + 1
        tmp['vmid'] = present_vm_id
        tmp['name'] = vm_name
        tmp['instance_type'] = int(vm_type)
        tmp['pmid'] = vm_pm
        print tmp
        # vm_database.append(tmp)
        # print vm_database
        append_data(tmp)
        print vm_database

        return jsonify({"vmid":present_vm_id})
    except:
        return jsonify({"vmid":0})
    return vm_name + vm_type + vm_image




@app.route("/vm/query", methods = ['GET'])
def vmQuery():
    found = 0
    list =[]
    vmid = int(request.args.get('vmid'))
    for i in vm_database:
        if i['vmid'] == vmid:
            found=1
            list.append(i)
    print list
    if found==1:
        return jsonify({"VM":list})
    else:
        return jsonify({"VM":0})


    return "Query vm"



@app.route("/vm/destroy", methods = ['GET'])
def vmDestroy():
    found=0
    name=""
    pmid=""
    vmid = int(request.args.get('vmid'))
    for i in vm_database:
        if i['vmid'] == vmid:
            found=1
            name = i['name']
            pmid = int(i['pmid'])
    if found == 0:
        return jsonify({"status":0})
    print pm_file[pmid]
    print name
    conn = libvirt.open("qemu://"+ pm_file[pmid]+"/system")
    dom = conn.lookupByName(name)
    if dom.undefine() == 0:
        return jsonify({"status":1})
    else:
        return jsonify({"status":0})





    return "Destroy VM"



@app.route("/vm/types")
def vmTypes():
    return jsonify(flavor_file)




@app.route("/pm/list")
def pmList():
    print pm_file
    tmp = []
    for i in pm_file:
        tmp.append(i)
    return jsonify({"pmids":tmp})
    print tmp

    return "Pm Lists"





@app.route("/pm/listvms", methods = ['GET'])
def listVms():
    found =0
    pmid = int(request.args.get('pmid'))
    list = []
    for i in vm_database:
        if i['pmid'] == pmid :
            found=1
            list.append(i['vmid'])
    if found==1:
        return jsonify({"vmids":list})
    else:
        return jsonify({"vmids":0})
        
    return " List VMS"




@app.route("/pm/query", methods = ['GET'])
def pmQuery():
    pmid = int(request.args.get('pmid'))
    conn = libvirt.open("qemu://"+ pm_file[pmid]+"/system")
    memory = conn.getMemoryStats(-1)
    total_ram = memory['total']/(1024*1024)
    free_ram = memory['free']/(1024*1024)
    cpu = conn.getCPUMap()[0]
    dict ={}
    dict['pmid'] =pmid
    dict['capacity']= {"cpu":cpu,"ram":total_ram}
    dict["free"] = {"ram":free_ram}
    dict['vms'] =1
    # tmp ={
    #     "pmid":pmid,
    #     "capacity":{
    #                     "cpu":cpu,
    #                     "ram" : total_ram,
    #                 },
    #     "free":{"ram":free_ram

    #     },
    #     "vms":1

    # }
    print dict

    return "Query pm"




@app.route("/image/list")
def listImage():
    tmp={}
    list = []
    print len(image_file)
    for i in image_file:
        tmp['id'] =i
        tmp1 =  image_file[i].split("/")
        size = len(tmp1)
        # print tmp1[size-1]

        tmp['name'] = tmp1[size-1]
        list.append(tmp)

        # print image_file[i]
    # print list
    return jsonify({"images":list})
    return "list images"




if __name__ == '__main__':
    listOfFiles = sys.argv
    pm = listOfFiles[1]
    image = listOfFiles[2]
    flavor = listOfFiles[3]
    parse_image_file(image)
    parse_pm_file(pm)
    parse_flavor_file(flavor)
    # print vm_database
    # print pm_file
    # print image_file
    app.run(debug=True)
    
