'''
Fuctions that can be used:
baselineCPU(self, xmlCPUs, flags=0)
changeBegin(self, flags=0)
changeCommit(self, flags=0)
close()
compareCPU()
createXML()
createXMLWithFiles()
defineXML()
findStoragePoolSources()
networkCreateXML()
networkDefineXML()
saveImageDefineXML()
saveImageGetXMLDesc()
virConnGetLastError()


'''
# qemu-img create /var/lib/libvirt/images/kvm3.img 10GB
import libvirt
connection = libvirt.open("qemu:///system")
# connection = libvirt.open("qemu+ssh://root@45.55.129.249/system")
# connection = libvirt.open("qemu+ssh://ubuntu@52.76.80.67/system?keyfile=/home/shrenik/Downloads/shrenik1.pem")
fd = open("a.xml")
xml = fd.read()% ('1','shrenik1','50000','50000','1','/home/shrenik/Desktop/winxp.img')
print xml
dom_ref = connection.defineXML(xml)
