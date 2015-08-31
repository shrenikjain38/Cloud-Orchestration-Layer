import pymongo
from pymongo import MongoClient
import json
import libvirt
# client = MongoClient()
# db = client['cloud']
image_file = {}
# flavor_file = {}
flavor_file = {}
pm_file = {}
def parse_pm_file(path):
    fd = open(path)
    pm = fd.read().split("\n")
    for i in range(0,len(pm)):
    	pm_file[i+1] = pm[i]
    print pm_file
    
    


def parse_image_file(path):
    fd = open(path,"r")
    image = fd.read().split('\n')
    for i in range(0,len(image)):
    	image_file[i+1] = image[i]
    print image_file

def parse_flavor_file(path):
	f = open('flavor_file')
    aa = json.loads(f.read())[u'types']
    # for i in range(0,len(aa)):
    #     flavor_file[i+1] = aa[i]
	   



if __name__ == "__main__":
    # parse_pm_file("pm_file")
    # parse_image_file("image_file")
    parse_flavor_file("flavor_file")
    print flavor_file
    # print image_file
    # print pm_file