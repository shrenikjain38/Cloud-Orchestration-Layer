#!flask/bin/python
import re
import libvirt
import json
import os
import sys
import sqlite3
from flask import Flask, jsonify,request

conn = sqlite3.connect('mydb.db',check_same_thread=False)



app = Flask(__name__)

@app.route("/")
def api_root():
    return "Welcome"

''' When u create a vm reduce the resources allocated from the pm list
	Then when u deallocate free the resources.
'''
@app.route("/vm/create",methods = ["GET"])
def vm_create():
	error_flag = False

	''' Gets the arguments'''
	vm_name = request.args.get('name')
	vm_instance_type = request.args.get('instance_type')
	vm_image_id = request.args.get('image_id')

	''' Raise error flag if number of arguments given are wrong '''
	if vm_instance_type is None or vm_name is None or vm_image_id is None:
		return jsonify({"vmid":0})

	'''Retreive the corresponding Image field and Instance field'''
	vm_image_field = conn.execute("select * from images where id = '%s'"%vm_image_id).fetchone()
	vm_instance_field = conn.execute("select * from flavor where id = '%s'"%vm_instance_type).fetchone()

	''' Check if invalid arguments are given such that there is no entry in the tables'''
	if(vm_instance_field == None or vm_image_field == None):
		error_flag = True
		return jsonify({"vmid":0})

	''' Create a dummy entry in vm database to get a unique key(All other values are initialized as null)'''
	conn.execute('insert into vm values (?,?,?,?,?)',(None,None,0,0,0))
	conn.commit()
	vm_id = conn.execute("select id from vm where pmid=0").fetchone()[0]
	conn.execute("delete from vm where pmid=0")
	conn.commit()

	''' Get the vm specifications from instance field'''
	vm_ram = str(vm_instance_field[2])
	vm_disk = str(vm_instance_field[3])
	vm_vcpu = str(vm_instance_field[1])
	vm_image = str(vm_image_field[1])

	''' Get vm image path'''
	vm_image_path = str(vm_image_field[1])

	''' Parse the xml with the given specifications'''
	domain_fd = open("domain.xml")
	xml = domain_fd.read()% (vm_id,vm_name,vm_ram,vm_vcpu,vm_image)

	''' Get all the physical machine list from the database and check if vm can be created iteratively'''
	list_of_pm = conn.execute("select * from pm")
	while(True):
		pm_instance = list_of_pm.fetchone()
		if(pm_instance == None):
			break
		try:
			''' Will require password 2 times one for ssh and other for scp'''

			''' Get info about the cpu and ram on pysical machine'''
			connection = libvirt.open("qemu+ssh://"+pm_instance[1]+"/system")
			pm_info = connection.getInfo()

			'''Only create vm if given specs are met and adds entry in database and returns vm_id'''
			if int(pm_info[1]) >= int(vm_ram):
				os.system("scp "+vm_image_path+" "+pm_instance[1]+":/home/"+pm_instance[1].split("@")[0])
				dom_ref = connection.defineXML(xml)
				conn.execute("insert into vm values (?,?,?,?,?)",(int(vm_id),vm_name,int(pm_instance[0]),vm_instance_type,vm_image_id))
				conn.commit()
				error_flag = False
				connection.close()
				return jsonify({"vmid":vm_id})
			else:
				error_flag = True
		except:
			error_flag = True

	'''If error_flag id true return 0 as vmid'''
	if error_flag == True:
		return jsonify({"vmid":0})
	else:
		return jsonify({"vmid":vm_id})

@app.route("/vm/query")
def vm_query():
	try:
		vm_id = request.args.get("vmid")
		vm_field = conn.execute("select * from vm where id = ?",(vm_id)).fetchone()
		return jsonify({"vmid":vm_id, "name":vm_field[1],"instance_type":vm_field[3],"pmid":vm_field[2]})
	except:
		return jsonify({"status":0})

@app.route("/vm/destroy")
def vm_destroy():
	try:
		vm_id = request.args.get("vmid")
		vm_name = conn.execute("select name from vm where id=?",(vm_id)).fetchone()[0]
		pm_id = conn.execute("select pmid from vm where id=?",(vm_id)).fetchone()[0]
		pm_ip = conn.execute("select ip from pm where id=?",(str(pm_id))).fetchone()[0]
		print vm_id, vm_name, pm_id, pm_ip
		connection = libvirt.open("qemu+ssh://"+pm_ip+"/system")
		dom = connection.lookupByName(vm_name)
		if dom.undefine() == 0:
			return jsonify({"status":1})
		else:
			return jsonify({"status":0})
	except:
		return jsonify({"status":0})


@app.route("/vm/types")
def vm_types():
	vm_types = conn.execute("select * from flavor")
	vm_all = []
	for row in vm_types:
		flavor_instance = {"tid":row[0], "cpu":row[1], "ram": row[2], "disk":row[3]}
		vm_all.append(flavor_instance)
	return jsonify({"types":vm_all})



@app.route("/pm/list")
def pm_list():
	pm_id_list = []
	for row in conn.execute("select id from pm"):
		pm_id_list.append(row[0])
	return jsonify({"types":pm_id_list})


@app.route("/pm/listvms")
def list_vm():
	return "yo"

	


	


if __name__ == "__main__":
	app.run(debug=True)