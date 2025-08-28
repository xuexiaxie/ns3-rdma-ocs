#include "ocs-switch-node.h"
#include "qbb-net-device.h"
#include "ns3/log.h"
#include "ns3/packet.h"
#include "ns3/simulator.h"
#include "ns3/uinteger.h"

NS_LOG_COMPONENT_DEFINE("OcsSwitchNode");

namespace ns3 {

NS_OBJECT_ENSURE_REGISTERED(OcsSwitchNode);

TypeId OcsSwitchNode::GetTypeId(void) {
    static TypeId tid = TypeId("ns3::OcsSwitchNode")
        .SetParent<Node>()
        .SetGroupName("ConWeave")
        .AddConstructor<OcsSwitchNode>();
    return tid;
}

OcsSwitchNode::OcsSwitchNode() 
    : m_totalPacketsForwarded(0), m_totalBytesForwarded(0) {
    NS_LOG_FUNCTION(this);
    // Set node type to 2 for OCS (different from regular switch which is 1)
    m_node_type = 2;
}

OcsSwitchNode::~OcsSwitchNode() {
    NS_LOG_FUNCTION(this);
}

void OcsSwitchNode::SetPortMapping(const std::unordered_map<uint32_t, uint32_t>& portMapping) {
    NS_LOG_FUNCTION(this);
    m_portMapping = portMapping;
    
    NS_LOG_INFO("OCS Node " << GetId() << " updated port mapping with " 
                << portMapping.size() << " entries");
    
    // Log the mapping for debugging
    for (const auto& mapping : m_portMapping) {
        NS_LOG_DEBUG("Port " << mapping.first << " -> Port " << mapping.second);
    }
}

void OcsSwitchNode::UpdatePortMapping(uint32_t inputPort, uint32_t outputPort) {
    NS_LOG_FUNCTION(this << inputPort << outputPort);
    
    if (inputPort >= GetNDevices() || outputPort >= GetNDevices()) {
        NS_LOG_ERROR("Invalid port mapping: input=" << inputPort 
                     << ", output=" << outputPort 
                     << ", total devices=" << GetNDevices());
        return;
    }
    
    m_portMapping[inputPort] = outputPort;
    NS_LOG_INFO("OCS Node " << GetId() << " updated mapping: Port " 
                << inputPort << " -> Port " << outputPort);
}

void OcsSwitchNode::ClearPortMapping() {
    NS_LOG_FUNCTION(this);
    m_portMapping.clear();
    NS_LOG_INFO("OCS Node " << GetId() << " cleared all port mappings");
}

const std::unordered_map<uint32_t, uint32_t>& OcsSwitchNode::GetPortMapping() const {
    return m_portMapping;
}

bool OcsSwitchNode::OcsReceiveFromDevice(Ptr<NetDevice> device, Ptr<Packet> packet, 
                                         uint16_t protocol, const Address& from) {
    NS_LOG_FUNCTION(this << device << packet << protocol);
    
    uint32_t inputPort = GetDeviceIndex(device);
    if (inputPort == UINT32_MAX) {
        NS_LOG_ERROR("Received packet from unknown device");
        return false;
    }
    
    // Skip device 0 which is typically the loopback
    if (inputPort == 0) {
        NS_LOG_DEBUG("Ignoring packet from loopback device");
        return false;  
    }
    
    ForwardPacket(inputPort, packet, protocol);
    return true;
}

void OcsSwitchNode::ForwardPacket(uint32_t inputPort, Ptr<Packet> packet, uint16_t protocol) {
    NS_LOG_FUNCTION(this << inputPort << packet << protocol);
    
    // Find the output port mapping
    auto it = m_portMapping.find(inputPort);
    if (it == m_portMapping.end()) {
        NS_LOG_WARN("No mapping found for input port " << inputPort 
                    << " on OCS node " << GetId() << ". Dropping packet.");
        return;
    }
    
    uint32_t outputPort = it->second;
    
    // Validate output port
    if (outputPort >= GetNDevices()) {
        NS_LOG_ERROR("Invalid output port " << outputPort 
                     << " for OCS node " << GetId() << ". Dropping packet.");
        return;
    }
    
    // Get the output device
    Ptr<NetDevice> outputDevice = GetDevice(outputPort);
    if (!outputDevice) {
        NS_LOG_ERROR("Output device " << outputPort << " not found. Dropping packet.");
        return;
    }
    
    // For QBB devices, we need to handle the transmission differently
    Ptr<QbbNetDevice> qbbDevice = DynamicCast<QbbNetDevice>(outputDevice);
    if (qbbDevice) {
        // Create a copy of the packet for transmission
        Ptr<Packet> packetCopy = packet->Copy();
        
        // Send the packet using QBB device's Send method
        // We use a dummy destination address since OCS just forwards
        Mac48Address dummyAddr = Mac48Address::GetBroadcast();
        qbbDevice->Send(packetCopy, dummyAddr, protocol);
        
        // Update statistics
        m_totalPacketsForwarded++;
        m_totalBytesForwarded += packet->GetSize();
        
        NS_LOG_DEBUG("OCS Node " << GetId() << " forwarded packet from port " 
                     << inputPort << " to port " << outputPort
                     << ", size=" << packet->GetSize());
    } else {
        NS_LOG_ERROR("Output device is not a QbbNetDevice. Cannot forward packet.");
    }
}

uint32_t OcsSwitchNode::GetDeviceIndex(Ptr<NetDevice> device) const {
    for (uint32_t i = 0; i < GetNDevices(); i++) {
        if (GetDevice(i) == device) {
            return i;
        }
    }
    return UINT32_MAX;
}

} // namespace ns3