#ifndef OCS_CONTROLLER_H
#define OCS_CONTROLLER_H

#include <ns3/object.h>
#include <ns3/ptr.h>
#include <ns3/simulator.h>
#include <unordered_map>
#include <vector>
#include "ocs-switch-node.h"

namespace ns3 {

/**
 * @brief OCS Controller for managing optical circuit switches
 * 
 * This class provides centralized control for OCS nodes,
 * allowing external events to trigger reconfiguration.
 */
class OcsController : public Object {
public:
    static TypeId GetTypeId(void);
    
    OcsController();
    virtual ~OcsController();

    /**
     * @brief Add an OCS node to be managed by this controller
     * @param ocsNode The OCS node to add
     */
    void AddOcsNode(Ptr<OcsSwitchNode> ocsNode);

    /**
     * @brief Set port mapping for a specific OCS node
     * @param nodeId The ID of the OCS node
     * @param portMapping The new port mapping
     */
    void SetOcsPortMapping(uint32_t nodeId, const std::unordered_map<uint32_t, uint32_t>& portMapping);

    /**
     * @brief Set port mapping for all OCS nodes
     * @param globalMapping Map from node ID to port mapping
     */
    void SetGlobalPortMapping(const std::unordered_map<uint32_t, std::unordered_map<uint32_t, uint32_t>>& globalMapping);

    /**
     * @brief Schedule a reconfiguration event
     * @param time When to execute the reconfiguration
     * @param nodeId The OCS node to reconfigure
     * @param portMapping The new port mapping
     */
    void ScheduleReconfiguration(Time time, uint32_t nodeId, 
                                const std::unordered_map<uint32_t, uint32_t>& portMapping);

    /**
     * @brief Get the current port mapping for an OCS node
     * @param nodeId The ID of the OCS node
     * @return The current port mapping
     */
    const std::unordered_map<uint32_t, uint32_t>& GetOcsPortMapping(uint32_t nodeId) const;

    /**
     * @brief Clear all port mappings for all OCS nodes
     */
    void ClearAllMappings();

private:
    /**
     * @brief Execute a scheduled reconfiguration
     * @param nodeId The OCS node to reconfigure
     * @param portMapping The new port mapping
     */
    void ExecuteReconfiguration(uint32_t nodeId, const std::unordered_map<uint32_t, uint32_t>& portMapping);

    // Map from node ID to OCS node pointer
    std::unordered_map<uint32_t, Ptr<OcsSwitchNode>> m_ocsNodes;
    
    // Track scheduled events for potential cancellation
    std::vector<EventId> m_scheduledEvents;
};

} // namespace ns3

#endif /* OCS_CONTROLLER_H */