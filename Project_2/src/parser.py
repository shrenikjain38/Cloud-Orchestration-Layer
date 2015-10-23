import sqlite3
import os
import json
import sys
import libvirt

os.system("rm mydb.db")
conn = sqlite3.connect("mydb.db")
pm_file_address = sys.argv[1]
image_file_address = sys.argv[2]
flavor_file_address = sys.argv[3]


def read_images():
	conn.execute("create table images (id integer PRIMARY KEY, address varchar)")
	image_fd = open(image_file_address)
	for line in image_fd:
		conn.execute("insert into images values (?,?)",(None,line.rstrip()))
	conn.commit()

def read_pm():
	conn.execute("create table pm (id integer PRIMARY KEY, ip varchar)")
	pm_fd = open(pm_file_address)
	for line in pm_fd:
		conn.execute("insert into pm values (?,?)",(None,line.rstrip()))
	conn.commit()

def read_flavor():
	conn.execute("create table flavor (id integer PRIMARY KEY, cpu integer, ram integer, disk integer)")
	with open(flavor_file_address) as data_file:
		flavor_data = json.load(data_file)
	for field in flavor_data["types"]:
		conn.execute("insert into flavor values (?,?,?,?)",(None,field["cpu"],field["ram"],field["disk"]))
	conn.commit()

def create_vm_table():
	conn.execute("create table vm (id integer PRIMARY KEY, name varchar, pmid integer, instance integer, image integer)")
	conn.commit()




if __name__ == "__main__":
	read_images()
	read_pm()
	read_flavor()
	create_vm_table()
	conn.close()
