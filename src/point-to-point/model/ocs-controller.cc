#include "ocs-controller.h"
#include "ns3/log.h"
#include "ns3/simulator.h"

NS_LOG_COMPONENT_DEFINE("OcsController");

namespace ns3 {

NS_OBJECT_ENSURE_REGISTERED(OcsController);

TypeId OcsController::GetTypeId(void) {
    static TypeId tid = TypeId("ns3::OcsController")
        .SetParent<Object>()
        .SetGroupName("ConWeave")
        .AddConstructor<OcsController>();
    return tid;
}

OcsController::OcsController() {
    NS_LOG_FUNCTION(this);
}

OcsController::~OcsController() {
    NS_LOG_FUNCTION(this);
    // Cancel any pending events
    for (auto& event : m_scheduledEvents) {
        if (event.IsRunning()) {
            Simulator::Cancel(event);
        }
    }
}

void OcsController::AddOcsNode(Ptr<OcsSwitchNode> ocsNode) {
    NS_LOG_FUNCTION(this << ocsNode);
    
    if (ocsNode == nullptr) {
        NS_LOG_ERROR("Cannot add null OCS node");
        return;
    }
    
    uint32_t nodeId = ocsNode->GetId();
    m_ocsNodes[nodeId] = ocsNode;
    
    NS_LOG_INFO("Added OCS node " << nodeId << " to controller");
}

void OcsController::SetOcsPortMapping(uint32_t nodeId, 
                                     const std::unordered_map<uint32_t, uint32_t>& portMapping) {
    NS_LOG_FUNCTION(this << nodeId);
    
    auto it = m_ocsNodes.find(nodeId);
    if (it == m_ocsNodes.end()) {
        NS_LOG_ERROR("OCS node " << nodeId << " not found in controller");
        return;
    }
    
    it->second->SetPortMapping(portMapping);
    NS_LOG_INFO("Updated port mapping for OCS node " << nodeId);
}

void OcsController::SetGlobalPortMapping(
    const std::unordered_map<uint32_t, std::unordered_map<uint32_t, uint32_t>>& globalMapping) {
    NS_LOG_FUNCTION(this);
    
    for (const auto& nodeMapping : globalMapping) {
        SetOcsPortMapping(nodeMapping.first, nodeMapping.second);
    }
    
    NS_LOG_INFO("Updated global port mapping for " << globalMapping.size() << " OCS nodes");
}

void OcsController::ScheduleReconfiguration(Time time, uint32_t nodeId, 
                                           const std::unordered_map<uint32_t, uint32_t>& portMapping) {
    NS_LOG_FUNCTION(this << time << nodeId);
    
    if (m_ocsNodes.find(nodeId) == m_ocsNodes.end()) {
        NS_LOG_ERROR("Cannot schedule reconfiguration for unknown OCS node " << nodeId);
        return;
    }
    
    // Schedule the reconfiguration event
    EventId event = Simulator::Schedule(time, &OcsController::ExecuteReconfiguration, 
                                       this, nodeId, portMapping);
    m_scheduledEvents.push_back(event);
    
    NS_LOG_INFO("Scheduled reconfiguration for OCS node " << nodeId 
                << " at time " << time.GetMilliSeconds() << "ms");
}

const std::unordered_map<uint32_t, uint32_t>& 
OcsController::GetOcsPortMapping(uint32_t nodeId) const {
    auto it = m_ocsNodes.find(nodeId);
    if (it == m_ocsNodes.end()) {
        NS_LOG_ERROR("OCS node " << nodeId << " not found");
        static std::unordered_map<uint32_t, uint32_t> empty;
        return empty;
    }
    
    return it->second->GetPortMapping();
}

void OcsController::ClearAllMappings() {
    NS_LOG_FUNCTION(this);
    
    for (auto& nodePair : m_ocsNodes) {
        nodePair.second->ClearPortMapping();
    }
    
    NS_LOG_INFO("Cleared all port mappings for " << m_ocsNodes.size() << " OCS nodes");
}

void OcsController::ExecuteReconfiguration(uint32_t nodeId, 
                                          const std::unordered_map<uint32_t, uint32_t>& portMapping) {
    NS_LOG_FUNCTION(this << nodeId);
    
    auto it = m_ocsNodes.find(nodeId);
    if (it == m_ocsNodes.end()) {
        NS_LOG_ERROR("OCS node " << nodeId << " not found during reconfiguration");
        return;
    }
    
    it->second->SetPortMapping(portMapping);
    NS_LOG_INFO("Executed reconfiguration for OCS node " << nodeId 
                << " at time " << Simulator::Now().GetMilliSeconds() << "ms");
}

} // namespace ns3