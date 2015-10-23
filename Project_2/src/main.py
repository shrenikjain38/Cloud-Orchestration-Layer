import sys
import sqlite3
import subprocess
import libvirt
import uuid
import logging
import os
import rados
import rbd
from flask import Flask, request, jsonify, render_template

PM_FILE = sys.argv[1]
IMAGE_FILE = sys.argv[2]
FLAVOR_FILE = sys.argv[3]
APP = Flask(__name__)
get_image_types = open(IMAGE_FILE)
IMAGES = []
IMAGE_ID = 1
for image in get_image_types.readlines():
	IMAGES.append({"id": IMAGE_ID, "source": image.rstrip('\n')})
	IMAGE_ID += 1
print IMAGES
get_vm_types = open(FLAVOR_FILE).read()
VM_TYPES = eval(get_vm_types)['types']
print VM_TYPES
VM_ID = 1
CEPH_CONF = "/etc/ceph/ceph.conf"
POOL_NAME = "miniproject"
DEV_NAME = "sdmini"
IOCTX = None
RBD_INST = None
HOSTNAME = None
VOLUME_ID = 1
DB_CONN = sqlite3.connect('server.db')
VM_XML = """
<domain type='qemu'>
  <name>%s</name>
  <memory unit='MiB'>%d</memory>
  <vcpu placement='static'>%d</vcpu>
  <uuid>%s</uuid>
  <os>
    <type arch='x86_64' machine='pc-i440fx-trusty'>hvm</type>
  </os>
  <features>
    <acpi/>
    <apic/>
    <pae/>
  </features>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <devices>
    <emulator>/usr/bin/kvm</emulator>
    <disk type='file' device='cdrom'>
      <source file='%s'/>
      <target dev='hdc' bus='ide'/>
    </disk>
  </devices>
</domain>
"""
VOLUME_XML = """
<disk type='network' device='disk'>
  <source protocol='rbd' name='%s/%s'>
    <host name='%s' port='6789'/>
  </source>
  <target dev='%s' bus='virtio'/>
</disk>
"""
logging.basicConfig(filename='debug.log', level=logging.DEBUG)


def cluster_init():
	"""
	Initialize the ceph storage cluster.
	"""
	VOLUME_CONN = rados.Rados(conffile=CEPH_CONF)
	VOLUME_CONN.connect()
	if POOL_NAME not in VOLUME_CONN.list_pools():
		VOLUME_CONN.create_pool(POOL_NAME)
	print VOLUME_CONN.list_pools()
	global IOCTX
	IOCTX = VOLUME_CONN.open_ioctx(POOL_NAME)

	# Create RBD instance.
	global RBD_INST
	RBD_INST = rbd.RBD()
	print RBD_INST

	# Get the hostname.
	mon_status = subprocess.Popen("ceph mon_status", shell=True, stdout=subprocess.PIPE)
	mon_status = eval(mon_status.stdout.read())
	global HOSTNAME
	HOSTNAME = mon_status['monmap']['mons'][0]['name']
	print HOSTNAME

def db_connection():
        """
        Start connection with the database. Create the tables and populate them.
        Also, establish keyless ssh.
        """
	db_cursor = DB_CONN.cursor()
	db_cursor.execute('''CREATE TABLE pms
(id int, ip text, ram int, cpu int)''')
	db_cursor.execute('''CREATE TABLE pms_capacity
(id int, ip text, ram int, cpu int)''')
	pm_file = open(PM_FILE)
	pm_id = 1
	for pm_ip in pm_file.readlines():
		pm_ip = pm_ip.rstrip('\n')
		command = "ssh-copy-id %s"
		subprocess.call(command % pm_ip, shell=True)
		vmm_conn = libvirt.open("qemu+ssh://%s/system" % pm_ip)
		pm_info = vmm_conn.getInfo()
		vmm_conn.close()
		db_cursor.execute("""INSERT INTO pms VALUES(%d, '%s', %d, %d)""" % (pm_id, pm_ip, pm_info[1], pm_info[2]))
		db_cursor.execute("""INSERT INTO pms_capacity VALUES(%d, '%s', %d, %d)""" % (pm_id, pm_ip, pm_info[1], pm_info[2]))
		pm_id = pm_id + 1
	db_cursor.execute('''CREATE TABLE pm_vm(pm_id int, vm_id int, vm_uuid text, vm_name text, vm_instance int)''')
	db_cursor.execute('''CREATE TABLE volumes(volume_id int, name text, size int, status text, dev_name text, vm_id int)''')
	DB_CONN.commit()

@APP.route('/vm/create')
def vm_create():
        """
        Check the PMs for resources and create a VM accordingly.
        """
	vmid = 0
	try:
		name = request.args.get('name')
		instance_type = int(request.args.get('instance_type'))
		image_id = int(request.args.get('image_id'))
		print name, instance_type, image_id
		vm_type = VM_TYPES[instance_type - 1]
		print vm_type
		image_type = IMAGES[image_id - 1]
		print image_type
		db_cursor = DB_CONN.cursor()
		pm_info = None
		for row in db_cursor.execute("SELECT * FROM pms WHERE ram>=%d AND cpu>=%d" % (vm_type["ram"], vm_type["cpu"])):
			pm_info = row
			break
		print pm_info
		if pm_info:
			# Copy the image file to the physical machine if it does not exsit.
			home_dir = pm_info[1].split('@')[0]
			home_dir = '/home/' + home_dir + '/'
			image_location = home_dir + image_type["source"].split('/')[-1]
			print home_dir, image_location
			image_present = os.system("ssh %s [[ -f %s ]]" % (pm_info[1], image_location))
			print image_present
			if image_present != 0:
				os.system("scp %s %s:%s" % (image_type["source"], pm_info[1], image_location))
			vmm_conn = libvirt.open("qemu+ssh://%s/system" % pm_info[1])
			vm_uuid = uuid.uuid4()
			vm_xml = VM_XML % (name, vm_type["ram"], vm_type["cpu"], vm_uuid, image_location)
			print vm_xml
			vmm_conn.createXML(vm_xml)
			vmm_conn.close()
			db_cursor.execute("INSERT INTO pm_vm VALUES (%d, %d, '%s', '%s', %d)" % (pm_info[0], VM_ID, vm_uuid, name, instance_type))
			db_cursor.execute("UPDATE pms SET ram=ram-%d, cpu=cpu-%d WHERE id=%d" % (vm_type["ram"], vm_type["cpu"], pm_info[0]))
			DB_CONN.commit()
			vmid = VM_ID
			global VM_ID
			VM_ID += 1
	except Exception as e:
		logging.debug(e)
	resp = {"vmid": vmid}
	return jsonify(**resp)

@APP.route('/vm/query')
def vm_query():
        """
        Return information about a VM.
        """
	try:
		vmid = int(request.args.get('vmid'))
		db_cursor = DB_CONN.cursor()
		db_cursor.execute("SELECT * FROM pm_vm WHERE vm_id=%d" % vmid)
		vm_info = db_cursor.fetchone()
		resp = {"vmid": vmid, "name": vm_info[3], "instance_type": vm_info[4], "pmid": vm_info[0]}
		return jsonify(**resp)
	except Exception as e:
		logging.debug(e)
	return jsonify({"status": 0})

@APP.route('/vm/destroy')
def vm_destroy():
        """
        Destroy a VM and free the resources on the specific PM.
        """
	status = 0
	try:
		vmid = int(request.args.get('vmid'))
		db_cursor = DB_CONN.cursor()
		db_cursor.execute("SELECT pm_id, vm_uuid, vm_instance FROM pm_vm WHERE vm_id=%d" % vmid)
		pm_id, vm_uuid, vm_instance = db_cursor.fetchone()
		vm_type = VM_TYPES[vm_instance - 1]
		print vm_type
		db_cursor.execute("SELECT ip FROM pms WHERE id=%d" % pm_id)
		pm_ip = db_cursor.fetchone()[0]
		vmm_conn = libvirt.open("qemu+ssh://%s/system" % pm_ip)
		status = 1
		vm_conn = vmm_conn.lookupByUUIDString(vm_uuid)
		print vm_conn
		db_cursor.execute("UPDATE pms SET ram=ram+%d, cpu=cpu+%d WHERE id=%d" % (vm_type["ram"], vm_type["cpu"], pm_id))
		db_cursor.execute("DELETE from pm_vm WHERE pm_id=%d" % pm_id)
		DB_CONN.commit()
		vm_conn.destroy()
		vmm_conn.close()
	except Exception as e:
		logging.debug(e)
	resp = {"status": status}
	return jsonify(**resp)

@APP.route('/vm/types')
def vm_types():
        """
        Return the types of VMs possible.
        """
	resp = {"types": VM_TYPES}
	return jsonify(**resp)

@APP.route('/pm/list')
def pm_list():
        """
        Return the list of PMs.
        """
	resp_val = []
	db_cursor = DB_CONN.cursor()
	for row in db_cursor.execute("SELECT id FROM pms"):
		resp_val.append(row[0])
	resp = {"pmids": resp_val}
	return jsonify(**resp)

@APP.route('/pm/listvms')
def pm_listvms():
        """
        Return the list of VMs running on a specific PM.
        """
	try:
		pmid = int(request.args.get('pmid'))
		resp_val = []
		db_cursor = DB_CONN.cursor()
		pm_valid = False
		for row in db_cursor.execute("SELECT id FROM pms WHERE id=%d" % pmid):
			pm_valid = True
			break
		if pm_valid is False:
			raise Exception
		for row in db_cursor.execute("SELECT vm_id FROM pm_vm WHERE pm_id=%d" % pmid):
			resp_val.append(row[0])
		print resp_val
		resp = {"vmids": resp_val}
		return jsonify(**resp)
	except Exception as e:
		logging.debug(e)
	return jsonify({"status": 0})

@APP.route('/pm/query')
def pm_query():
        """
        Return information specific to a PM.
        """
	try:
		pmid = int(request.args.get('pmid'))
		resp = {"pmid": pmid}
		db_cursor = DB_CONN.cursor()
		db_cursor.execute("SELECT * FROM pms_capacity WHERE id=%d" % pmid)
		pm_resp = db_cursor.fetchone()
		capacity = {"cpu": pm_resp[3], "ram": pm_resp[2]}
		db_cursor.execute("SELECT * FROM pms WHERE id=%d" % pmid)
		pm_resp = db_cursor.fetchone()
		free = {"cpu": pm_resp[3], "ram": pm_resp[2]}
		resp["capacity"] = capacity
		resp["free"] = free
		db_cursor.execute("SELECT * FROM pm_vm WHERE pm_id=%d" % pmid)
		vms = len(db_cursor.fetchall())
		resp["vms"] = vms
		return jsonify(**resp)
	except Exception as e:
		logging.debug(e)
	return jsonify({"status": 0})

@APP.route('/image/list')
def image_list():
        """
        Return the list of images.
        """
	print IMAGES
	images = []
	for image in IMAGES:
		images.append({"id": image['id'], "name": image['source'].split('/')[-1].split('.')[0]})
	resp = {"images": images}
	return jsonify(**resp)

@APP.route('/gui')
def gui():
        """
        A GUI for basic use.
        """
	return render_template('index.html')

@APP.errorhandler(404)
def not_found(error):
        """
        In case the user navigates to some undefined path.
        """
	return jsonify({"status": 0})

@APP.route('/volume/create')
def volume_create():
	"""
	Check the storage cluster for resources and create a new volume.
	"""
	volume_id = 0
	try:
		volume_name = request.args.get('name')
		volume_size = request.args.get('size')
		volume_name = str(volume_name)
		volume_size = int(float(volume_size) * (1024 ** 3))
		print volume_name, volume_size
		RBD_INST.create(IOCTX, volume_name, volume_size)
		os.system("sudo rbd map %s --pool %s --name client.admin" % (volume_name, POOL_NAME))
		db_cursor = DB_CONN.cursor()
		volume_id = VOLUME_ID
		global VOLUME_ID
		VOLUME_ID = VOLUME_ID + 1
		db_cursor.execute("""INSERT INTO volumes VALUES(%d, '%s', %d, 'available', '%s', -1)""" % (volume_id, volume_name, volume_size, DEV_NAME + str(volume_id)))
		DB_CONN.commit()
	except Exception as e:
		logging.debug(e)
	resp = {"volumeid": volume_id}
	return jsonify(**resp)

@APP.route('/volume/query')
def volume_query():
	"""
	Query an existing volume.
	"""
	resp = {}
	try:
		volume_id = request.args.get('volumeid')
		volume_id = int(volume_id)
		db_cursor = DB_CONN.cursor()
		db_cursor.execute("SELECT * FROM volumes WHERE volume_id=%d" % volume_id)
		volume_info = db_cursor.fetchone()
		if str(volume_info[3]) == "available":
			resp = {"volumeid": volume_info[0], "name": volume_info[1], "size": volume_info[2], "status": volume_info[3]}
		elif str(volume_info[3]) == "attached":
			resp = {"volumeid": volume_info[0], "name": volume_info[1], "size": volume_info[2], "status": volume_info[3], "vmid": volume_info[5]}
	except Exception as e:
		resp = {"error": "volumeid: %d does not exist" % volume_id}
		logging.debug(e)
	return jsonify(**resp)

@APP.route('/volume/destroy')
def volume_destroy():
	"""
	Destroy an exising volume and free its resources.
	"""
	status = 0
	try:
		volume_id = request.args.get('volumeid')
		volume_id = int(volume_id)
		db_cursor = DB_CONN.cursor()
		db_cursor.execute("SELECT * FROM volumes WHERE volume_id=%d" % volume_id)
		volume_info = db_cursor.fetchone()
		if str(volume_info[3]) == "attached":
			raise Exception
		volume_name = str(volume_info[1])
		os.system("sudo rbd unmap /dev/rbd/%s/%s" % (POOL_NAME, volume_name))
		RBD_INST.remove(IOCTX, volume_name)
		db_cursor.execute("DELETE FROM volumes WHERE volume_id=%d" % volume_id)
		DB_CONN.commit()
		status = 1
	except Exception as e:
		logging.debug(e)
	resp = {"status": status}
	return jsonify(**resp)

@APP.route('/volume/attach')
def volume_attach():
	"""
	Attach a volume with a VM.
	"""
	status = 0
	try:
		vmid = request.args.get('vmid')
		volume_id = request.args.get('volumeid')
		vmid = int(vmid)
		volume_id = int(volume_id)
		db_cursor = DB_CONN.cursor()
		db_cursor.execute("SELECT * FROM volumes WHERE volume_id=%d" % volume_id)
		volume_info = db_cursor.fetchone()
		print volume_info
		if str(volume_info[3]) == "attached":
			raise Exception
		db_cursor.execute("SELECT * FROM pm_vm WHERE vm_id=%d" % vmid)
		pm_vm_info = db_cursor.fetchone()
		print pm_vm_info
		db_cursor.execute("SELECT * FROM pms WHERE id=%d" % int(pm_vm_info[0]))
		pm_info = db_cursor.fetchone()
		print pm_info
		vmm_conn = libvirt.open("qemu+ssh://%s/system" % pm_info[1])
		print vmm_conn
		domain = vmm_conn.lookupByName(str(pm_vm_info[3]))
		print domain
		volume_xml = VOLUME_XML % (POOL_NAME, str(volume_info[1]), HOSTNAME, str(volume_info[4]))
		print volume_xml
		domain.attachDevice(volume_xml)
		vmm_conn.close()
		db_cursor.execute("UPDATE volumes SET status='%s', vm_id=%d WHERE volume_id=%d" % ("attached", vmid, volume_id))
		DB_CONN.commit()
		status = 1
	except Exception as e:
		logging.debug(e)
	resp = {"status": status}
	return jsonify(**resp)

@APP.route('/volume/detach')
def volume_detach():
	"""
	Detach a volume from a VM.
	"""
	status = 0
	try:
		volume_id = request.args.get('volumeid')
		volume_id = int(volume_id)
		db_cursor = DB_CONN.cursor()
		db_cursor.execute("SELECT * FROM volumes WHERE volume_id=%d" % volume_id)
		volume_info = db_cursor.fetchone()
		print volume_info
		if str(volume_info[3]) == "available":
			raise Exception
		db_cursor.execute("SELECT * FROM pm_vm WHERE vm_id=%d" % int(volume_info[5]))
		pm_vm_info = db_cursor.fetchone()
		print pm_vm_info
		db_cursor.execute("SELECT * FROM pms WHERE id=%d" % int(pm_vm_info[0]))
		pm_info = db_cursor.fetchone()
		print pm_info
		vmm_conn = libvirt.open("qemu+ssh://%s/system" % pm_info[1])
		print vmm_conn
		domain = vmm_conn.lookupByName(str(pm_vm_info[3]))
		print domain
		volume_xml = VOLUME_XML % (POOL_NAME, str(volume_info[1]), HOSTNAME, str(volume_info[4]))
		print volume_xml
		domain.detachDevice(volume_xml)
		vmm_conn.close()
		db_cursor.execute("UPDATE volumes SET status='%s', vm_id=-1 WHERE volume_id=%d" % ("available", volume_id))
		DB_CONN.commit()
		status = 1
	except Exception as e:
		logging.debug(e)
	resp = {"status": status}
	return jsonify(**resp)


if __name__ == "__main__":
	cluster_init()
	db_connection()
	APP.run(host='0.0.0.0')
