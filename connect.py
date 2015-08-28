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
import libvirt
connection = libvirt.open("qemu+ssh://root@45.55.129.249/system")
fd = open("a.xml")
xml = fd.read()
dom_ref = connection.defineXML(xml)
